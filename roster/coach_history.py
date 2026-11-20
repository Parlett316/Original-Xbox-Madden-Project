"""Real coaching histories and team records for the 2026 staffs.

    python coach_history.py <template.dat> <DB_TEAMS.dat> <schedule games.csv> --year 2026 [--out-dir DIR]
    python coach_history.py <template.dat> <DB_TEAMS.dat> --clear [--out-dir DIR]

The coach history screen joins two tables (docs/findings.md §13):
  OCIS  (CCID, TGID, SEYR, COPS)  who held each role for a team in each past season;
        each team's DB in DB_TEAMS.dat holds its own rows, template.dat's franchise
        DB (0xab500) a copy
  OTRS  (TGID, SEYR, TSRW, TSRO, TSRI, TSRL)  each team's past seasons: wins, losses and
        ties including playoff games (as the game's own season-end rows count them: a
        2026 franchise row read 11-8 in a 17-game season), and postseason result (0 won the Super Bowl, 1 lost it,
        2 lost in the playoffs, 3 missed them); DB_TEAMS.dat only
SEYR counts back from the franchise's first season (0), so the rows only line up when
the game counts its years from 2026 (patches/year_base.py, build_all.py --year 2026):
SEYR -1 is 2025. The game keeps at most 30 seasons of each (0x3ac1c3, 0x3bde33).

With --year, every old row goes and the 2026 coaches' NFL seasons since 1999 as head
coach (COPS 0), offensive (1), defensive (2) or special teams coordinator (3) go in,
with each team's real 1999-2025 records from nflverse's schedule. 1999 is where the
schedule file starts. A coach keeps the CCID of the slot he took over (coaches.py), so
rows are written under that. Without a 2026 year base no history can be right, so
--clear just empties both tables, which beats a stranger's seasons.

CAREERS was gathered 2026-11-20 from team sites, Wikipedia and news reports (special
teams coordinators and 2025 jobs checked one by one); interim head coaching counts as
head coach. Teams are nflverse codes for the franchise (LV for the Raiders in Oakland,
LAC for San Diego, LA for St. Louis).
"""
import argparse
import collections
import csv
import os
import sys

import coaches
import headshots
import tdb

FIRST_SEASON = 1999
# nflverse franchise codes -> TGID (patches/season17.py)
TGID = dict(CHI=1, CIN=2, BUF=3, DEN=4, CLE=5, TB=6, ARI=7, LAC=8, KC=9, IND=10, DAL=11, MIA=12,
            PHI=13, ATL=14, SF=15, NYG=16, JAX=17, NYJ=18, DET=19, GB=20, CAR=21, NE=22, LV=23,
            LA=24, BAL=25, WAS=26, NO=27, SEA=28, PIT=29, TEN=30, MIN=31, HOU=32)
OLD_CODES = {'OAK': 'LV', 'SD': 'LAC', 'STL': 'LA'}
HC, OC, DC, ST = 0, 1, 2, 3

