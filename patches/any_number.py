"""Let the edit screen give any player any jersey number, 0-99 (default.xbe).

    python any_number.py <in default.xbe> <out default.xbe>

Two tables of (low, high) dword pairs, one pair per position (PPOS 0-20),
hold 09's number rules: the primary range at 0x61ee18 and a second at 0x61eec0
(a low of 0 means none). Stock: QB 1-19, HB/FB 20-49, WR 80-89 and 10-19,
TE 80-89, OL 60-79 (C 50-59 and 60-79), DL 60-79 and 90-99, LB 50-59 and
90-99, DB 20-49, K/P 1-19.

Only two functions read them:
- 0x39d510 builds the numbers offered (a 13-byte bit set), for the edit screen
  (0x14d337) and 0x29aae.
- 0x39d6c0 checks a number against a position. 0x3d5a2 keeps a player's number
  when it passes, otherwise 0x39d700 picks a new one.

This sets every primary range to 0-99 and leaves the second ranges, now inside
it. Rookies and signings still get traditional numbers: 0x39d700 picks from
ranges in its own code, not these tables. Loaded rosters were never limited
(PJEN is 7 bits) and #0 displays on the uniform.
"""
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'loadscreen'))
from xbe import XBE  # noqa: E402

PRIMARY = 0x61ee18
POSITIONS = 21
STOCK = ((1, 19), (20, 49), (20, 49), (80, 89), (80, 89), (60, 79), (60, 79), (50, 59),
         (60, 79), (60, 79), (60, 79), (60, 79), (60, 79), (50, 59), (50, 59), (50, 59),
         (20, 49), (20, 49), (20, 49), (1, 19), (1, 19))
ANY = (0, 99)


def patch(path_in):
    x = XBE(path_in)
    buf = bytearray(x.d)
    at = x.v2f(PRIMARY)
    now = tuple(struct.unpack_from('<ii', buf, at + 8 * i) for i in range(POSITIONS))
    if now == (ANY,) * POSITIONS:
        return buf
    assert now == STOCK, f'unexpected number table at {PRIMARY:#x}'
    for i in range(POSITIONS):
        struct.pack_into('<ii', buf, at + 8 * i, *ANY)
    return buf


def main(src, dst):
    buf = patch(src)
    assert len(buf) == os.path.getsize(src)
    with open(dst, 'wb') as f:
        f.write(buf)
    print(f'jersey numbers 0-99 for all {POSITIONS} positions')


if __name__ == '__main__':
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    main(*sys.argv[1:])
