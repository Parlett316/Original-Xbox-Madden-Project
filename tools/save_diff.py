"""Show what changed between two Madden franchise saves, table by table.

Usage: python save_diff.py <old save> <new save> [--rows N] [--tables A,B,...]

Prints each table whose stored rows differ: the row counts, how many rows changed,
which fields changed in how many rows, and the first N changes of every table
(default 3). --tables limits the output to those tables. Tables with the same bytes
are only counted. Rows are compared by position, so a table that gains or loses a row
in the middle shows every row after it as changed.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'roster'))
import tdb  # noqa: E402


def open_db(path):
    with open(path, 'rb') as f:
        b = bytearray(f.read())
    return tdb.DB(b, b.find(b'DB\x00\x08'))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('old')
    ap.add_argument('new')
    ap.add_argument('--rows', type=int, default=3)
    ap.add_argument('--tables', default='')
    a = ap.parse_args()
    A, B = open_db(a.old), open_db(a.new)
    only = set(filter(None, a.tables.split(',')))
    print(f'db size {A.size} -> {B.size}')
    same = 0
    for t in A.order:
        if only and t.name not in only:
            continue
        u = B.tables.get(t.name)
        if u is None:
            print(f'{t.name}: missing from new')
            continue
        changed, fields, sample = 0, {}, []
        for i in range(min(t.count, u.count)):
            if t.raw(i) != u.raw(i):
                changed += 1
                x, y = t.row(i), u.row(i)
                diff = {k: (x[k], y[k]) for k in x if x[k] != y[k]}
                for k in diff:
                    fields[k] = fields.get(k, 0) + 1
                if len(sample) < a.rows:
                    sample.append((i, diff))
        if not changed and t.count == u.count:
            same += 1
            continue
        print(f'{t.name}: rows {t.count} -> {u.count} (cap {t.capacity}), {changed} changed; ' +
              ' '.join(f'{k}:{v}' for k, v in sorted(fields.items(), key=lambda kv: -kv[1])))
        for i, d in sample:
            print(f'    [{i}] ' + ' '.join(f'{k} {v[0]!r}->{v[1]!r}' for k, v in d.items()))
    print(f'{same} tables unchanged')


if __name__ == '__main__':
    main()