# coach: [(first season, last season, team, role)], NFL seasons from 1999 on only
CAREERS = {
    # Bears
    'Ben Johnson': [(2022, 2024, 'DET', OC), (2025, 2025, 'CHI', HC)],
    'Press Taylor': [(2022, 2024, 'JAX', OC)],
    'Dennis Allen': [(2011, 2011, 'DEN', DC), (2012, 2014, 'LV', HC), (2015, 2021, 'NO', DC),
                     (2022, 2024, 'NO', HC), (2025, 2025, 'CHI', DC)],
    'Richard Hightower': [(2017, 2021, 'SF', ST), (2022, 2025, 'CHI', ST)],
    # Bengals
    'Zac Taylor': [(2015, 2015, 'MIA', OC), (2019, 2025, 'CIN', HC)],
    'Dan Pitcher': [(2024, 2025, 'CIN', OC)],
    'Al Golden': [(2025, 2025, 'CIN', DC)],
    'Darrin Simmons': [(2003, 2025, 'CIN', ST)],
    # Bills
    'Joe Brady': [(2020, 2021, 'CAR', OC), (2023, 2025, 'BUF', OC)],
    'Pete Carmichael': [(2009, 2023, 'NO', OC)],
    'Jim Leonhard': [],
    'Jeff Rodgers': [(2010, 2010, 'CAR', ST), (2011, 2014, 'DEN', ST), (2015, 2017, 'CHI', ST),
                     (2018, 2025, 'ARI', ST)],
    # Broncos
    'Sean Payton': [(2000, 2002, 'NYG', OC), (2006, 2011, 'NO', HC), (2013, 2021, 'NO', HC),
                    (2023, 2025, 'DEN', HC)],
    'Davis Webb': [],
    'Vance Joseph': [(2016, 2016, 'MIA', DC), (2017, 2018, 'DEN', HC), (2019, 2022, 'ARI', DC),
                     (2023, 2025, 'DEN', DC)],
    'Darren Rizzi': [(2010, 2018, 'MIA', ST), (2019, 2024, 'NO', ST), (2024, 2024, 'NO', HC),
                     (2025, 2025, 'DEN', ST)],
    # Browns
    'Todd Monken': [(2016, 2018, 'TB', OC), (2019, 2019, 'CLE', OC), (2023, 2025, 'BAL', OC)],
    'Travis Switzer': [],
    'Mike Rutenberg': [],
    'Byron Storer': [],
    # Buccaneers
    'Todd Bowles': [(2011, 2011, 'MIA', HC), (2012, 2012, 'PHI', DC), (2013, 2014, 'ARI', DC),
                    (2015, 2018, 'NYJ', HC), (2019, 2021, 'TB', DC), (2022, 2025, 'TB', HC)],
    'Zac Robinson': [(2024, 2025, 'ATL', OC)],
    'Danny Smith': [(2001, 2003, 'BUF', ST), (2004, 2012, 'WAS', ST), (2013, 2025, 'PIT', ST)],
    # Cardinals
    'Mike LaFleur': [(2021, 2022, 'NYJ', OC), (2023, 2025, 'LA', OC)],
    'Nathaniel Hackett': [(2013, 2014, 'BUF', OC), (2016, 2018, 'JAX', OC), (2019, 2021, 'GB', OC),
                          (2022, 2022, 'DEN', HC), (2023, 2024, 'NYJ', OC)],
    'Nick Rallis': [(2023, 2025, 'ARI', DC)],
    'Michael Ghobrial': [(2024, 2025, 'NYG', ST)],
    # Chargers
    'Jim Harbaugh': [(2011, 2014, 'SF', HC), (2024, 2025, 'LAC', HC)],
    'Mike McDaniel': [(2021, 2021, 'SF', OC), (2022, 2025, 'MIA', HC)],
    "Chris O'Leary": [],
    'Ryan Ficken': [(2021, 2021, 'MIN', ST), (2022, 2025, 'LAC', ST)],
    # Chiefs
    'Andy Reid': [(1999, 2012, 'PHI', HC), (2013, 2025, 'KC', HC)],
    'Eric Bieniemy': [(2018, 2022, 'KC', OC), (2023, 2023, 'WAS', OC)],
    'Steve Spagnuolo': [(2007, 2008, 'NYG', DC), (2009, 2011, 'LA', HC), (2012, 2012, 'NO', DC),
                        (2015, 2017, 'NYG', DC), (2017, 2017, 'NYG', HC), (2019, 2025, 'KC', DC)],
    'Dave Toub': [(2004, 2012, 'CHI', ST), (2013, 2025, 'KC', ST)],
    # Colts
    'Shane Steichen': [(2019, 2020, 'LAC', OC), (2021, 2022, 'PHI', OC), (2023, 2025, 'IND', HC)],
    'Jim Bob Cooter': [(2015, 2018, 'DET', OC), (2023, 2025, 'IND', OC)],
    'Lou Anarumo': [(2015, 2015, 'MIA', DC), (2019, 2024, 'CIN', DC), (2025, 2025, 'IND', DC)],
    'Brian Mason': [(2023, 2025, 'IND', ST)],
    # Cowboys
    'Brian Schottenheimer': [(2006, 2011, 'NYJ', OC), (2012, 2014, 'LA', OC), (2018, 2020, 'SEA', OC),
                             (2023, 2024, 'DAL', OC), (2025, 2025, 'DAL', HC)],
    'Klayton Adams': [(2025, 2025, 'DAL', OC)],
    'Christian Parker': [],
    'Nick Sorensen': [(2021, 2021, 'JAX', ST), (2024, 2024, 'SF', DC), (2025, 2025, 'DAL', ST)],
    # Dolphins
    'Jeff Hafley': [(2024, 2025, 'GB', DC)],
    'Bobby Slowik': [(2023, 2024, 'HOU', OC)],
    'Sean Duggan': [],
    'Chris Tabor': [(2011, 2017, 'CLE', ST), (2018, 2021, 'CHI', ST), (2022, 2023, 'CAR', ST),
                    (2023, 2023, 'CAR', HC), (2025, 2025, 'BUF', ST)],
    # Eagles
    'Nick Sirianni': [(2018, 2020, 'IND', OC), (2021, 2025, 'PHI', HC)],
    'Sean Mannion': [],
    'Vic Fangio': [(1999, 2001, 'IND', DC), (2002, 2005, 'HOU', DC), (2011, 2014, 'SF', DC),
                   (2015, 2018, 'CHI', DC), (2019, 2021, 'DEN', HC), (2023, 2023, 'MIA', DC),
                   (2024, 2025, 'PHI', DC)],
    'Michael Clay': [(2021, 2025, 'PHI', ST)],
    # Falcons
    'Kevin Stefanski': [(2018, 2019, 'MIN', OC), (2020, 2025, 'CLE', HC)],
    'Tommy Rees': [(2025, 2025, 'CLE', OC)],
    'Jeff Ulbrich': [(2021, 2024, 'NYJ', DC), (2024, 2024, 'NYJ', HC), (2025, 2025, 'ATL', DC)],
    'Craig Aukerman': [(2016, 2016, 'LAC', ST), (2018, 2023, 'TEN', ST), (2025, 2025, 'MIA', ST)],
    # 49ers
    'Kyle Shanahan': [(2008, 2009, 'HOU', OC), (2010, 2013, 'WAS', OC), (2014, 2014, 'CLE', OC),
                      (2015, 2016, 'ATL', OC), (2017, 2025, 'SF', HC)],
    'Klay Kubiak': [(2025, 2025, 'SF', OC)],
    'Raheem Morris': [(2009, 2011, 'TB', HC), (2020, 2020, 'ATL', DC), (2020, 2020, 'ATL', HC),
                      (2021, 2023, 'LA', DC), (2024, 2025, 'ATL', HC)],
    'Brant Boyer': [(2016, 2024, 'NYJ', ST), (2025, 2025, 'SF', ST)],
    # Giants
    'John Harbaugh': [(1999, 2006, 'PHI', ST), (2008, 2025, 'BAL', HC)],
    'Matt Nagy': [(2016, 2017, 'KC', OC), (2018, 2021, 'CHI', HC), (2023, 2025, 'KC', OC)],
    'Dennard Wilson': [(2024, 2025, 'TEN', DC)],
    'Chris Horton': [(2019, 2025, 'BAL', ST)],
    # Jaguars
    'Liam Coen': [(2022, 2022, 'LA', OC), (2024, 2024, 'TB', OC), (2025, 2025, 'JAX', HC)],
    'Grant Udinski': [(2025, 2025, 'JAX', OC)],
    'Anthony Campanile': [(2025, 2025, 'JAX', DC)],
    'Heath Farwell': [(2019, 2021, 'BUF', ST), (2022, 2025, 'JAX', ST)],
    # Jets
    'Aaron Glenn': [(2021, 2024, 'DET', DC), (2025, 2025, 'NYJ', HC)],
    'Frank Reich': [(2014, 2015, 'LAC', OC), (2016, 2017, 'PHI', OC), (2018, 2022, 'IND', HC),
                    (2023, 2023, 'CAR', HC)],
    'Brian Duker': [],
    'Chris Banjo': [(2025, 2025, 'NYJ', ST)],
    # Lions
    'Dan Campbell': [(2015, 2015, 'MIA', HC), (2021, 2025, 'DET', HC)],
    'Drew Petzing': [(2023, 2025, 'ARI', OC)],
    'Kelvin Sheppard': [(2025, 2025, 'DET', DC)],
    'Dave Fipp': [(2011, 2012, 'MIA', ST), (2013, 2020, 'PHI', ST), (2021, 2025, 'DET', ST)],
    # Packers
    'Matt LaFleur': [(2017, 2017, 'LA', OC), (2018, 2018, 'TEN', OC), (2019, 2025, 'GB', HC)],
    'Adam Stenavich': [(2022, 2025, 'GB', OC)],
    'Jonathan Gannon': [(2021, 2022, 'PHI', DC), (2023, 2025, 'ARI', HC)],
    'Cameron Achord': [(2020, 2023, 'NE', ST)],
    # Panthers
    'Dave Canales': [(2023, 2023, 'TB', OC), (2024, 2025, 'CAR', HC)],
    'Brad Idzik': [(2024, 2025, 'CAR', OC)],
    'Todd Wash': [(2016, 2020, 'JAX', DC)],
    'Tracy Smith': [(2024, 2025, 'CAR', ST)],
    # Patriots
    'Mike Vrabel': [(2017, 2017, 'HOU', DC), (2018, 2023, 'TEN', HC), (2025, 2025, 'NE', HC)],
    'Josh McDaniels': [(2006, 2008, 'NE', OC), (2009, 2010, 'DEN', HC), (2011, 2011, 'LA', OC),
                       (2012, 2021, 'NE', OC), (2022, 2023, 'LV', HC), (2025, 2025, 'NE', OC)],
    'Zak Kuhr': [],
    'Jeremy Springer': [(2024, 2025, 'NE', ST)],
    # Raiders
    'Klint Kubiak': [(2021, 2021, 'MIN', OC), (2024, 2024, 'NO', OC), (2025, 2025, 'SEA', OC)],
    'Andrew Janocko': [],
    'Rob Leonard': [],
    'Joe DeCamillis': [(1999, 2006, 'ATL', ST), (2007, 2008, 'JAX', ST), (2009, 2012, 'DAL', ST),
                       (2013, 2014, 'CHI', ST), (2015, 2016, 'DEN', ST), (2017, 2020, 'JAX', ST),
                       (2021, 2022, 'LA', ST)],
    # Rams
    'Sean McVay': [(2014, 2016, 'WAS', OC), (2017, 2025, 'LA', HC)],
    'Nathan Scheelhaase': [],
    'Chris Shula': [(2024, 2025, 'LA', DC)],
    'Ray Ventrone': [(2018, 2022, 'IND', ST), (2023, 2025, 'CLE', ST)],
    # Ravens
    'Jesse Minter': [(2024, 2025, 'LAC', DC)],
    'Declan Doyle': [(2025, 2025, 'CHI', OC)],
    'Anthony Weaver': [(2020, 2020, 'HOU', DC), (2024, 2025, 'MIA', DC)],
    'Anthony Levine': [],
    # Commanders
    'Dan Quinn': [(2013, 2014, 'SEA', DC), (2015, 2020, 'ATL', HC), (2021, 2023, 'DAL', DC),
                  (2024, 2025, 'WAS', HC)],
    'David Blough': [],
    'Daronte Jones': [],
    'Larry Izzo': [(2016, 2017, 'HOU', ST), (2020, 2023, 'SEA', ST), (2024, 2025, 'WAS', ST)],
    # Saints
    'Kellen Moore': [(2019, 2022, 'DAL', OC), (2023, 2023, 'LAC', OC), (2024, 2024, 'PHI', OC),
                     (2025, 2025, 'NO', HC)],
    'Doug Nussmeier': [(2025, 2025, 'NO', OC)],
    'Brandon Staley': [(2020, 2020, 'LA', DC), (2021, 2023, 'LAC', HC), (2025, 2025, 'NO', DC)],
    'Phil Galiano': [(2025, 2025, 'NO', ST)],
    # Seahawks
    'Mike Macdonald': [(2022, 2023, 'BAL', DC), (2024, 2025, 'SEA', HC)],
    'Brian Fleury': [],
    'Aden Durde': [(2024, 2025, 'SEA', DC)],
    'Jay Harbaugh': [(2024, 2025, 'SEA', ST)],
    # Steelers
    'Mike McCarthy': [(2000, 2004, 'NO', OC), (2005, 2005, 'SF', OC), (2006, 2018, 'GB', HC),
                      (2020, 2024, 'DAL', HC)],
    'Brian Angelichio': [],
    'Patrick Graham': [(2019, 2019, 'MIA', DC), (2020, 2021, 'NYG', DC), (2022, 2025, 'LV', DC)],
    'Danny Crossman': [(2007, 2009, 'CAR', ST), (2010, 2012, 'DET', ST), (2013, 2018, 'BUF', ST),
                       (2019, 2024, 'MIA', ST)],
    # Titans
    'Robert Saleh': [(2017, 2020, 'SF', DC), (2021, 2024, 'NYJ', HC), (2025, 2025, 'SF', DC)],
    'Brian Daboll': [(2009, 2010, 'CLE', OC), (2011, 2011, 'MIA', OC), (2012, 2012, 'KC', OC),
                     (2018, 2021, 'BUF', OC), (2022, 2025, 'NYG', HC)],
    'Gus Bradley': [(2009, 2012, 'SEA', DC), (2013, 2016, 'JAX', HC), (2017, 2020, 'LAC', DC),
                    (2021, 2021, 'LV', DC), (2022, 2024, 'IND', DC)],
    'John Fassel': [(2009, 2011, 'LV', ST), (2012, 2019, 'LA', ST), (2016, 2016, 'LA', HC),
                    (2020, 2024, 'DAL', ST), (2025, 2025, 'TEN', ST)],
    # Vikings
    "Kevin O'Connell": [(2019, 2019, 'WAS', OC), (2020, 2021, 'LA', OC), (2022, 2025, 'MIN', HC)],
    'Wes Phillips': [(2022, 2025, 'MIN', OC)],
    'Brian Flores': [(2019, 2021, 'MIA', HC), (2023, 2025, 'MIN', DC)],
    'Matt Daniels': [(2022, 2025, 'MIN', ST)],
    # Texans
    'DeMeco Ryans': [(2021, 2022, 'SF', DC), (2023, 2025, 'HOU', HC)],
    'Nick Caley': [(2025, 2025, 'HOU', OC)],
    'Matt Burke': [(2017, 2018, 'MIA', DC), (2023, 2025, 'HOU', DC)],
    'Frank Ross': [(2021, 2025, 'HOU', ST)],
}


