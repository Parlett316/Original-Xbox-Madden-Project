import struct
from PIL import Image
def morton_tables(w,h):
    # xbox swizzle: interleave x/y bits, x first, while both have bits
    def tab(n,other):
        pass
    xs=[0]*w; ys=[0]*h
    bit=1; xb=1; yb=1
    while xb<w or yb<h:
        if xb<w:
            for x in range(w):
                if x&xb: xs[x]|=bit
            bit<<=1; xb<<=1
        if yb<h:
            for y in range(h):
                if y&yb: ys[y]|=bit
            bit<<=1; yb<<=1
    return xs,ys
def parse(b):
    n=struct.unpack_from('<H',b,0xc)[0]
    texs=[struct.unpack_from('<HHIII',b,0x28+16*i) for i in range(n)]
    palhdr=struct.unpack_from('<I',b,0x1c)[0]
    pals=[]
    k=0
    while True:
        cnt,sz,off=struct.unpack_from('<III',b,palhdr+12*k)
        if cnt==0: break
        pals.append(off+0x80); k+=1
    return texs,pals
def render(b,ti,pi,shift=0x80,crop=None):
    texs,pals=parse(b)
    w,h,fmt,sz,off=texs[ti]; off+=shift
    pal=b[pals[pi]:pals[pi]+1024]
    xs,ys=morton_tables(w,h)
    px=bytearray(w*h*4)
    for y in range(h):
        for x in range(w):
            c=b[off+xs[x]+ys[y]]*4
            i=(y*w+x)*4
            px[i]=pal[c+2];px[i+1]=pal[c+1];px[i+2]=pal[c];px[i+3]=pal[c+3]
    return Image.frombytes('RGBA',(w,h),bytes(px))
