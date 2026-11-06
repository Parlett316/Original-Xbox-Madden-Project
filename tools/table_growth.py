"""Show how close a franchise's database tables are to their capacity, across saves.

Usage: python table_growth.py <save> [<save> ...] [--all]

A save is a Fran- file, or any folder holding one. Saves are listed in the order given,
so give them oldest first. Prints a row for each table whose count changes between saves
(or every non-empty table with --all), with its capacity, then its count per save and the
room left in the last one. Tables are sorted by room left, tightest first.
"""
import argparse
import glob
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'roster'))
import tdb  # noqa: E402


def find_save(path):
    if os.path.isfile(path):
        return path
    hits = glob.glob(os.path.join(path, '**', 'Fran-*'), recursive=True)
    if not hits:
        raise SystemExit(f'no Fran- file under {path}')
    return hits[0]


def open_db(path):
    with open(path, 'rb') as f:
        b = bytearray(f.read())
    return tdb.DB(b, b.find(b'DB\x00\x08'))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('saves', nargs='+')
    ap.add_argument('--all', action='store_true')
    args = ap.parse_args()

    dbs = [open_db(find_save(s)) for s in args.saves]
    for name, db in zip(args.saves, dbs):
        seai = db['SEAI'].row(0)
        print(f"{os.path.basename(name.rstrip('/')):28} year {seai.get('SEYR', '?')} "
              f"stage {seai.get('SEWT', '?')} week {seai.get('SEWN', '?')}")
    print()

    names = list(dbs[0].tables)
    rows = []
    for n in names:
        tabs = [db[n] for db in dbs]
        counts = [t.count for t in tabs]
        if not args.all and len(set(counts)) == 1:
            continue
        if args.all and not any(counts):
            continue
        cap = tabs[-1].capacity
        rows.append((cap - counts[-1], n, cap, tabs[-1].reclen, counts))
    print(f"{'table':6}{'cap':>7}{'reclen':>7}  " + ''.join(f'{i + 1:>7}' for i in range(len(dbs))) + f"{'room':>7}")
    for room, n, cap, reclen, counts in sorted(rows):
        print(f'{n:6}{cap:7}{reclen:7}  ' + ''.join(f'{c:7}' for c in counts) + f'{room:7}')


if __name__ == '__main__':
    main()
