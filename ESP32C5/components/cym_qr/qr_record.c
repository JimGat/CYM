#include "qr_record.h"
#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

static const char hex[] = "0123456789ABCDEF";
size_t cym_qr_escape(const uint8_t *data, size_t len, char *out, size_t cap)
{
    size_t n = 0;
    if (!data && len) { if (cap && out) out[0] = 0; return 0; }
    for (size_t i = 0; i < len; ++i) {
        char b[4] = {'\\', 'x', hex[data[i] >> 4], hex[data[i] & 15]};
        const char *s = (data[i] >= 32 && data[i] <= 126) ? (const char *)&data[i] : b;
        size_t k = s == b ? 4 : 1;
        for (size_t j = 0; j < k; ++j, ++n) if (out && cap && n < cap-1) out[n] = s[j];
    }
    if (out && cap) out[n < cap ? n : cap-1] = 0;
    return n;
}
static int all(int fd, const char *s, size_t n)
{
    while (n) {
        ssize_t k = write(fd, s, n);
        if (k < 0 && errno == EINTR) continue;
        if (k <= 0) return errno ? errno : EIO;
        s += k; n -= (size_t)k;
    }
    return 0;
}
static int text(int fd, const char *s) { return all(fd, s, strlen(s)); }
static int quoted(int fd, const char *s)
{
    int e = text(fd, "\"");
    for (; !e && *s; ++s) {
        if (*s == '"' || *s == '\\') e = text(fd, "\\");
        if (!e) e = all(fd, s, 1);
    }
    return e ? e : text(fd, "\"");
}
static int directory(const char *path)
{
    struct stat st;
    if (!stat(path, &st)) return S_ISDIR(st.st_mode) ? 0 : ENOTDIR;
    if (errno != ENOENT) return errno;
    if (!mkdir(path, 0775)) return 0;
    if (errno == EEXIST && !stat(path, &st) && S_ISDIR(st.st_mode)) return 0;
    return errno ? errno : EIO;
}
int cym_qr_record(const char *root, const uint8_t *data, size_t len,
                  const char *version, int64_t utc, uint64_t uptime,
                  char *filename, size_t cap)
{
    char path[256], name[32], buf[256];
    struct stat st;
    if (filename && cap) filename[0] = 0;
    if (!root || (!data && len) || !version || !filename || cap < 25 || len > 8896) return EINVAL;
    /* Never fabricate a mount point on an absent card. */
    if (stat(root, &st)) return errno;
    if (!S_ISDIR(st.st_mode)) return ENOTDIR;
    if (snprintf(path, sizeof(path), "%s/lab", root) >= (int)sizeof(path)) return ENAMETOOLONG;
    int e = directory(path); if (e) return e;
    if (snprintf(path, sizeof(path), "%s/lab/QR", root) >= (int)sizeof(path)) return ENAMETOOLONG;
    e = directory(path); if (e) return e;
    int fd = -1;
    /* Exclusive creation is authoritative, including across reboot. Payload never
     * participates in the filename. Caller serializes card operations. */
    for (uint32_t i = 0; i < 1000000; ++i) {
        snprintf(name, sizeof(name), "qr-%08" PRIu32 ".json", i);
        if (snprintf(path,sizeof(path),"%s/lab/QR/%s",root,name) >= (int)sizeof(path)) return ENAMETOOLONG;
        fd = open(path, O_WRONLY | O_CREAT | O_EXCL, 0664);
        if (fd >= 0) break;
        if (errno != EEXIST) return errno;
    }
    if (fd < 0) return EEXIST;
    e = text(fd, "{\n  \"schema_version\": 1,\n  \"board\": \"ws-c5-35\",\n  \"firmware\": ");
    if (!e) e = quoted(fd, version);
    snprintf(buf,sizeof(buf),",\n  \"symbology\": \"QR\",\n  \"byte_length\": %zu,\n  \"timestamp_valid\": %s,\n  \"utc_unix\": ",len,utc >= 1577836800 ? "true" : "false");
    if (!e) e = text(fd,buf);
    if (utc >= 1577836800) snprintf(buf,sizeof(buf),"%" PRId64,utc); else strcpy(buf,"null");
    if (!e) e = text(fd,buf);
    snprintf(buf,sizeof(buf),",\n  \"uptime_ms\": %" PRIu64 ",\n  \"payload_hex\": \"",uptime);
    if (!e) e = text(fd,buf);
    /* Batched hex output limits card syscall overhead without a large RAM buffer. */
    for (size_t pos = 0; !e && pos < len;) {
        size_t n = len-pos; if (n > sizeof(buf)/2) n = sizeof(buf)/2;
        for (size_t j = 0; j < n; ++j) { buf[2*j]=hex[data[pos+j]>>4];buf[2*j+1]=hex[data[pos+j]&15]; }
        e = all(fd,buf,n*2); pos += n;
    }
    if (!e) e = text(fd,"\",\n  \"display_text\": \"");
    for (size_t i = 0; !e && i < len; ++i) {
        char disp[5]; cym_qr_escape(data+i,1,disp,sizeof(disp));
        for (const char *p = disp; !e && *p; ++p) {
            if (*p == '"' || *p == '\\') e = text(fd,"\\");
            if (!e) e = all(fd,p,1);
        }
    }
    if (!e) e = text(fd,"\"\n}\n");
    int close_rc = close(fd);
    if (close_rc && !e) e = errno ? errno : EIO;
    if (e) { unlink(path); return e; } /* only our exclusively-created file */
    snprintf(filename,cap,"%s",name);
    return 0;
}

int cym_qr_debug_frame(const char *root,const uint8_t *gray,int w,int h,
                       size_t stride,const char *meta,char *filename,size_t cap)
{
    char path[256],name[40],header[768];struct stat st;
    if(filename&&cap)filename[0]=0;
    if(!root||!gray||!meta||!filename||cap<32||w<1||h<1||w>1024||h>1024||stride<(size_t)w)return EINVAL;
    if(strlen(meta)>640||strchr(meta,'\n')||strchr(meta,'\r'))return EINVAL;
    if(stat(root,&st))return errno;
    if(!S_ISDIR(st.st_mode))return ENOTDIR;
    const char *dirs[]={"lab","lab/QR","lab/QR/debug"};
    for(unsigned i=0;i<3;i++){
        if(snprintf(path,sizeof(path),"%s/%s",root,dirs[i])>=(int)sizeof(path))return ENAMETOOLONG;
        int e=directory(path);if(e)return e;
    }
    int fd=-1;
    /* Bounded collision search, never overwrite an earlier voluntary frame. */
    for(unsigned i=0;i<1024;i++){
        snprintf(name,sizeof(name),"frame-%04u.pgm",i);
        if(snprintf(path,sizeof(path),"%s/lab/QR/debug/%s",root,name)>=(int)sizeof(path))return ENAMETOOLONG;
        fd=open(path,O_WRONLY|O_CREAT|O_EXCL,0664);
        if(fd>=0)break;
        if(errno!=EEXIST)return errno;
    }
    if(fd<0)return EEXIST;
    int n=snprintf(header,sizeof(header),"P5\n# %s\n%d %d\n255\n",meta,w,h);
    int e=n<0||n>=(int)sizeof(header)?EINVAL:all(fd,header,(size_t)n);
    for(int y=0;!e&&y<h;y++)e=all(fd,(const char *)gray+y*stride,(size_t)w);
    if(close(fd)&&!e)e=errno?errno:EIO;
    if(e){unlink(path);return e;}
    snprintf(filename,cap,"%s",name);return 0;
}
