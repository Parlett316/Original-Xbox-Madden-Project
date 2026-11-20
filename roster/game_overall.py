"""Madden 09's own overall rating formula (09 XBE 0x39ebb0; docs/findings.md §13).

Per position, a row of the PORC table (template.dat, stats DB at 0x16ad00) gives
17 weights and a range PRDL..PRDH:

    S   = sum(weight_k * rating_k)
    W   = sum(weight_k)
    OVR = trunc(99 * (S / W - PRDL) / (PRDH - PRDL) + 0.5), clamped to 12..99

The game rewrites POVR with this for every player on a team when a mode builds
its teams and in the weekly progression, so a roster file's own overall only
lasts until then (free agents keep theirs).
"""
import struct

# PORC weight field -> PLAY rating field, in the game's slot order (query 0x61f7d8).
# The table's PINW (injury) column isn't read.
WEIGHTS = (('PSTW', 'PSTR'), ('PAGW', 'PAGI'), ('PSEW', 'PSPD'), ('PACW', 'PACC'),
           ('PAWW', 'PAWR'), ('PCAW', 'PCTH'), ('PCRW', 'PCAR'), ('PTPW', 'PTHP'),
           ('PTAW', 'PTHA'), ('PKPW', 'PKPR'), ('PKAW', 'PKAC'), ('PBTW', 'PBTK'),
           ('PTCW', 'PTAK'), ('PPBW', 'PPBK'), ('PRBW', 'PRBK'), ('PJUW', 'PJMP'),
           ('PKRW', 'PKRT'))


def _f32(v):
    return struct.unpack('<f', struct.pack('<I', v & 0xFFFFFFFF))[0]


def weights(porc_table):
    """{PPOS: (PRDH, PRDL, [(rating field, weight), ...])} from a tdb PORC Table."""
    out = {}
    for r in porc_table.rows():
        out[r['PPOS']] = (_f32(r['PRDH']), _f32(r['PRDL']),
                          [(rf, _f32(r[wf])) for wf, rf in WEIGHTS])
    return out


def overall(table, pos, ratings):
    """The game's overall for a player at `pos` with `ratings` (a dict of PLAY fields)."""
    hi, lo, ws = table[pos]
    s = sum(w * ratings[rf] for rf, w in ws)
    wt = sum(w for _, w in ws)
    v = (s - lo * wt) / ((hi - lo) * wt * (1 / 99)) + 0.5
    return int(min(max(v, 12.0), 99.0))
