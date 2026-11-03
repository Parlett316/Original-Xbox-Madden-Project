"""Add the Madden 2005, 06, 07 and 08 soundtracks to Madden NFL 09 (Xbox).

Usage: python music_import.py <09 BGM.dat> <09 strmdata.db> <out dir> [games dir]

<out dir> gets BGM.dat and strmdata.db. The strmdata.db given can be stock or
already patched (e.g. by progression_2005.py); only the music tables change.
Source games are read from [games dir] (default: the folder above this
script), as "Madden NFL 2005 (USA)", "Madden NFL 06 (USA)" and so on.
After this, update data/fe.qkl with qkl_sync.py: it preloads BGM.dat's
directory, and without the update the new tracks stay silent.

How 09 plays music:
  data/BGM.dat     TERF archive, one EA SCHl stream per song (22,050 Hz
                   stereo, same codec in 2005-09), 0x800-aligned in DATA.
  strmdata.db MUST soundtracks (MSTI id, MSTN name); 09 has one.
              MUSO songs: MSTI soundtrack, MSOI song number within it (the
                   EA Trax list order, alphabetical by artist), MSOR the
                   BGM.dat entry, plus album/song/artist text.
  The EA Trax playlist (MUPL, 40 slots, in template.dat) is left as is; the
  new songs start switched off and can be switched on in EA Trax.
Each older game becomes its own soundtrack. The NFL Films instrumentals
(Sam Spence, Tom Hedden, Dave Robidoux) are skipped; 09 already has them.
2005's stream headers lack the platform tag and use 0x04 for tag 0x8C; they
are rewritten to the 06-09 form (the data blocks are already identical).
"""
import glob
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'roster'))
import tdb  # noqa: E402
from headshots import terf_entries  # noqa: E402

SOURCES = (  # (soundtrack name, game folder)
    ('Madden NFL 2005 Soundtrack', 'Madden NFL 2005 (USA)'),
    ('Madden NFL 06 Soundtrack', 'Madden NFL 06 (USA)'),
    ('Madden NFL 07 Soundtrack', 'Madden NFL 07 (USA)'),
    ('Madden NFL 08 Soundtrack', 'Madden NFL 08 (USA)'),
)
NFL_FILMS = {'sam spence', 'tom hedden', 'dave robidoux'}
ALIGN = 0x800


GAMES = os.path.join(HERE, '..')


def find(folder, *names):
    for name in names:
        hits = [p for p in glob.glob(os.path.join(GAMES, folder, '*', '*'))
                if os.path.basename(p).lower() == name.lower()]
        if hits:
            return hits[0]
    raise SystemExit(f'{folder}: none of {names} found')


def find_db(buf, table):
    i = buf.find(b'DB\x00\x08')
    while i != -1:
        try:
            db = tdb.DB(buf, i)
            if table in db.tables:
                return db
        except Exception:
            pass
        i = buf.find(b'DB\x00\x08', i + 4)
    raise SystemExit(f'no {table} table')


def normalize(stream):
    """Give a 2005-style SCHl header the 06-09 form; others pass through."""
    length = struct.unpack_from('<I', stream, 4)[0]
    head = bytearray(stream[8:length])
    if head[:7] != bytes.fromhex('50540700060165'):
        raise ValueError('unexpected SCHl header')
    if head[7] != 0x0B:
        head[7:7] = bytes.fromhex('0b0102')          # platform: Xbox
    i = head.find(bytes.fromhex('8c01'))
    if i >= 0 and head[i + 2] == 0x04:
        head[i + 2] = 0x24
    while head[-1] == 0:                              # drop padding after the 0xFF end tag
        head.pop()
    head += bytes(-(len(head) + 8) % 4)               # re-pad to a multiple of 4
    new_len = 8 + len(head)
    return b'SCHl' + struct.pack('<I', new_len) + bytes(head) + stream[length:]


def build_bgm(base, extra):
    """TERF with base entries followed by extra streams."""
    data_at, entries = terf_entries(base)
    streams = [base[data_at + o:data_at + o + s] for o, s in entries] + extra
    assert 8 + 8 * len(streams) <= 0x800, 'too many entries for DIR1'
    hdr = bytearray(base[:0x800])
    struct.pack_into('<H', hdr, 14, len(streams))
    dir1 = bytearray(b'DIR1' + struct.pack('<I', 0x800) + bytes(0x800 - 8))
    data = bytearray()
    pos = ALIGN                                       # offsets are from DATA start
    for k, s in enumerate(streams):
        struct.pack_into('<II', dir1, 8 + 8 * k, pos, len(s))
        data += s + bytes(-len(s) % ALIGN)
        pos += len(s) + (-len(s) % ALIGN)
    chunk = bytearray(b'DATA' + struct.pack('<I', ALIGN + len(data)) + bytes(ALIGN - 8)) + data
    return hdr + dir1 + chunk


def main(bgm09, strm09, out, games=None):
    global GAMES
    if games:
        GAMES = games
    base = open(bgm09, 'rb').read()
    sbuf = bytearray(open(strm09, 'rb').read())
    db = find_db(sbuf, 'MUSO')
    _, base_entries = terf_entries(base)
    next_entry = len(base_entries)
    next_type = max(r['MSTI'] for r in db['MUST'].rows()) + 1

    new_types, new_songs, streams = [], [], []
    for name, folder in SOURCES:
        bgm = open(find(folder, 'BGM.dat'), 'rb').read()
        data_at, entries = terf_entries(bgm)
        sb = bytearray(open(find(folder, 'strmdata.db', 'STREAMEDDATA.DB'), 'rb').read())
        songs = [r for r in find_db(sb, 'MUSO')['MUSO'].rows()
                 if r['MARN'].strip().lower() not in NFL_FILMS]
        songs.sort(key=lambda r: r['MARN'].strip().lower())
        for k, r in enumerate(songs):
            o, s = entries[r['MSOR']]
            streams.append(normalize(bgm[data_at + o:data_at + o + s]))
            new_songs.append(dict(MSTI=next_type, MSOI=k, MSOR=next_entry, MALN=r['MALN'],
                                  MSON=r['MSON'], MARN=r['MARN']))
            next_entry += 1
        new_types.append(dict(MSTI=next_type, MSTN=name))
        print(f'{name}: {len(songs)} songs')
        next_type += 1

    # strmdata.db: grow MUST and MUSO and append the rows
    grown = db.resized({'MUST': db['MUST'].count + len(new_types),
                        'MUSO': db['MUSO'].count + len(new_songs)})
    sbuf = bytearray(sbuf[:db.off]) + grown + sbuf[db.off + db.size:]
    db = tdb.DB(sbuf, db.off)
    for table, rows in (('MUST', new_types), ('MUSO', new_songs)):
        T = db[table]
        start = T.count
        T.count = start + len(rows)
        for k, row in enumerate(rows):
            for f, v in row.items():
                T.set(start + k, f, v)
    db.fix()
    assert db.verify()

    os.makedirs(out, exist_ok=True)
    open(os.path.join(out, 'strmdata.db'), 'wb').write(sbuf)
    open(os.path.join(out, 'BGM.dat'), 'wb').write(build_bgm(base, streams))
    print(f'wrote {out}: {len(new_songs)} songs added, {next_entry} BGM entries')


if __name__ == '__main__':
    if len(sys.argv) not in (4, 5):
        sys.exit(__doc__)
    main(*sys.argv[1:5])
