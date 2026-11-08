"""Give Madden 09 a modern kickoff through its playbooks (GAMEDATA.dat).

Usage: python kickoff_setup.py <stock GAMEDATA.dat> <out GAMEDATA.dat> [--hold N] [--lineup] [--ball YARD]

GAMEDATA.dat entries are LZH1-compressed TDBs holding the playbooks. Kickoff
plays use SETL 5 and their returns SETL 6. Each player is a SETP row (poso) and
SETP -> SETG holds his spot as floats, in yards from the ball, x___/y___ and the
mirrored fx__/fy__. +y is downfield, for both teams.

--hold N  gives the kickoff and kick-return plays their own copies of their
          scripts (new PSAL ids, the table grown), each starting with a wait
          (code 51, val1 N, 0-255) that ends on its timer or when the receiving
          team touches the ball. The kicker's copy holds him right after the
          kick (code 45), while the CPU controls him. The stock
          scripts stay as they are for the plays that share them: safety kicks
          and their returns, punts and punt blocks. A safety kick held on the
          shared scripts left everyone standing.
--lineup  follows the NFL's hybrid kickoff diagram: kicking team evenly
          spaced at the receiving 40 and facing
          downfield (stock faces the middle, which makes them step forward
          during the kicker's motion), seven blockers on the 35 and two on the
          32. The returners are stacked as in stock: the deep one (poso 0)
          fields on the 5, the other (poso 1) blocks from the 15.
--ball YARD  the kicking team's yard line the ball is kicked from: 30 is stock,
          35 goes with patches/kickoff_spot.py. Spots are stored from the ball,
          so the lineup subtracts it.

Run patches/qkl_sync.py afterwards: fe.qkl copies this archive's directory.
With no options this reproduces the input byte for byte. Changed entries can
change size, packed and unpacked (COMP), so later entries move; gaps and the
tail stay as they were.
"""
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(HERE, '..', 'roster'), os.path.join(HERE, 'loadscreen')]
import lzh1emu  # noqa: E402
import tdb  # noqa: E402

KICKOFF_SET = 5
RETURN_SET = 6
WAIT = 51
KICK = 45
ALIGN = 0x80
KICKER = 0                                  # coverage poso whose script is left alone
MAX_SCRIPT = (1 << 11) - 1                  # PSAL ids are 11 bits
DOWNFIELD = 64                              # dir_ and fdir: 256 units a turn
STOCK_BALL = 30
# poso: (x, yard line counted from the kicking team's goal). The return team's
# order keeps each blocker on his stock side.
COVERAGE = {1: (-23.85, 60), 2: (-18.55, 60), 3: (-13.25, 60), 4: (-7.95, 60), 5: (-2.65, 60),
            6: (2.65, 60), 7: (7.95, 60), 8: (13.25, 60), 9: (18.55, 60), 10: (23.85, 60)}
RECEIVING = {0: (0.0, 95), 1: (0.0, 85),
             2: (7.0, 65), 3: (-5.5, 65), 4: (12.0, 68), 5: (-12.0, 68),
             6: (23.5, 65), 7: (17.5, 65), 8: (1.0, 65), 9: (-18.5, 65), 10: (-23.5, 65)}


def from_ball(spots, ball):
    return {p: (x, float(y - ball)) for p, (x, y) in spots.items()}


def layout(buf):
    """(DATA position, DIR1 position, [(offset, size)], [(codec, unpacked size)])."""
    n = struct.unpack_from('<H', buf, 14)[0]
    pos = struct.unpack_from('<I', buf, 4)[0]
    chunks = {}
    while pos < len(buf):
        tag, size = bytes(buf[pos:pos + 4]), struct.unpack_from('<I', buf, pos + 4)[0]
        chunks[tag] = pos
        if tag == b'DATA':
            break
        pos += size
    pairs = lambda tag: [struct.unpack_from('<II', buf, chunks[tag] + 8 + 8 * i) for i in range(n)]
    return chunks[b'DATA'], chunks[b'DIR1'], pairs(b'DIR1'), pairs(b'COMP')


