"""Match Madden 09's classic-team players to the real players they model.

    python classic_names.py <DB_TEAMS.dat> <nflverse roster dir> <out.csv>
    python classic_names.py --apply <DB_TEAMS.dat> <matches.csv> <out DB_TEAMS.dat> [levels]

--apply writes the matched names (default levels: high,medium) into PFNA/PLNA
of the classic players and recomputes each changed DB's checksums. Every row
is checked against the file first (team, slot, number, age, height, weight),
so a CSV from a different DB_TEAMS.dat is refused.

The classic teams in DB_TEAMS.dat ('57 Lions ... '02 Raiders) carry no names:
each player is "<position> #<number>". EA also changed the jersey numbers, so
those can't be matched. Age, years pro, height and weight do follow the real
players, so each team is matched to that season's real roster (nflverse
roster_<year>.csv: name, position, birth date, height, weight) as a min-cost
assignment over position group, age, years pro, height and weight. Years pro
is counted from a player's first nflverse season (keyed by name + birth date),
so the roster dir should hold every season from 1940 on. Some teams have
placeholder ages (27 for nearly everyone, or 26-31 at random); a team's ages
are used only when most age-free matches agree with them. EA counts the
season itself in years pro before 2000 (measured: +1 for 80% of matches).

Writes one CSV row per classic player: team, slot, the game's data, the match,
its cost, and the margin to that player's next-best real player. Matches above
COST_LIMIT are left unnamed. The all-time teams ("All 49ers") and the fantasy
squads have no single season and are skipped.
"""
import csv
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'tools'))
from db_survey import find_dbs  # noqa: E402

FIRST_CLASSIC = 33                      # DBs 0-31 current teams, 32 free agents
COST_LIMIT = 40
NO_MATCH = COST_LIMIT                   # cost of leaving a slot unnamed
AGE_TRUST = 0.6                         # share of age-free matches whose ages agree
FIRST_LEN, LAST_LEN = 11, 13            # PFNA / PLNA widths

# game PPOS -> position group
GAME_GROUP = ['QB', 'RB', 'RB', 'WR', 'TE', 'OL', 'OL', 'OL', 'OL', 'OL',
              'DL', 'DL', 'DL', 'LB', 'LB', 'LB', 'DB', 'DB', 'DB', 'K', 'P']
REAL_GROUP = {'QB': 'QB', 'RB': 'RB', 'HB': 'RB', 'FB': 'RB', 'WR': 'WR', 'TE': 'TE',
              'OL': 'OL', 'T': 'OL', 'OT': 'OL', 'G': 'OL', 'OG': 'OL', 'C': 'OL', 'LS': 'OL',
              'DL': 'DL', 'DE': 'DL', 'DT': 'DL', 'NT': 'DL',
              'LB': 'LB', 'OLB': 'LB', 'ILB': 'LB', 'MLB': 'LB',
              'DB': 'DB', 'CB': 'DB', 'S': 'DB', 'SS': 'DB', 'FS': 'DB', 'SAF': 'DB',
              'K': 'K', 'P': 'P', 'SPEC': 'KP'}
NEAR = {frozenset(p) for p in (('RB', 'WR'), ('TE', 'OL'), ('TE', 'WR'), ('DL', 'LB'),
                               ('LB', 'DB'), ('RB', 'TE'), ('DL', 'OL'))}

# nickname -> nflverse team code, by first season it applies to
TEAM_CODES = {
    'Falcons': [(0, 'ATL')], 'Broncos': [(0, 'DEN')], 'Vikings': [(0, 'MIN')],
    'Packers': [(0, 'GB')], '49ers': [(0, 'SF')], 'Panthers': [(0, 'CAR')],
    'Jaguars': [(0, 'JAX')], 'Patriots': [(0, 'BOS'), (1971, 'NE')],
    'Cowboys': [(0, 'COW'), (1963, 'DAL')], 'Steelers': [(0, 'PIT')],
    'Chargers': [(0, 'SD')], 'Bills': [(0, 'BUF')], 'Oilers': [(0, 'HOU')],
    'Saints': [(0, 'NO')], 'Lions': [(0, 'DET')], 'Redskins': [(0, 'WAS')],
    'Chiefs': [(0, 'KC')], 'Texans': [(0, 'TEX')],
    'Raiders': [(0, 'OAK'), (1982, 'RAI'), (1995, 'OAK')],
    'Giants': [(0, 'NY'), (1960, 'NYG')], 'Eagles': [(0, 'PHI')],
    'Bears': [(0, 'CHB'), (1960, 'CHI')], 'Bengals': [(0, 'CIN')],
    'Browns': [(0, 'CLE'), (2002, 'CLV')], 'Jets': [(0, 'NYT'), (1963, 'NYJ')],
    'Rams': [(0, 'LA'), (1960, 'RAM'), (1962, 'LA'), (1984, 'RAM'), (1995, 'STL'), (2002, 'SL')],
    'Dolphins': [(0, 'MIA')], 'Seahawks': [(0, 'SEA')], 'Bucs': [(0, 'TB')],
    'Colts': [(0, 'BAL'), (1984, 'IND')], 'Cardinals': [(0, 'STL'), (1988, 'PHO'), (1994, 'ARI')],
    'Ravens': [(0, 'BAL'), (2002, 'BLT')],
}


