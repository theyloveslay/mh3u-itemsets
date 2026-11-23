/* Restricted 3DS SD-file transport. IPC layouts follow devkitPro/libctru;
 * see THIRD_PARTY.md. This is an altered, standalone implementation and does
 * not claim to be libctru. Real hardware/Azahar execution remains untested.
 */
#include "sd_io.h"
extern u32 *mhl_ipc_buffer(void);
extern u32 mhl_connect(u32 *handle,const char *port);
extern u32 mhl_send(u32 handle);
extern u32 mhl_close(u32 handle);
static int failed(u32 result){return (result&0x80000000u)!=0;}
static u32 send(u32 handle,u32 *c){u32 r=mhl_send(handle);return failed(r)?r:c[1];}
static void copy(u32 *to,const u32 *from){for(u32 i=0;i<64;++i)to[i]=from[i];}
static u32 initialize(SdSession *s,u32 *c){
    if(s->session)return 0;
    u32 srv=0,fs=0,r=mhl_connect(&srv,"srv:");if(failed(r))return r;
    c[0]=0x00010002;c[1]=0x20;c[2]=0;r=send(srv,c);
    if(!failed(r)){
        const char *name="fs:USER";c[0]=0x00050100;c[1]=c[2]=0;
        for(u32 i=0;i<7;++i)((u8 *)(c+1))[i]=(u8)name[i];
        c[3]=7;c[4]=0;r=send(srv,c);if(!failed(r))fs=c[3];
    }
    mhl_close(srv);
    if(failed(r) || !fs)return failed(r)?r:0xffffffffu;
    c[0]=0x08010002;c[1]=0x20;c[2]=0;r=send(fs,c);
    if(failed(r)){mhl_close(fs);return r;}
    s->session=fs;return 0;
}
static void filename(char *name,u32 character,u32 bank){
    const char *pattern="/mh3u_loadouts_user#_@.bin";u32 i=0;
    do{name[i]=pattern[i]=='#'?(char)('1'+character):pattern[i]=='@'?(char)('a'+bank):pattern[i];}while(pattern[i++]);
}
static u32 open_file(SdSession *s,u32 *c,const char *name,u32 flags,u32 *file){
    static const char empty[1]={0};u32 length=0;while(name[length])++length;++length;
    c[0]=0x08030204;c[1]=0;c[2]=9;c[3]=1;c[4]=1;c[5]=3;c[6]=length;c[7]=flags;c[8]=0;
    c[9]=(1u<<14)|(2u<<10)|2;c[10]=(u32)empty;
    c[11]=(length<<14)|2;c[12]=(u32)name;
    u32 r=send(s->session,c);*file=failed(r)?0:c[3];return r;
}
static u32 close_file(u32 file,u32 *c){
    c[0]=0x08080000;u32 r=send(file,c),closed=mhl_close(file);
    return failed(r)?r:closed;
}
/* A failed flush/close can leave a complete, checksummed candidate behind.
 * Best-effort invalidation prevents that failed edit winning the next load.
 * This touches only the alternate bank, never the previous committed bank.
 * If the device rejects cleanup too, durability cannot be guaranteed.
 */
static void invalidate(SdSession *s,u32 *c,const char *name){
    u32 file=0;if(failed(open_file(s,c,name,6,&file)) || !file)return;
    c[0]=0x08050080;c[1]=c[2]=0;
    if(!failed(send(file,c))){c[0]=0x08090000;send(file,c);}
    close_file(file,c);
}
static int read_bank(void *user,u32 character,u32 bank,u8 *out,u32 *length){
    if(!user || character>2 || bank>1 || !out || !length)return -1;
    u32 *c=mhl_ipc_buffer(),saved[64];copy(saved,c);
    SdSession *s=user;u32 r=initialize(s,c),file=0;int result=-1;
    if(!failed(r)){
        char name[40];filename(name,character,bank);r=open_file(s,c,name,1,&file);
        if(r==0xc8804478u)result=0; /* libctru's FS file-not-found result */
        else if(!failed(r) && file){
            c[0]=0x08040000;r=send(file,c);u32 size=c[2],high=c[3];
            if(!failed(r) && !high && size<=*length && (size==BANK_BYTES || size==BANK_V1_BYTES)){
                c[0]=0x080200c2;c[1]=c[2]=0;c[3]=size;c[4]=(size<<4)|12;c[5]=(u32)out;
                r=send(file,c);if(!failed(r) && c[2]==size){*length=size;result=1;}
            }
            if(failed(close_file(file,c)))result=-1;
        }
    }
    copy(c,saved);return result;
}
static int write_bank(void *user,u32 character,u32 bank,const u8 *data,u32 length){
    if(!user || character>2 || bank>1 || !data || length!=BANK_BYTES)return 0;
    u32 *c=mhl_ipc_buffer(),saved[64];copy(saved,c);
    SdSession *s=user;u32 r=initialize(s,c),file=0;int result=0;
    if(!failed(r)){
        char name[40];filename(name,character,bank);r=open_file(s,c,name,6,&file);
        if(!failed(r) && file){
            c[0]=0x08050080;c[1]=length;c[2]=0;r=send(file,c);
            if(!failed(r)){
                c[0]=0x08030102;c[1]=c[2]=0;c[3]=length;c[4]=1;c[5]=(length<<4)|10;c[6]=(u32)data;
                r=send(file,c);
                if(!failed(r) && c[2]==length){c[0]=0x08090000;r=send(file,c);if(!failed(r))result=1;}
            }
            if(failed(close_file(file,c)))result=0;
            if(!result)invalidate(s,c,name);
        }
    }
    copy(c,saved);return result;
}
void sd_bank_io(BankIO *io,SdSession *session){io->user=session;io->read=read_bank;io->write=write_bank;}
int sd_write_layout_report(const u8 *data,u32 length){
    static SdSession diagnostic_session;
    if(!data || !length || length>65536)return 0;
    u32 *c=mhl_ipc_buffer(),saved[64];copy(saved,c);
    u32 r=initialize(&diagnostic_session,c),file=0;int result=0;
    if(!failed(r)){
        r=open_file(&diagnostic_session,c,"/mh3u_itemsets_layout.bin",6,&file);
        if(!failed(r) && file){
            c[0]=0x08050080;c[1]=length;c[2]=0;r=send(file,c);
            if(!failed(r)){
                c[0]=0x08030102;c[1]=c[2]=0;c[3]=length;c[4]=1;c[5]=(length<<4)|10;c[6]=(u32)data;
                r=send(file,c);
                if(!failed(r) && c[2]==length){c[0]=0x08090000;r=send(file,c);if(!failed(r))result=1;}
            }
            if(failed(close_file(file,c)))result=0;
        }
    }
    copy(c,saved);return result;
}
