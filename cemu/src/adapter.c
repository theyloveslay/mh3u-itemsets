/* Cemu US v32 adapter. Original implementation; native addresses were checked
   against the supplied executable. No original game binary is distributed. */
#include "loadouts.h"
extern int original_box_step(u8 *lobby);
extern const char *original_text(void *sid,u32 group,u32 index);
extern int original_character(void *app,void *blob,u32 slot);

#define U32(a) (*(volatile u32 *)(a))
#define U16(a) (*(volatile u16 *)(a))
#define PTR(a) ((void *)(a))
typedef int (*F2)(void *,u32);
typedef void (*F1)(void *);
typedef int (*F7)(void *,void *,u32,const char *,const char *,u32 *,u32);
typedef int (*F8)(void *,void *,void *,u32,u32,u32,u32,u32);
typedef int (*F4)(void *,void *,u32,u32);
typedef u32 (*N2)(void *,void *);
enum { BANK_BYTES=3712, OLD_BANK_BYTES=2688, HEADER=48, MAGIC=0x4d334c44, VERSION=2 };
typedef struct {
    u32 magic,version,character,sequence,checksum;
    u8 reserved[28];
    Loadout sets[L_SETS];
    char names[L_SETS][20];
    u8 padding[16];
} Bank;
_Static_assert(sizeof(Bank)==BANK_BYTES,"Bank format size");

/* Separate FS client/cmd buffers: never borrow the game's asynchronous save
   client's state. Buffers and file payloads meet Cafe's 64-byte alignment. */
static u8 fs_client[0x1700] __attribute__((aligned(64)));
static u8 fs_cmd[0xa80] __attribute__((aligned(64)));
static Bank banks[2] __attribute__((aligned(64)));
static Bank write_bank __attribute__((aligned(64)));
Loadout sets[L_SETS];
char set_names[L_SETS][20];
static Transaction transaction;
static ItemRule rules[L_ITEMS];
static u32 character=3, cached_character=3, sequence;
u32 selected;
u32 load_missing_units;
static int loaded, bank_index=-1, fs_ready, io_ready;
const char *message="";

static void bytes_copy(void *to,const void *from,u32 n) {
    u8 *d=to;const u8 *s=from;for(u32 i=0;i<n;++i)d[i]=s[i];
}
static void zero(void *to,u32 n) {u8 *d=to;for(u32 i=0;i<n;++i)d[i]=0;}
static void numbered_name(char *name,u32 n){
    zero(name,20);bytes_copy(name,"Set ",4);u32 pos=4;
    if(n>=10)name[pos++]=(char)('0'+n/10);
    name[pos]=(char)('0'+n%10);
}
void default_name(u32 index){numbered_name(set_names[index],index+1);}

/* Decode the live relocated import callsite. The loader resolves its branch;
   using its actual target avoids assuming Cafe import addresses are fixed.
   Unrecognized instructions fail closed, rather than calling an arbitrary PC. */
u32 import_target(u32 site) {
    u32 instruction=U32(site);
    if((instruction&0xfc000001)!=0x48000001)return 0;
    int displacement=(int)(instruction&0x03fffffc);
    if(displacement&0x02000000)displacement|=(int)0xfc000000;
    return instruction&2 ? (u32)displacement : site+(u32)displacement;
}
/* Keep the actual failure visible: a generic storage error cannot distinguish
   an unbound slot, an unavailable save account, imports or a damaged bank. */
