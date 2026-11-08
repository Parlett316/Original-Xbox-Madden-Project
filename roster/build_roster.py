"""Build a Madden 09 (Xbox) default roster from EA ratings-site data.

Usage: python build_roster.py RATINGS.json GAME_DIR OUT_DIR [--photos DIR] [--keep-team-names]
                              [--keep-coaches] [--coach-photos DIR] [--free-agents JSON]

GAME_DIR is the original 'Madden NFL 09 (USA)' folder (read only). Writes
OUT_DIR/data/template.dat and OUT_DIR/data/DB_TEAMS.dat, plus a CSV report.
With --photos (EA headshots from fetch_headshots.py) it also writes
OUT_DIR/data/uis_plyr.dat with those headshots and sets skin tone from them.

How values are produced:
  - Ratings: each EA rating is turned into a percentile within its position
    and mapped onto 09's own distribution for that rating and position, so
    the league keeps the balance 09 was tuned for. A QB's awareness is then
    raised to within QB_AWARENESS_GAP of his overall, because EA rates some
    mobile starters far below their overall.
  - Appearance and equipment: copied from a 2008 player at the same position
    and skin tone with a generic face, close in weight.
  - Contracts: the 2008 contract at the same position and the same rank.
  - Rosters are cut to each team's original 09 size (the per-team DBs in
    DB_TEAMS.dat are packed to that size); cuts become free agents.
  - Team names: relocated/renamed current teams get their modern names
    (TEAM_RENAMES); the classic teams keep theirs. Coaches: the 2026 staffs
    from coaches.py. --keep-team-names / --keep-coaches leave them stock.
    With --coach-photos (from fetch_coach_photos.py) it also writes
    OUT_DIR/data/uis_coac.dat with their photos.
  - --free-agents (from pick_free_agents.py) adds players after everyone else, with
    their own random numbers and no photo, so no other player changes. DB_TEAMS.dat's free-agent DB
    grows to fit, and the archive entries after it move.
"""
import bisect, collections, csv, json, os, random, struct, sys, unicodedata

from PIL import Image

import coaches
import headshots
import tdb

ROSTER_DB = 0x180          # league roster DB inside template.dat
STATS_DB = 0x16ad00        # career/season stats DB inside template.dat
FA_TEAM = 1009
NO_ROLE = 45
NO_COMMENTARY = 999
UNDRAFTED_PICK, UNDRAFTED_ROUND = 63, 15
STATS_TABLES = ('PCDE', 'PCKI', 'PCKP', 'PCNG', 'PCOF', 'PCOL',
                'PSDE', 'PSKI', 'PSKP', 'PSNG', 'PSOF', 'PSOL', 'PICO')

QB, HB, FB, WR, TE, LT, LG, C, RG, RT, LE, RE, DT, LOLB, MLB, ROLB, CB, FS, SS, K, P = range(21)
KR, PR, KOS, LS_SLOT, RB3 = range(21, 26)
EA_POS = {'QB': QB, 'HB': HB, 'FB': FB, 'WR': WR, 'TE': TE, 'LT': LT, 'LG': LG,
          'C': C, 'RG': RG, 'RT': RT, 'LEDG': LE, 'REDG': RE, 'DT': DT,
          'SAM': LOLB, 'MIKE': MLB, 'WILL': ROLB, 'CB': CB, 'FS': FS, 'SS': SS,
          'K': K, 'P': P, 'LS': C}

# Fewest players per position a 09 team should carry, and who can fill in.
MINIMUM = {QB: 2, HB: 3, FB: 1, WR: 5, TE: 3, LT: 2, LG: 2, C: 2, RG: 2, RT: 2,
           LE: 2, RE: 2, DT: 4, LOLB: 2, MLB: 2, ROLB: 2, CB: 5, FS: 2, SS: 2,
           K: 1, P: 1}
FILL_IN = {QB: [], HB: [FB], FB: [HB, TE], WR: [], TE: [FB], LT: [RT, LG, RG],
           RT: [LT, RG, LG], LG: [RG, C, LT, RT], RG: [LG, C, RT, LT], C: [LG, RG],
           LE: [RE, DT, LOLB, ROLB], RE: [LE, DT, ROLB, LOLB], DT: [LE, RE],
           LOLB: [ROLB, MLB, LE, RE], ROLB: [LOLB, MLB, RE, LE], MLB: [LOLB, ROLB],
           CB: [FS, SS], FS: [SS, CB], SS: [FS, CB], K: [P], P: [K]}

