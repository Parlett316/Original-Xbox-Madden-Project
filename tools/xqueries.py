"""List an XBE's DB query strings that mention a tag, with the code addresses that use them.

Usage: python xqueries.py <default.xbe> <tag as stored, e.g. SRts for table stRS> [<tag> ...]
"""
import os
import re
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'patches', 'loadscreen'))
from xbe import XBE  # noqa: E402

if __name__ == '__main__':
    x = XBE(sys.argv[1])
    tags = [t.encode() for t in sys.argv[2:]]
    for m in re.finditer(rb'[\x09\x0a\x20-\x7e\x80-\x8c]{12,}', x.d):
        s = m.group()
        if not any(b"'" + t + b"'" in s for t in tags):
            continue
        va = x.f2v(m.start())
        if not va:
            continue
        pat, refs, i = struct.pack('<I', va), [], -1
        while (i := x.d.find(pat, i + 1)) >= 0:
            if x.f2v(i):
                refs.append('%x' % x.f2v(i))
        text = re.sub(rb'[\x80-\x8c]', b'?', s).decode('latin1').replace('\n', ' ')
        print(f'{va:x} [{" ".join(refs)}] {text}')
