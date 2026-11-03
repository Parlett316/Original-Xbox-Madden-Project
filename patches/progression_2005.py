"""Give Madden NFL 09 (Xbox) Madden 2005's in-season player progression.

Usage: python progression_2005.py <2005 STREAMEDDATA.DB> <09 strmdata.db> <out strmdata.db> [strength | performance]

strength (default 1) blends the two games: 0 = stock 09, 1 = Madden 2005,
0.5 = halfway, applied to both the rating changes and the grade thresholds.

performance: progression follows performance both ways, with a brake at the
top so 99 stays rare. Per checkpoint:
  good grades (0-2): 2005's gains x overall-group factor x career-phase factor
  neutral grade (3): no change
  bad grade (4):     09's declines x overall-group factor (x1.25 for veterans)
  the preseason checkpoint changes nothing (simmed preseasons graded starters
  as poor and dropped them).
Grades come from 09's own thresholds, which match 09's scoring code (2005's
are on a different scale and put most starters in the top grades). The game
grades a player's average score against PLLO: >= PL3P best, >= PL2P good,
>= PL1P ok, >= PLSP neutral, below PLSP bad. Stock PLSP is almost always 0,
so the bad grade never happens; here it is set to half of PL1P, so a starter
who plays below half an "ok" level declines. Players who don't play are
scored at exactly PLSP, so the bench stays neutral.
Fractions are spread over the season's checkpoints (error diffusion), so a
halved +1 becomes +1 at every other checkpoint instead of always 0 or 1.

In-season progression is driven by two tables, applied at the same six SCWE
checkpoints in both games (preseason week 3, weeks 4/10/16, playoff weeks):
  PLLO  grade thresholds, keyed by position group (PDRP), overall-rating
        group (PRGR) and career phase (PCPH)
  PWRA  rating changes for 11 ratings, keyed by PDRP, PRGR and performance
        grade (PLEV)
09 adds the checkpoint (PPRD) as an extra key to both, and PCPH to PWRA, with
mostly smaller values. 09's loader indexes rows by their key fields, so both
tables are rewritten with every key combination listed once, each holding the
2005 values for its (PDRP, PRGR[, PCPH][, PLEV]), blended with 09's own value
for that key. That also fixes stock 09's one mis-keyed PWRA row (PDRP 14
stored as 1 for checkpoint 1, phase 1); its 09 value is taken from the next
checkpoint.
"""
import itertools
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'roster'))
import tdb  # noqa: E402

DELTAS = ('PGCA', 'PGKA', 'PGSA', 'PGTA', 'PGPB', 'PGRB', 'PGTK', 'PGKR', 'PGBT', 'PGCT', 'PGAW')
THRESHOLDS = ('PLSP', 'PL1P', 'PL2P', 'PL3P')
CHECKPOINTS, PHASES, GROUPS, RATING_GROUPS, GRADES = 6, 3, 17, 6, 5


def find_db(buf, table):
    i = buf.find(b'DB\x00\x08')
    while i != -1:
        try:
            db = tdb.DB(buf, i)
            if table in db.tables:
                return db
        except Exception:
            pass
        i = buf.find(b'DB\x00\x08', i + 4)
    raise SystemExit(f'no {table} table found')


def blend(v09, v05, strength):
    return int(round(v09 + strength * (v05 - v09)))


# performance mode: overall groups are PRGR 0 = 90+, 1 = 82-89, 2 = 76-81,
# 3 = 70-75, 4 = 60-69, 5 = under 60; career phase PCPH 0 young .. 2 veteran.
GAIN_BY_GROUP = {0: 0.5, 1: 0.75}
LOSS_BY_GROUP = {0: 1.5, 1: 1.25}
GAIN_BY_PHASE = {0: 1.25, 1: 1.0, 2: 0.75}
LOSS_BY_PHASE = {2: 1.25}
BAD_SHARE = 0.5                  # PLSP = this share of PL1P
DELTA_RANGE = (-16, 15)          # 5-bit signed fields


def performance_targets(src, own, prd, cph, rgr, lev):
    """Unrounded change per rating for one checkpoint row."""
    out = {}
    for f in DELTAS:
        if prd == 0 or lev == 3:
            out[f] = 0.0
        elif lev == 4:
            v = own[f]
            out[f] = v * LOSS_BY_GROUP.get(rgr, 1.0) * LOSS_BY_PHASE.get(cph, 1.0) if v < 0 else v
        else:
            v = src[f]
            out[f] = v * GAIN_BY_GROUP.get(rgr, 1.0) * GAIN_BY_PHASE[cph] if v > 0 else v
    return out


