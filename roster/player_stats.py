"""Give a built roster its players' real NFL stats: recent seasons and career totals.

Usage: python player_stats.py TEMPLATE_IN STATS_DIR TEMPLATE_OUT [--teams DB_TEAMS_IN DB_TEAMS_OUT]
                              [--seasons 5] [--last 2025] [--report CSV]

TEMPLATE_IN is a template.dat with the roster already in it (build_roster.py empties
the stats tables). STATS_DIR holds nflverse's open data, downloaded by hand:
  players.csv                 github.com/nflverse/nflverse-data/releases/download/players/
  stats_player_reg_YYYY.csv   .../releases/download/stats_player/   (1999 to --last)

Each player with at least one year in the league is matched to nflverse by name, then by
age, position, team and jersey number. Matched players get:
  - a row a season for the last --seasons seasons (SEYR -1 is --last, the season before
    the franchise's first), in PSNG (games and team), PSOF, PSDE, PSKI and PSKP;
  - career totals over every season since 1999, in PCNG, PCOF, PCDE, PCKI and PCKP.
Only the fields the stock roster fills are written, plus sacks taken, passes defended and
tackles for loss. Longest plays, field goals by distance and the linemen's tables
(PSOL, PCOL) stay empty: nflverse has no season totals for them.

template.dat's copy shows in the main menu's Rosters screen. A new franchise takes its
stats from each team's own DB in DB_TEAMS.dat, so pass --teams as well: the 32 current
teams' DBs and the free agents' get their players' rows.

Tables grow when they have to, and the archives are repacked, so fe.qkl needs a re-sync.
Row counts are kept under the franchise's own capacities (docs/findings.md section 11).
The report lists every player and what he was matched to.
"""
import argparse, collections, csv, os, sys, unicodedata

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'patches'))
import tdb
from headshots import terf_entries
from season17 import repack

ROSTER = 0x180
QB, HB, FB, WR, TE, LT, LG, C, RG, RT, LE, RE, DT, LOLB, MLB, ROLB, CB, FS, SS, K, P = range(21)
OFFENSE = {QB, HB, FB, WR, TE}
DEFENSE = {LE, RE, DT, LOLB, MLB, ROLB, CB, FS, SS}
GROUPS = {QB: {'QB'}, HB: {'RB'}, FB: {'RB', 'TE'}, WR: {'WR'}, TE: {'TE'}, K: {'SPEC'}, P: {'SPEC'},
          **{p: {'OL', 'SPEC'} for p in (LT, LG, C, RG, RT)},      # long snappers are centres here
          **{p: {'DL', 'LB'} for p in (LE, RE, DT, LOLB, MLB, ROLB)},
          **{p: {'DB', 'LB'} for p in (CB, FS, SS)}}
OLD_TEAMS = {'LA': 'LAR', 'STL': 'LAR', 'OAK': 'LV', 'SD': 'LAC'}
SUFFIXES = {'jr', 'sr', 'ii', 'iii', 'iv', 'v'}

# Rows a new franchise may start with: its table capacity, less room for a few seasons.
LIMITS = {'PSNG': 7000, 'PSOF': 2600, 'PSDE': 4200, 'PSKI': 500, 'PSKP': 500,
          'PCNG': 1900, 'PCOF': 620, 'PCDE': 1000, 'PCKI': 80, 'PCKP': 250}

num = lambda r, k: float(r.get(k) or 0)


def norm(s):
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode().lower()
    words = ''.join(c if c.isalnum() or c == ' ' else '' for c in s.replace('-', ' ')).split()
    return ''.join(w for w in words if w not in SUFFIXES)


def load_people(path, last):
    by_name = collections.defaultdict(list)
    for r in csv.DictReader(open(path, encoding='utf8')):
        if not r['gsis_id'] or int(r['last_season'] or 0) < last - 1:
            continue
        ln = norm(r['last_name'])
        firsts = {norm(r[k]) for k in ('first_name', 'common_first_name', 'football_name') if r[k]}
        for fn in firsts:
            by_name[fn, ln].append(r)
        by_name[norm(r['display_name']), ''].append(r)
    return by_name


