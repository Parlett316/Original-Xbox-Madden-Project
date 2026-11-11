"""Find the same function in another XBE: match its code with addresses and call targets masked.

Usage: python xmatch.py <from default.xbe> <to default.xbe> <VA> [<VA> ...] [--bytes N]

The first N bytes of code (default 96) become a pattern in which every call or jump displacement
and every 4-byte value that looks like an address (0x10000 to 0x900000) is a wildcard.
"""
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'patches', 'loadscreen'))
from xbe import XBE  # noqa: E402


def pattern(x, va, want):
    import capstone
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    o = x.v2f(va)
    out, n = b'', 0
    for ins in md.disasm(x.d[o:o + want + 32], va):
        b = bytes(ins.bytes)
        keep = bytearray(b'\x01' * len(b))
        if b[0] in (0xe8, 0xe9) and len(b) == 5:
            keep[1:] = b'\0\0\0\0'
        elif b[0] == 0x0f and 0x80 <= b[1] <= 0x8f and len(b) == 6:
            keep[2:] = b'\0\0\0\0'
        else:
            for i in range(1, len(b) - 3):
                if 0x10000 <= int.from_bytes(b[i:i + 4], 'little') < 0x900000:
                    keep[i:i + 4] = b'\0\0\0\0'
        out += b''.join(re.escape(b[i:i + 1]) if keep[i] else b'.' for i in range(len(b)))
        n += len(b)
        if n >= want:
            break
    return re.compile(out, re.S)


def find(a, b, va, want=96):
    nm, tva, _, raw, rsize = b.secs[0]
    return [tva + m.start() - raw for m in pattern(a, va, want).finditer(b.d, raw, raw + rsize)]


if __name__ == '__main__':
    args = sys.argv[1:]
    want = 96
    if '--bytes' in args:
        i = args.index('--bytes')
        want = int(args[i + 1], 0)
        del args[i:i + 2]
    a, b = XBE(args[0]), XBE(args[1])
    for v in args[2:]:
        print(v, '->', ' '.join('%x' % h for h in find(a, b, int(v, 16), want)) or 'no match')
