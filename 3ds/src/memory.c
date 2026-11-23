/* Freestanding compiler support. */
void *memcpy(void *destination,const void *source,unsigned int size) {
    unsigned char *d=destination;
    const unsigned char *s=source;
    for(unsigned int i=0;i<size;++i)d[i]=s[i];
    return destination;
}
void *memset(void *destination,int value,unsigned int size) {
    unsigned char *d=destination;
    for(unsigned int i=0;i<size;++i)d[i]=(unsigned char)value;
    return destination;
}
void *memmove(void *destination,const void *source,unsigned int size) {
    unsigned char *d=destination;
    const unsigned char *s=source;
    if(d<s){for(unsigned int i=0;i<size;++i)d[i]=s[i];}
    else{while(size){--size;d[size]=s[size];}}
    return destination;
}