def comp_position(buf):
    pos = struct.unpack_from('<I', buf, 4)[0]
    while bytes(buf[pos:pos + 4]) != b'COMP':
        pos += struct.unpack_from('<I', buf, pos + 4)[0]
    return pos


def float_bits(value):
    return struct.unpack('<I', struct.pack('<f', value))[0]


def place(db, setl, spots):
    """Set the spots of one set's players, mirrored fields too. Returns how many moved."""
    setp = db['SETP']
    poso = {setp.get(r, 'SETP'): setp.get(r, 'poso')
            for r in range(setp.count) if setp.get(r, 'SETL') == setl}
    setg = db['SETG']
    moved = 0
    for r in range(setg.count):
        spot = spots.get(poso.get(setg.get(r, 'SETP')))
        if spot is not None:
            for field, value in zip(('x___', 'fx__', 'y___', 'fy__'), (spot[0], spot[0], spot[1], spot[1])):
                setg.set(r, field, float_bits(value))
            moved += 1
    return moved


def plays_of(db, setl):
    return {r['PLYL'] for r in db['PLYL'].rows() if r['SETL'] == setl}


def held_copies(buf, ticks):
    """Give the kickoff and return plays held copies of their scripts.
    Returns the playbook rebuilt as a new bytearray."""
    db = tdb.DB(buf, 0)
    kick, ret = plays_of(db, KICKOFF_SET), plays_of(db, RETURN_SET)
    plys = db['PLYS']
    rows = [r for r in range(plys.count) if plys.get(r, 'PLYL') in ret | kick]
    is_kicker = {r: plys.get(r, 'PLYL') in kick and plys.get(r, 'poso') == KICKER for r in rows}
    kickers = {plys.get(r, 'PSAL') for r in rows if is_kicker[r]}
    others = {plys.get(r, 'PSAL') for r in rows if not is_kicker[r]}
    assert not kickers & others, 'a kicker script is also a player script'
    scripts = sorted(kickers | others)
    psal = db['PSAL']
    steps = {name: sorted((psal.get(r, 'step'), r) for r in range(psal.count) if psal.get(r, 'PSAL') == name)
             for name in scripts}
    added = sum(len(v) for v in steps.values()) + len(kickers)
    top = max(psal.get(r, 'PSAL') for r in range(psal.count))
    assert top + len(scripts) <= MAX_SCRIPT, 'no room for new script ids'
    copy_of = {name: top + 1 + k for k, name in enumerate(scripts)}
    old = [psal.raw(r) for r in range(psal.count)]
    count = psal.count
    db.fix()
    out = db.resized({'PSAL': max(psal.capacity, count + added)})
    db = tdb.DB(out, 0)
    psal, plys = db['PSAL'], db['PLYS']
    psal.count = count + added
    at = count

    def write(name, step, raw, wait=False):
        nonlocal at
        psal.set_raw(at, raw)
        psal.set(at, 'PSAL', copy_of[name])
        psal.set(at, 'step', step)
        if wait and step == 0:
            assert psal.get(at, 'code') in (3, WAIT), f"script {name} starts with {psal.get(at, 'code')}"
        if wait:
            for field, value in (('code', WAIT), ('val1', ticks), ('val2', 0), ('val3', 0)):
                psal.set(at, field, value)
        at += 1

    for name in scripts:
        if name in others:
            # players: the first step (run, or the stock wait) becomes the hold
            for step, r in steps[name]:
                write(name, step, old[r], wait=step == 0)
        else:
            # the kicker: kick (code 45), then hold, then the rest one step later
            shift = 0
            for step, r in steps[name]:
                write(name, step + shift, old[r])
                if not shift and psal.get(at - 1, 'code') == KICK:
                    write(name, step + 1, old[r], wait=True)
                    shift = 1
            assert shift, f'kicker script {name} has no kick step'
            assert max(st for st, _ in steps[name]) + 1 < 16, 'step field is 4 bits'
    for r in rows:
        plys.set(r, 'PSAL', copy_of[plys.get(r, 'PSAL')])
    db.fix()
    return out


