"""Show play assignment scripts (PSAL steps) from unpacked Madden 09 playbook TDBs.

Usage: python play_scripts.py <file.bin> <set number> [more set numbers]
       python play_scripts.py <file.bin> --codes
       python play_scripts.py <file.bin> --codes-in <folder of .bin files>

Each player in a play has a PLYS row linking PLYL + poso to a PSAL script, whose
rows (code, val1, val2, val3) run in `step` order.
"""
import collections
import glob
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'roster'))
import tdb  # noqa: E402


def load(path):
    buf = bytearray(open(path, 'rb').read())
    return tdb.DB(buf, 0) if buf[:4] == b'DB\x00\x08' else None


def scripts(db):
    out = collections.defaultdict(list)
    for r in db['PSAL'].rows():
        out[r['PSAL']].append((r['step'], r['code'], r['val1'], r['val2'], r['val3']))
    return {k: [s[1:] for s in sorted(v)] for k, v in out.items()}


def show_sets(db, sets):
    sc = scripts(db)
    for play in db['PLYL'].rows():
        if play['SETL'] not in sets:
            continue
        print(f"{play['name']} (PLYL {play['PLYL']}, SETL {play['SETL']}, PLYT {play['PLYT']})")
        for r in sorted((r for r in db['PLYS'].rows() if r['PLYL'] == play['PLYL']), key=lambda r: r['poso']):
            print(f"  poso {r['poso']:2} PSAL {r['PSAL']:5} ARTL {r['ARTL']:5} {sc.get(r['PSAL'])}")


def codes(paths):
    seen = collections.defaultdict(collections.Counter)
    plays = collections.defaultdict(collections.Counter)
    for path in paths:
        db = load(path)
        if db is None or 'PSAL' not in db.tables or 'PLYL' not in db.tables or 'PLYS' not in db.tables:
            continue
        sc = scripts(db)
        name = {r['PLYL']: r['name'] for r in db['PLYL'].rows()}
        for r in db['PLYS'].rows():
            for code, a, b, c in sc.get(r['PSAL'], []):
                seen[code][(a, b, c)] += 1
                plays[code][name.get(r['PLYL'], '?')] += 1
    for code in sorted(seen):
        print(f"code {code}: {sum(seen[code].values())} uses, {len(seen[code])} value sets,",
              f"e.g. {[k for k, _ in seen[code].most_common(4)]}; plays {[k for k, _ in plays[code].most_common(3)]}")


if __name__ == '__main__':
    if sys.argv[2] == '--codes':
        codes([sys.argv[1]])
    elif sys.argv[2] == '--codes-in':
        codes(sorted(glob.glob(os.path.join(sys.argv[3], '*.bin'))))
    else:
        show_sets(load(sys.argv[1]), {int(a) for a in sys.argv[2:]})
