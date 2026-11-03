import struct
from unicorn import *
from unicorn.x86_const import *
from xbe import XBE
import os
# the game's own LZH1 code runs from the stock 09 XBE; set MADDEN09_XBE to point at it
X=XBE(os.environ.get('MADDEN09_XBE') or os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','..','Madden NFL 09 (USA)','default.xbe'))
HEAP=0x10000000; STACK=0x0f000000; RET=0x0e000000
def mkemu():
    mu=Uc(UC_ARCH_X86,UC_MODE_32)
    mu.mem_map(0x10000,0x1000000-0x10000)
    for nm,va,vs,ra,rs in X.secs: mu.mem_write(va,X.d[ra:ra+rs])
    mu.mem_map(STACK,0x100000); mu.mem_map(RET,0x1000); mu.mem_map(HEAP,0x4000000)
    mu.heap=HEAP
    def alloc(n):
        p=mu.heap; mu.heap+=(n+15)&~15; return p
    mu.alloc=alloc
    stubs={}
    def ret(v=0):
        esp=mu.reg_read(UC_X86_REG_ESP); ra=struct.unpack('<I',mu.mem_read(esp,4))[0]
        mu.reg_write(UC_X86_REG_EAX,v); mu.reg_write(UC_X86_REG_ESP,esp+4); mu.reg_write(UC_X86_REG_EIP,ra)
    def arg(i):
        esp=mu.reg_read(UC_X86_REG_ESP); return struct.unpack('<I',mu.mem_read(esp+4+4*i,4))[0]
    stubs[0x371ba0]=lambda: ret(alloc(arg(1)))
    stubs[0x360060]=lambda: ret(0)
    stubs[0x360450]=lambda: ret(0)
    stubs[0x360000]=lambda: ret(0)
    stubs[0x360070]=lambda: ret(0)
    stubs[0x371de0]=lambda: ret(0)
    def hook(mu,addr,size,u):
        if addr in stubs: stubs[addr]()
        elif addr==RET: mu.emu_stop()
    for a in stubs: mu.hook_add(UC_HOOK_CODE,hook,begin=a,end=a)
    mu.hook_add(UC_HOOK_CODE,hook,begin=RET,end=RET)
    return mu
def call(mu,fn,*args):
    esp=STACK+0xff000
    for a in reversed(args): esp-=4; mu.mem_write(esp,struct.pack('<I',a))
    esp-=4; mu.mem_write(esp,struct.pack('<I',RET))
    mu.reg_write(UC_X86_REG_ESP,esp)
    try: mu.emu_start(fn,RET)
    except UcError as e:
        esp=mu.reg_read(UC_X86_REG_ESP); raise Exception(hex(mu.reg_read(UC_X86_REG_EIP))+" ret="+hex(struct.unpack("<I",mu.mem_read(esp,4))[0])+" "+str(e))
    return mu.reg_read(UC_X86_REG_EAX)
def decompress(src,outlen):
    mu=mkemu()
    sp=mu.alloc(len(src)); mu.mem_write(sp,src)
    dp=mu.alloc(outlen+0x1000)
    s0=mu.alloc(0x20); s1=mu.alloc(0x20)
    mu.mem_write(s0,struct.pack('<III',sp,len(src),0)+b'\0'*12+b'\1'+b'\0'*7)
    mu.mem_write(s1,struct.pack('<III',dp,outlen,0)+b'\0'*20)
    call(mu,0x5330a0)
    ctx=call(mu,0x5354b0,s0,s1)
    r=call(mu,0x533ca0,s0,s1,ctx)
    used=struct.unpack('<III',mu.mem_read(s1,12))
    return bytes(mu.mem_read(dp,outlen)),r,used
def compress(src):
    mu=mkemu()
    sp=mu.alloc(len(src)); mu.mem_write(sp,src)
    cap=len(src)*2+0x10000
    dp=mu.alloc(cap)
    s0=mu.alloc(0x20); s1=mu.alloc(0x20)
    mu.mem_write(s0,struct.pack('<III',sp,len(src),0)+b'\0'*12+b'\1'+b'\0'*7)
    mu.mem_write(s1,struct.pack('<III',dp,cap,0)+b'\0'*20)
    call(mu,0x5330a0)
    ctx=call(mu,0x535a50,s0,s1)
    r=call(mu,0x533ca0,s0,s1,ctx)
    p,size,pos=struct.unpack('<III',mu.mem_read(s1,12))
    call(mu,0x533150,s0,s1,ctx)
    p2,size2,pos2=struct.unpack('<III',mu.mem_read(s1,12))
    return r,(size,pos),(size2,pos2),bytes(mu.mem_read(dp,cap))
