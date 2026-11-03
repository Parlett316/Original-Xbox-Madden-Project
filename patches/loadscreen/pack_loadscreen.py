# Replaces the cover image of the Madden 09 loading screen (data/LOADDATA.dat entries 0 and 2) with a PNG.
# Usage: python pack_loadscreen.py <original LOADDATA.dat> <out LOADDATA.dat> <image.png>   (640x480; the visible area of the 1024x512 texture)
import struct,sys
from PIL import Image
import eammap
from terf import parse
from lzh1emu import compress,decompress
SRC=sys.argv[1]; DST=sys.argv[2]; PNG=sys.argv[3]

def encode_tex(buf):
    b=bytearray(buf)
    texs,pals=eammap.parse(b)
    w,h,fmt,sz,off=texs[0]; off+=0x80
    assert (w,h,fmt,sz)==(1024,512,11,0x80000)
    img=Image.new('RGB',(w,h),(0,0,0)); img.paste(Image.open(PNG).convert('RGB'),(0,0))
    q=img.quantize(256,method=Image.Quantize.MEDIANCUT,dither=Image.Dither.FLOYDSTEINBERG)
    pal=q.getpalette()[:768]; pal+= [0]*(768-len(pal))
    pb=bytearray()
    for i in range(256): pb+=bytes([pal[i*3+2],pal[i*3+1],pal[i*3],255])
    b[pals[0]:pals[0]+1024]=pb
    xs,ys=eammap.morton_tables(w,h)
    px=q.tobytes()
    for y in range(h):
        row=px[y*w:(y+1)*w]; yo=off+ys[y]
        for x in range(w): b[yo+xs[x]]=row[x]
    return bytes(b)

d,ch,ents,comp=parse(SRC)
base=ch[b'DATA'][0]
blobs=[];types=[]
for k,(o,s) in enumerate(ents):
    raw=d[base+o:base+o+s]
    if comp[k][0]==5:
        full=decompress(raw,comp[k][1])[0]
        t=eammap.parse(full)[0]
        if t[0][:2]==(1024,512) and k in (0,2):
            full=encode_tex(full)
            r,_,_,_=0,0,0,0
            r,a,_,out=compress(full); raw=out[:a[1]]
            assert decompress(raw,len(full))[0]==full
            print('replaced entry',k,len(raw))
        blobs.append((raw,(5,len(full))))
    else:
        blobs.append((raw,comp[k]))
# rebuild: same header/chunks, entries aligned to 0x80 from DATA start
hs=struct.unpack_from('<I',d,4)[0]
out=bytearray(d[:base])
dp=ch[b'DIR1'][0]; cp=ch[b'COMP'][0]
data=bytearray(d[base:base+ents[0][0]])  # DATA header + padding
for k,(raw,(ct,us)) in enumerate(blobs):
    while len(data)%0x80: data.append(0)
    off=len(data); data+=raw
    struct.pack_into('<II',out,dp+8+8*k,off,len(raw))
    struct.pack_into('<II',out,cp+8+8*k,ct,us)
while len(data)%0x80: data.append(0)
struct.pack_into('<I',data,4,len(data))
out+=data
open(DST,'wb').write(out)
print('wrote',len(out))
