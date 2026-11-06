"""Let a Madden 09 team carry no fullback (template.dat and default.xbe; use both).

    python optional_fullback.py <in template.dat> <out template.dat>
    python optional_fullback.py <in default.xbe>  <out default.xbe>

The game refuses to leave a stage when a team is short at a position ("do not
meet the minimum requirements"). The minimums are in three tables of the stats
DB, which saves don't carry (docs/findings.md section 8): PPIR is the roster
minimum and PPIA the active one, counting healthy players.

            row                       PPIR, PPIA
    PLPS    fullback (PPOS 2)         1, 1 -> 0, 0
    DRPS    fullback (PDRP 2)         1, 1 -> 0, 0
    POSG    running backs (PPGR 1)    4, 2 -> 3, 1

The prompt follows DRPS. PLPS alone at 0 didn't remove it, and POSG wasn't
tested separately, so all three change together, as they did in the test that
worked. The file keeps its size, so this can run before or after season17.py.
The bundles don't preload these tables: on the 2026-11-05 build, qkl_sync.py
gave the same fe.qkl and game.qkl with and without this change.

default.xbe: a minimum of 0 alone hard locks the console (hardware and xemu).
When a team is over its roster limit, 0x396bd0 picks a position group to cut
from by each group's players x 100 / PPIR, so it divides by zero at 0x396d99.
That div now calls a cave that divides by 1 when PPIR is 0, the fullback's stock
minimum, so this ranking behaves as stock. Every other function that reads the
minimums was checked: the only other division, the fidiv at 0x397320 in
0x396f60, guards its divisor first.
"""
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'roster'))
import tdb  # noqa: E402
from headshots import terf_entries  # noqa: E402

# (table, key field, key value, stock (PPIR, PPIA), new (PPIR, PPIA))
CHANGES = (
    ('PLPS', 'PPOS', 2, (1, 1), (0, 0)),
    ('DRPS', 'PDRP', 2, (1, 1), (0, 0)),
    ('POSG', 'PPGR', 1, (4, 2), (3, 1)),
)


CAVE_VA = 0x10ee0                 # header page, after playoffs7.py's cave and before the awareness fix's
CAVE_END = 0x10f00
DIVIDE = 0x396d99
STOCK_DIVIDE = bytes.fromhex('f7b48c94000000')    # div dword ptr [esp+ecx*4+0x94]
CAVE = bytes.fromhex(
    '53'                          # push ebx
    '8b9c8c9c000000'              # mov ebx, [esp+ecx*4+0x9c]   (same slot: return address and ebx pushed)
    '85db'                        # test ebx, ebx
    '7501'                        # jnz +1
    '43'                          # inc ebx
    'f7f3'                        # div ebx                     (edx is already 0)
    '5b'                          # pop ebx
    'c3')                         # ret


def patch_xbe(buf):
    """Guard the division at DIVIDE in the XBE in bytearray `buf`, in place."""
    base = struct.unpack_from('<I', buf, 0x104)[0]
    headers = struct.unpack_from('<I', buf, 0x120)[0] - base
    for k in range(struct.unpack_from('<I', buf, 0x11c)[0]):
        _, va, vsize, raw, rsize = struct.unpack_from('<5I', buf, headers + k * 56)
        if va <= DIVIDE < va + vsize:
            site = DIVIDE - va + raw
            break
    else:
        raise SystemExit('no section holds the division')
    assert bytes(buf[site:site + 7]) == STOCK_DIVIDE, 'unexpected code at the division'
    o = CAVE_VA - base
    # loaded with the headers: the awareness fix extends the header size over these caves
    assert CAVE_VA + len(CAVE) <= CAVE_END <= base + struct.unpack_from('<I', buf, 0x108)[0], 'needs the awareness fix first'
    assert not any(buf[o:CAVE_END - base]), 'cave space in use'
    buf[o:o + len(CAVE)] = CAVE
    buf[site:site + 7] = bytes([0xe8]) + struct.pack('<i', CAVE_VA - (DIVIDE + 5)) + bytes([0x90, 0x90])
    print(f'division at {DIVIDE:#x} guarded, cave: {len(CAVE)} bytes at {CAVE_VA:#x}')


def patch(buf):
    """Apply CHANGES to the template.dat in bytearray `buf`, in place."""
    data_at, entries = terf_entries(buf)
    dbs = []
    for off, _ in entries:
        if buf[data_at + off:data_at + off + 4] == b'DB\x00\x08':
            db = tdb.DB(buf, data_at + off)
            if 'PLPS' in db.tables and db['PLPS'].count:
                dbs.append(db)
    assert len(dbs) == 1, f'expected one DB with position minimums, found {len(dbs)}'
    db = dbs[0]
    assert db.verify(), 'stats DB fails its checksums before the change'
    for name, key, value, old, new in CHANGES:
        t = db[name]
        rows = [i for i in range(t.count) if t.get(i, key) == value]
        assert len(rows) == 1, f'{name}: {len(rows)} rows with {key} {value}'
        i = rows[0]
        have = (t.get(i, 'PPIR'), t.get(i, 'PPIA'))
        assert have == old, f'{name} {key} {value}: expected {old}, found {have}'
        t.set(i, 'PPIR', new[0])
        t.set(i, 'PPIA', new[1])
        print(f'{name} {key} {value}: PPIR, PPIA {old} -> {new}')
    db.fix()
    assert db.verify(), 'stats DB fails its checksums after the change'


def main(src, dst):
    with open(src, 'rb') as f:
        buf = bytearray(f.read())
    size = len(buf)
    (patch_xbe if buf[:4] == b'XBEH' else patch)(buf)
    assert len(buf) == size
    with open(dst, 'wb') as f:
        f.write(buf)


if __name__ == '__main__':
    main(*sys.argv[1:])
