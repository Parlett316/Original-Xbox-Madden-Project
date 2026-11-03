"""List every TDB found inside the given files: tables, row counts, fields.

    python db_survey.py <file> [<file> ...] [--rows N]

With --rows, also prints the first N rows of tables with at most 64 rows
(small tables are usually settings/tuning tables).
"""
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'roster'))
import tdb  # noqa: E402


def find_dbs(buf):
    pos = 0
    while True:
        pos = buf.find(b'DB\x00\x08', pos)
        if pos < 0:
            return
        try:
            size = struct.unpack_from('<I', buf, pos + 8)[0]
            n = struct.unpack_from('<I', buf, pos + 0x10)[0]
            if 0 < n < 512 and pos + size <= len(buf):
                yield tdb.DB(buf, pos)
                pos += size
                continue
        except Exception:
            pass
        pos += 4


def main():
    args = sys.argv[1:]
    rows = 0
    if '--rows' in args:
        i = args.index('--rows')
        rows = int(args[i + 1])
        del args[i:i + 2]
    for path in args:
        buf = bytearray(open(path, 'rb').read())
        for db in find_dbs(buf):
            print(f'== {os.path.basename(path)} @0x{db.off:x} ({len(db.order)} tables)')
            for t in db.order:
                names = ' '.join(sorted(t.fields))
                print(f'  {t.name} {t.count}/{t.capacity}: {names}')
                if rows and 0 < t.count <= 64:
                    for r in range(min(rows, t.count)):
                        print('     ', t.row(r))


if __name__ == '__main__':
    main()