static const char *storage_stage="not initialized";
static int storage_result,storage_bank=-1;
static u32 storage_character=3,storage_account=0xff;
static void storage_fail(const char *stage,int result,int bank){
    storage_stage=stage;storage_result=result;storage_bank=bank;
}
static char *append_text(char *out,const char *text){while(*text)*out++=*text++;return out;}
static char *append_unsigned(char *out,u32 value){
    char digits[10];u32 n=0;do{digits[n++]=(char)('0'+value%10);value/=10;}while(value);
    while(n)*out++=digits[--n];return out;
}
const char *storage_error(void){
    static char text[160];char *out=append_text(text,"Storage: ");
    out=append_text(out,storage_stage);
    if(storage_bank>=0){*out++=' ';*out++=(char)('A'+storage_bank);}
    out=append_text(out," (");
    u32 magnitude=(u32)storage_result;
    if(storage_result<0){*out++='-';magnitude=0u-magnitude;}
    out=append_unsigned(out,magnitude);out=append_text(out,")\r\nChar ");
    out=append_unsigned(out,storage_character);out=append_text(out,", account ");
    out=append_unsigned(out,storage_account);*out=0;return text;
}
static u32 storage_import(u32 site,const char *name){
    u32 target=import_target(site);
    if(!target)storage_fail(name,(int)U32(site),-1);
    return target;
}
static F2 fs_add;
static F1 fs_init_cmd;
static F7 save_open;
static F8 fs_read,fs_write;
static F4 fs_close,save_flush;
static int init_fs(void) {
    if(fs_ready)return 1;
    fs_add=(F2)storage_import(0x02bdbf18,"fs_add import");
    fs_init_cmd=(F1)storage_import(0x02935b84,"fs_init_cmd import");
    save_open=(F7)storage_import(0x02bdcef8,"save_open import");
    fs_read=(F8)storage_import(0x02bdc56c,"fs_read import");
    fs_write=(F8)storage_import(0x02bdcff8,"fs_write import");
    fs_close=(F4)storage_import(0x02bdce88,"fs_close import");
    save_flush=(F4)storage_import(0x02bdd1ec,"save_flush import");
    if(!fs_add||!fs_init_cmd||!save_open||!fs_read||!fs_write||!fs_close||!save_flush)return 0;
    int result=fs_add(fs_client,0xffffffff);
    if(result!=0){storage_fail("FSAddClient",result,-1);return 0;}
    fs_init_cmd(fs_cmd);fs_ready=1;return 1;
}
static u32 account(void) {
    u32 savedata=U32(0x102cebe0);
    return savedata?*(volatile u8 *)(savedata+0x42bf):0xff;
}
static void filename(char *out,int bank) {
    const char *s="mh3u_loadouts_user#_@.bin";
    u32 i=0;do {out[i]=s[i]=='#'?(char)('1'+character):s[i]=='@'?(char)('a'+bank):s[i];}while(s[i++]);
}
static u32 checksum_size(const Bank *b,u32 length) {
    const u8 *data=(const u8 *)b;
    u32 value=2166136261u;
    for(u32 i=0;i<length;++i) {
        u8 byte=(i>=16 && i<20)?0:data[i];
        value=(value^byte)*16777619u;
    }
    return value;
}
static int valid_bank(const Bank *b,u32 length) {
    u32 count=b->version==1?20:24;
    if(b->magic!=MAGIC||b->character!=character||
        !((b->version==1&&length==OLD_BANK_BYTES)||(b->version==VERSION&&length==BANK_BYTES))||
        b->checksum!=checksum_size(b,length))return 0;
    for(u32 i=0;i<count;++i)if(b->sets[i].valid>1||b->sets[i].gunner>1)return 0;
    return 1;
}
/* -6 = FS_STATUS_NOT_FOUND. Other open/read errors must not be interpreted as
   an empty loadout file: doing that could overwrite existing registrations. */
static int read_bank(int index) {
    char path[40];u32 fd=0;filename(path,index);
    int result=save_open(fs_client,fs_cmd,account(),path,"r",&fd,0xffffffff);
    if(result==-6)return 0;
    if(result){storage_fail("open",result,index);return -1;}
    zero(&banks[index],sizeof(Bank));
    result=fs_read(fs_client,fs_cmd,&banks[index],1,BANK_BYTES,fd,0,0xffffffff);
    int closed=fs_close(fs_client,fs_cmd,fd,0xffffffff);
    if(result!=BANK_BYTES&&result!=OLD_BANK_BYTES){storage_fail("read",result,index);return -1;}
    if(closed){storage_fail("close",closed,index);return -1;}
    if(!valid_bank(&banks[index],(u32)result)){storage_fail("invalid bank",-1,index);return -1;}
    return 1;
}
int ensure_loaded(void) {
    /* A failed initialization may become usable later (account/FS readiness).
       Retry on the next request, but retain the validated-bank write guards. */
    if(loaded && cached_character==character && io_ready)return 1;
    storage_character=character;storage_account=account();
    storage_fail("initialization",0,-1);
    cached_character=character;loaded=1;io_ready=0;sequence=0;bank_index=-1;
    zero(sets,sizeof(sets));
    for(u32 i=0;i<L_SETS;++i)default_name(i);
    if(character>2){storage_fail("character",(int)character,-1);return 0;}
    if(storage_account==0xff){storage_fail("account",(int)storage_account,-1);return 0;}
    if(!init_fs())return 0;
    int a=read_bank(0),b=read_bank(1);
    if(a==1||b==1) {
        bank_index=a==1?0:1;
        if(a==1&&b==1&&(int)(banks[1].sequence-banks[0].sequence)>0)bank_index=1;
        sequence=banks[bank_index].sequence;
        bytes_copy(sets,banks[bank_index].sets,sizeof(sets));
        if(banks[bank_index].version==VERSION){
            bytes_copy(set_names,banks[bank_index].names,sizeof(set_names));
            for(u32 i=0;i<L_SETS;++i){
                set_names[i][19]=0;
                /* Upgrade generated legacy names, including reordered sets,
                   while retaining every other custom name verbatim. */
                char *p=set_names[i];const char *prefix="Item Set ";u32 k=0;
                while(k<9 && p[k]==prefix[k])++k;
                if(k==9 && p[9]>='0' && p[9]<='2' && p[10]>='0' && p[10]<='9' && !p[11]){
                    u32 n=(u32)(p[9]-'0')*10+(u32)(p[10]-'0');
                    if(n>=1 && n<=L_SETS)numbered_name(p,n);
                }
            }
        }
    } else if(a!=0||b!=0)return 0;
    io_ready=1;return 1;
}
int persist(void) {
    int next=bank_index==0?1:0;
    zero(&write_bank,sizeof(write_bank));
    write_bank.magic=MAGIC;write_bank.version=VERSION;write_bank.character=character;
    write_bank.sequence=sequence+1;
    bytes_copy(write_bank.sets,sets,sizeof(sets));bytes_copy(write_bank.names,set_names,sizeof(set_names));
    write_bank.checksum=checksum_size(&write_bank,BANK_BYTES);
    char path[40];u32 fd=0;filename(path,next);
    if(save_open(fs_client,fs_cmd,account(),path,"w",&fd,0xffffffff))return 0;
    int result=fs_write(fs_client,fs_cmd,&write_bank,1,BANK_BYTES,fd,0,0xffffffff);
    int closed=fs_close(fs_client,fs_cmd,fd,0xffffffff);
    if(result!=BANK_BYTES||closed||save_flush(fs_client,fs_cmd,account(),0xffffffff))return 0;
    sequence=write_bank.sequence;bank_index=next;return 1;
}

