"""Coach ratings for the 2026 staffs, by rank (used by build_roster.py).

    python coach_ratings.py <stock template.dat>      # print the plan

Coach ratings become game-day bonuses (docs/findings.md §13: OPRA, +1 to +3 for a
rating of 85+, -2 at 73 or lower), so they should follow the coach. Each role's
32 stock rows (TGID 1-32) keep 09's spread: the 2026 coaches of that role are
ranked by merit and each gets the whole rating row of the stock coach at the
same rank, so a row's mix (a QB-minded OC is good at QB and offense together)
stays coherent. Special teams coordinators keep their ratings, and so does a
role left stock (STAFF None, e.g. Todd Bowles as his own DC).

Merit (2026-11-20):
  head coaches   career win %, shrunk toward .500 by one season (8.5-8.5), plus
                 0.01 a playoff win and 0.03 a Super Bowl win; none yet = .500.
                 The row's best numbers go on the coach's side of the ball (side_of_ball).
  coordinators   their 2025 unit's points rank (scored for an OC, allowed for a
                 DC; nflverse 2025 regular season) for the team they coordinated
                 or were head coach of in 2025 (ESPN's 2025 staff ranking, Aug 2025).
                 Coordinators new to the job rank in the middle.
"""
import os
import sys

import coaches

RATING_FIELDS = ('CMOT', 'CKNW', 'CCHM', 'CETH', 'COFF', 'CDEF', 'CROL', 'CRQB', 'CRRB', 'CRWR',
                 'CRDL', 'CRLB', 'CRDB', 'CRSA', 'CRKS', 'CRPS')
# What makes a stock row strong for its role: the fields whose bonuses that role hands out.
ROLE_KEYS = {0: ('CKNW', 'COFF', 'CDEF'),
             1: ('COFF', 'CRQB', 'CRRB', 'CRWR', 'CROL'),
             2: ('CDEF', 'CRDL', 'CRLB', 'CRDB', 'CRSA')}

# 2025 regular-season points rank, 1 = best (scored for offense, allowed for defense).
OFF_2025 = ['LA', 'NE', 'SEA', 'DET', 'BUF', 'JAX', 'DAL', 'IND', 'CHI', 'SF', 'BAL', 'CIN', 'HOU', 'DEN',
            'PIT', 'GB', 'NYG', 'TB', 'PHI', 'LAC', 'KC', 'WAS', 'ARI', 'ATL', 'MIA', 'MIN', 'CAR', 'NO',
            'NYJ', 'TEN', 'CLE', 'LV']
DEF_2025 = ['SEA', 'HOU', 'DEN', 'NE', 'PHI', 'KC', 'MIN', 'JAX', 'LAC', 'LA', 'GB', 'BUF', 'SF', 'CLE',
            'CAR', 'NO', 'PIT', 'BAL', 'ATL', 'TB', 'IND', 'DET', 'CHI', 'MIA', 'LV', 'NYG', 'WAS', 'TEN',
            'ARI', 'CIN', 'NYJ', 'DAL']
# 2026 coordinator -> the 2025 team whose unit he ran (as coordinator, or as head coach).
UNIT_2025 = {
    # offense
    'Dan Pitcher': 'CIN', 'Zac Robinson': 'ATL', 'Mike McDaniel': 'MIA', 'Jim Bob Cooter': 'IND',
    'Klayton Adams': 'DAL', 'Tommy Rees': 'CLE', 'Klay Kubiak': 'SF', 'Matt Nagy': 'KC',
    'Grant Udinski': 'JAX', 'Drew Petzing': 'ARI', 'Adam Stenavich': 'GB', 'Brad Idzik': 'CAR',
    'Josh McDaniels': 'NE', 'Declan Doyle': 'CHI', 'Doug Nussmeier': 'NO', 'Brian Daboll': 'NYG',
    'Wes Phillips': 'MIN', 'Nick Caley': 'HOU',
    # defense
    'Dennis Allen': 'CHI', 'Al Golden': 'CIN', 'Vance Joseph': 'DEN', 'Nick Rallis': 'ARI',
    'Steve Spagnuolo': 'KC', 'Lou Anarumo': 'IND', 'Vic Fangio': 'PHI', 'Jeff Ulbrich': 'ATL',
    'Raheem Morris': 'ATL', 'Dennard Wilson': 'TEN', 'Anthony Campanile': 'JAX', 'Kelvin Sheppard': 'DET',
    'Jonathan Gannon': 'ARI', 'Chris Shula': 'LA', 'Anthony Weaver': 'MIA', 'Brandon Staley': 'NO',
    'Aden Durde': 'SEA', 'Patrick Graham': 'LV', 'Brian Flores': 'MIN', 'Matt Burke': 'HOU',
}
NEW_TO_JOB = 16.5   # a coordinator with no 2025 unit ranks in the middle
# A head coach's higher of COFF/CDEF goes on his side of the ball. Neither: John Harbaugh
# (special teams). Everyone else is an offensive head coach.
DEFENSIVE_HC = {'Mike Macdonald', 'DeMeco Ryans', 'Mike Vrabel', 'Aaron Glenn', 'Robert Saleh',
                'Todd Bowles', 'Jesse Minter', 'Jeff Hafley', 'Dan Quinn'}
