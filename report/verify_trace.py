"""Replay saved CacheLab traces; this does not rerun the official Linux tests."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent.parent
BASE = 0x30000000
DIMS = {0: (2, 2, 2), 1: (16, 16, 16), 2: (32, 32, 32), 3: (27, 41, 27)}


def source_events(case, baseline=False):
    """Address order of the recorded baseline and current gemm.cpp kernels."""
    m, n, p = DIMS[case]
    a, b, c = BASE, BASE + 4*m*n, BASE + 4*(m*n+n*p)
    if baseline or case == 0:
        for i in range(m):
            for j in range(p):
                for k in range(n):
                    yield "L", a + 4*(i*n+k)
                    yield "L", b + 4*(k*p+j)
                yield "S", c + 4*(i*p+j)
    elif case in (1, 2):
        for i in range(0, m, 4):
            for j in range(0, p, 4):
                for k in range(n):
                    for r in range(min(4, m-i)):
                        yield "L", a + 4*((i+r)*n+k)
                    for col in range(min(4, p-j)):
                        yield "L", b + 4*(k*p+j+col)
                for r in range(min(4, m-i)):
                    for col in range(min(4, p-j)):
                        yield "S", c + 4*((i+r)*p+j+col)
    else:
        for j in range(0, p, 7):
            for i in range(0, m, 3):
                ks = range(n-1, -1, -1) if (i//3+j//7) % 2 else range(n)
                for k in ks:
                    for r in range(3):
                        yield "L", a + 4*((i+r)*n+k)
                    for col in range(min(7, p-j)):
                        yield "L", b + 4*(k*p+j+col)
                for r in range(3):
                    for col in range(min(7, p-j)):
                        yield "S", c + 4*((i+r)*p+j+col)


def read_trace(path):
    events = []
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.fullmatch(r"\s*([LS])\s+(?:0x)?([0-9a-fA-F]+),4\s+-?\d+\s*", line)
        if not match:
            raise ValueError(f"Unexpected trace line in {path.name}: {line!r}")
        events.append((match[1], int(match[2], 16)))
    return events


def replay(events):
    cache = [None]*32
    misses = 0
    for _, address in events:
        block = address >> 4
        set_id, tag = block & 31, block >> 5
        if cache[set_id] != tag:
            misses += 1
            cache[set_id] = tag
    count = len(events)
    return misses, count, 15*misses+count


def main():
    print("Saved-trace replay (not an official test rerun)")
    print(f"{'Case':<18} {'cache miss':>10} {'load/store':>11} {'Latency':>10}")
    results = {}
    for case in range(4):
        for baseline in (True, False):
            name = f"case{case}" + ("_baseline" if baseline else "")
            actual = read_trace(ROOT / "gemm_traces" / f"{name}.trace")
            expected = list(source_events(case, baseline))
            if actual != expected:
                raise ValueError(f"{name}: saved addresses differ from the modeled source order")
            results[name] = replay(actual)
            print(f"{name:<18} {results[name][0]:>10} {results[name][1]:>11} {results[name][2]:>10}")
    weighted = sum(w*results[f"case{i}_baseline"][2]/results[f"case{i}"][2]
                   for i, w in ((1, .3), (2, .3), (3, .4)))
    print(f"Weighted speedup: {weighted:.10f}")
    events = list(source_events(1))
    cache, per_matrix, per_tile = [None]*32, [0]*3, []
    for start in range(0, len(events), 144):
        tile_misses = 0
        for _, address in events[start:start+144]:
            block = address >> 4
            q, tag = block & 31, block >> 5
            if cache[q] != tag:
                cache[q] = tag
                tile_misses += 1
                per_matrix[(address-BASE)//1024] += 1
        per_tile.append(tile_misses)
    print("case1 misses for A/B/C:", per_matrix)
    print("case1 tile misses (i outer, j inner):")
    for start in range(0, 16, 4):
        print(" ".join(f"{value:3}" for value in per_tile[start:start+4]))
    print("All 8 saved address sequences match the modeled source access order.")


if __name__ == "__main__":
    main()