def team_records(games_csv, first=FIRST_SEASON, last=2025):
    """{(TGID, season): (W, L, T, postseason code)} from nflverse's games.csv."""
    rec = collections.defaultdict(lambda: [0, 0, 0, 3])
    for g in csv.DictReader(open(games_csv, encoding='utf8')):
        y = int(g['season'])
        if not first <= y <= last or g['home_score'] == '':
            continue
        h, a = (TGID[OLD_CODES.get(t, t)] for t in (g['home_team'], g['away_team']))
        hs, as_ = int(g['home_score']), int(g['away_score'])
        if g['game_type'] == 'REG':
            for t, d in ((h, hs - as_), (a, as_ - hs)):
                rec[t, y][0 if d > 0 else 1 if d < 0 else 2] += 1
        else:   # playoff games count in the record, as in the rows the game writes itself
            win, lose = (h, a) if hs > as_ else (a, h)
            rec[win, y][0] += 1
            rec[lose, y][1] += 1
            if g['game_type'] == 'SB':
                rec[win, y][3], rec[lose, y][3] = 0, 1
            else:
                rec[lose, y][3] = 2
                if rec[win, y][3] == 3:
                    rec[win, y][3] = 2
    return {k: tuple(v) for k, v in rec.items()}


def dbs(buf):
    i = -1
    while (i := buf.find(b'DB\x00\x08', i + 1)) >= 0:
        try:
            yield tdb.DB(buf, i)
        except (AssertionError, IndexError, UnicodeDecodeError, ValueError):
            continue


