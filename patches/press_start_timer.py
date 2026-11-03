"""Change the Press START screen's attract-demo constant in uis_all.dat (Madden 09).

    python press_start_timer.py "<09>/data/uis_all.dat" out/uis_all.dat <value>

The Press START screen script is uis_all.dat sub-archive 0, entry 3 (LZH1).
Its constant table at +0x1a0 holds 75000, 5000, 2500, 4000, 500; 75000 is
the idle time in ms before the attract-mode demo starts (confirmed on hardware:
15000 started the demo after about 15 s). Leaving the demo hard-locks the
console, even on the stock game, so the build sets 86400000 (24 h). The entry is
recompressed in place (it must fit its old slot), so every other byte of the
archive is unchanged. Run qkl_sync.py afterwards.
"""
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'loadscreen'))
from lzh1emu import compress, decompress  # noqa: E402

SUB, ENTRY, OFF, STOCK = 0, 3, 0x1a0, 75000


def chunks(buf, at):
    p = at + struct.unpack_from('<I', buf, at + 4)[0]
    c = {}
    while True:
        tag = bytes(buf[p:p + 4])
        c[tag] = p
        if tag == b'DATA':
            return c
        p += struct.unpack_from('<I', buf, p + 4)[0]


def entry(buf, at, k):
    c = chunks(buf, at)
    o, s = struct.unpack_from('<II', buf, c[b'DIR1'] + 8 + 8 * k)
    return c, c[b'DATA'] + o, s


def main(src, dst, value):
    buf = bytearray(open(src, 'rb').read())
    _, sub, _ = entry(buf, 0, SUB)
    c, pos, size = entry(buf, sub, ENTRY)
    typ, ulen = struct.unpack_from('<II', buf, c[b'COMP'] + 8 + 8 * ENTRY)
    assert typ == 5
    n = struct.unpack_from('<H', buf, sub + 14)[0]
    nxt = entry(buf, sub, ENTRY + 1)[1] if ENTRY + 1 < n else c[b'DATA'] + struct.unpack_from('<I', buf, c[b'DATA'] + 4)[0]
    script = bytearray(decompress(bytes(buf[pos:pos + size]), ulen)[0])
    assert b'PRESS_START::ONINIT' in script
    old = struct.unpack_from('<I', script, OFF)[0]
    assert old == STOCK, f'unexpected constant {old}'
    struct.pack_into('<I', script, OFF, value)
    _, (_, used), _, out = compress(bytes(script))
    raw = out[:used]
    assert decompress(raw, ulen)[0] == bytes(script)
    assert pos + len(raw) <= nxt, f'recompressed entry {len(raw)} does not fit slot {nxt - pos}'
    buf[pos:nxt] = raw + bytes(nxt - pos - len(raw))
    struct.pack_into('<I', buf, c[b'DIR1'] + 8 + 8 * ENTRY + 4, len(raw))
    open(dst, 'wb').write(buf)
    print(f'{old} -> {value}; entry {size} -> {len(raw)} bytes (slot {nxt - pos})')


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], int(sys.argv[3], 0))
