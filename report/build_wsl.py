#!/usr/bin/env python3
"""Build this project's report from WSL using the installed Windows XeLaTeX."""
import gzip
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

WINDOWS_XELATEX = Path("/mnt/c/texlive/2026/bin/windows/xelatex.exe")
WINDOWS_CMD = "/mnt/c/Windows/System32/cmd.exe"


def windows_path(path):
    return subprocess.check_output(["wslpath", "-w", str(path)], text=True).strip()


def copy_synctex(source, destination, build, original):
    """Keep source-to-PDF navigation pointing at the original WSL sources."""
    build_windows = windows_path(build).replace("\\", "/").rstrip("/")
    lines = gzip.decompress(source.read_bytes()).decode("utf-8", errors="surrogateescape").splitlines(True)
    for index, line in enumerate(lines):
        if not line.startswith("Input:"):
            continue
        prefix, number, name = line.rstrip("\r\n").split(":", 2)
        normalized = name.replace("\\", "/")
        relative = None
        if normalized.lower().startswith(build_windows.lower() + "/"):
            relative = normalized[len(build_windows) + 1:]
        elif not (len(normalized) > 1 and normalized[1] == ":") and not normalized.startswith("/"):
            if (build / normalized).is_file():
                relative = normalized
        if relative is not None:
            lines[index] = f"{prefix}:{number}:{(original / relative).resolve()}\n"
    destination.write_bytes(gzip.compress("".join(lines).encode("utf-8", errors="surrogateescape")))


def main():
    if len(sys.argv) != 2:
        print("Usage: python3 report/build_wsl.py report/report.tex", file=sys.stderr)
        return 2
    document = Path(sys.argv[1]).expanduser().resolve()
    if not document.is_file() or document.suffix.lower() != ".tex":
        print(f"TeX source not found: {document}", file=sys.stderr)
        return 2
    if not WINDOWS_XELATEX.is_file():
        print(f"Windows XeLaTeX not found: {WINDOWS_XELATEX}", file=sys.stderr)
        return 2

    temp_windows = subprocess.check_output(
        [WINDOWS_CMD, "/d", "/c", "echo %TEMP%"],
        cwd="/mnt/c", text=True, errors="replace",
    ).strip()
    temp_linux = Path(subprocess.check_output(
        ["wslpath", "-u", temp_windows], text=True,
    ).strip()).resolve()
    if not temp_linux.is_dir() or "%TEMP%" in temp_windows:
        print("Cannot locate the Windows temporary directory.", file=sys.stderr)
        return 2

    with tempfile.TemporaryDirectory(prefix="cachelab-latex-", dir=temp_linux) as temporary:
        build = Path(temporary).resolve()
        if build.parent != temp_linux or not build.name.startswith("cachelab-latex-"):
            raise RuntimeError("Unexpected temporary build directory")
        shutil.copytree(
            document.parent, build, dirs_exist_ok=True,
            ignore=shutil.ignore_patterns(
                "*.pdf", "*.aux", "*.log", "*.out", "*.toc", "*.synctex.gz",
                "*.fls", "*.fdb_latexmk", "__pycache__",
            ),
        )
        print(f"Building {document.name} with Windows XeLaTeX from WSL.", flush=True)
        command = [
            str(WINDOWS_XELATEX), "-synctex=1", "-interaction=nonstopmode",
            "-halt-on-error", "-file-line-error", document.name,
        ]
        for pass_number in (1, 2):
            print(f"XeLaTeX pass {pass_number}/2", flush=True)
            result = subprocess.run(
                command, cwd=build, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
            sys.stdout.buffer.write(result.stdout)
            sys.stdout.flush()
            log = build / document.with_suffix(".log").name
            if log.is_file():
                shutil.copy2(log, document.with_suffix(".log"))
            if result.returncode:
                return result.returncode

        for suffix in (".pdf", ".aux", ".out", ".toc"):
            output = build / document.with_suffix(suffix).name
            if output.is_file():
                shutil.copy2(output, document.with_suffix(suffix))
        synctex = build / document.with_suffix(".synctex.gz").name
        if synctex.is_file():
            copy_synctex(synctex, document.with_suffix(".synctex.gz"), build, document.parent)
        print(f"PDF: {document.with_suffix('.pdf')}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

