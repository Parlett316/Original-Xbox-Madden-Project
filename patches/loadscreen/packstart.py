# Writes a PNG over the start-screen background (uis_fe.dat entry 7, 512x256 P8, uncompressed) in place.
# Usage: python packstart.py <original uis_fe.dat> <out uis_fe.dat> <image.png>   (any size; centre-cropped to the part the game shows)
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
# the game shows only this part of the texture, about 585x425 on a 640x480 screen (measured in xemu)
VISIBLE=(64,4,448,252); SHOWN_ASPECT=585/425
vw,vh=VISIBLE[2]-VISIBLE[0],VISIBLE[3]-VISIBLE[1]
src=Image.open(PNG).convert('RGB')
cw=min(src.width,round(src.height*SHOWN_ASPECT)); ch_=min(src.height,round(cw/SHOWN_ASPECT))
x0,y0=(src.width-cw)//2,(src.height-ch_)//2
win=src.crop((x0,y0,x0+cw,y0+ch_)).resize((vw,vh),Image.LANCZOS)
img=Image.new('RGB',(w,h))
img.paste(win.crop((0,0,1,vh)).resize((VISIBLE[0],vh)),(0,VISIBLE[1]))     # repeat the edges into the hidden margins
img.paste(win.crop((vw-1,0,vw,vh)).resize((w-VISIBLE[2],vh)),(VISIBLE[2],VISIBLE[1]))
img.paste(win,VISIBLE[:2])
img.paste(img.crop((0,VISIBLE[1],w,VISIBLE[1]+1)).resize((w,VISIBLE[1])),(0,0))
img.paste(img.crop((0,VISIBLE[3]-1,w,VISIBLE[3])).resize((w,h-VISIBLE[3])),(0,VISIBLE[3]))
q=img.quantize(256,method=Image.Quantize.MEDIANCUT,dither=Image.Dither.FLOYDSTEINBERG)
pal=q.getpalette()[:768]; pal+=[0]*(768-len(pal))
b[pals[0]:pals[0]+1024]=b''.join(bytes([pal[i*3+2],pal[i*3+1],pal[i*3],255]) for i in range(256))
xs,ys=eammap.morton_tables(w,h); px=q.tobytes()
for y in range(h):
    for x in range(w): b[off+ys[y]+xs[x]]=px[y*w+x]
out=bytearray(d); out[start:start+s]=b
open(DST,'wb').write(out)
eammap.render(bytes(b),0,0).convert('RGB').crop(VISIBLE).resize((585,425),Image.LANCZOS).save('start_preview.png')
print('wrote',DST)