def team_code(nick, year):
    return [c for y, c in TEAM_CODES[nick] if y <= year][-1]


def season_year(two):
    y = int(two)
    return 1900 + y if y >= 50 else 2000 + y


def age_on(birth, year):
    """Age on September 1 of the season."""
    y, m, d = (int(v) for v in birth.split('-'))
    return year - y - ((m, d) > (9, 1))


def load_seasons(folder):
    seasons, first = {}, {}
    for f in sorted(os.listdir(folder)):
        if f.startswith('roster_') and f.endswith('.csv'):
            year = int(f[7:11])
            rows = list(csv.DictReader(open(os.path.join(folder, f), encoding='utf8')))
            seasons[year] = rows
            for r in rows:
                key = (r['full_name'], r['birth_date'])
                first[key] = min(first.get(key, year), year)
    return seasons, first


def years_pro(r, year, first):
    """Years pro as the game counts it: before 2000 EA counts the season itself."""
    return year - first[(r['full_name'], r['birth_date'])] + (year < 2000)


def classic_teams(buf):
    for k, db in enumerate(find_dbs(buf)):
        if k < FIRST_CLASSIC or 'TEAM' not in db.tables or 'PLAY' not in db.tables or not db['TEAM'].count:
            continue
        name = db['TEAM'].row(0)['TDNA']
        two, _, nick = name.partition(' ')
        if len(two) == 2 and two.isdigit() and nick in TEAM_CODES:
            yield k, name, season_year(two), nick, db


def cost(g, r, year, first, use_age=True):
    """How unlike game player g is real player r (lower is better)."""
    gg, rg = GAME_GROUP[g['PPOS']], REAL_GROUP.get(r['position'], '?')
    if gg == rg or (rg == 'KP' and gg in ('K', 'P')):
        pos = 0
    elif frozenset((gg, rg)) in NEAR:
        pos = 12
    else:
        return None
    if not (r['birth_date'] and r['height'] and r['weight']):
        return None
    c = pos
    if use_age:
        c += 4 * abs(age_on(r['birth_date'], year) - g['PAGE'])
    c += 3 * abs(years_pro(r, year, first) - g['PYRP'])
    c += 1.5 * abs(int(r['height']) - g['PHGT'])
    c += 0.25 * abs(int(r['weight']) - (g['PWGT'] + 160))
    return c


def assign(costs):
    """Min-cost assignment (Hungarian, rectangular n <= m). costs[i][j]; returns j per i."""
    n, m = len(costs), len(costs[0])
    INF = float('inf')
    u, v, p, way = [0] * (n + 1), [0] * (m + 1), [0] * (m + 1), [0] * (m + 1)
    for i in range(1, n + 1):
        p[0], j0 = i, 0
        minv, used = [INF] * (m + 1), [False] * (m + 1)
        while True:
            used[j0], i0, delta, j1 = True, p[j0], INF, 0
            for j in range(1, m + 1):
                if not used[j]:
                    cur = costs[i0 - 1][j - 1] - u[i0] - v[j]
                    if cur < minv[j]:
                        minv[j], way[j] = cur, j0
                    if minv[j] < delta:
                        delta, j1 = minv[j], j
            for j in range(m + 1):
                if used[j]:
                    u[p[j]] += delta
                    v[j] -= delta
                else:
                    minv[j] -= delta
            j0 = j1
            if p[j0] == 0:
                break
        while j0:
            j1 = way[j0]
            p[j0] = p[j1]
            j0 = j1
    out = [None] * n
    for j in range(1, m + 1):
        if p[j]:
            out[p[j] - 1] = j - 1
    return out


def match_team(players, real, year, first):
    """[(game row, real row or None, cost, margin)] for one team.

    Some teams' ages are placeholders (27 for nearly everyone, or 26-31 at
    random), so a first pass matches without age; age is used only when most
    of those matches' ages agree."""
    loose = assign_team(players, real, year, first, lambda g: False)
    named = [(g, r) for g, r, _, _ in loose if r]
    agree = sum(abs(age_on(r['birth_date'], year) - g['PAGE']) <= 1 for g, r in named)
    if named and agree / len(named) < AGE_TRUST:
        return loose
    return assign_team(players, real, year, first, lambda g: True)