def coach_ids(template):
    """{2026 coach name: CCID} from the built league COCH (template.dat, first COCH)."""
    db = next(d for d in dbs(template) if 'COCH' in d.tables)
    t = db['COCH']
    out = {}
    for r in t.rows():
        if 1 <= r['TGID'] <= 32 and coaches.STAFF[r['TGID']][r['COPS']] is not None:
            out[coaches.STAFF[r['TGID']][r['COPS']]] = r['CCID']
    return out


def history_rows(ids, base):
    """{TGID: [(CCID, SEYR, COPS)]} for every 2026 coach's seasons."""
    missing = set(ids) - set(CAREERS)
    assert not missing, f'no career listed for {sorted(missing)}'
    out = collections.defaultdict(set)
    for name, ccid in ids.items():
        for first, last, team, role in CAREERS[name]:
            for y in range(max(first, FIRST_SEASON), last + 1):
                out[TGID[team]].add((ccid, y - base, role))
    return {t: sorted(v, key=lambda r: (r[1], r[2], r[0])) for t, v in out.items()}


def fill(table, rows, fields):
    assert len(rows) <= table.capacity, (table.name, len(rows), table.capacity)
    table.count = len(rows)
    blank = bytes(table.reclen)
    for i, r in enumerate(rows):
        table.set_raw(i, blank)
        for f, v in zip(fields, r):
            table.set(i, f, v)


