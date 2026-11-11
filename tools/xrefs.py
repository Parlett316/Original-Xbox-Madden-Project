"""List where an XBE mentions an address (any 4-byte little-endian match), as virtual addresses.

Usage: python xrefs.py <default.xbe> <VA> [<VA> ...]
"""
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'patches', 'loadscreen'))
from xbe import XBE  # noqa: E402

if __name__ == '__main__':
    x = XBE(sys.argv[1])
    for a in sys.argv[2:]:
        pat, out, i = struct.pack('<I', int(a, 16)), [], -1
        while (i := x.d.find(pat, i + 1)) >= 0:
            v = x.f2v(i)
            if v:
                out.append(v)
        print(a, len(out), ' '.join('%x' % v for v in out[:60]))
