/* Optional live GUI capture. No game save data is opened or modified.
 * Memory is checked through QueryMemory before every bounded read. */
#include "layout_diagnostics.h"
#include "sd_io.h"
#ifdef MHL_LAYOUT_DIAGNOSTICS
#define WORD(a) (*(volatile u32 *)(a))
#define MAX_BYTES 65536
extern u32 item_memory_readable(u32 address,u32 length);
static u8 report[MAX_BYTES] __attribute__((aligned(4)));
static u32 frames,animations,scroll_calls,line_calls,scroll_ptr,line_ptr;
static u32 shift_words[24],shift_count,used,records,invalid,truncated,attempted;
static u32 samples[32][2],sample_count;
static int valid(u32 address,u32 size){
    return address && !(address&3) && item_memory_readable(address,size);
}
static void copy(u8 *out,const u8 *in,u32 n){for(u32 i=0;i<n;++i)out[i]=in[i];}
static void block(u32 tag,u32 address,u32 aux,const void *data,u32 size){
    if(used+16+size>MAX_BYTES){truncated|=2;return;}
    u32 *p=(u32 *)(report+used);p[0]=tag;p[1]=address;p[2]=aux;p[3]=size;
    copy(report+used+16,data,size);used+=16+size;++records;
}
static int memory(u32 tag,u32 address,u32 aux,u32 size){
    if(!valid(address,size)){u32 info[2]={address,size};block(0xffffffff,address,tag,info,8);++invalid;return 0;}
    block(tag,address,aux,(const void *)address,size);return 1;
}
static void graph(u32 root,int instance,u32 limit){
    u32 todo[96],seen[96],count=0,n=0;
    if(root)todo[n++]=root;
    while(n && count<limit && count<96 && !(truncated&2)){
        u32 node=todo[--n],found=0;
        for(u32 i=0;i<count;++i)if(seen[i]==node)found=1;
        if(found)continue;
        seen[count++]=node;
        if(!memory(instance?7:8,node,instance?0:root,0x120))continue;
        u32 child=WORD(node+(instance?0x80:0x7c)),next=WORD(node+(instance?0x84:0x80));
        if(next && n<96)todo[n++]=next;
        if(child && n<96)todo[n++]=child;
    }
    if(n)truncated|=1;
}
void item_diag_targets(u32 scroll,u32 line,const void *shifts,u32 count){
    scroll_ptr=scroll;line_ptr=line;shift_count=count>4?4:count;
    copy((u8 *)shift_words,shifts,shift_count*24);
}
void item_diag_animation(void *instance){
    ++animations;
    if(!frames || attempted)return;
    u32 ptr=(u32)instance;
    if(ptr==scroll_ptr)++scroll_calls;if(ptr==line_ptr)++line_calls;
    for(u32 i=0;i<sample_count;++i)if(samples[i][0]==ptr){++samples[i][1];return;}
    if(sample_count<32){samples[sample_count][0]=ptr;samples[sample_count++][1]=1;}
}
void item_diag_menu(void *widget,const u8 *state){
    if(attempted || ++frames!=60)return;
    attempted=1;used=64;records=invalid=truncated=0;
    memory(1,(u32)state,0,32);memory(2,(u32)widget,0,0x240);
    block(6,0,shift_count,shift_words,shift_count*24);
    block(9,0,sample_count,samples,sample_count*8);
    if(valid((u32)widget,0x240)){
        /* The watched animation roots are first, so a large graph cannot
         * crowd the critical frame/divider objects out of the report. */
        u32 watched[2]={scroll_ptr,line_ptr};
        for(u32 i=0;i<2;++i)if(valid(watched[i],0x120)){
            memory(10,watched[i],i,0x120);graph(WORD(watched[i]+0xf8),0,32);
        }
        /* Capture the real frame components and reserved/last row parents.
         * v2 established that watching only 428 cannot find the divider. */
        const u32 ids[]={430,439,429,438,431,450,466,534};
        for(u32 i=0;i<8;++i){
            u32 inst=((u32 (*)(void *,u32,u32))0x00a2dd50)(widget,ids[i],1);
            if(valid(inst,0x120)){
                memory(10,inst,ids[i],0x120);
                if(WORD(inst)==0x00b5ea6cu)graph(WORD(inst+0xf8),0,24);
            }
        }
        for(u32 j=0;j<3;++j){
            u32 array=WORD((u32)widget+0x224+4*j);
            if(!memory(3+j,array,0,32))continue;
            for(u32 i=0;i<8;++i)memory(11+j,WORD(array+i*4),i,0x120);
        }
        graph(WORD((u32)widget+0xf4),1,80);
    }
    u32 *h=(u32 *)report;
    h[0]=0x4744334d;h[1]=1;h[2]=used;h[3]=0x000500d4;
    h[4]=frames;h[5]=animations;h[6]=scroll_calls;h[7]=line_calls;
    h[8]=scroll_ptr;h[9]=line_ptr;h[10]=shift_count;h[11]=records;
    h[12]=invalid;h[13]=truncated;h[14]=sample_count;h[15]=0;
    sd_write_layout_report(report,used);
}
#else
void item_diag_targets(u32 a,u32 b,const void *c,u32 d){(void)a;(void)b;(void)c;(void)d;}
void item_diag_animation(void *instance){(void)instance;}
void item_diag_menu(void *widget,const u8 *state){(void)widget;(void)state;}
#endif
