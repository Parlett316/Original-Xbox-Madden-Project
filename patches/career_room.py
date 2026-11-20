"""More room in a Madden 09 franchise's career stat tables, so long franchises keep career totals.

    python career_room.py <in template.dat> <out template.dat>
    python career_room.py <in Fran-FranN>   <out Fran-FranN>    # test only; needs --save-unlock

A franchise's career tables have fixed capacities, and once one is full a player who
needs a new row gets none. In xemu, PCDE (career defense) was full by year 5 and 26 to
112 players a year had season rows with no career row (docs/findings.md section 11).
Real stats (roster/player_stats.py) preload 821 PCDE rows, so it fills sooner.

template.dat: the franchise DB (entry 4) gets the capacities in ROOM, which a new
franchise and its saves inherit. The franchise DB stores these tables' current rows
only, so template.dat barely grows; a save stores each table at full capacity once it
has rows, so a save's DB grows by (new - old capacity) x record length: 17,000 bytes
for PCDE and 2,400 for PCNG. The save file stays 1,490,944 bytes; the in-season saves
seen have 103,000 to 184,000 spare bytes after the DB.

A save: the same tables grow inside it, the file keeps its size and name, and the
data signature moves to just after the DB (it can't be recomputed, so the XBE needs
the save unlock). Only for testing a franchise that has already filled a table.
"""
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'roster'))
sys.path.insert(0, HERE)
import tdb  # noqa: E402
from season17 import FRANCHISE, entry_db, repack  # noqa: E402

ROOM = {'PCDE': 2400, 'PCNG': 2400}     # stock 1,550 and 2,100
SAVE_DB = 0x29                          # a franchise save's DB offset
SIG = 20


def grow(db):
    caps = {n: c for n, c in ROOM.items() if c > db[n].capacity}
    out = tdb.DB(db.resized(caps), 0)
    assert out.verify()
    for n in ROOM:
        assert out[n].rows() == db[n].rows(), n
    return out.buf


def save(buf):
    assert buf[SAVE_DB:SAVE_DB + 4] == b'DB\x00\x08', 'not a franchise save'
    db = tdb.DB(buf, SAVE_DB)
    end = SAVE_DB + db.size
    body = grow(db)
    out = bytearray(buf)
    new_end = SAVE_DB + len(body)
    assert new_end + SIG <= len(buf) - SIG, 'the grown DB does not fit the save'
    out[SAVE_DB:new_end] = body
    out[new_end:new_end + SIG] = buf[end:end + SIG]           # the data signature
    out[new_end + SIG:len(buf) - SIG] = bytes(len(buf) - SIG - new_end - SIG)
    print(f'save DB {db.size:,} -> {len(body):,} bytes, '
          f'{len(buf) - SIG - new_end - SIG:,} spare')
    return out


def main(src, dst):
    buf = bytearray(open(src, 'rb').read())
    if buf[SAVE_DB:SAVE_DB + 4] == b'DB\x00\x08':
        out = save(buf)
    else:
        out = repack(buf, {FRANCHISE: grow(entry_db(buf, FRANCHISE))})
    open(dst, 'wb').write(out)
    print(f'{os.path.basename(dst)}: {len(buf):,} -> {len(out):,} bytes')


if __name__ == '__main__':
    main(*sys.argv[1:])