def main(src05, src09, dst, strength=1.0):
    performance = strength == 'performance'
    old = find_db(bytearray(open(src05, 'rb').read()), 'PWRA')
    buf = bytearray(open(src09, 'rb').read())
    new = find_db(buf, 'PWRA')

    pwra05 = {(r['PDRP'], r['PRGR'], r['PLEV']): r for r in old['PWRA'].rows()}
    pllo05 = {(r['PDRP'], r['PRGR'], r['PCPH']): r for r in old['PLLO'].rows()}
    pwra09 = {(r['PPRD'], r['PCPH'], r['PDRP'], r['PRGR'], r['PLEV']): r for r in new['PWRA'].rows()}
    pllo09 = {(r['PPRD'], r['PCPH'], r['PDRP'], r['PRGR']): r for r in new['PLLO'].rows()}
    assert len(pwra05) == GROUPS * RATING_GROUPS * GRADES
    assert len(pllo05) == GROUPS * RATING_GROUPS * PHASES

    T = new['PWRA']
    keys = list(itertools.product(range(CHECKPOINTS), range(PHASES), range(GROUPS),
                                  range(RATING_GROUPS), range(GRADES)))
    assert len(keys) <= T.capacity
    values = {}
    for prd, cph, drp, rgr, lev in keys:
        src = pwra05[drp, rgr, lev]
        own = pwra09.get((prd, cph, drp, rgr, lev)) or pwra09[prd + 1, cph, drp, rgr, lev]
        if performance:
            values[prd, cph, drp, rgr, lev] = performance_targets(src, own, prd, cph, rgr, lev)
        else:
            values[prd, cph, drp, rgr, lev] = {f: blend(own[f], src[f], strength) for f in DELTAS}
    if performance:
        # error diffusion per row key and rating, separately over the regular
        # season checkpoints and the playoff ones (non-playoff teams never see those)
        for cph, drp, rgr, lev in itertools.product(range(PHASES), range(GROUPS), range(RATING_GROUPS), range(GRADES)):
            for f, span in itertools.product(DELTAS, ((0,), (1, 2, 3), (4, 5))):
                total = emitted = 0
                for prd in span:
                    total += values[prd, cph, drp, rgr, lev][f]
                    v = int(round(total)) - emitted
                    v = max(DELTA_RANGE[0], min(DELTA_RANGE[1], v))
                    values[prd, cph, drp, rgr, lev][f] = v
                    emitted += v
    for i, key in enumerate(keys):
        for f, v in zip(('PPRD', 'PCPH', 'PDRP', 'PRGR', 'PLEV'), key):
            T.set(i, f, v)
        for f in DELTAS:
            T.set(i, f, values[key][f])
    T.count = len(keys)

    T = new['PLLO']
    keys = list(itertools.product(range(CHECKPOINTS), range(PHASES), range(GROUPS), range(RATING_GROUPS)))
    assert len(keys) <= T.capacity
    for i, (prd, cph, drp, rgr) in enumerate(keys):
        src = pllo05[drp, rgr, cph]
        own = pllo09[prd, cph, drp, rgr]
        for f, v in dict(PPRD=prd, PCPH=cph, PDRP=drp, PRGR=rgr).items():
            T.set(i, f, v)
        for f in THRESHOLDS:
            T.set(i, f, own[f] if performance else blend(own[f], src[f], strength))
        if performance:
            T.set(i, 'PLSP', max(own['PLSP'], int(round(BAD_SHARE * own['PL1P']))))
    T.count = len(keys)

    new.fix()
    assert new.verify()
    open(dst, 'wb').write(buf)
    mode = 'performance' if performance else f'2005 strength {strength:g}'
    print(f'wrote {dst}: PWRA {new["PWRA"].count} rows, PLLO {new["PLLO"].count} rows, {mode}')


if __name__ == '__main__':
    if len(sys.argv) not in (4, 5):
        sys.exit(__doc__)
    mode = sys.argv[4:5]
    main(*sys.argv[1:4], *[a if a == 'performance' else float(a) for a in mode])