def face(db, setl, posos, direction):
    setp = db['SETP']
    ids = {setp.get(r, 'SETP') for r in range(setp.count)
           if setp.get(r, 'SETL') == setl and setp.get(r, 'poso') in posos}
    setg = db['SETG']
    for r in range(setg.count):
        if setg.get(r, 'SETP') in ids:
            setg.set(r, 'dir_', direction)
            setg.set(r, 'fdir', direction)


def edit(raw, ticks, lineup, ball=STOCK_BALL):
    """Apply the options to one decompressed playbook. Returns new bytes, or None if it has neither set."""
    if raw[:4] != b'DB\x00\x08':
        return None
    buf = bytearray(raw)
    db = tdb.DB(buf, 0)
    if not all(t in db.tables for t in ('SETP', 'SETG', 'PLYL', 'PLYS', 'PSAL')):
        return None
    sets = {r['SETL'] for r in db['SETP'].rows()}
    if not sets & {KICKOFF_SET, RETURN_SET}:
        return None
    assert db.verify()
    if lineup:
        if KICKOFF_SET in sets:
            assert place(db, KICKOFF_SET, from_ball(COVERAGE, ball)) == len(COVERAGE)
            face(db, KICKOFF_SET, COVERAGE, DOWNFIELD)
        if RETURN_SET in sets:
            assert place(db, RETURN_SET, from_ball(RECEIVING, ball)) == len(RECEIVING)
    if ticks is not None:
        buf = held_copies(buf, ticks)
        db = tdb.DB(buf, 0)
    db.fix()
    assert db.verify()
    return bytes(buf)


def rounded(size):
    return -(-size // ALIGN) * ALIGN


def main(src, dst, ticks, lineup, ball=STOCK_BALL):
    buf = open(src, 'rb').read()
    data_at, dir_at, entries, comp = layout(buf)
    order = sorted(range(len(entries)), key=lambda n: entries[n][0])
    out = bytearray(buf[:data_at + entries[order[0]][0]])
    new_dir = list(entries)
    new_comp = list(comp)
    changed = 0
    for at, n in enumerate(order):
        off, size = entries[n]
        end = entries[order[at + 1]][0] if at + 1 < len(order) else len(buf) - data_at
        slot = bytes(buf[data_at + off:data_at + end])
        new_off = len(out) - data_at
        new_dir[n] = (new_off, size)
        new = None
        if size and comp[n][0] == 5 and (ticks is not None or lineup):
            raw = lzh1emu.decompress(slot[:size], comp[n][1])[0]
            new = edit(raw, ticks, lineup, ball)
            new = None if new == raw else new
        if new is None:
            out += slot
            continue
        _, _, (_, used), output = lzh1emu.compress(new)
        packed = bytes(output[:used])
        assert lzh1emu.decompress(packed, len(new))[0] == new
        new_dir[n] = (new_off, len(packed))
        new_comp[n] = (comp[n][0], len(new))
        out += packed + bytes(rounded(len(packed)) - len(packed)) + slot[rounded(size):]
        changed += 1
    comp_at = comp_position(out)
    for n, (pair, cpair) in enumerate(zip(new_dir, new_comp)):
        struct.pack_into('<II', out, dir_at + 8 + 8 * n, *pair)
        struct.pack_into('<II', out, comp_at + 8 + 8 * n, *cpair)
    struct.pack_into('<I', out, data_at + 4, struct.unpack_from('<I', buf, data_at + 4)[0] + len(out) - len(buf))
    with open(dst, 'wb') as f:
        f.write(out)
    print(f'{changed} playbooks changed, {len(out)} bytes (stock {len(buf)})')


if __name__ == '__main__':
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    args = sys.argv[3:]
    hold_ticks = None
    if '--hold' in args:
        at = args.index('--hold')
        hold_ticks = int(args[at + 1])
        del args[at:at + 2]
    yard = STOCK_BALL
    if '--ball' in args:
        yard = int(args[args.index('--ball') + 1])
    use_lineup = '--lineup' in args
    main(sys.argv[1], sys.argv[2], hold_ticks, use_lineup, yard)