static u32 userdata(void) {return U32(0x10315f50);}
static int gunner(u32 ud) {return ((N2)0x02199e48)(PTR(ud),PTR(ud+0x38))!=0;}
void capture(void) {
    if(!ensure_loaded()){message=storage_error();return;}
    u32 ud=userdata();if(!ud)return;
    Loadout old=sets[selected];int g=gunner(ud);
    char old_name[20];bytes_copy(old_name,set_names[selected],20);
    if(!old.valid)default_name(selected);
    zero(&sets[selected],sizeof(Loadout));sets[selected].valid=1;sets[selected].gunner=(u8)g;
    bytes_copy(sets[selected].slots,PTR(ud+0x38+(g?0x108:0xa8)),g?128:96);
    if(!persist()){sets[selected]=old;bytes_copy(set_names[selected],old_name,20);message="Could not confirm registration.\r\nThe current registration was kept.";}
    else message="Item set registered.";
}
static int read_rules(void) {
    u32 table=U32(0x10167e50);if(!table)return 0;
    for(u32 i=0;i<L_ITEMS;++i) {
        const u8 *row=PTR(table+20*i);
        rules[i]=(ItemRule){row[3],row[0],(u8)(i>1 && !(i>=0x4db && i<=0x4de) && i!=0x5f3),0};
    }
    return 1;
}
int apply(void) {
    load_missing_units=0;
    if(!ensure_loaded()){message=storage_error();return 0;}
    if(!sets[selected].valid){message="This item set is empty.\r\nChoose Register Set to save your pouch.";return 0;}
    u32 ud=userdata();if(!ud||!read_rules()){message="Item data is unavailable.\r\nNo items were changed.";return 0;}
    int g=gunner(ud);u32 hunter=ud+0x38;
    Slot *target=PTR(hunter+(g?0x108:0xa8)),*donor=PTR(hunter+(g?0xa8:0x108)),*box=PTR(ud+0x1c0);
    u32 count=g?32:24,opposite=g?24:32;
    u32 box_count=((N2)0x0219880c)(PTR(ud),PTR(hunter));
    int result=plan_loadout(target,count,donor,opposite,box,box_count,&sets[selected],rules,&transaction);
    if(result==L_WRONG_POUCH){message="Equip this set's weapon type\r\nbefore loading its Item Pouch.";return 0;}
    if(result==L_BOX_FULL){message="No room to store leftover items.\r\nNothing changed.";return 0;}
    if(result!=L_OK && result!=L_PARTIAL){message="The set contains invalid items\r\nor quantities. Nothing changed.";return 0;}
    commit_loadout(target,count,donor,opposite,box,box_count,&transaction);
    load_missing_units=transaction.missing_units;
    message="Item set loaded.";
    return 1;
}

int track_character(void *app,void *blob,u32 slot) {
    int result=original_character(app,blob,slot);
    character=slot<3?slot:3;loaded=0;selected=0;
    extern void reset_item_ui(void);reset_item_ui();
    return result;
}
