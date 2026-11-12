"""Make Madden 09 count its years from another year than 2008 (default.xbe).

    python year_base.py <in default.xbe> <out default.xbe> [year, default 2026]

The game stores a season as a number (0 is a franchise's first, -1 the season
before it) and adds 2008 wherever it shows or needs the real year: the stats on
a player's card ("%d Stats", and each row's year), "Acquired in %d", the
franchise's "Year %d", "%d Income", "%d Record", and the calendar that gives the
weeks their dates. Each is an `add reg, 2008`, a `lea reg, [reg + 2008]` or a
`push 2008`; one site adds 2007 (the season before). This changes those
constants, so a roster with real stats for 2021 to 2025 shows those years.

Left alone:
- Seven `cmp reg, 2008` (0xde976 and its inlined copies). They pick the season's
  opening Thursday: the first of September in 2008, the second in any other
  year (0xde5f0 works out the weekday). With a later base no year is 2008, so
  every season opens on the second Thursday, which is the NFL's rule.
- 0x547f81, `lea ecx, [ebx + 0x7d8]`: an offset into a structure, not a year.

Existing franchises change too: they store season numbers, not years.
"""
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'loadscreen'))
from xbe import XBE  # noqa: E402

STOCK = 2008
# VA of each 32-bit constant, and what stock holds there relative to 2008
SITES = {va: 0 for va in (
    0x2e99d, 0x1339f2, 0x133a03, 0x1360df, 0x1360ee, 0x14c9c4, 0x16f46e, 0x16f8b0, 0x16faae,
    0x179425, 0x179436, 0x179f86, 0x193ec4, 0x195cd0, 0x1964f6, 0x1980a9, 0x19f9e2, 0x23d43e,
    0x29b443, 0x29d3b2, 0x29df54, 0x29f7aa, 0x29f7f6, 0x2bc696, 0x395a15)}
SITES[0x29defb] = -1


def patch(path_in, year):
    x = XBE(path_in)
    buf = bytearray(x.d)
    for va, delta in SITES.items():
        at = x.v2f(va)
        old = struct.unpack_from('<I', buf, at)[0]
        assert old in (STOCK + delta, year + delta), f'unexpected value {old} at {va:#x}'
        struct.pack_into('<I', buf, at, year + delta)
    return buf


def main(src, dst, year=2026):
    buf = patch(src, int(year))
    assert len(buf) == os.path.getsize(src)
    with open(dst, 'wb') as f:
        f.write(buf)
    print(f'years count from {year} at {len(SITES)} sites')


if __name__ == '__main__':
    if len(sys.argv) not in (3, 4):
        raise SystemExit(__doc__)
    main(*sys.argv[1:])