def assign_team(players, real, year, first, use_age):
    table = [[cost(g, r, year, first, use_age(g)) for r in real] for g in players]
    # one "unnamed" column per game player, so every slot can opt out
    big = 10 ** 6
    costs = [[big if c is None else c for c in row] + [NO_MATCH] * len(players) for row in table]
    pick = assign(costs)
    out = []
    for g, row, j in zip(players, table, pick):
        if j < len(real) and row[j] is not None and row[j] < COST_LIMIT:
            others = sorted(c for k, c in enumerate(row) if k != j and c is not None)
            out.append((g, real[j], row[j], (others[0] - row[j]) if others else 99))
        else:
            out.append((g, None, None, None))
    return out


def main(teams_path, roster_dir, out_csv):
    buf = bytearray(open(teams_path, 'rb').read())
    seasons, first = load_seasons(roster_dir)
    fields = ['db', 'team', 'slot', 'pos', 'number', 'age', 'yrs', 'ht', 'wt',
              'name', 'first', 'last', 'real_pos', 'real_age', 'real_yrs', 'real_ht', 'real_wt',
              'cost', 'margin', 'confidence']
    totals = {'high': 0, 'medium': 0, 'low': 0, 'none': 0}
    with open(out_csv, 'w', newline='', encoding='utf8') as f:
        w = csv.DictWriter(f, fields)
        w.writeheader()
        for k, name, year, nick, db in classic_teams(buf):
            code = team_code(nick, year)
            real = [r for r in seasons.get(year, []) if r['team'] == code]
            players = db['PLAY'].rows()
            matches = match_team(players, real, year, first) if real else [(g, None, None, None) for g in players]
            for slot, (g, r, c, margin) in enumerate(matches):
                row = {'db': k, 'team': name, 'slot': slot, 'pos': g['PFNA'], 'number': g['PJEN'],
                       'age': g['PAGE'], 'yrs': g['PYRP'], 'ht': g['PHGT'], 'wt': g['PWGT'] + 160}
                if r is None:
                    row['confidence'] = 'none'
                else:
                    conf = 'high' if c <= 8 else 'medium' if c <= 16 else 'low'
                    row.update(name=r['full_name'], first=r['first_name'], last=r['last_name'],
                               real_pos=r['position'], real_age=age_on(r['birth_date'], year),
                               real_yrs=years_pro(r, year, first),
                               real_ht=r['height'], real_wt=r['weight'],
                               cost=round(c, 1), margin=round(margin, 1), confidence=conf)
                totals[row['confidence']] += 1
                w.writerow(row)
            if not real:
                print(f'{name}: no nflverse roster for {code} {year}')
    print('matches by confidence:', totals)


def known_as(r):
    """(first, last) as the player was known: nflverse's first_name is the legal
    one (Joseph Montana), full_name the common one (Joe Montana)."""
    full, last = r['name'], r['last']
    if full.endswith(' ' + last):
        return full[:-len(last) - 1], last
    first, _, rest = full.partition(' ')
    return first, rest or last


def fit(first, last):
    """Names that fit PFNA/PLNA: a long first name becomes its initial, a long
    hyphenated last name its second part (Davidds-Garrido -> Garrido)."""
    if len(first) > FIRST_LEN:
        first = first[0] + '.'
    if len(last) > LAST_LEN and '-' in last:
        last = last.split('-')[-1]
    assert len(first) <= FIRST_LEN and len(last) <= LAST_LEN, (first, last)
    return first, last


def apply(teams_path, matches_csv, out_path, levels='high,medium'):
    levels = set(levels.split(','))
    buf = bytearray(open(teams_path, 'rb').read())
    dbs = {k: db for k, db in enumerate(find_dbs(buf))}
    named, changed = 0, set()
    for r in csv.DictReader(open(matches_csv, encoding='utf8')):
        db, slot = dbs[int(r['db'])], int(r['slot'])
        play = db['PLAY']
        g = play.row(slot)
        assert db['TEAM'].row(0)['TDNA'] == r['team'] and (g['PJEN'], g['PAGE'], g['PHGT'], g['PWGT'] + 160) == \
            (int(r['number']), int(r['age']), int(r['ht']), int(r['wt'])), f'{r["team"]} slot {slot}: CSV does not match the file'
        if r['confidence'] not in levels:
            continue
        first, last = fit(*known_as(r))
        play.set(slot, 'PFNA', first)
        play.set(slot, 'PLNA', last)
        named += 1
        changed.add(int(r['db']))
    for k in changed:
        dbs[k].fix()
        assert dbs[k].verify()
    open(out_path, 'wb').write(buf)
    print(f'{named} players named in {len(changed)} teams -> {out_path}')


if __name__ == '__main__':
    if sys.argv[1:2] == ['--apply'] and len(sys.argv) in (5, 6):
        apply(*sys.argv[2:])
        sys.exit()
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    main(*sys.argv[1:])
