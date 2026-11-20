"""Check a roster or save's overalls against Madden 09's own formula.

Usage: python overall.py <template.dat or franchise/roster save> [--list N]

The formula is in roster/game_overall.py (docs/findings.md §13); its weights are
read from the stock template.dat. Prints how many PLAY rows match POVR and the
largest differences.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'roster'))
import game_overall  # noqa: E402
import tdb  # noqa: E402

STOCK = os.path.join(HERE, '..', 'Madden NFL 09 (USA)', 'data', 'template.dat')


def dbs(buf):
    i = -1
    while (i := buf.find(b'DB\x00\x08', i + 1)) >= 0:
        try:
            yield tdb.DB(buf, i)
        except Exception:
            continue


def porc_table(path=STOCK):
    buf = bytearray(open(path, 'rb').read())
    for db in dbs(buf):
        if 'PORC' in db.tables:
            return game_overall.weights(db['PORC'])
    raise SystemExit(f'no PORC table in {path}')


def overall(porc, pos, ratings):
    return game_overall.overall(porc, pos, ratings)


def main():
    porc = porc_table()
    buf = bytearray(open(sys.argv[1], 'rb').read())
    n = same = 0
    diffs = []
    for db in dbs(buf):
        if 'PLAY' not in db.tables or db['PLAY'].count == 0:
            continue
        for r in db['PLAY'].rows():
            if r['PPOS'] not in porc:
                continue
            n += 1
            c = overall(porc, r['PPOS'], r)
            if c == r['POVR']:
                same += 1
            else:
                diffs.append((r['POVR'] - c, r['PPOS'], r['PFNA'], r['PLNA'], r['POVR'], c))
    print(f'{same} of {n} PLAY rows match the formula')
    k = int(sys.argv[sys.argv.index('--list') + 1]) if '--list' in sys.argv else 15
    for d in sorted(diffs, key=lambda d: -abs(d[0]))[:k]:
        print(f'  pos {d[1]:2} {d[2]} {d[3]}: stored {d[4]}, formula {d[5]}')


if __name__ == '__main__':
    main()
