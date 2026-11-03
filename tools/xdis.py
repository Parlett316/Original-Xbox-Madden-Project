"""Disassemble a range of an Xbox XBE, annotating pointers to strings.

Usage: python xdis.py <default.xbe> <start VA> <end VA>
       python xdis.py <default.xbe> --find "<text>"     # string VA + code refs
       python xdis.py <default.xbe> --callers <VA>      # direct call sites

EA's DB queries are byte-reversed SQL-like strings ('YALP' = PLAY), so
searching for a table usually means searching for its reversed tag.
Needs capstone (pip install capstone).
"""
import os
import re
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'patches', 'loadscreen'))
from xbe import XBE  # noqa: E402

QUERY_MARKERS = (0x80, 0x81, 0x82, 0x83, 0x84, 0x85, 0x88, 0x8A, 0x8C, 10)


def string_at(x, va):
    o = x.v2f(va)
    if o is None or not 0 <= o < len(x.d):
        return None
    s = x.d[o:x.d.find(b'\0', o)]
    if 4 < len(s) < 300 and all(32 <= c < 127 or c in QUERY_MARKERS for c in s):
        return s.decode('latin1')[:100]
    return None


def disassemble(x, start, end):
    import capstone
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    o = x.v2f(start)
    for ins in md.disasm(x.d[o:o + (end - start)], start):
        note = ''
        for tok in re.findall(r'0x[0-9a-f]+', ins.op_str):
            s = string_at(x, int(tok, 16))
            if s:
                note = '  ; ' + repr(s)
        print(f'{ins.address:#x}  {ins.mnemonic} {ins.op_str}{note}')


def refs(x, va):
    pat, out, i = struct.pack('<I', va), [], x.d.find(struct.pack('<I', va))
    while i != -1:
        out.append(x.f2v(i))
        i = x.d.find(pat, i + 1)
    return [r for r in out if r]


def callers(x, target):
    d, out, o = x.d, [], 0
    while True:
        o = d.find(b'\xe8', o + 1)
        if o == -1:
            return out
        va = x.f2v(o)
        if va and va + 5 + struct.unpack_from('<i', d, o + 1)[0] == target:
            out.append(va)


def main(argv):
    x = XBE(argv[0])
    if argv[1] == '--find':
        for m in re.finditer(re.escape(argv[2].encode('latin1')), x.d):
            s = m.start()
            while s and x.d[s - 1] != 0:
                s -= 1
            va = x.f2v(s)
            print(f'{va:#x}  {string_at(x, va)!r}  refs: {[hex(r) for r in refs(x, va)]}')
    elif argv[1] == '--callers':
        print([hex(c) for c in callers(x, int(argv[2], 16))])
    else:
        disassemble(x, int(argv[1], 16), int(argv[2], 16))


if __name__ == '__main__':
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    main(sys.argv[1:])
