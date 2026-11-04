"""Give Madden 09's franchise a 17-game, 18-week regular season (template.dat).

    python season17.py <in template.dat> <out template.dat>
    python season17.py <in strmdata.db> <out strmdata.db>
    python season17.py <in default.xbe> <out default.xbe>

Run it on the roster build's template.dat (it shifts every DB after entry 4,
so it must be the last change to the file), then qkl_sync.py: fe.qkl preloads
template.dat's directory.

Schedules are data (docs/findings.md section 8). Entry 5's SCHD holds two
seasons (SESI 0/1, alternating by year); the game derives the week and round
counts from the rows' week types (SEWT 25 regular, 50/75/100/125 playoff
rounds, 150 Pro Bowl; SEST 9 preseason). For both seasons this
- drops the 4th preseason week (the NFL has played three since 2021), and
- adds regular-season week 17, the modern 17th game: each AFC division meets
  an NFC division it isn't already scheduled against that year, team for
  team, so nobody plays an opponent twice (or a rival three times). The AFC
  hosts in SESI 0, the NFC in SESI 1, and the two years use different
  division pairs. Kickoff times are week 16's.
Playoffs move to weeks 18-21 and the Pro Bowl to week 22. The Pro Bowl week is
kept because box scores only last while their week is current: it is where
the Super Bowl's stats can be viewed. Schedule slots are TEAM.TORD - 1
(stock alphabetical order, so the Texans, TGID 32, are slot 29); divisions come
from entry 1's TEAM and are checked against the schedule (rivals meet twice).

Entry 4 is the empty franchise DB copied into new franchises. Its per-week
tables are sized for 21 weeks and grow by one week: SCHD (+16 games), OTIW
(+32 rows, 32 teams x 22 weeks), AWPL (+5 weekly awards). SCWE, the
progression checkpoint list, follows the schedule: the preseason checkpoint
moves to the last preseason week, the new week joins the third period (its
checkpoint moves from week 16 to 17) and the playoff rows shift by one.
Only franchises started with this file get the new format.

strmdata.db (mode picked from the file): per-week owner tables stop at stock's
last team week. OWFW (fan weights, weeks 0-20) gets week 21 and OACI/OFAC
(weeks 0-16) get week 17, copies of the last stock week. A missing OWFW row
aborts end-of-week processing (0x3d96d3), so the stock game could never get
past a Super Bowl at week 21 (hardware tests 2 and 3; fixed in test 4).

default.xbe: the offseason start (0x3a9530) sets the week to 22 and inserts
its marker game (SEWT 175) at week 22, the week after stock's Pro Bowl. With
the Pro Bowl at week 22 both move to 23 (two push imm8 operands).

With no change requested (--repack-only) the archive is rebuilt as is and
must match the input byte for byte.
"""
import itertools
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


def week17(season, div, afc_home, avoid=()):
    """The 17th game for one season: AFC division vs an unplayed NFC division
    (preferring division pairs not in `avoid`, so the years differ)."""
    met = {}
    for r in season:
        for a, b in ((r['GHTG'], r['GATG']), (r['GATG'], r['GHTG'])):
            met.setdefault(a, []).append(b)
    for t, opps in met.items():
        rivals = {o for o in opps if opps.count(o) == 2}
        assert rivals == {o for o in div if o != t and div[o] == div[t]}, f'slot {t}: divisions disagree'
    teams = lambda c, d: sorted(t for t in div if div[t] == (c, d))
    afc, nfc = (sorted({d for c, d in div.values() if c == k}) for k in (0, 1))
    played = {a: {div[o][1] for t in teams(0, a) for o in met[t] if div[o][0] == 1} for a in afc}
    picks = [dict(zip(afc, p)) for p in itertools.permutations(nfc)]
    picks = [p for p in picks if all(p[a] not in played[a] for a in afc)]
    if not picks:
        raise SystemExit(f'no free NFC division for every AFC division: {played}')
    pick = min(picks, key=lambda p: sum((a, p[a]) in avoid for a in afc))
    games = []
    for a in afc:
        for x, y in zip(teams(0, a), teams(1, pick[a])):
            assert y not in met[x]
            games.append((x, y) if afc_home else (y, x))
    return games, set(pick.items())


def league(db, div):
    """3-week preseason and a 17th game in both stock schedules."""
    s = db['SCHD']
    assert s.count == 664 and s.capacity == 664, 'not the stock 09 schedule'
    rows = [r for r in s.rows() if not (r['SEST'] == PRESEASON and r['SEWN'] == 3)]
    for r in rows:
        if r['SEST'] == 0 and r['SEWN'] >= NEW_WEEK:
            r['SEWN'] += 1
    used = set()
    for sesi in (0, 1):
        reg = [r for r in rows if r['SESI'] == sesi and r['SEST'] == 0 and r['SEWT'] == REGULAR]
        slots = sorted((r for r in reg if r['SEWN'] == NEW_WEEK - 1), key=lambda r: r['SGNM'])
        games, used = week17(reg, div, afc_home=sesi == 0, avoid=used)
        assert len(slots) == len(games) == 16
        for n, ((home, away), slot) in enumerate(zip(games, slots)):
            rows.append(dict(slot, SEWN=NEW_WEEK, SGNM=n, GHTG=home, GATG=away))
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
    pre = pre[:3]
    pre[2]['PRAR'] = 1                        # preseason checkpoint: now the last preseason week
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


def offseason_week(src):
    """The offseason start's week 22 -> 23 (it follows the Pro Bowl, now week 22)."""
    x = XBE(src)
    buf = bytearray(x.d)
    for va in OFFSEASON_WEEK:
        o = x.v2f(va)
        assert buf[o:o + 2] == b'\x6a\x16', f'{va:#x}: expected push 22'
        buf[o + 1] = 0x17
    return buf


def main(src, dst, repack_only=False):
    buf = bytearray(open(src, 'rb').read())
    if buf[:4] == b'XBEH':
        out = offseason_week(src)
    elif buf[:4] == b'DB\x00\x08':
        assert tdb.DB(buf, 0).size == len(buf), 'expected a bare DB file'
        out = streamed(tdb.DB(buf, 0))
    elif repack_only:
        out = repack(buf, {})
        assert out == buf, 'repack does not reproduce the input'
    else:
        out = repack(buf, {LEAGUE: league(entry_db(buf, LEAGUE), divisions(entry_db(buf, ROSTER))),
                           FRANCHISE: franchise(entry_db(buf, FRANCHISE))})
    open(dst, 'wb').write(out)
    print(f'{os.path.basename(dst)}: {len(buf):,} -> {len(out):,} bytes')


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if a != '--repack-only']
    main(*args, repack_only='--repack-only' in sys.argv)
