import struct,sys
def parse(p):
    d=open(p,'rb').read()
    hs=struct.unpack_from('<I',d,4)[0]; n=struct.unpack_from('<H',d,14)[0]
    pos=hs; chunks={}
    while pos<len(d):
        tag=d[pos:pos+4]; sz=struct.unpack_from('<I',d,pos+4)[0]
        chunks[tag]=(pos,sz)
        if tag==b'DATA': break
        pos+=sz
    dp=chunks[b'DIR1'][0]
    ents=[struct.unpack_from('<II',d,dp+8+8*i) for i in range(n)]
    comp=None
    if b'COMP' in chunks:
        cp=chunks[b'COMP'][0]; comp=[struct.unpack_from('<II',d,cp+8+8*i) for i in range(n)]
    return d,chunks,ents,comp
if __name__=='__main__':
    d,ch,ents,comp=parse(sys.argv[1])
    print({k:v for k,v in ch.items()})
    for i,(o,s) in enumerate(ents):
        print(i,hex(o),hex(s),comp[i] if comp else '',d[o:o+16].hex())
