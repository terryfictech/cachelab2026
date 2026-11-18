// student id: 2025201863
// please change the above line to your student id

#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <getopt.h>

void printSummary(int hits, int misses, int evictions)
{
  printf("hits:%d misses:%d evictions:%d\n", hits, misses, evictions);
  FILE *output_fp = fopen(".csim_results", "w");
  assert(output_fp);
  fprintf(output_fp, "%d %d %d\n", hits, misses, evictions);
  fclose(output_fp);
}

void printHelp(const char *name)
{
  printf(
      "Usage: %s [-hv] -s <num> -E <num> -b <num> -t <file>\n"
      "Options:\n"
      "  -h         Print this help message.\n"
      "  -v         Optional verbose flag.\n"
      "  -s <num>   Number of set index bits.\n"
      "  -E <num>   Number of lines per set.\n"
      "  -b <num>   Number of block offset bits.\n"
      "  -t <file>  Trace file.\n\n"
      "Examples:\n"
      "  linux>  %s -s 4 -E 1 -b 4 -t traces/yi.trace\n"
      "  linux>  %s -v -s 8 -E 2 -b 4 -t traces/yi.trace\n",
      name, name, name);
}

typedef struct{
  int valid;//0:空行  1：里面有块
  unsigned long tag;//当前装入的块的tag
  unsigned long long last_used;
}cacheline;

int main(int argc, char *argv[])
{
  // printHelp(argv[0]);
  /*原来的注释掉
  // printSummary(0, 0, 0);
  // return 0;
  */

  int s=-1,E=-1,b=-1;
  const char *trace_path=NULL;
  int opt;
  //读命令行里的参数
  while((opt=getopt(argc,argv,"hs:E:b:t:"))!=-1){
    switch(opt){
      case 'h':
        printHelp(argv[0]);
        return 0;

      case 's':
        s=atoi(optarg);
        break;

      case 'E':
        E=atoi(optarg);
        break;

      case 'b':
        b=atoi(optarg);
        break;

      case 't':
        trace_path=optarg;
        break;

      default:
        return 1;
    }
  }

  if(s<0 || E<=0 || b<0 || trace_path==NULL){
    printHelp(argv[0]);
    return 1;
  }

  printf("s=%d, E=%d, b=%d, trace=%s\n", s, E, b, trace_path);

  

  int hits = 0, misses = 0, evictions = 0;
  unsigned long long access_time=0;

  unsigned long set_mask=(1ul<<s)-1;
  // unsigned long offset_mask=(1ul<<b)-1;

  //打开trace
  FILE *trace=fopen(trace_path, "r");
  if(trace==NULL){
    perror(trace_path);
    return 1;
  }
  //创建缓存
  // if (E != 1) {
  //     fprintf(stderr, "This version supports E=1 only.\n");
  //     fclose(trace);
  //     return 1;
  // }

  unsigned long set_count = 1UL << s;//高速缓存组数
  cacheline *cache = calloc(set_count, E*sizeof (cacheline));
  if (cache == NULL) {
      perror("calloc");
      fclose(trace);
      return 1;
  }

  

  char line[128];
  while(fgets(line,sizeof(line),trace)!=NULL){
      char op;
      unsigned long address;
      int size;

      if(sscanf(line," %c %lx,%d",&op,&address,&size) == 3) {
          // printf("%c address=0x%lx size=%d\n",op,address,size);
          unsigned long block_id=address>>b;
          unsigned long set_id=block_id&set_mask;
          unsigned long tag=block_id>>s;
          // unsigned long offset=address&offset_mask;

          // printf("%c address=0x%lx set=%lu tag=0x%lx offset=%lu\n",
          //         op, address, set_id, tag, offset);

          //只有一行的情况，E=1
          // cacheline *target=&cache[set_id];
          // if(target->valid && target->tag==tag){
          //   ++hits;
          // }else{
          //   ++misses;//找不到先+1

          //   if (target->valid){//存放着别的块要覆盖，eviction
          //     ++evictions;
          //   }
          //   target->valid=1;
          //   target->tag=tag;
          // }
          ++access_time;
          cacheline *set=&cache[set_id*E];
          cacheline *hit_line=NULL;
          cacheline *empty_line=NULL;
          cacheline *lru_line=NULL;

          for(int i=0;i<E;i++){//开始扫描该组
            cacheline *line=&set[i];

            if(!line->valid){//如果是空行
              if(empty_line==NULL){//且之前未记录空行
                empty_line=line;
              }
              continue;
            }

            if(line->tag==tag){
              hit_line=line;
              break;
            }

            if(lru_line==NULL || line->last_used<lru_line->last_used){
              lru_line=line;//成为淘汰候选
            }
          }

          if(hit_line!=NULL){
            ++hits;
            hit_line->last_used=access_time;
          }else{
            ++misses;
            cacheline *target=empty_line;

            if(target==NULL){
              ++evictions;
              target=lru_line;
            }

            target->valid=1;
            target->tag=tag;
            target->last_used=access_time;
          }
      }
  }
  fclose(trace);
  free(cache);
  printSummary(hits,misses,evictions);
  return 0;
}