NEUTRAL_HC = {'John Harbaugh'}
OFF_POS = ('CRQB', 'CRRB', 'CRWR', 'CROL')
DEF_POS = ('CRLB', 'CRDB', 'CRDL', 'CRSA')
KICK_POS = ('CRKS', 'CRPS')


def side_of_ball(r, defensive):
    """A head coach's row with its best numbers on his side: the higher of COFF/CDEF, and of the
    10 position ratings the top 4 on his side's positions, the next 4 on the other side's and
    the lowest 2 on kickers and punters. Within a group, the row's own order is kept."""
    r = dict(r)
    hi, lo = max(r['COFF'], r['CDEF']), min(r['COFF'], r['CDEF'])
    r['COFF'], r['CDEF'] = (lo, hi) if defensive else (hi, lo)
    own, other = (DEF_POS, OFF_POS) if defensive else (OFF_POS, DEF_POS)
    values = sorted((r[f] for f in own + other + KICK_POS), reverse=True)
    for group, vals in ((own, values[:4]), (other, values[4:8]), (KICK_POS, values[8:])):
        for f, v in zip(sorted(group, key=lambda f: -r[f]), vals):
            r[f] = v
    return r


def merit(name, role):
    """Higher is better."""
    if role == 0:
        w, l, t, pw = (coaches.RECORDS.get(name) or (0, 0, 0, 0))[:4]
        sb = coaches.SUPER_BOWLS.get(name, (0, 0))[0]
        return (w + t / 2 + 8.5) / (w + l + t + 17) + 0.01 * pw + 0.03 * sb
    team = UNIT_2025.get(name)
    order = OFF_2025 if role == 1 else DEF_2025
    return -(order.index(team) + 1 if team else NEW_TO_JOB)


def plan(table):
    """{(TGID, COPS): (coach, merit, stock row)} from a stock COCH table."""
    stock = {(r['TGID'], r['COPS']): r for r in table.rows() if 1 <= r['TGID'] <= 32}
    out = {}
    for role, keys in ROLE_KEYS.items():
        slots = [t for t in range(1, 33) if coaches.STAFF[t][role] is not None]
        rows = sorted((stock[t, role] for t in slots), key=lambda r: -sum(r[k] for k in keys))
        ranked = sorted(slots, key=lambda t: -merit(coaches.STAFF[t][role], role))
        for t, r in zip(ranked, rows):
            name = coaches.STAFF[t][role]
            r = dict(r)
            if role == 0 and name not in NEUTRAL_HC:
                r = side_of_ball(r, name in DEFENSIVE_HC)
            out[t, role] = (name, merit(name, role), r)
    return out


def apply(table, stock_plan):
    """Give the 1-32 staffs their planned ratings (after coaches.apply)."""
    n = 0
    for i in range(table.count):
        key = (table.get(i, 'TGID'), table.get(i, 'COPS'))
        if key in stock_plan:
            for f in RATING_FIELDS:
                if f in table.fields:
                    table.set(i, f, stock_plan[key][2][f])
            n += 1
    return n


if __name__ == '__main__':
    import tdb
    buf = bytearray(open(sys.argv[1], 'rb').read())
    db = tdb.DB(buf, buf.find(b'DB\x00\x08', 0x3c000))
    p = plan(db['COCH'])
    for role, keys in ROLE_KEYS.items():
        print(['Head coaches', 'Offensive coordinators', 'Defensive coordinators'][role], '(' + ', '.join(keys) + ')')
        for k, (t, c) in enumerate(sorted((k for k in p if k[1] == role), key=lambda k: -p[k][1]), 1):
            name, m, r = p[t, c]
            src = UNIT_2025.get(name, '') if role else ''
            print(f'  {k:2} {name:22} {m:+.3f} {src:4} ' + ' '.join(f'{f}={r[f]}' for f in keys))
