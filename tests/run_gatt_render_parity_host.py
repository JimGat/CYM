#!/usr/bin/env python3
"""Production GATT saved-details formatting parity; no real captures."""
from pathlib import Path
import subprocess,os
OLD='            static char hexraw[1028];\n            static char ascii[516];\n            static char row[620];\n            hexraw[0] = \'\\0\';\n            sscanf(line + 14, "%1027[^\\"]", hexraw);'
NEW='            char *hexraw = line + 14;\n            size_t hex_len = strcspn(hexraw, "\\"");\n            if (hex_len > 1027) hex_len = 1027;\n            char saved_hex_end = hexraw[hex_len];\n            hexraw[hex_len] = \'\\0\';\n            static char ascii[516];\n            static char row[620];'
CMAIN='int main(void){char src[4096],a[4096],b[4096],x[2048],y[2048];unsigned checks=0;const char *patterns[]={"0123456789abcdef","GGxy"," #a","\\"",""};for(unsigned t=0;t<5;t++)for(unsigned n=0;n<=1100;n++){memset(src,0,sizeof(src));memcpy(src,"\\"read_data\\": \\"",14);for(unsigned k=0;k<n;k++)src[14+k]=patterns[t][0]?patterns[t][k%strlen(patterns[t])]:0;src[14+n]=\'"\';strcpy(src+15+n,", trailing");strcpy(a,src);strcpy(b,src);before(a,x);after(b,y);assert(!strcmp(x,y));assert(!strcmp(src,b));checks++;}printf("PASS %u formatting parity + input restoration cases\\n",checks);}'

r=Path(__file__).resolve().parents[1];s=(r/'ESP32C5/main/main.c').read_text()
assert OLD not in s,'RED: redundant 1028-byte static hex copy remains'
a=s.index(NEW);end='            hexraw[hex_len] = saved_hex_end;';b=s.index(end,a)+len(end);body=s[a:b];old=body.replace(NEW,OLD).replace(end,'')
c='#include <stdio.h>\n#include <stdlib.h>\n#include <string.h>\n#include <assert.h>\n#define DET_ROW(a,b,c,d) snprintf(out,2048,"%s",b)\n'
c+='void before(char *line,char *out){'+old+'}\nvoid after(char *line,char *out){'+body+'}\n'+CMAIN
out=Path(os.environ['CYM_TEST_OUT'])/'gatt-render-parity';out.mkdir(parents=True,exist_ok=True);(out/'test.c').write_text(c)
subprocess.run(['cc','-fsanitize=address,undefined','-g',str(out/'test.c'),'-o',str(out/'test')],check=True)
subprocess.run([str(out/'test')],check=True)
