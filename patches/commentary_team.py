"""Make Al Michaels call a renamed team by its city: the Commanders become "Washington".

Usage: python commentary_team.py <stock data dir> <out dir> [--check] [--clip city|surname]

A team's nickname (TEAM.TDNA) is looked up in name tables in SOUNDDAT.dat. Each table gives a
sub-bank number, and a name it doesn't list falls back to "the home team" or "the visiting team".
There's no "Commanders" recording, so this gives the name a slot of its own and puts Al's existing
"Washington" audio in that slot. Teams still named Redskins, and the classic teams, keep their
slot and their line. Table 4 isn't a team name but a "Welcome to <sponsor> Stadium" line, so there
the name joins the Redskins' row and behaves as stock Washington does. Real stadium names such as
FedEx Field come from table 17, which isn't changed. Details: docs/findings.md section 10.

The slot comes from a team that never appears, the NFL Europe Galaxy. Every entry keeps its directory
size (docs/formats.md), so the audio is padded with zeros and the name tables stay the same length.

--check rebuilds the name tables with no changes, compares them with stock, and writes nothing.
--clip picks the recording: his player surname "Washington" (default) or his quieter city name.
Copy SOUNDDAT.dat and SPCHDATA.dat with fe.qkl and game.qkl, re-synced by qkl_sync.py.
"""
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'roster'))
from headshots import terf_entries  # noqa: E402

NICKNAME = 'COMMANDERS'    # upper case, as the game compares it
DONOR = 'GALAXY'

# SOUNDDAT.dat name tables: entry -> (the name's sub-bank, a row with no team to make room).
# 7 is the team name, in the donor's slot. 4 is "Welcome to <sponsor> Stadium", 32 being the Redskins' row.
TABLES = {7: (34, 'NFL-E ALUMNI'), 4: (32, 'MILLENIUM')}

# Al's "Washington" recordings in SPCHDATA.dat: (descriptor entry, audio entry, bank, sub-bank, total,
# take name -> 256-byte offsets, and the takes each slot below uses, in its descriptor's row order).
CLIPS = {
    # City name. Quieter than his nicknames on the console.
    'city': (0x2a56 + 30, 0x1185 + 30, 0x1f0, 31, 0x79,
             {'first': (0x00, 0x17), 'second': (0x17, 0x2b), 'general': (0x47, 0x79)},
             [('first', 'second', 'general'), ('second',)]),
    # Player surname. Sentences use takes 0 and 2 mid-sentence and take 1 only at the end. Take 2 is
    # the loudest, so it fills both of the mid-sentence rows.
    'surname': (0x1e37 + 1351, 0x566 + 1351, 0x00a, 1351, 0x41,
                {'end': (19, 45), 'mid2': (45, 65)},
                [('mid2', 'mid2', 'end'), ('mid2',)]),
}

# Slots that change: (descriptor entry, audio entry)
SLOTS = [
    (0x29cb + 33, 0x10fa + 33),    # bank 0x08d, sub-bank 34: main nickname
    (0x2a24 + 33, 0x1153 + 33),    # bank 0x7f1, sub-bank 34: second nickname
]


def read_table(blob):
    """Rows of a name table: u32 count, (u32 string offset, s32 value) each, then the strings."""
    count = struct.unpack_from('<I', blob, 0)[0]
    rows = []
    for i in range(count):
        offset, value = struct.unpack_from('<Ii', blob, 4 + 8 * i)
        rows.append((bytes(blob[offset:blob.index(b'\0', offset)]), value))
    return rows


def write_table(rows, size):
    """Rebuild a table with its strings in row order, padded with zeros to its directory size."""
    pool_at = 4 + 8 * len(rows)
    head, pool = [struct.pack('<I', len(rows))], bytearray()
    for name, value in rows:
        head.append(struct.pack('<Ii', pool_at + len(pool), value))
        pool += name + b'\0'
    out = b''.join(head) + bytes(pool)
    assert len(out) <= size, f'name table needs {len(out)} bytes, has {size}'
    return out.ljust(size, b'\0')


