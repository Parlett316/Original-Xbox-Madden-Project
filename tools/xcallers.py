"""List the direct call and jmp sites to an address in an XBE (functions needn't be aligned).

Usage: python xcallers.py <default.xbe> <VA> [<VA> ...]
"""
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'patches', 'loadscreen'))
from xbe import XBE  # noqa: E402


def callers(x, va):
    out = []
    for nm, v, vs, ra, rs in x.secs:
        for op in (b'\xe8', b'\xe9'):
            i = ra - 1
            while (i := x.d.find(op, i + 1, ra + rs - 4)) >= 0:
                if (v + i - ra + 5 + struct.unpack_from('<i', x.d, i + 1)[0]) & 0xffffffff == va:
                    out.append(v + i - ra)
    return sorted(out)


if __name__ == '__main__':
    x = XBE(sys.argv[1])
    for a in sys.argv[2:]:
        c = callers(x, int(a, 16))
        print(a, len(c), ' '.join('%x' % v for v in c))
