"""Find another XBE's address for a global: match the code around its uses, then read the operand there.

Usage: python xglobal.py <from default.xbe> <to default.xbe> <VA of the global> [<VA> ...]

For each use in game code, the enclosing function (found by its int3 padding) is disassembled up
to just past the use, addresses and call targets are masked as in xmatch.py, and the other XBE
is searched for the result. Each unique hit votes for the value found at the operand's place.
"""
import os
import re
import struct
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'patches', 'loadscreen'))
from xbe import XBE  # noqa: E402


def uses(x, va):
    nm, tva, _, raw, rsize = x.secs[0]
    pat, i = struct.pack('<I', va), raw - 1
    while (i := x.d.find(pat, i + 1, raw + rsize)) >= 0:
        yield tva + i - raw


def function_start(x, va):
    o = x.v2f(va) & ~15
    while o > 0x1000 and not (x.d[o - 1] == 0xcc and x.d[o] != 0xcc):
        o -= 16
    return x.f2v(o)


def lookup(a, b, va, tail=24, limit=400):
    import capstone
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    nm, tva, _, raw, rsize = b.secs[0]
    votes = Counter()
    for use in uses(a, va):
        start = function_start(a, use)
        if not start or use - start > limit:
            continue
        o = a.v2f(start)
        out, at, n = b'', None, 0
        for ins in md.disasm(a.d[o:o + (use - start) + tail + 16], start):
            code = bytes(ins.bytes)
            keep = bytearray(b'\x01' * len(code))
            if code[0] in (0xe8, 0xe9) and len(code) == 5:
                keep[1:] = b'\0\0\0\0'
            elif code[0] == 0x0f and 0x80 <= code[1] <= 0x8f and len(code) == 6:
                keep[2:] = b'\0\0\0\0'
            else:
                for i in range(1, len(code) - 3):
                    if 0x10000 <= int.from_bytes(code[i:i + 4], 'little') < 0x900000:
                        keep[i:i + 4] = b'\0\0\0\0'
            if ins.address <= use < ins.address + len(code):
                at = n + use - ins.address
            out += b''.join(re.escape(code[i:i + 1]) if keep[i] else b'.' for i in range(len(code)))
            n += len(code)
            if at is not None and n >= at + 4 + tail:
                break
        if at is None:
            continue
        hits = [m.start() for m in re.compile(out, re.S).finditer(b.d, raw, raw + rsize)]
        if len(hits) == 1:
            votes[struct.unpack_from('<I', b.d, hits[0] + at)[0]] += 1
    return votes


if __name__ == '__main__':
    a, b = XBE(sys.argv[1]), XBE(sys.argv[2])
    for v in sys.argv[3:]:
        votes = lookup(a, b, int(v, 16))
        print(v, '->', ', '.join(f'{k:x} ({n})' for k, n in votes.most_common(4)) or 'no match')
