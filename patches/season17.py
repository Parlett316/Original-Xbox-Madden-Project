"""Give Madden 09's franchise a 17-game, 18-week regular season (template.dat).

    python season17.py <in template.dat> <out template.dat> [<games.csv> [season]]
    python season17.py <in strmdata.db> <out strmdata.db>
    python season17.py <in default.xbe> <out default.xbe>

Run it on the roster build's template.dat (it shifts every DB after entry 4,
so it must be the last change to the file), then qkl_sync.py: fe.qkl preloads
template.dat's directory.

Schedules are data (docs/findings.md section 8). Entry 5's SCHD holds two
seasons; the game derives the week and round counts from the rows' week types
(SEWT 25 regular, 50/75/100/125 playoff rounds, 150 Pro Bowl; SEST 9
preseason). SESI 0 is year 1's, copied as is (0x41f2d7 sets SESI = SEYR > 0).
Every later year copies SESI 1 and a generator (0x41e280) rebuilds weeks 0-16:
standings-based matchups, every game re-dated, only the prime-time slots kept.
Its interconference games follow a 4-year rotation, AFC division a against NFC
division ROTATION[a][(SEYR + 2) & 3]. This
- drops the 4th preseason week (the NFL has played three since 2021),
- adds regular-season week 17, the modern 17th game: AFC division a against
  NFC division ROTATION[a][SEYR & 3], the one it played two years earlier, so
  nobody meets an opponent twice (or a rival three times); kickoff times are
  week 16's. From year 2 default.xbe recomputes these 16 games each year;
- with nflverse's games.csv (nfldata repository), replaces year 1 with a real
  NFL season's 272 games (default: the latest complete one): weeks, days
  (GDAT counts from Thursday; Wednesday games show as Thursday), Eastern
  kickoff times and the Thanksgiving flag (GFTG).
Playoffs move to weeks 18-21 and the Pro Bowl to week 22. The Pro Bowl week is
kept because box scores only last while their week is current: it is where
the Super Bowl's stats can be viewed. Schedule slots are TEAM.TORD - 1
(stock alphabetical order, so the Texans, TGID 32, are slot 29); divisions come
from entry 1's TEAM and are checked against the schedule (rivals meet twice).

Entry 4 is the empty franchise DB copied into new franchises. Its per-week
tables are sized for 21 weeks and grow by one week: SCHD (+16 games), OTIW
(+32 rows, 32 teams x 22 weeks), AWPL (+5 weekly awards). SCWE, the
progression checkpoint list, follows the schedule: the preseason checkpoint
moves to the 3rd preseason week (week 4 keeps a row: from year 2 the user
picks up to 4 preseason games), the new week joins the third period (its
checkpoint moves from week 16 to 17) and the playoff rows shift by one.
Only franchises started with this file get the new format.

strmdata.db (mode picked from the file): per-week owner tables stop at stock's
last team week. OWFW (fan weights, weeks 0-20) gets week 21 and OACI/OFAC
(weeks 0-16) get week 17, copies of the last stock week. A missing OWFW row
aborts end-of-week processing (0x3d96d3), so the stock game could never get
past a Super Bowl at week 21 (hardware tests 2 and 3; fixed in test 4).

default.xbe: the offseason start (0x3a9530) sets the week to 22 and inserts
its marker game (SEWT 175) at week 22, the week after stock's Pro Bowl. With
the Pro Bowl at week 22 both move to 23 (two push imm8 operands). The
generator's placement step (0x41d970) deletes the regular-season games it
will re-place (Sunday afternoon: GDAT 3, GTOD 750-1097) and every
regular-season game from week 17 on, so it deletes the 17th game (hardware:
year 2 had 17 weeks). It can't keep it either: its cursor over unplaced rows
(0x41dc6b) steps back after every row and only moves on once a row is filled,
so a week-17 row it has no game for hangs the game ("Advancing To Regular
Season", hardware). So the call (0x41e31e) goes to a cave after the awareness
fix's (needs that XBE): the stock step, then 16 inserts (its own query) for
week 17 from the generator's team tables (0x7ba440 AFC, 0x7ba460 NFC, 4 per
division) and its rotation table: game n is AFC division n // 4 team n % 4
against the same NFC team, Sunday 1:00, home side alternating by n and year.

With no change requested (--repack-only) the archive is rebuilt as is and
must match the input byte for byte.
"""
import csv
import datetime
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'roster'))
import tdb  # noqa: E402
from headshots import terf_entries  # noqa: E402

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'loadscreen'))
from xbe import XBE  # noqa: E402