def patched_table(rows, value, spare):
    """Replace the donor's row with the new name and drop a spare row, keeping the table sorted."""
    donor_value = dict(rows)[DONOR.encode()]
    assert value != donor_value or [n for n, v in rows if v == value] == [DONOR.encode()], 'the donor slot is shared'
    assert spare.encode() in [n for n, _ in rows], f'{spare} is missing'
    assert NICKNAME.encode() not in [n for n, _ in rows], f'{NICKNAME} is already listed'
    drop = {DONOR.encode(), spare.encode()}
    return sorted([r for r in rows if r[0] not in drop] + [(NICKNAME.encode(), value)], key=lambda r: r[0])


def entry(buf, data_at, entries, i):
    offset, size = entries[i]
    return data_at + offset, size


def descriptor_rows(blob):
    """Sub-bank descriptor: u16 bank, u16 sub-bank, u8 type, u8 samples, u16, u32 total, then
    samples of big-endian u16 offset (256-byte units) and `type` parameter bytes."""
    kind, count = blob[4], blob[5]
    return count, [12 + (2 + kind) * k for k in range(count)]


def patch_speech(spch, clip):
    source_desc, source_audio, bank, sub, total, spans, uses = CLIPS[clip]
    data_at, entries = terf_entries(spch)
    at, size = entry(spch, data_at, entries, source_desc)
    assert struct.unpack_from('<HH', spch, at) == (bank, sub), 'unexpected source descriptor'
    assert struct.unpack_from('<I', spch, at + 8)[0] == total, 'unexpected source audio size'
    source_at, _ = entry(spch, data_at, entries, source_audio)
    takes = {k: bytes(spch[source_at + a * 256:source_at + b * 256]) for k, (a, b) in spans.items()}

    for (desc_i, audio_i), names in zip(SLOTS, uses):
        desc_at, _ = entry(spch, data_at, entries, desc_i)
        count, row_at = descriptor_rows(spch[desc_at:desc_at + 64])
        assert count == len(names), f'descriptor {desc_i:#x} has {count} samples'

        audio = bytearray()
        for name, row in zip(names, row_at):
            struct.pack_into('>H', spch, desc_at + row, len(audio) // 256)
            audio += takes[name]
        struct.pack_into('<I', spch, desc_at + 8, len(audio) // 256)

        audio_at, audio_size = entry(spch, data_at, entries, audio_i)
        assert len(audio) <= audio_size, f'audio entry {audio_i:#x}: {len(audio)} > {audio_size}'
        spch[audio_at:audio_at + audio_size] = bytes(audio).ljust(audio_size, b'\0')
        print(f'  speech slot {desc_i:#x}/{audio_i:#x}: {len(audio)} of {audio_size} bytes')


def main(stock, out, check=False, clip='surname'):
    def stock_file(name):
        match = [f for f in os.listdir(stock) if f.lower() == name.lower()]
        return os.path.join(stock, match[0])

    sound = bytearray(open(stock_file('SOUNDDAT.dat'), 'rb').read())
    data_at, entries = terf_entries(sound)
    for table, (value, spare) in TABLES.items():
        at, size = entry(sound, data_at, entries, table)
        blob = bytes(sound[at:at + size])
        rows = read_table(blob)
        assert [r[0] for r in rows] == sorted(r[0] for r in rows), f'table {table} is not sorted'
        assert write_table(rows, size) == blob, f'table {table}: rebuild differs from stock'
        print(f'  table {table}: {len(rows)} rows rebuild byte for byte')
        if not check:
            sound[at:at + size] = write_table(patched_table(rows, value, spare), size)
    if check:
        return

    os.makedirs(out, exist_ok=True)
    open(os.path.join(out, 'SOUNDDAT.dat'), 'wb').write(sound)
    del sound

    speech = bytearray(open(stock_file('SPCHDATA.dat'), 'rb').read())
    patch_speech(speech, clip)
    open(os.path.join(out, 'SPCHDATA.dat'), 'wb').write(speech)
    print(f'wrote SOUNDDAT.dat and SPCHDATA.dat to {out}')


if __name__ == '__main__':
    args = sys.argv[1:]
    clip = 'surname'
    if '--clip' in args:
        i = args.index('--clip')
        clip = args[i + 1]
        del args[i:i + 2]
        if clip not in CLIPS:
            sys.exit(__doc__)
    check = '--check' in args
    args = [a for a in args if a != '--check']
    if len(args) != 2:
        sys.exit(__doc__)
    main(args[0], args[1], check, clip)
