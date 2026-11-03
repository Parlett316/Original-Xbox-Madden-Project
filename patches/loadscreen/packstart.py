# Writes a PNG over the start-screen background (uis_fe.dat entry 7, 512x256 P8, uncompressed) in place.
# Usage: python packstart.py <original uis_fe.dat> <out uis_fe.dat> <image.png>   (any size; resized to 512x256, shown stretched)
import sys
from PIL import Image
import eammap
from terf import parse
SRC=sys.argv[1]; DST=sys.argv[2]; PNG=sys.argv[3]
d,ch,ents,comp=parse(SRC); base=ch[b'DATA'][0]
o,s=ents[7]; start=base+o
b=bytearray(d[start:start+s])
texs,pals=eammap.parse(b)
w,h,fmt,sz,off=texs[0]; off+=0x80
assert (w,h,fmt,sz)==(512,256,11,0x20000)
img=Image.open(PNG).convert('RGB').resize((w,h),Image.LANCZOS)
q=img.quantize(256,method=Image.Quantize.MEDIANCUT,dither=Image.Dither.FLOYDSTEINBERG)
pal=q.getpalette()[:768]; pal+=[0]*(768-len(pal))
b[pals[0]:pals[0]+1024]=b''.join(bytes([pal[i*3+2],pal[i*3+1],pal[i*3],255]) for i in range(256))
xs,ys=eammap.morton_tables(w,h); px=q.tobytes()
for y in range(h):
    for x in range(w): b[off+ys[y]+xs[x]]=px[y*w+x]
out=bytearray(d); out[start:start+s]=b
open(DST,'wb').write(out)
eammap.render(bytes(b),0,0).convert('RGB').save('start_preview.png')
print('wrote',DST)
