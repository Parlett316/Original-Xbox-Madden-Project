"""Jump a Madden 09 franchise save to a later regular-season week, to make late-season tests cheap.

Usage: python save_jump.py <in save> <out save> --week N [--seed S]
       python save_jump.py <save> --show

  --week N  N is the week as the schedule screen numbers it (1 = week 1). The save must
            be in the regular season. Unplayed games before week N get made-up scores,
            and the standings are recalculated from every result. The next simmed week
            behaves normally; sim the last regular-season week to get the playoffs.
  --seed S  score generator seed (default 1); the same seed gives the same results.

The database keeps its size and position, and CRCs are recomputed. On the console the
output must replace the input under the same file name, and the game needs an XBE built
with --save-unlock. Player stats and box scores for skipped weeks stay empty, and ratings,
injuries and rankings by yardage don't change, so don't use a jumped save to judge
progression or awards. Conference and league ranks break ties approximately; the game
recalculates them when it sims a week.
"""
import argparse
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'roster'))
import tdb  # noqa: E402

REGULAR = 25    # SEWT of a regular-season week
UNPLAYED = 1    # GSTA; 2 = the away team won, 3 = the home team won
AWAY_WON, HOME_WON = 2, 3
SCORING = (0, 3, 6, 7, 10, 13, 14, 16, 17, 20, 21, 23, 24, 27, 28, 30, 31, 34, 35, 38, 41, 45)


def open_save(path):
    with open(path, 'rb') as f:
        buf = bytearray(f.read())
    off = buf.find(b'DB\x00\x08')
    if off < 0:
        sys.exit(f'{path}: no database found')
    return buf, tdb.DB(buf, off)


def state(db):
    return db['SEAI'].row(0)


def play(rng, home_rating, away_rating):
    """Scores for one game: better teams and home teams win more. Never a tie."""
    edge = (home_rating - away_rating) / 2 + 2.5
    home = rng.gauss(22 + edge / 2, 9)
    away = rng.gauss(22 - edge / 2, 9)
    nearest = lambda x: min(SCORING, key=lambda s: abs(s - x))
    h, a = nearest(home), nearest(away)
    if h == a:
        if rng.random() < 0.5 + edge / 40:
            h += 3
        else:
            a += 3
    return h, a


def fill_scores(db, week, seed):
    """Give every unplayed regular-season game before schedule index `week` a result."""
    rng = random.Random(seed)
    s, t = db['SCHD'], db['TEAM']
    rating = {t.get(i, 'TGID'): t.get(i, 'TROV') for i in range(t.count)}
    filled = 0
    for i in range(s.count):
        if s.get(i, 'SEWT') != REGULAR or s.get(i, 'SEWN') >= week or s.get(i, 'GSTA') != UNPLAYED:
            continue
        h, a = play(rng, rating.get(s.get(i, 'GHTG'), 75), rating.get(s.get(i, 'GATG'), 75))
        s.set(i, 'GHSC', h)
        s.set(i, 'GASC', a)
        s.set(i, 'GSTA', HOME_WON if h > a else AWAY_WON)
        s.set(i, 'GFHU', 0)
        filled += 1
    return filled


def pct(w, l, tied):
    games = w + l + tied
    return (1000 * (2 * w + tied)) // (2 * games) if games else 0


def standings(db):
    """Recalculate each team's record and rank fields from the schedule's results."""
    t = db['TEAM']
    index = {t.get(i, 'TGID'): i for i in range(t.count) if t.get(i, 'TGID') < 32}
    conf = {g: t.get(i, 'CGID') for g, i in index.items()}
    div = {g: t.get(i, 'DGID') for g, i in index.items()}
    zero = dict(w=0, l=0, t=0, pf=0, pa=0, cw=0, cl=0, ct=0, cpf=0, cpa=0, dw=0, dl=0, dt=0, dpf=0, dpa=0,
                hw=0, hl=0, ht=0, aw=0, al=0, at=0, seq=[])
    rec = {g: dict(zero, seq=[]) for g in index}
    rows = db['SCHD'].rows()
    rows.sort(key=lambda r: (r['SEWN'], r['SGNM']))
    for r in rows:
        if r['SEWT'] != REGULAR or r['GSTA'] not in (AWAY_WON, HOME_WON, 4):
            continue
        h, a = r['GHTG'], r['GATG']
        for me, op, pf, pa, loc in ((h, a, r['GHSC'], r['GASC'], 'h'), (a, h, r['GASC'], r['GHSC'], 'a')):
            x = rec[me]
            res = 'w' if pf > pa else 'l' if pf < pa else 't'
            x[res] += 1
            x[loc + res] += 1
            x['pf'] += pf
            x['pa'] += pa
            x['seq'].append(res)
            if conf[me] == conf[op]:
                x['c' + res] += 1
                x['cpf'] += pf
                x['cpa'] += pa
                if div[me] == div[op]:
                    x['d' + res] += 1
                    x['dpf'] += pf
                    x['dpa'] += pa
    for g, x in rec.items():
        i = index[g]
        streak = 0
        for res in reversed(x['seq']):
            step = 1 if res == 'w' else -1 if res == 'l' else 0
            if not step or (streak and (streak > 0) != (step > 0)):
                break
            streak += step
        fields = {'TSWI': x['w'], 'TSLO': x['l'], 'TSTI': x['t'], 'TWPC': pct(x['w'], x['l'], x['t']),
                  'TSPF': x['pf'], 'TSPA': x['pa'], 'TCPF': x['cpf'], 'TCPA': x['cpa'],
                  'TDPF': x['dpf'], 'TDPA': x['dpa'], 'TCWP': pct(x['cw'], x['cl'], x['ct']),
                  'TDWP': pct(x['dw'], x['dl'], x['dt']), 'TSCS': streak,
                  'tscw': x['cw'], 'tscl': x['cl'], 'tsct': x['ct'], 'tsdw': x['dw'], 'tsdl': x['dl'],
                  'tsdi': x['dt'], 'tshw': x['hw'], 'tshl': x['hl'], 'tsht': x['ht'],
                  'tsaw': x['aw'], 'tsal': x['al'], 'tsat': x['at']}
        for k, v in fields.items():
            t.set(i, k, v)
    ranks(t, index, rec, conf, div)