ROSTER, FRANCHISE, LEAGUE = 1, 4, 5   # template.dat entries
ALIGN = 0x40
NEW_WEEK = 17                   # 0-based: the 18th week, after stock week 16
REGULAR, PRESEASON = 25, 9      # SEWT of regular-season games; SEST of preseason
OFFSEASON_WEEK = (0x3a9536, 0x3a957b)   # push 22 (6a 16): SEAI week, marker game week
# Year-2+ generator (0x41d6e0, table 0x7261bc): AFC division a plays NFC
# division ROTATION[a][(SEYR + 2) & 3] (divisions numbered DGID & 3).
ROTATION = ((1, 3, 2, 0), (2, 1, 0, 3), (0, 2, 3, 1), (3, 0, 1, 2))
ROTATION_VA = 0x7261bc                  # u16[4 * a + column]
AFC_TEAMS, NFC_TEAMS = 0x7ba440, 0x7ba460   # u16 team index [4 * division + i]
GENERATOR_CALL = 0x41e31e               # call 0x41d970 (push esi before it: the generator state)
PLACE, DB_EXEC = 0x41d970, 0x427eb0
INSERT_GAME = 0x650d68                  # the generator's insert (SEWN, SEWT, SGNM, GSTA, GHTG, GATG,
                                        # GHSC, GASC, GTOD, GDAT, GFHU)
KICKOFF = 780                           # week 17 from year 2: Sunday (GDAT 3) 1:00 pm
CAVE_VA = 0x10f60                       # header page, after the awareness fix's cave
# nflverse team codes -> TGID (stock 09 numbering)
TGID = dict(CHI=1, CIN=2, BUF=3, DEN=4, CLE=5, TB=6, ARI=7, LAC=8, KC=9, IND=10, DAL=11, MIA=12,
            PHI=13, ATL=14, SF=15, NYG=16, JAX=17, NYJ=18, DET=19, GB=20, CAR=21, NE=22, LV=23,
            LA=24, BAL=25, WAS=26, NO=27, SEA=28, PIT=29, TEN=30, MIN=31, HOU=32)
GDAT = dict(Wednesday=0, Thursday=0, Friday=1, Saturday=2, Sunday=3, Monday=4)


