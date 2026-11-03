"""Compare Madden 09 franchise saves: rating spread and whether progression follows performance.

Usage: python franchise_report.py <start roster> <run name>=<season-1 save>,<season-2 save> [...]

  <start roster>  the roster the franchises were created from: a memory-card
                  roster save (Rost-Rost1) or data/template.dat
  each run        two Fran-FranN saves, taken after season 1 and season 2
                  (the user saves right after the Super Bowl, week 21)

Prints, per snapshot: awareness/overall averages and how many players are at
90+/95+/99; per run, season-2 changes by overall group (players matched by
PGID, which is stable within a franchise; the franchise renumbers players at
creation, so the start roster is only used for totals); and season-2 starters
(8+ starts) split into thirds by production at their position.

Save layout: 'Fran1' header + 20-byte signature, TDB at 0x29. Roster save:
TDB at 0x25. Season stats: PSNG (sgms = games started), PSOF, PSDE keyed by
PGID + SEYR (0 = first franchise season).
"""
import collections
import os
import statistics as st
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'roster'))
import tdb  # noqa: E402

GROUP = {0: 'QB', 1: 'RB', 3: 'WR', 4: 'TE', 10: 'DL', 11: 'DL', 12: 'DL',
         13: 'LB', 14: 'LB', 15: 'LB', 16: 'DB', 17: 'DB', 18: 'DB'}
BANDS = ((95, 99), (90, 94), (82, 89), (76, 81), (0, 75))


def open_db(path):
    b = bytearray(open(path, 'rb').read())
    return tdb.DB(b, b.find(b'DB\x00\x08'))


def players(db):
    return {r['PGID']: r for r in db['PLAY'].rows()}


def rostered(r):
    return r['TGID'] <= 32


def summary(P):
    a = [r for r in P.values() if rostered(r)]
    aw, ov = [r['PAWR'] for r in a], [r['POVR'] for r in a]
    return (f'AWR mean {st.mean(aw):5.1f} | AWR 90+ {sum(x >= 90 for x in aw):3} | AWR 99 {sum(x >= 99 for x in aw):3} | '
            f'OVR mean {st.mean(ov):5.1f} | 90+ {sum(x >= 90 for x in ov):3} | 95+ {sum(x >= 95 for x in ov):3} | '
            f'99 {sum(x >= 99 for x in ov):3}')


def production(pos, o, d):
    if pos == 0 and o:
        return o['saya'] + 20 * o['satd'] - 45 * o['sain']
    if pos == 1 and o:
        return o['suya'] + o['scya'] + 20 * (o['sutd'] + o['sctd'])
    if pos in (3, 4) and o:
        return o['scya'] + 20 * o['sctd']
    if pos >= 10 and d:
        return d['sdta'] + 4 * d['slsk'] + 5 * d['ssin'] + 3 * d['sdpd']
    return None


def report(name, s1, s2):
    A, B = players(s1), players(s2)
    common = [k for k in A if k in B and rostered(A[k]) and rostered(B[k])]
    print(f'\n== {name}: season 2, {len(common)} players')
    for lo, hi in BANDS:
        g = [k for k in common if lo <= A[k]['POVR'] <= hi]
        if g:
            print(f'   OVR {lo:2}-{hi}: {len(g):4}  OVR {st.mean(B[k]["POVR"] - A[k]["POVR"] for k in g):+5.2f}  '
                  f'AWR {st.mean(B[k]["PAWR"] - A[k]["PAWR"] for k in g):+5.2f}  '
                  f'new 99s {sum(B[k]["POVR"] >= 99 > A[k]["POVR"] for k in g):2}  '
                  f'lost 99 {sum(A[k]["POVR"] >= 99 > B[k]["POVR"] for k in g)}')
    season = s2['SEAI'].row(0)['SEYR']
    of = {r['PGID']: r for r in s2['PSOF'].rows() if r['SEYR'] == season}
    de = {r['PGID']: r for r in s2['PSDE'].rows() if r['SEYR'] == season}
    gs = {r['PGID']: r['sgms'] for r in s2['PSNG'].rows() if r['SEYR'] == season}
    by_pos = collections.defaultdict(list)
    for k in common:
        a = A[k]
        if gs.get(k, 0) < 8 or a['PPOS'] not in GROUP:
            continue
        p = production(a['PPOS'], of.get(k), de.get(k))
        if p is not None:
            by_pos[GROUP[a['PPOS']]].append((p, B[k]['PAWR'] - a['PAWR'], B[k]['POVR'] - a['POVR']))
    thirds = {'top': [], 'middle': [], 'bottom': []}
    for v in by_pos.values():
        v.sort()
        t = len(v) // 3
        thirds['bottom'] += v[:t]
        thirds['middle'] += v[t:len(v) - t]
        thirds['top'] += v[len(v) - t:]
    print('   starters (8+ starts) by production third at their position:')
    for k in ('top', 'middle', 'bottom'):
        v = thirds[k]
        if v:
            print(f'     {k:6}: {len(v):3} players  AWR {st.mean(x[1] for x in v):+5.2f}  OVR {st.mean(x[2] for x in v):+5.2f}  '
                  f'declined {sum(x[1] < 0 for x in v)}')


def main(argv):
    start = players(open_db(argv[0]))
    print(f'{"start roster":26} {summary(start)}')
    runs = []
    for spec in argv[1:]:
        name, paths = spec.split('=', 1)
        s1, s2 = (open_db(p) for p in paths.split(','))
        print(f'{name + " after season 1":26} {summary(players(s1))}')
        print(f'{name + " after season 2":26} {summary(players(s2))}')
        runs.append((name, s1, s2))
    for name, s1, s2 in runs:
        report(name, s1, s2)


if __name__ == '__main__':
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    main(sys.argv[1:])