def match(p, by_name, teams, last):
    """(nflverse row or None, 'high' | 'medium' | 'none', note)"""
    fn, ln = norm(p['PFNA']), norm(p['PLNA'])
    cands = {r['gsis_id']: r for r in by_name.get((fn, ln), []) + by_name.get((fn + ln, ''), [])}
    how = 'name'
    if not cands:      # a shortened first name or half of a two-part surname
        same = lambda l: l == ln or (len(ln) >= 5 and l.startswith(ln))
        cands = {r['gsis_id']: r for (f, l), rs in by_name.items() if l and same(l) and f[:1] == fn[:1] for r in rs}
        how = 'part'
    scored = []
    for r in cands.values():
        born = int(r['birth_date'][:4]) if r['birth_date'] else 0
        off = abs((last + 1 - born) - p['PAGE']) if born else 9
        s = (max(0, 3 - max(off, 1) + 1) * (off <= 2) + 2 * (r['position_group'] in GROUPS[p['PPOS']])
             + 2 * (OLD_TEAMS.get(r['latest_team'], r['latest_team']) == teams.get(p['TGID']))
             + (r['jersey_number'] == str(p['PJEN'])) + (int(r['last_season']) > last))
        scored.append((s, off <= 2 and r['position_group'] in GROUPS[p['PPOS']], r))
    scored.sort(key=lambda x: -x[0])
    if not scored:
        return None, 'none', 'no one by that name'
    s, fits, r = scored[0]
    clear = len(scored) == 1 or s - scored[1][0] >= 2
    if how == 'name' and fits and clear:
        return r, 'high', ''
    if fits and s >= 6 and clear:
        return r, 'medium', f'name differs: {r["display_name"]}'
    return None, 'none', f'unsure: {r["display_name"]} ({r["position"]}, {r["latest_team"]}, born {r["birth_date"]})'


def season_rows(stats_dir, first, last):
    """{gsis_id: {season: csv row}}"""
    out = collections.defaultdict(dict)
    for y in range(first, last + 1):
        path = os.path.join(stats_dir, f'stats_player_reg_{y}.csv')
        if not os.path.exists(path):
            raise SystemExit(f'missing {path}')
        for r in csv.DictReader(open(path, encoding='utf8')):
            out[r['player_id']][y] = r
    return out


def figures(r):
    """One season's csv row as the game's stats, keyed by field name without its s/c prefix."""
    n = lambda k: int(num(r, k) + 0.5) if num(r, k) >= 0 else -int(-num(r, k) + 0.5)
    ints, dtd = n('def_interceptions'), n('def_tds')
    return {
        'of': dict(cca=n('receptions'), aya=n('passing_yards'), cya=n('receiving_yards'), uya=n('rushing_yards'),
                   atd=n('passing_tds'), ctd=n('receiving_tds'), utd=n('rushing_tds'), acm=n('completions'),
                   ain=n('passing_interceptions'), aat=n('attempts'), uat=n('carries'),
                   ufu=n('rushing_fumbles') + n('receiving_fumbles') + n('sack_fumbles'), asa=n('sacks_suffered')),
        'de': dict(dta=n('def_tackles_solo') + n('def_tackles_with_assist') + n('def_tackle_assists'), lff=n('def_fumbles_forced'),
                   lsk=n('def_sacks'), sin=ints, lfr=n('fumble_recovery_opp'), siy=n('def_interception_yards'),
                   sit=dtd if ints else 0, lft=0 if ints else dtd,
                   dpd=n('def_pass_defended'), dtl=n('def_tackles_for_loss')),
        'ki': dict(kea=n('pat_att'), kem=n('pat_made'), kfa=n('fg_att'), kfm=n('fg_made'), keb=n('pat_blocked'),
                   kfb=n('fg_blocked'), pat=n('pt_att'), pya=n('pt_yards'), ptb=n('pt_touchback'),
                   ppt=n('pt_inside_20'), pbl=n('pt_blocked')),
        'kp': dict(rka=n('kickoff_returns'), rky=n('kickoff_return_yards'), rpa=n('punt_returns'),
                   rpy=n('punt_return_yards')),
        'games': n('games'), 'team': OLD_TEAMS.get(r['recent_team'], r['recent_team']),
    }


