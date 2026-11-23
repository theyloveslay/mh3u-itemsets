#include "store.h"
/* UI-thread-only scratch avoids putting multiple 3.7KB banks on game stacks. */
static u8 wire[BANK_BYTES];
static SetCollection candidate;
int store_load(BankStore *store,const BankIO *io,u32 character){
    if(!store)return 0;
    store->ready=0;store->bank_index=-1;
    if(!io || !io->read || character>2)return 0;
    int missing=0;
    for(u32 i=0;i<2;++i){
        u32 length=BANK_BYTES;int result=io->read(io->user,character,i,wire,&length);
        if(!result){++missing;continue;}
        if(result!=1 || !bank_decode(wire,length,character,&candidate))continue;
        if(store->bank_index<0 || bank_newer(candidate.sequence,store->collection.sequence)){
            store->collection=candidate;store->bank_index=(int)i;
        }
    }
    if(store->bank_index<0){
        if(missing!=2)return 0;
        bank_defaults(&store->collection,character);
    }
    store->ready=1;return 1;
}
int store_save(BankStore *store,const BankIO *io){
    if(!store || !store->ready || !io || !io->write)return 0;
    candidate=store->collection;candidate.sequence++;
    if(!bank_encode(&candidate,wire))return 0;
    u32 next=store->bank_index==0?1:0;
    if(io->write(io->user,candidate.character,next,wire,BANK_BYTES)!=1)return 0;
    store->collection.sequence=candidate.sequence;store->bank_index=(int)next;return 1;
}