TEAM_RENAMES = {8: ('Los Angeles', 'Chargers', 'LAC'),
                23: ('Las Vegas', 'Raiders', 'LV'),
                24: ('Los Angeles', 'Rams', 'LAR'),
                26: ('Washington', 'Commanders', 'WAS')}

COLLEGE_ALIASES = {
    'Texas AM': 'Texas A&M', 'South Carolina': 'S. Carolina', 'North Carolina': 'N. Carolina',
    'Boston College': 'Boston Coll.', 'Mississippi St.': 'Miss. State',
    'Central Michigan': 'Central MI', 'San Diego St.': 'S.D. State', 'East Carolina': 'E. Carolina',
    'William  Mary': 'Will. & Mary', 'Bowling Green St.': 'Bowl. Green',
    'Eastern Michigan': 'East. Mich.', 'Stephen F. Austin': 'S.F. Austin',
    'Youngstown St.': 'Youngstwn St.', 'Sacramento State': 'Cal-Sacrmnto',
    'IUP': 'Indiana(Penn.)', 'Florida AM': 'Florida A&M', 'Alabama AM': 'Alabama A&M',
    'Jacksonville State': 'Jacksonv. St.', 'Texas AM-Commerce': 'T A&M K\'ville',
    'Wisc-Whitewater': 'UW Lacrosse', 'Manitoba': 'No College', 'UBC': 'No College',
    'Appalachian St.': 'Appalach. St.', 'Miami (FL)': 'Miami', 'Miami (OH)': 'Miami Univ.',
    'Louisiana Tech': 'LA. Tech', 'Middle Tennessee': 'Mid Tenn St.',
    'Western Michigan': 'W. Michigan', 'Northern Illinois': 'N. Illinois',
    'Western Kentucky': 'W. Kentucky', 'Southern Mississippi': 'Southern Miss',
    'Washington St.': 'Wash. St.', 'Louisiana-Lafayette': 'UL Lafayette',
    'Louisiana': 'UL Lafayette', 'Louisiana-Monroe': 'UL Monroe', 'Pittsburgh St.': 'Pittsburg St.',
    'Mississippi': 'Ole Miss', 'South Florida': 'USF', 'Central Florida': 'UCF',
    'North Carolina St.': 'N.C. State', 'NC State': 'N.C. State',
}

# 09 rating field -> function of the EA stats dict.
def _avg(*keys):
    return lambda s: round(sum(s[k] for k in keys) / len(keys))

RATING_SOURCES = {
    'PSPD': _avg('speed'), 'PACC': _avg('acceleration'),
    'PAGI': _avg('agility', 'changeOfDirection'), 'PSTR': _avg('strength'),
    'PAWR': _avg('awareness'), 'PCTH': _avg('catching'), 'PCAR': _avg('carrying'),
    'PBTK': _avg('breakTackle'), 'PTAK': _avg('tackle'), 'PTHP': _avg('throwPower'),
    'PTHA': _avg('throwAccuracyShort', 'throwAccuracyMid', 'throwAccuracyDeep'),
    'PKPR': _avg('kickPower'), 'PKAC': _avg('kickAccuracy'),
    'PPBK': _avg('passBlock'), 'PRBK': _avg('runBlock'), 'PJMP': _avg('jumping'),
    'PKRT': _avg('kickReturn'), 'PSTA': _avg('stamina'), 'PINJ': _avg('injury'),
    'PTGH': _avg('toughness'), 'POVR': _avg('overall'), 'PIMP': _avg('overall'),
}
DEFENSE = {LE, RE, DT, LOLB, MLB, ROLB, CB, FS, SS}
QB_AWARENESS_GAP = 12      # a QB's awareness is at most this far below his overall
CONTRACT_FIELDS = ('PTSA', 'PSBO', 'PCON', 'PCYL', 'PTEN')


def ascii_name(s):
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode()
    return s.strip()


SUFFIXES = {'jr', 'jr.', 'sr', 'sr.', 'ii', 'iii', 'iv', 'v'}