def ranks(t, index, rec, conf, div):
    def order(x):
        return (-pct(x['w'], x['l'], x['t']), -pct(x['dw'], x['dl'], x['dt']),
                -pct(x['cw'], x['cl'], x['ct']), -(x['pf'] - x['pa']), -x['pf'])
    groups = {}
    for g in index:
        groups.setdefault(('div', conf[g], div[g]), []).append(g)
    for key, members in groups.items():
        members.sort(key=lambda g: order(rec[g]))
        for n, g in enumerate(members):
            t.set(index[g], 'TSDS', n)
    for field, scope in (('tscs', lambda g: conf[g]), ('tsns', lambda g: 0)):
        buckets = {}
        for g in index:
            buckets.setdefault(scope(g), []).append(g)
        for members in buckets.values():
            members.sort(key=lambda g: order(rec[g]))
            for n, g in enumerate(members):
                t.set(index[g], field, n)


def fill_owner_weeks(db, current, week):
    """Add OTIW rows up to `week`: 32 per week in order, up to and including the current one.

    The current week's row is a zero placeholder that the game fills in when the week ends;
    without it, Simulate Week returns at once and plays nothing. Skipped weeks repeat each
    team's last values, or stay zero if the team has none yet.
    """
    t = db['OTIW']
    teams = 32
    if t.count != teams * (current + 1) or teams * (week + 1) > t.capacity:
        sys.exit(f'OTIW has {t.count} rows (capacity {t.capacity}); expected {teams * (current + 1)} at this week')
    values = [f for f in t.fields if f not in ('TGID', 'SEWN')]
    last = {}
    for i in range(t.count):
        if t.get(i, 'SEWN') != i // teams:
            sys.exit('OTIW rows are not in week order')
        row = t.row(i)
        if any(row[f] for f in values):
            last[row['TGID']] = {f: row[f] for f in values}
    ids = [t.get(k, 'TGID') for k in range(teams)]
    t.count = teams * (week + 1)
    for w in range(current, week + 1):
        for k, team in enumerate(ids):
            i = w * teams + k
            t.set_raw(i, bytes(t.reclen))
            t.set(i, 'TGID', team)
            t.set(i, 'SEWN', w)
            if w < week:
                for f, v in last.get(team, {}).items():
                    t.set(i, f, v)


def set_week(db, week):
    """Move the season to schedule index `week`, with a game of that week featured."""
    db['SEAI'].set(0, 'SEWN', week)
    s = db['SCHD']
    numbers = [s.get(i, 'SGNM') for i in range(s.count) if s.get(i, 'SEWT') == REGULAR and s.get(i, 'SEWN') == week]
    if numbers:
        db['SEAI'].set(0, 'SGOW', numbers[len(numbers) // 2])


def jump_week(db, shown_week, seed):
    a = state(db)
    if a['SEWT'] != REGULAR:
        sys.exit(f'the save must be in the regular season (it has SEWT {a["SEWT"]}, week {a["SEWN"]})')
    week, last = shown_week - 1, a['SERW'] - 1
    if not a['SEWN'] <= week <= last:
        sys.exit(f'--week must be {a["SEWN"] + 1} to {last + 1}: this save is at week {a["SEWN"] + 1} '
                 f'and the season has {last + 1} regular-season weeks')
    n = fill_scores(db, week, seed)
    standings(db)
    fill_owner_weeks(db, a['SEWN'], week)
    set_week(db, week)
    print(f'week {a["SEWN"] + 1} -> {shown_week}: {n} games given results')


def show(db):
    a, s = state(db), db['SCHD'].rows()
    done = sum(r['SEWT'] == REGULAR and r['GSTA'] in (AWAY_WON, HOME_WON, 4) for r in s)
    print(f'year {a["SEYR"] + 1}, week index {a["SEWN"]} (SEWT {a["SEWT"]}), {done} regular-season results, '
          f'stage {db["MOIN"].row(0)["MCSA"]}, CRCs {"ok" if db.verify() else "BAD"}')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('input')
    ap.add_argument('output', nargs='?')
    ap.add_argument('--week', type=int)
    ap.add_argument('--seed', type=int, default=1)
    ap.add_argument('--show', action='store_true')
    a = ap.parse_args()
    buf, db = open_save(a.input)
    if a.show:
        show(db)
        return
    if not a.output or a.week is None:
        ap.error('give an output file and --week')
    if os.path.abspath(a.output) == os.path.abspath(a.input):
        ap.error('write to a new file; the input is kept')
    jump_week(db, a.week, a.seed)
    db.fix()
    assert db.verify()
    with open(a.output, 'wb') as f:
        f.write(buf)
    show(db)


if __name__ == '__main__':
    main()
