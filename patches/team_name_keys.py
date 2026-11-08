"""Point Madden 09's hardcoded team-name lookups at the Commanders (default.xbe).

    python team_name_keys.py <in default.xbe> <out default.xbe>

Some features find a team by its nickname with a query on TEAM.TDNA, using a
name stored in the XBE. The modern roster renames Washington's TDNA from
"Redskins" to "Commanders", so these lookups find no team (or a classic
Redskins team, which keeps the old name) and the game uses whatever the output
variables held: the minicamp showed another team in Washington's place.

The XBE holds "Redskins" four times, each one a lookup key:

- 0x6e5d10, the minicamp table at 0x6e5dc8 (stride 0x28: team, then its drills).
  0x1fed80 passes it to 0x1f18b0: select TGID, TTYP, TDRI from TEAM where TDNA = name.
- 0x6e3f24, the scenario "Redskins vs Raiders" (0x746d00) in the eight groups of
  four at 0x746e58. 0x1f0c50 looks up both teams: select TGID, TDRI from TEAM
  where TTYP = 0 and TDNA = name.
- 0x6ac330 and 0x6ac350, two entries of the city table at 0x6ac618 (stride 0x14:
  nickname, "City, ST", map position). 0x140d4b looks up TLNA by TTYP 0 and TDNA.

Each has 12 bytes before the next string, enough for "Commanders" and its
terminator; the rest is zero-filled. Only use this with a template.dat whose
modern Washington is named Commanders (roster/build_roster.py).
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'loadscreen'))
from xbe import XBE  # noqa: E402

SITES = (0x6ac330, 0x6ac350, 0x6e3f24, 0x6e5d10)
ROOM = 12
OLD = b'Redskins'
NEW = b'Commanders'


def patch(path_in):
    x = XBE(path_in)
    buf = bytearray(x.d)
    for va in SITES:
        at = x.v2f(va)
        if buf[at:at + ROOM] == NEW.ljust(ROOM, b'\0'):
            continue
        assert buf[at:at + ROOM] == OLD.ljust(ROOM, b'\0'), f'unexpected bytes at {va:#x}'
        buf[at:at + ROOM] = NEW.ljust(ROOM, b'\0')
    return buf


def main(src, dst):
    buf = patch(src)
    assert len(buf) == os.path.getsize(src)
    with open(dst, 'wb') as f:
        f.write(buf)
    print(f'team-name keys "Redskins" -> "Commanders" at {len(SITES)} sites')


if __name__ == '__main__':
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    main(*sys.argv[1:])