def fit_name(s, width):
    s = ascii_name(s)
    words = s.split()
    while len(words) > 1 and words[-1].lower() in SUFFIXES:
        words.pop()
    s = ' '.join(words)
    if len(s) <= width:
        return s
    if '-' in s and len(s.split('-')[0]) <= width:  # hyphenated: keep first part
        return s.split('-')[0]
    return s[:width]


class Quantiles:
    """Map a value's percentile in one sample onto another sample."""

    def __init__(self, src, dst):
        self.src, self.dst = sorted(src), sorted(dst)

    def __call__(self, v):
        lo = bisect.bisect_left(self.src, v)
        hi = bisect.bisect_right(self.src, v)
        q = ((lo + hi) / 2) / len(self.src)
        x = q * (len(self.dst) - 1)
        i = int(x)
        j = min(i + 1, len(self.dst) - 1)
        return round(self.dst[i] + (self.dst[j] - self.dst[i]) * (x - i))


def find_dbs(buf):
    out, i = [], buf.find(b'DB\x00\x08')
    while i != -1:
        try:
            db = tdb.DB(buf, i)
            if 0 < len(db.order) < 300:
                out.append(db)
        except Exception:
            pass
        i = buf.find(b'DB\x00\x08', i + 4)
    return out


def repack(buf, replace):
    """Rebuild a TERF archive with entries {index: new bytes}; others kept."""
    align = 0x40
    data_at, ents = headshots.terf_entries(buf)
    d1 = struct.unpack_from('<I', buf, 4)[0]   # DIR1 follows the header
    out = bytearray(buf[:data_at + align])
    pos = align
    for k, (o, s) in enumerate(ents):
        body = replace.get(k, buf[data_at + o:data_at + o + s])
        assert pos == len(out) - data_at
        struct.pack_into('<II', out, d1 + 8 + 8 * k, pos, len(body))
        out += body
        pos = -(-(pos + max(len(body), 1)) // align) * align
        out += bytes(pos - (len(out) - data_at))
    struct.pack_into('<I', out, data_at + 4, len(out) - data_at)
    return out


def main(ratings_path, game_dir, out_dir, photos_dir=None, keep_team_names=False, keep_coaches=False,
         coach_photos_dir=None, free_agents=None):
    rng = random.Random(2027)
    ea = json.load(open(ratings_path, encoding='utf8'))['items']
    tpl = bytearray(open(os.path.join(game_dir, 'data', 'template.dat'), 'rb').read())
    teams_buf = bytearray(open(os.path.join(game_dir, 'data', 'DB_TEAMS.dat'), 'rb').read())
    strm = bytearray(open(os.path.join(game_dir, 'data', 'strmdata.db'), 'rb').read())

    league = tdb.DB(tpl, ROSTER_DB)
    PLAY = league['PLAY']
    old = PLAY.rows()
    old_raw = [PLAY.raw(i) for i in range(PLAY.count)]
    colleges = {r['CONA']: r['COID'] for r in tdb.DB(strm, 0)['COLL'].rows()}

    # Per-team DBs in DB_TEAMS.dat: team id -> DB, and their packed roster sizes.
    team_dbs, fa_db = {}, None
    for db in find_dbs(teams_buf):
        if 'PLAY' not in db.tables or 'TEAM' not in db.tables:
            continue
        tid = db['TEAM'].get(0, 'TGID')
        if 1 <= tid <= 32 and tid not in team_dbs:
            team_dbs[tid] = db
        elif tid == FA_TEAM and fa_db is None:
            fa_db = db
    assert len(team_dbs) == 32 and fa_db is not None
    roster_size = {t: db['PLAY'].capacity for t, db in team_dbs.items()}

    # Player IDs in use anywhere: new players get IDs outside this set, so no
    # leftover row (stats, icons, rookie lists) attaches to them.
    used_ids = set()
    for buf in (tpl, teams_buf, strm):
        for db in find_dbs(buf):
            for t in db.order:
                if 'PGID' in t.fields:
                    used_ids.update(t.get(i, 'PGID') for i in range(t.count))

    # ---- players: position, team, ratings ------------------------------------
    players = []
    for it in ea:
        s = {k: v['value'] for k, v in it['stats'].items()}
        players.append(dict(ea=it, s=s, pos=EA_POS[it['position']['id']],
                            ea_pos=it['position']['id'], team=it['team']['id'],
                            ovr=s['overall']))

    # ---- roster cuts with position minimums ----------------------------------
    by_team = collections.defaultdict(list)
    for p in players:
        by_team[p['team']].append(p)
    for t, plist in by_team.items():
        plist.sort(key=lambda p: -p['ovr'])
        keep, pool = [], list(plist)
        # long snapper first so the team keeps one
        for p in pool:
            if p['ea_pos'] == 'LS':
                keep.append(p); pool.remove(p); break
        def short(pos):
            have = sum(1 for p in keep if p['pos'] == pos and p['ea_pos'] != 'LS')
            return MINIMUM[pos] - have
        # pass 1: each position from its own players
        for pos in MINIMUM:
            for p in [p for p in pool if p['pos'] == pos][:max(0, short(pos))]:
                keep.append(p); pool.remove(p)
        # pass 2: remaining gaps from unkept players at related positions,
        # then from kept players at a related position that has a surplus or
        # can itself be refilled from the pool (e.g. edge -> OLB, DT -> edge);
        # repeated so those chains settle.
        def refillable(pos):
            return any(p['pos'] in [pos] + FILL_IN[pos] for p in pool)
        for _ in range(4):
            for pos in MINIMUM:
                for cand_pos in FILL_IN[pos]:
                    for p in [p for p in pool if p['pos'] == cand_pos]:
                        if short(pos) <= 0:
                            break
                        p['pos'] = pos
                        keep.append(p); pool.remove(p)
                for cand_pos in FILL_IN[pos]:
                    for p in sorted((p for p in keep if p['pos'] == cand_pos and p['ea_pos'] != 'LS'),
                                    key=lambda p: p['ovr']):
                        if short(pos) <= 0 or (short(cand_pos) >= 0 and not refillable(cand_pos)):
                            break
                        p['pos'] = pos
            for pos in MINIMUM:  # refill anything the moves left short
                for p in [p for p in pool if p['pos'] == pos][:max(0, short(pos))]:
                    keep.append(p); pool.remove(p)
        for p in pool:
            if len(keep) >= roster_size[t]:
                break
            keep.append(p)
        keep = keep[:roster_size[t]]
        for p in plist:
            if p not in keep:
                p['team'] = FA_TEAM

    # Teams EA lists too thin at a position sign the best cut player there,
    # releasing their weakest player at a position with a surplus.
    for t in range(1, 33):
        for pos, need in MINIMUM.items():
            while True:
                team = [p for p in players if p['team'] == t]
                if sum(1 for p in team if p['pos'] == pos and p['ea_pos'] != 'LS') >= need:
                    break
                fas = [p for p in players if p['team'] == FA_TEAM and p['pos'] in [pos] + FILL_IN[pos]]
                count = collections.Counter(p['pos'] for p in team if p['ea_pos'] != 'LS')
                spare = [p for p in team if p['ea_pos'] != 'LS' and count[p['pos']] > MINIMUM[p['pos']]]
                if not fas or not spare:
                    break
                sign = max(fas, key=lambda p: p['ovr'])
                cut = min(spare, key=lambda p: p['ovr'])
                sign['team'], sign['pos'] = t, pos
                cut['team'], cut['pos'] = FA_TEAM, EA_POS[cut['ea_pos']]
                print(f'team {t}: signed {sign["ea"]["lastName"]} ({sign["ea_pos"]}), '
                      f'released {cut["ea"]["lastName"]} ({cut["ea_pos"]})')

    # ---- added free agents: after every roster decision -------------------------
    if free_agents:
        for it in json.load(open(free_agents, encoding='utf8'))['items']:
            s = {k: v['value'] for k, v in it['stats'].items()}
            players.append(dict(ea=it, s=s, pos=EA_POS[it['playsAt']], ea_pos=it['position']['id'],
                                team=FA_TEAM, ovr=s['overall'], added=True))

    # ---- ratings by percentile within position --------------------------------
    old_by_pos = collections.defaultdict(list)
    for r in old:
        old_by_pos[r['PPOS']].append(r)
    ea_by_pos = collections.defaultdict(list)
    for p in players:
        if not p.get('added'):
            ea_by_pos[p['ea_pos']].append(p)
    maps = {}
    for p in players:
        key = (p['ea_pos'], p['pos'])
        if key not in maps:
            maps[key] = {f: Quantiles([fn(q['s']) for q in ea_by_pos[p['ea_pos']]],
                                      [r[f] for r in old_by_pos[p['pos']]])
                         for f, fn in RATING_SOURCES.items()}
        m = maps[key]
        s = dict(p['s'])
        if p['pos'] in DEFENSE:
            s['awareness'] = round((s['awareness'] + s['playRecognition']) / 2)
        p['r'] = {f: max(0, min(99, m[f](fn(s)))) for f, fn in RATING_SOURCES.items()}
        if p['pos'] == QB:
            p['r']['PAWR'] = max(p['r']['PAWR'], p['r']['POVR'] - QB_AWARENESS_GAP)

    # ---- appearance donors -----------------------------------------------------
    # Skin tone (PSKI 0 light .. 2 dark) from the EA headshot's face
    # brightness, split in the same proportions as 09's own roster, so the
    # donor's face model and skin match the player.
    face_count = collections.Counter(r['PFEx'] for r in old)
    donors = collections.defaultdict(list)
    for r, raw in zip(old, old_raw):
        if face_count[r['PFEx']] >= 5 and not r['PICN']:
            donors[r['PPOS'], r['PSKI']].append((r['PWGT'] + 160, raw))
            donors[r['PPOS'], None].append((r['PWGT'] + 160, raw))
    if photos_dir:
        for p in players:
            path = os.path.join(photos_dir, f"{p['ea']['id']}.png")
            if os.path.exists(path) and not p.get('added'):
                p['photo'] = headshots.ea_photo(path)
                p['bright'] = headshots.skin_brightness(p['photo'])
    lit = sorted((p for p in players if p.get('bright') is not None), key=lambda p: p['bright'])
    tones = collections.Counter(r['PSKI'] for r in old)
    dark_n = round(len(lit) * tones[2] / len(old))
    mid_n = round(len(lit) * tones[1] / len(old))
    for k, p in enumerate(lit):
        p['skin'] = 2 if k < dark_n else 1 if k < dark_n + mid_n else 0
    # ---- commentary names by surname ------------------------------------------
    voices = collections.defaultdict(list)
    for r in old:
        if r['PCMT'] != NO_COMMENTARY:
            voices[r['PLNA'].lower()].append((r['PFNA'].lower(), r['PCMT']))

    # ---- contracts by rank ------------------------------------------------------
    old_rost = collections.defaultdict(list)
    for r in old:
        if r['TGID'] != FA_TEAM:
            old_rost[r['PPOS']].append(r)
    for v in old_rost.values():
        v.sort(key=lambda r: -r['POVR'])
    old_rookies = sorted((r for r in old if r['TGID'] != FA_TEAM and r['PYRP'] == 0),
                         key=lambda r: -r['POVR'])
    old_fa = [r for r in old if r['TGID'] == FA_TEAM]
    new_rost = collections.defaultdict(list)
    for p in players:
        if p['team'] != FA_TEAM:
            new_rost[p['pos'] if p['ea']['yearsPro'] else 'R'].append(p)
    for key, plist in new_rost.items():
        plist.sort(key=lambda p: -p['r']['POVR'])
        src = old_rookies if key == 'R' else old_rost[key]
        for k, p in enumerate(plist):
            p['contract'] = src[min(len(src) - 1, round(k * (len(src) - 1) / max(1, len(plist) - 1)))]
    added_rng = random.Random(2026)
    for p in players:
        if p['team'] == FA_TEAM:
            p['contract'] = (added_rng if p.get('added') else rng).choice(old_fa)

    # ---- build records ---------------------------------------------------------
    unmatched_colleges = collections.Counter()
    next_id = 100
    order = sorted(players, key=lambda p: (p['team'], bool(p.get('added')), ascii_name(p['ea']['lastName']),
                                           ascii_name(p['ea']['firstName'])))
    assert len(order) <= PLAY.capacity

    # Headshots: PSXP n shows uis_plyr.dat entry n+1. Reuse the 2008 roster's
    # photo numbers, skipping any another roster (e.g. scenario teams) uses.
    if photos_dir:
        other_psxp = set()
        current = {(id(tpl), ROSTER_DB), (id(teams_buf), fa_db.off)} | \
                  {(id(teams_buf), db.off) for db in team_dbs.values()}
        for buf in (tpl, teams_buf):
            for db in find_dbs(buf):
                if 'PLAY' in db.tables and 'PSXP' in db['PLAY'].fields \
                        and (id(buf), db.off) not in current:
                    T = db['PLAY']
                    other_psxp.update(T.get(i, 'PSXP') for i in range(T.count))
        free = (n for n in range(1, max(r['PSXP'] for r in old) + 1) if n not in other_psxp)
        plyr = bytearray(open(os.path.join(game_dir, 'data', 'uis_plyr.dat'), 'rb').read())
        data_at, entries = headshots.terf_entries(plyr)
        for p in order:
            if 'photo' in p:
                n = next(free)
                off, size = entries[n + 1]
                a = data_at + off
                plyr[a:a + size] = headshots.encode(plyr[a:a + size], p['photo'])
                p['psxp'] = n

    for seq, p in enumerate(order, 1):
        it, r = p['ea'], p['r']
        while next_id in used_ids:
            next_id += 1
        p['pgid'] = next_id
        used_ids.add(next_id)
        wt = it['weight']
        pool = donors[p['pos'], p.get('skin')]
        if len(pool) < 3:
            pool = donors[p['pos'], None]
        cands = sorted(pool, key=lambda d: abs(d[0] - wt))[:6]
        PLAY.set_raw(seq - 1, (added_rng if p.get('added') else rng).choice(cands)[1])
        i = seq - 1
        first = fit_name(it['firstName'], PLAY.fields['PFNA'].bits // 8)
        last = fit_name(it['lastName'], PLAY.fields['PLNA'].bits // 8)
        p['first'], p['last'] = first, last
        PLAY.set(i, 'PFNA', first)
        PLAY.set(i, 'PLNA', last)
        for f, v in r.items():
            PLAY.set(i, f, v)
        college = COLLEGE_ALIASES.get(it['college'], it['college'])
        if college not in colleges:
            unmatched_colleges[it['college']] += 1
            college = 'N/A'
        cmt = NO_COMMENTARY
        v = voices.get(last.lower())
        if v:
            same_first = [c for f, c in v if f == first.lower()]
            cmt = (same_first or [c for _, c in v])[0]
        p['cmt'] = cmt
        c = p['contract']
        yrs = min(it['yearsPro'], 31)
        vals = dict(
            PGID=p['pgid'], POID=p['pgid'], TGID=p['team'], PPOS=p['pos'], POPS=p['pos'],
            PAGE=max(18, min(63, it['age'])), PYRP=yrs, PYWT=yrs,
            PHGT=it['height'], PWGT=max(0, min(255, wt - 160)),
            PJEN=it['jerseyNum'] if 0 <= it['jerseyNum'] <= 99 else 0,
            PHAN=1 if it['handedness'] == 0 else 0,
            PCOL=colleges[college], PCMT=cmt,
            PROL=NO_ROLE, PRL2=NO_ROLE, PICN=0, PFPB=0, PSXP=p.get('psxp', 0),
            PDPI=UNDRAFTED_PICK, PDRO=UNDRAFTED_ROUND, PPTI=1015,
        )
        for f in CONTRACT_FIELDS:
            vals[f] = c[f]
        vals['PVTS'], vals['PVSB'], vals['PVCO'] = c['PTSA'], c['PSBO'], c['PCON']
        for f, v in vals.items():
            PLAY.set(i, f, v)
    PLAY.count = len(order)

    # ---- depth charts -----------------------------------------------------------
    old_dc = league['DCHT'].rows()
    per_team = collections.Counter((d['TGID'], d['PPOS']) for d in old_dc)
    depth = {s: max(1, round(sum(per_team[(t, s)] for t in range(1, 33)) / 32)) for s in range(26)}
    charts = {}
    for t in range(1, 33):
        roster = [p for p in order if p['team'] == t]
        def best(pos, key='POVR', exclude=()):
            return sorted((p for p in roster if p['pos'] == pos and p not in exclude),
                          key=lambda p: -p['r'][key])
        rows = []
        for s in range(21):
            for d, p in enumerate(best(s)[:depth[s]]):
                rows.append((s, d, p))
        ret = sorted((p for p in roster if p['pos'] in (HB, WR, CB)), key=lambda p: -p['r']['PKRT'])
        rows += [(KR, d, p) for d, p in enumerate(ret[:depth[KR]])]
        rows += [(PR, d, p) for d, p in enumerate(ret[:depth[PR]])]
        rows += [(KOS, 0, p) for p in best(K, 'PKPR')[:1]]
        ls = [p for p in roster if p['ea_pos'] == 'LS'] or best(C)[-1:]
        rows += [(LS_SLOT, 0, p) for p in ls[:1]]
        rows += [(RB3, 0, p) for p in best(HB, 'PCTH', exclude=best(HB)[:1])[:1]]
        # trim deepest entries to fit the team DB's packed depth chart
        cap = team_dbs[t]['DCHT'].capacity
        rows.sort(key=lambda x: (x[1], x[0]))
        charts[t] = sorted(rows[:cap], key=lambda x: (x[0], x[1]))

    def write_chart(table, teams):
        n = 0
        for t in teams:
            for s, d, p in charts[t]:
                table.set(n, 'PGID', p['pgid']); table.set(n, 'TGID', t)
                table.set(n, 'PPOS', s); table.set(n, 'ddep', d)
                n += 1
        table.count = n

    write_chart(league['DCHT'], range(1, 33))
    league['INJY'].count = 0

    def rename(team_table):
        if keep_team_names:
            return
        for i in range(team_table.count):
            tid = team_table.get(i, 'TGID')
            if tid in TEAM_RENAMES:
                city, nick, abbr = TEAM_RENAMES[tid]
                team_table.set(i, 'TLNA', city); team_table.set(i, 'TDNA', nick)
                team_table.set(i, 'TMNC', nick); team_table.set(i, 'TSNA', abbr)

    rename(league['TEAM'])
    league.fix()

    # Coaches: the league/franchise DBs in template.dat and the per-team DBs in DB_TEAMS.dat.
    coach_dbs = [db for db in find_dbs(tpl) if 'COCH' in db.tables and db['COCH'].count]
    coach_dbs += [db for db in team_dbs.values() if 'COCH' in db.tables]
    if not keep_coaches:
        # the per-team tables hold only their own 4 coaches, so they take the moved coaches from the league table
        base = coaches.stock_rows(coach_dbs[0]['COCH'])
        coac, photos = None, None
        if coach_photos_dir:
            # menu photo CSXP n is uis_coac.dat entry n+1
            coac = bytearray(open(os.path.join(game_dir, 'data', 'uis_coac.dat'), 'rb').read())
            data_at, entries = headshots.terf_entries(coac)
            plan = coaches.photo_plan(coach_dbs[0]['COCH'], [size for _, size in entries])
            shots = {}
            for (tid, role), csxp in plan.items():
                path = os.path.join(coach_photos_dir, f'{tid}_{role}.jpg')
                if os.path.exists(path):
                    shots[tid, role] = csxp, Image.open(path).convert('RGBA').resize(
                        (headshots.PHOTO, headshots.PHOTO), Image.LANCZOS)
            for csxp, im in shots.values():
                off, size = entries[csxp + 1]
                a = data_at + off
                coac[a:a + size] = headshots.encode(coac[a:a + size], im)
            photos = {k: csxp for k, (csxp, _) in shots.items()}
            print(f'coach photos: {len(shots)} of {len(plan)}')
        renamed = [coaches.apply(db['COCH'], coaches.stock_rows(db['COCH']) if db['COCH'].count > 4 else base, photos)
                   for db in coach_dbs]
        print(f'coaches renamed: {renamed[:3]} in template.dat, {sum(renamed[3:])} in DB_TEAMS.dat')
        for db in coach_dbs[:3]:
            db.fix()
    stats = tdb.DB(tpl, STATS_DB)
    for nm in STATS_TABLES:
        if nm in stats.tables:
            stats[nm].count = 0
    stats.fix()

    # ---- DB_TEAMS.dat: same players, same depth charts ---------------------------
    index = {p['pgid']: i for i, p in enumerate(order)}
    def copy_players(db, plist):
        T = db['PLAY']
        assert len(plist) <= T.capacity, (db['TEAM'].get(0, 'TGID'), len(plist), T.capacity)
        for k, p in enumerate(plist):
            T.set_raw(k, PLAY.raw(index[p['pgid']]))
        T.count = len(plist)
        for nm in STATS_TABLES + ('INJY',):
            if nm in db.tables:
                db[nm].count = 0
    for t, db in team_dbs.items():
        copy_players(db, [p for p in order if p['team'] == t])
        write_chart(db['DCHT'], [t])
        rename(db['TEAM'])
        db.fix()
    fa_list = [p for p in order if p['team'] == FA_TEAM]
    if len(fa_list) > fa_db['PLAY'].capacity:
        data_at, entries = headshots.terf_entries(teams_buf)
        entry = next(k for k, (o, s) in enumerate(entries) if data_at + o == fa_db.off)
        assert entries[entry][1] == fa_db.size, 'free-agent DB does not fill its archive entry'
        grown = tdb.DB(fa_db.resized({'PLAY': len(fa_list)}), 0)
        copy_players(grown, fa_list)
        grown.fix()
        assert grown.verify()
        teams_buf = repack(teams_buf, {entry: grown.buf})
        print(f'free-agent DB grown to {len(fa_list)} players: entry {entry}, {fa_db.size:,} -> {grown.size:,} bytes')
    else:
        copy_players(fa_db, fa_list)
        fa_db.fix()

    # ---- write -----------------------------------------------------------------
    os.makedirs(os.path.join(out_dir, 'data'), exist_ok=True)
    open(os.path.join(out_dir, 'data', 'template.dat'), 'wb').write(tpl)
    open(os.path.join(out_dir, 'data', 'DB_TEAMS.dat'), 'wb').write(teams_buf)
    if not keep_coaches and coach_photos_dir:
        open(os.path.join(out_dir, 'data', 'uis_coac.dat'), 'wb').write(coac)
    if photos_dir:
        open(os.path.join(out_dir, 'data', 'uis_plyr.dat'), 'wb').write(plyr)
        print(f'headshots: {sum("psxp" in p for p in order)}; skin tone light/medium/dark: '
              f'{[sum(p.get("skin") == k for p in order) for k in (0, 1, 2)]}, '
              f'{sum("skin" not in p for p in order)} without a photo')
    with open(os.path.join(out_dir, 'roster_report.csv'), 'w', newline='', encoding='utf8') as f:
        w = csv.writer(f)
        w.writerow(['team', 'pos09', 'ea_pos', 'first', 'last', 'ea_ovr', 'ovr09', 'pgid',
                    'commentary', 'salary_k', 'years'] + [k for k in RATING_SOURCES if k not in ('POVR', 'PIMP')])
        for p in order:
            w.writerow([p['team'], p['pos'], p['ea_pos'], p['first'], p['last'], p['ovr'],
                        p['r']['POVR'], p['pgid'], p['cmt'], p['contract']['PTSA'],
                        p['contract']['PCON']] +
                       [p['r'][k] for k in RATING_SOURCES if k not in ('POVR', 'PIMP')])
    fa = sum(p['team'] == FA_TEAM for p in order)
    print(f'{len(order)} players: {len(order) - fa} rostered, {fa} free agents, '
          f'{sum(bool(p.get("added")) for p in order)} added')
    print(f'commentary names matched: {sum(p["cmt"] != NO_COMMENTARY for p in order)}')
    print(f'colleges defaulted to N/A: {sum(unmatched_colleges.values())} '
          f'({", ".join(c for c, _ in unmatched_colleges.most_common(8))}...)')
    print(f'player IDs {min(p["pgid"] for p in order)}..{max(p["pgid"] for p in order)}')


if __name__ == '__main__':
    argv = sys.argv[1:]
    photos = argv[argv.index('--photos') + 1] if '--photos' in argv else None
    coach_photos = argv[argv.index('--coach-photos') + 1] if '--coach-photos' in argv else None
    added = argv[argv.index('--free-agents') + 1] if '--free-agents' in argv else None
    args = [a for a in argv if not a.startswith('--') and a not in (photos, coach_photos, added)]
    main(*args, photos_dir=photos, keep_team_names='--keep-team-names' in argv,
         keep_coaches='--keep-coaches' in argv, coach_photos_dir=coach_photos, free_agents=added)
