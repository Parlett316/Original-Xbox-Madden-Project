import struct
class XBE:
    def __init__(s,p):
        d=s.d=open(p,'rb').read()
        s.base=struct.unpack_from('<I',d,0x104)[0]
        n=struct.unpack_from('<I',d,0x11c)[0]; sh=struct.unpack_from('<I',d,0x120)[0]-s.base
        s.secs=[]
        for i in range(n):
            fl,va,vs,ra,rs,na=struct.unpack_from('<6I',d,sh+56*i)
            nm=d[na-s.base:d.index(b'\0',na-s.base)].decode()
            s.secs.append((nm,va,vs,ra,rs))
    def f2v(s,o):
        for nm,va,vs,ra,rs in s.secs:
            if ra<=o<ra+rs: return va+o-ra
    def v2f(s,v):
        for nm,va,vs,ra,rs in s.secs:
            if va<=v<va+rs: return ra+v-va
    def dis(s,va,n=200):
        import capstone
        md=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_32)
        o=s.v2f(va)
        for ins in md.disasm(s.d[o:o+n],va): print(hex(ins.address),ins.mnemonic,ins.op_str)