def wanted(kind, f, pos, career):
    """Does this player get a row in this table?"""
    if kind == 'of':
        touches = f['aat'] + f['uat'] + f['cca']
        return touches > 0 if pos in OFFENSE else touches >= (20 if career else 5)
    if kind == 'de':
        if pos in DEFENSE:
            return any(f[k] for k in ('dta', 'lsk', 'sin', 'lff', 'lfr'))
        return f['dta'] >= (25 if career else 8)
    if kind == 'ki':
        return f['kea'] + f['kfa'] + f['pat'] > 0
    return f['rka'] + f['rpa'] > 0


def write(t, rows):
    t.count = len(rows)
    for i, row in enumerate(rows):
        t.set_raw(i, bytes(t.reclen))
        for k, v in row.items():
            if k not in t.fields:
                continue
            f = t.fields[k]
            lo, hi = (-(1 << (f.bits - 1)), (1 << (f.bits - 1)) - 1) if f.typ == 2 else (0, (1 << f.bits) - 1)
            t.set(i, k, max(lo, min(hi, v)))


def fill(db, rows):
    """Write {table: rows} into a DB, growing tables that are too small; returns its bytes."""
    grow = {name: len(r) for name, r in rows.items() if len(r) > db[name].capacity}
    if grow:
        db = tdb.DB(db.resized(grow), 0)
    for name, r in rows.items():
        write(db[name], r)
    db.fix()
    assert db.verify()
    return db.buf[db.off:db.off + db.size]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('template'), ap.add_argument('stats_dir'), ap.add_argument('out')
    ap.add_argument('--seasons', type=int, default=5)
    ap.add_argument('--last', type=int, default=2025, help='the last finished NFL season')
    ap.add_argument('--report')
    ap.add_argument('--teams', nargs=2, metavar=('DB_TEAMS_IN', 'DB_TEAMS_OUT'))
    a = ap.parse_args()

    buf = bytearray(open(a.template, 'rb').read())
    league = tdb.DB(buf, ROSTER)
    teams = {r['TGID']: r['TSNA'] for r in league['TEAM'].rows()}
    tgid = {v: k for k, v in teams.items()}
    data_at, ents = terf_entries(buf)
    # the franchise DB has these tables too; the default roster's stats are in the smaller DB
    entry = min((k for k, (o, s) in enumerate(ents) if buf[data_at + o:data_at + o + 4] == b'DB\x00\x08'
                 and 'PCNG' in tdb.DB(buf, data_at + o).tables), key=lambda k: ents[k][1])
    stats = tdb.DB(bytearray(buf[data_at + ents[entry][0]:data_at + sum(ents[entry])]), 0)

    by_name = load_people(os.path.join(a.stats_dir, 'players.csv'), a.last)
    seasons = season_rows(a.stats_dir, 1999, a.last)
    rows = collections.defaultdict(list)       # table -> [(weight, row)]
    report, tally = [], collections.Counter()
    for p in league['PLAY'].rows():
        if p['PYRP'] == 0:
            tally['rookies'] += 1
            continue
        who, conf, note = match(p, by_name, teams, a.last)
        mine = seasons.get(who['gsis_id'], {}) if who else {}
        tally[conf if mine or not who else 'no stats'] += 1
        report.append(dict(pgid=p['PGID'], team=teams.get(p['TGID'], p['TGID']), pos=p['PPOS'],
                           first=p['PFNA'], last=p['PLNA'], age=p['PAGE'], match=conf,
                           gsis_id=who['gsis_id'] if who else '', nflverse=who['display_name'] if who else '',
                           seasons=len(mine), note=note))
        if not mine:
            continue
        pg, pos = p['PGID'], p['PPOS']
        career = collections.defaultdict(collections.Counter)
        games = 0
        for y, r in sorted(mine.items()):
            f = figures(r)
            games += f['games']
            seyr = y - a.last - 1
            for kind in ('of', 'de', 'ki', 'kp'):
                career[kind].update(f[kind])
                if seyr >= -a.seasons and wanted(kind, f[kind], pos, False):
                    rows['PS' + kind.upper()].append((sum(abs(v) for v in f[kind].values()),
                                                      dict(PGID=pg, SEYR=seyr, **{'s' + k: v for k, v in f[kind].items()})))
            if seyr >= -a.seasons and f['games']:
                rows['PSNG'].append((f['games'], dict(PGID=pg, SEYR=seyr, sgmp=f['games'],
                                                      sgYY=tgid.get(f['team'], p['TGID'] if p['TGID'] in teams and p['TGID'] < 1000 else 1))))
        if games:
            rows['PCNG'].append((games, dict(PGID=pg, cgmp=games)))
        for kind in ('of', 'de', 'ki', 'kp'):
            if wanted(kind, career[kind], pos, True):
                rows['PC' + kind.upper()].append((sum(abs(v) for v in career[kind].values()),
                                                  dict(PGID=pg, **{'c' + k: v for k, v in career[kind].items()})))

    for name, limit in LIMITS.items():
        keep = sorted(rows[name], key=lambda x: -x[0])[:limit]      # over the limit: the smallest lines go
        if len(keep) < len(rows[name]):
            print(f'  {name}: dropped the {len(rows[name]) - len(keep)} smallest rows to stay at {limit}')
        rows[name] = sorted((r for _, r in keep), key=lambda r: (r['PGID'], r.get('SEYR', 0)))
        print(f'  {name}: {len(rows[name]):5,} rows')
    out = repack(buf, {entry: fill(stats, rows)})
    open(a.out, 'wb').write(out)
    print(f'{os.path.basename(a.out)}: {len(buf):,} -> {len(out):,} bytes')

    # A new franchise takes its stats from the teams' own DBs in DB_TEAMS.dat, not from template.dat.
    if a.teams:
        tbuf = bytearray(open(a.teams[0], 'rb').read())
        data_at, ents = terf_entries(tbuf)
        replace, seen, placed = {}, set(), 0
        for k, (o, size) in enumerate(ents):
            if tbuf[data_at + o:data_at + o + 4] != b'DB\x00\x08':
                continue
            db = tdb.DB(bytearray(tbuf[data_at + o:data_at + o + size]), 0)
            if not {'PLAY', 'TEAM', 'PCNG'} <= set(db.tables) or not db['TEAM'].count:
                continue
            tid = db['TEAM'].get(0, 'TGID')
            if tid not in teams or tid in seen:      # the 32 current teams and the free agents, once each
                continue
            seen.add(tid)
            ids = {r['PGID'] for r in db['PLAY'].rows()}
            mine = {name: [r for r in rows[name] if r['PGID'] in ids] for name in LIMITS}
            placed += len(mine['PCNG'])
            replace[k] = fill(db, mine)
        assert len(seen) == len(teams), f'found {len(seen)} of {len(teams)} team DBs'
        tout = repack(tbuf, replace)
        open(a.teams[1], 'wb').write(tout)
        print(f'{os.path.basename(a.teams[1])}: {len(tbuf):,} -> {len(tout):,} bytes, '
              f'{placed:,} of {len(rows["PCNG"]):,} players placed in {len(seen)} team DBs')
    print(f'players: {dict(tally)}')
    if a.report:
        with open(a.report, 'w', newline='', encoding='utf8') as f:
            w = csv.DictWriter(f, list(report[0]))
            w.writeheader()
            w.writerows(report)


if __name__ == '__main__':
    main()