def repack(buf, replace):
    """DB_TEAMS.dat with archive entries replaced by new bytes (sizes may change)."""
    from build_roster import repack as _repack
    return _repack(buf, replace)


def apply(template, teams, games_csv=None, base=None):
    """Rewrite the history tables in template.dat and DB_TEAMS.dat (bytearrays, in place for
    template; returns the new DB_TEAMS bytes, which may have grown)."""
    if base is not None:
        ids = coach_ids(template)
        hist = history_rows(ids, base)
        recs = team_records(games_csv, last=base - 1)
    else:
        hist, recs = {}, {}
    # template.dat's franchise copy: every row (OCIS only; its OTRS is empty in stock too)
    for db in dbs(template):
        if 'OCIS' in db.tables:
            rows = [(c, t, s, p) for t, v in sorted(hist.items()) for c, s, p in v]
            fill(db['OCIS'], rows, ('CCID', 'TGID', 'SEYR', 'COPS'))
            db.fix()
    # DB_TEAMS.dat: each team's own rows, growing a team DB whose table is too small
    data_at, entries = headshots.terf_entries(teams)
    replace, grown = {}, []
    for db in dbs(teams):
        if 'OCIS' not in db.tables or 'COCH' not in db.tables:
            continue
        tid = db['COCH'].get(0, 'TGID')
        ocis = [(c, tid, s, p) for c, s, p in hist.get(tid, [])]
        otrs = [(tid, y - base) + recs[tid, y] for y in range(FIRST_SEASON, base) if (tid, y) in recs] if base else []
        need = {n: len(v) for n, v in (('OCIS', ocis), ('OTRS', otrs)) if len(v) > db[n].capacity}
        if need:
            k = next(k for k, (o, s) in enumerate(entries) if data_at + o == db.off)
            assert entries[k][1] == db.size, f'team {tid} DB does not fill its archive entry'
            db = tdb.DB(db.resized(need), 0)
            grown.append((tid, need))
        fill(db['OCIS'], ocis, ('CCID', 'TGID', 'SEYR', 'COPS'))
        fill(db['OTRS'], otrs, ('TGID', 'SEYR', 'TSRW', 'TSRO', 'TSRI', 'TSRL'))
        db.fix()
        assert db.verify()
        if need:
            replace[k] = db.buf
    if replace:
        teams = repack(teams, replace)
    return teams, hist, grown


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('template')
    ap.add_argument('teams')
    ap.add_argument('games', nargs='?')
    ap.add_argument('--year', type=int)
    ap.add_argument('--clear', action='store_true')
    ap.add_argument('--out-dir')
    a = ap.parse_args()
    assert a.clear or (a.year and a.games), 'give --year and the schedule, or --clear'
    template = bytearray(open(a.template, 'rb').read())
    teams = bytearray(open(a.teams, 'rb').read())
    teams, hist, grown = apply(template, teams, a.games, None if a.clear else a.year)
    out = a.out_dir
    for path, buf in ((a.template, template), (a.teams, teams)):
        dst = os.path.join(out, os.path.basename(path)) if out else path
        open(dst, 'wb').write(buf)
    print(f'coach history: {sum(map(len, hist.values()))} rows over {len(hist)} teams'
          + (f'; grew {len(grown)} team DBs: {grown}' if grown else ''))


if __name__ == '__main__':
    main()