def repack(buf, replace):
    """Rebuild a TERF archive with entries {index: new bytes}; others kept."""
    data_at, ents = terf_entries(buf)
    d1 = struct.unpack_from('<I', buf, 4)[0]   # DIR1 follows the header
    out = bytearray(buf[:data_at + ALIGN])
    pos = ALIGN
    for k, (o, s) in enumerate(ents):
        body = replace.get(k, buf[data_at + o:data_at + o + s])
        assert pos == len(out) - data_at
        struct.pack_into('<II', out, d1 + 8 + 8 * k, pos, len(body))
        out += body
        pos = -(-(pos + max(len(body), 1)) // ALIGN) * ALIGN
        out += bytes(pos - (len(out) - data_at))
    struct.pack_into('<I', out, data_at + 4, len(out) - data_at)
    return out


def entry_db(buf, k):
    data_at, ents = terf_entries(buf)
    o, s = ents[k]
    return tdb.DB(bytearray(buf[data_at + o:data_at + o + s]), 0)


def write(t, rows):
    t.count = len(rows)
    for i, row in enumerate(rows):
        t.set_raw(i, bytes(t.reclen))
        for k, v in row.items():
            t.set(i, k, v)


def divisions(roster):
    """{schedule slot: (conference, division)} from the roster DB's TEAM."""
    return {r['TORD'] - 1: (r['CGID'], r['DGID'])
            for r in roster['TEAM'].rows() if 1 <= r['TGID'] <= 32}


def slots(roster):
    """{TGID: schedule slot}."""
    return {r['TGID']: r['TORD'] - 1 for r in roster['TEAM'].rows() if 1 <= r['TGID'] <= 32}


def opponents(season):
    met = {}
    for r in season:
        for a, b in ((r['GHTG'], r['GATG']), (r['GATG'], r['GHTG'])):
            met.setdefault(a, []).append(b)
    return met


def check(season, div, games):
    """Every team plays `games` games: rivals twice, everyone else at most once."""
    met = opponents(season)
    assert sorted(met) == sorted(div), 'not all 32 teams'
    for t, opps in met.items():
        assert len(opps) == games, f'slot {t}: {len(opps)} games'
        assert len({r['SEWN'] for r in season if t in (r['GHTG'], r['GATG'])}) == games, f'slot {t}: two games in a week'
        rivals = {o for o in opps if opps.count(o) == 2}
        assert rivals == {o for o in div if o != t and div[o] == div[t]}, f'slot {t}: divisions disagree'
        assert all(opps.count(o) <= 2 for o in opps)


def week17(season, div, seyr):
    """The 17th game: AFC division a against NFC division ROTATION[a][SEYR & 3],
    team for team, AFC at home for even n ^ SEYR (as the XBE's cave does)."""
    check(season, div, 16)
    met = opponents(season)
    teams = lambda c, d: sorted(t for t in div if div[t] == (c, d))
    afc, nfc = (sorted({d for c, d in div.values() if c == k}) for k in (0, 1))
    played = {a: {div[o][1] & 3 for t in teams(0, a) for o in met[t] if div[o][0] == 1} for a in afc}
    games = []
    for a in afc:                         # the data is the generator's rotation for that year
        assert played[a] == {ROTATION[a & 3][(seyr + 2) & 3]}, f'AFC division {a}: not the generator rotation'
        b, = (d for d in nfc if d & 3 == ROTATION[a & 3][seyr & 3])
        for x, y in zip(teams(0, a), teams(1, b)):
            games.append((x, y) if not (len(games) ^ seyr) & 1 else (y, x))
    return games


def real_season(path, season, slot):
    """Year 1's regular season from nflverse games.csv: SCHD rows (SESI 0)."""
    with open(path, encoding='utf8') as f:
        games = [g for g in csv.DictReader(f) if g['game_type'] == 'REG']
    if season is None:
        season = max(int(g['season']) for g in games
                     if sum(h['season'] == g['season'] for h in games) == 272)
    games = [g for g in games if g['season'] == str(season)]
    assert len(games) == 272, f'{season}: {len(games)} regular-season games, expected 272'
    nov1 = datetime.date(season, 11, 1)
    thanksgiving = (nov1 + datetime.timedelta((3 - nov1.weekday()) % 7 + 21)).isoformat()
    rows = []
    for g in games:
        h, m = map(int, g['gametime'].split(':'))
        rows.append(dict(SESI=0, SEST=0, SEWT=REGULAR, GSTA=1, SEWN=int(g['week']) - 1,
                         GDAT=GDAT[g['weekday']], GTOD=60 * h + m, GFTG=int(g['gameday'] == thanksgiving),
                         GHTG=slot[TGID[g['home_team']]], GATG=slot[TGID[g['away_team']]]))
    rows.sort(key=lambda r: (r['SEWN'], r['GDAT'], r['GTOD']))
    for r in rows:
        r['SGNM'] = sum(q['SEWN'] == r['SEWN'] for q in rows[:rows.index(r)])
    assert max(r['SEWN'] for r in rows) == NEW_WEEK
    assert sum(r['GFTG'] for r in rows) == 3, 'expected three Thanksgiving games'
    print(f'year 1: the {season} NFL schedule')
    return rows


def league(db, div, real=None):
    """3-week preseason and a 17th game in both stock schedules; `real` replaces year 1."""
    s = db['SCHD']
    assert s.count == 664 and s.capacity == 664, 'not the stock 09 schedule'
    rows = [r for r in s.rows() if not (r['SEST'] == PRESEASON and r['SEWN'] == 3)]
    for r in rows:
        if r['SEST'] == 0 and r['SEWN'] >= NEW_WEEK:
            r['SEWN'] += 1
    if real:
        rows = [r for r in rows if not (r['SESI'] == 0 and r['SEST'] == 0 and r['SEWT'] == REGULAR)]
    for sesi in ((1,) if real else (0, 1)):
        reg = [r for r in rows if r['SESI'] == sesi and r['SEST'] == 0 and r['SEWT'] == REGULAR]
        slots = sorted((r for r in reg if r['SEWN'] == NEW_WEEK - 1), key=lambda r: r['SGNM'])
        games = week17(reg, div, seyr=sesi)
        assert len(slots) == len(games) == 16
        for n, ((home, away), slot) in enumerate(zip(games, slots)):
            rows.append(dict(slot, SEWN=NEW_WEEK, SGNM=n, GHTG=home, GATG=away))
    if real:
        rows += real
    for sesi in (0, 1):
        check([r for r in rows if r['SESI'] == sesi and r['SEST'] == 0 and r['SEWT'] == REGULAR], div, 17)
    grown = tdb.DB(db.resized({'SCHD': max(len(rows), s.capacity)}), 0)
    write(grown['SCHD'], rows)
    grown.fix()
    assert grown.verify()
    return grown.buf


def franchise(db):
    """Make room for one more week; move the progression checkpoints with the schedule."""
    w = db['SCWE']
    rows = w.rows()
    pre = sorted((r for r in rows if r['SEST'] == PRESEASON), key=lambda r: r['SEWN'])
    reg = sorted((r for r in rows if r['SEST'] == 0), key=lambda r: r['SEWN'])
    assert [r['SEWN'] for r in pre] == list(range(4)) and pre[3]['PRAR'] == 1, 'unexpected SCWE'
    assert [r['SEWN'] for r in reg] == list(range(21)) and reg[NEW_WEEK - 1]['PRAR'] == 1, 'unexpected SCWE'
    # Year 1's preseason is 3 weeks, but from year 2 the user picks preseason
    # opponents and the picker still offers 4 games, so week 3 keeps its row.
    pre[2]['PRAR'], pre[3]['PRAR'] = 1, 0     # preseason checkpoint: the 3rd week
    reg[NEW_WEEK - 1]['PRAR'] = 0             # period 3 now ends at the new week
    new = []
    for r in reg:
        new.append(dict(r, SEWN=r['SEWN'] + (r['SEWN'] >= NEW_WEEK)))
        if r['SEWN'] == NEW_WEEK - 1:
            new.append(dict(r, SEWN=NEW_WEEK, PRAR=1))
    grown = tdb.DB(db.resized({'SCHD': db['SCHD'].capacity + 16,
                               'OTIW': db['OTIW'].capacity + 32,
                               'AWPL': db['AWPL'].capacity + 5,
                               'SCWE': max(w.capacity, len(pre) + len(new))}), 0)
    write(grown['SCWE'], pre + new)
    grown.fix()
    assert grown.verify()
    return grown.buf


def streamed(db):
    """One more week in the per-week owner tables (copies of the last week)."""
    grow = {'OWFW': 21, 'OACI': NEW_WEEK, 'OFAC': NEW_WEEK}   # table: week to add
    for name, week in grow.items():
        assert [r['SEWN'] for r in db[name].rows()] == list(range(week)), f'unexpected {name}'
    grown = tdb.DB(db.resized({n: db[n].capacity + 1 for n in grow}), 0)
    for name, week in grow.items():
        rows = grown[name].rows()
        write(grown[name], rows + [dict(rows[-1], SEWN=week)])
    grown.fix()
    assert grown.verify()
    return grown.buf


def week17_cave(va):
    """cdecl f(state): the generator's PLACE(state), then week 17's games."""
    p32 = lambda v: struct.pack('<I', v)
    c = bytearray()

    def call(target):
        c.extend(b'\xe8' + struct.pack('<i', target - (va + len(c) + 5)))
    c += bytes.fromhex('ff742404')                          # push [esp+4]       state
    call(PLACE)
    c += bytes.fromhex('83c404 85c0 75')                    # add esp,4; test eax,eax; jnz done
    jnz_done = len(c)
    c += b'\0'
    c += bytes.fromhex('53 56 57 8b742410 31db')            # push ebx,esi,edi; esi = state; ebx = n = 0
    loop = len(c)
    c += bytes.fromhex('89d8 c1e802 8b4e10 83e103 8d0c81')  # ecx = (year & 3) + 4 * (n >> 2)
    c += bytes.fromhex('0fb70c4d') + p32(ROTATION_VA)       # movzx ecx, ROTATION[ecx]: NFC division
    c += bytes.fromhex('89d8 83e003 8d0c88')                # ecx = 4 * division + (n & 3)
    c += bytes.fromhex('0fb70c4d') + p32(NFC_TEAMS)         # movzx ecx, NFC_TEAMS[ecx]
    c += bytes.fromhex('0fb7145d') + p32(AFC_TEAMS)         # movzx edx, AFC_TEAMS[n]
    c += bytes.fromhex('8b3e 6bd21c 8b541708 6bc91c 8b4c0f08')  # team index -> TGID (+8 of 0x1c-byte entries)
    c += bytes.fromhex('89d8 334610 a801 7402 87ca')        # odd n ^ year: NFC at home
    c += bytes.fromhex('6a00 6a03 68') + p32(KICKOFF)       # GFHU 0, GDAT 3, GTOD
    c += bytes.fromhex('6a00 6a00 51 52 6a01 53 6a19 6a11 68') + p32(INSERT_GAME) + bytes.fromhex('6a00')
    call(DB_EXEC)                                           # (0, query, 17, 25, n, 1, home, away, 0, 0, ...)
    c += bytes.fromhex('83c434 85c0 75')                    # error: stop
    jnz_out = len(c)
    c += b'\0'
    c += bytes.fromhex('43 83fb10 72')                      # inc ebx; cmp ebx,16; jb loop
    c += struct.pack('<b', loop - (len(c) + 1))
    c[jnz_out] = len(c) - (jnz_out + 1)
    c += bytes.fromhex('5f5e5b')
    c[jnz_done] = len(c) - (jnz_done + 1)
    c += b'\xc3'
    return bytes(c)


def executable(src):
    """Offseason start week 22 -> 23; the year-2+ generator keeps and fills week 17."""
    x = XBE(src)
    buf = bytearray(x.d)
    for va in OFFSEASON_WEEK:
        o = x.v2f(va)
        assert buf[o:o + 2] == b'\x6a\x16', f'{va:#x}: expected push 22'
        buf[o + 1] = 0x17
    base = struct.unpack_from('<I', buf, 0x104)[0]
    assert struct.unpack_from('<I', buf, 0x108)[0] >= 0x1000, 'needs the awareness-fixed XBE (header page mapped)'
    cave = week17_cave(CAVE_VA)
    o = CAVE_VA - base
    assert o + len(cave) <= 0x1000 and not any(buf[o - 16:o + len(cave)]), 'cave space in use'
    buf[o:o + len(cave)] = cave
    o = x.v2f(GENERATOR_CALL)
    assert buf[o - 1:o + 1] == b'\x56\xe8' and struct.unpack_from('<i', buf, o + 1)[0] == PLACE - (GENERATOR_CALL + 5)
    struct.pack_into('<i', buf, o + 1, CAVE_VA - (GENERATOR_CALL + 5))
    return buf


def main(src, dst, games_csv=None, season=None, repack_only=False):
    buf = bytearray(open(src, 'rb').read())
    if buf[:4] == b'XBEH':
        out = executable(src)
    elif buf[:4] == b'DB\x00\x08':
        assert tdb.DB(buf, 0).size == len(buf), 'expected a bare DB file'
        out = streamed(tdb.DB(buf, 0))
    elif repack_only:
        out = repack(buf, {})
        assert out == buf, 'repack does not reproduce the input'
    else:
        roster = entry_db(buf, ROSTER)
        real = games_csv and real_season(games_csv, season and int(season), slots(roster))
        out = repack(buf, {LEAGUE: league(entry_db(buf, LEAGUE), divisions(roster), real),
                           FRANCHISE: franchise(entry_db(buf, FRANCHISE))})
    open(dst, 'wb').write(out)
    print(f'{os.path.basename(dst)}: {len(buf):,} -> {len(out):,} bytes')


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if a != '--repack-only']
    main(*args, repack_only='--repack-only' in sys.argv)
