"""Find lobby protocol code in an XBE: where a 4-letter tag is used, and which keys a function reads.

Usage: python xkeys.py <default.xbe> --tag room +rom gcre ...   # code addresses using each tag
       python xkeys.py <default.xbe> <start VA> [end VA]        # strings a function references

EA's protocol code compares and sends commands as big-endian dwords, so 'room' is stored as the
bytes 'moor' (cmp eax, 0x726f6f6d). --tag lists every place those bytes occur; the hits in
0x4dc000-0x4ec000 are the game's lobby screens (OSDK), 0x53d000-0x554000 DirtySDK's LobbyApi.

With a VA, the function is disassembled from there (to the first ret past 0x40 bytes, or to the
end VA) and every short printable string it pushes or loads is listed with the instruction's
address: for a reply parser these are the KEY names it reads ('IDENT', 'NAME', 'OPPO%d'...),
in order. Keys built with '%s%d' are indexed: VIEW0, VIEW1...
"""
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'patches', 'loadscreen'))
from xbe import XBE  # noqa: E402


def string_at(x, va):
    o = x.v2f(va)
    if o is None or not 0 <= o < len(x.d):
        return None
    b = x.d[o:x.d.find(b'\0', o)]
    return b.decode('latin1') if 0 < len(b) < 48 and all(32 <= c < 127 for c in b) else None


def tags(x, names):
    for name in names:
        hits = [x.f2v(m.start()) for m in re.finditer(re.escape(name[::-1].encode('latin1')), x.d)]
        print(f'{name}: ' + ' '.join(hex(h) for h in hits if h))


def keys(x, start, end=None):
    import capstone
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    o = x.v2f(start)
    for ins in md.disasm(x.d[o:o + ((end or start + 0x2000) - start)], start):
        for tok in re.findall(r'0x[0-9a-f]{6}', ins.op_str):
            s = string_at(x, int(tok, 16))
            if s:
                print(f'{ins.address:#x}  {s}')
        if end is None and ins.mnemonic == 'ret' and ins.address > start + 0x40:
            break


def main(argv):
    if len(argv) < 2:
        raise SystemExit(__doc__)
    x = XBE(argv[0])
    if argv[1] == '--tag':
        tags(x, argv[2:])
    else:
        keys(x, int(argv[1], 16), int(argv[2], 16) if len(argv) > 2 else None)


if __name__ == '__main__':
    main(sys.argv[1:])
