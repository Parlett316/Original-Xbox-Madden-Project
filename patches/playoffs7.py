"""Seven playoff teams per conference for Madden 09, with one bye (apply after season17.py).

    python playoffs7.py <in default.xbe>   <out default.xbe>
    python playoffs7.py <in template.dat>  <out template.dat>

Stock seeds 6 teams per conference (docs/findings.md section 8): 0x41b590 lists the
division winners and wild cards into a stack array and a global (0x7ba428), then writes
#3 v #6 and #4 v #5, with #1 and #2 as hosts of the next round. After the wild-card
round, 0x41b6f0 collects 2 winners per conference, best seed first, and sends the worse
one to #1 and the better one to #2.

Now: the wild-card round is #2 v #7, #3 v #6 and #4 v #5, and only #1 waits. The
divisional round is #1 v the worst winner, and the best winner v the other winner.

Executable:
- 0x41b590 is replaced by a cave with room for 7 teams and a third game per conference.
  Games are numbered by conference: AFC 0, 2, 4 and NFC 1, 3, 5.
- The seed global moves to the padding at the end of .data (0x80dea4, nothing refers to
  it, exactly 2 x 7 words), because stock's is followed by the schedule generator's
  tables. The three places that index it use 7 per conference.
- 0x41b6f0 collects 3 winners, in a buffer moved down one slot so it stays in its frame.
- The clinch routine (0x41aee0) marks 3 wild cards per conference. The draft order needs
  every playoff team marked (see PATCHES).

template.dat: two more wild-card rows in both schedules, and room for them in the
franchise database (a season now has 286 rows), so a franchise needs this build from
its creation. The rounds' game counts are read from the schedule (0x3c0ff0).
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import season17 as S  # noqa: E402

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'loadscreen'))
from xbe import XBE  # noqa: E402

CAVE_VA = 0x10b40               # zero padding in the header page, up to 0x10f00
SEEDING = 0x41b590
SEEDS = 0x80dea4                # 2 conferences x 7 words, up to the next section at 0x80dec0
OLD_SEEDS = 0x7ba428
WILD_CARD = 50                  # SEWT
EXTRA_GAMES = 2                 # one more game per conference
# Wild-card kickoffs by game number: (GDAT, GTOD). Sat 4:30, Sat 8:00, Sun 1:00, Sun 4:30,
# Sun 8:15, Mon 8:15.
KICKOFFS = ((2, 990), (2, 1200), (3, 780), (3, 990), (3, 1215), (4, 1215))

COUNT_CONFERENCES, CONFERENCE, COUNT_DIVISIONS = 0x3a3660, 0x3a36d0, 0x3a3670
LIST_WINNERS, LIST_WILD_CARDS, SET_GAME = 0x41aa10, 0x41ab00, 0x3d7a80
IS_ACTIVE, NOTE_A, NOTE_B = 0x422d80, 0x423530, 0x4234c0
UNSET = 0x3ff                   # team id that leaves a game's side unchanged

# (VA, stock bytes, new bytes). Seed lookups and stores: 7 words per conference.
PATCHES = (
    (0x41a844, bytes.fromhex('8d0440') + b'\x8d\x04\x85' + struct.pack('<I', OLD_SEEDS),
     bytes.fromhex('6bc00e') + b'\x05' + struct.pack('<I', SEEDS) + b'\x90\x90'),   # imul eax,14; add eax,SEEDS
    (0x41a87b, bytes.fromhex('83f806'), bytes.fromhex('83f807')),                   # scan 7 seeds
    (0x41a882, bytes.fromhex('83f806'), bytes.fromhex('83f807')),
    (0x41aa88, bytes.fromhex('6683ff06'), bytes.fromhex('6683ff07')),               # division winners
    (0x41aa8e, bytes.fromhex('8d145b8d0450'), bytes.fromhex('6bd3078d0410')),       # edx = conf * 7; eax += edx
    (0x41aa94, b'\x66\x89\x0c\x45' + struct.pack('<I', OLD_SEEDS),
     b'\x66\x89\x0c\x45' + struct.pack('<I', SEEDS)),
    (0x41ab7b, bytes.fromhex('83fa06'), bytes.fromhex('83fa07')),                   # wild cards
    (0x41ab80, bytes.fromhex('8d147f8d0450'), bytes.fromhex('6bd7078d0410')),
    (0x41ab86, b'\x66\x89\x0c\x45' + struct.pack('<I', OLD_SEEDS + 8),
     b'\x66\x89\x0c\x45' + struct.pack('<I', SEEDS + 8)),
    # Clinch status (TEAM.TMPS): 3 wild cards per conference, not 2. A team without a
    # status counts as a non-playoff team in the draft order (0x3d42d0), so a losing #7
    # seed went into its 32-entry list twice, overran the heap block and crashed.
    (0x41b566, bytes.fromhex('8b542414d1ea'), bytes.fromhex('ba0300000090')),       # mov edx, 3
    # After the wild-card round: 3 winners at [frame+0x24..0x2c], best seed first.
    (0x41b746, bytes.fromhex('6a02'), bytes.fromhex('6a03')),                       # collect 3
    (0x41b749, bytes.fromhex('8d5c2434'), bytes.fromhex('8d5c2430')),               # buffer one slot lower
    # Game conf + 2: the best winner hosts the other. [frame+0x2c], the worst, still goes to #1.
    (0x41b78a, bytes.fromhex('52') + b'\x68' + struct.pack('<I', UNSET),
     bytes.fromhex('52') + bytes.fromhex('ff74242c') + b'\x90'),                    # push away; push home
)


class Asm:
    """Just enough of an assembler: bytes, calls and forward or backward rel32 jumps."""

    def __init__(self, va):
        self.va, self.items, self.labels = va, [], {}
        self.size = 0

    def code(self, text):
        b = bytes.fromhex(text)
        self.items.append(b)
        self.size += len(b)

    def label(self, name):
        self.labels[name] = self.size

    def call(self, target):
        self.items.append(('call', target))
        self.size += 5

    def jump(self, op, name):
        """`op` is the opcode's hex: 'e9' or a two-byte conditional like '0f85'."""
        self.items.append(('jump', bytes.fromhex(op), name))
        self.size += len(op) // 2 + 4

    def bytes(self):
        out = bytearray()
        for it in self.items:
            if isinstance(it, bytes):
                out += it
            elif it[0] == 'call':
                out += b'\xe8' + struct.pack('<i', it[1] - (self.va + len(out) + 5))
            else:
                end = len(out) + len(it[1]) + 4
                out += it[1] + struct.pack('<i', self.labels[it[2]] - end)
        assert len(out) == self.size
        return bytes(out)


def seeding_cave(va):
    """cdecl f(last regular week). Frame: t[7] at +0, conference index +0x1c, count +0x20."""
    a = Asm(va)
    a.code('55 53 56 57')                   # push ebp, ebx, esi, edi
    a.code('83ec24')                        # sub esp, 0x24
    a.call(COUNT_CONFERENCES)
    a.code('0fb7c0 89442420')               # movzx eax, ax; mov [esp+0x20], eax
    a.code('c744241c00000000')              # mov dword [esp+0x1c], 0
    a.label('top')
    a.code('8b6c241c 3b6c2420')             # mov ebp, [esp+0x1c]; cmp ebp, [esp+0x20]
    a.jump('0f83', 'done')                  # jae
    a.code('55')
    a.call(CONFERENCE)
    a.code('83c404 8bf8 8bd8')              # edi = ebx = conference id (the listers take it there)
    a.code('57')
    a.call(COUNT_DIVISIONS)
    a.code('83c404 8bf0')                   # esi = divisions
    a.code('56 8d442404 50')                # push esi; lea eax, [esp+4]; push eax
    a.call(LIST_WINNERS)
    a.code('83c408 85c0')
    a.jump('0f85', 'out')
    a.code('b907000000 2bce 51')            # ecx = 7 - divisions; push ecx
    a.code('8d44b404 50')                   # lea eax, [esp+esi*4+4]; push eax
    a.call(LIST_WILD_CARDS)
    a.code('83c408 85c0')
    a.jump('0f85', 'out')
    a.code('8b742438')                      # esi = last regular week ([esp+0x38])
    # Next round: #1 hosts, opponent to come.
    a.code('6a06 68ff030000 ff742408 55 8d4602 50')     # status 6, UNSET, t[0], conf, week + 2
    a.call(SET_GAME)
    a.code('83c414 8bd8')                   # ebx = result
    a.call(IS_ACTIVE)
    a.code('84c0')
    a.jump('0f84', 'noted')                 # je
    a.code('ff3424')
    a.call(NOTE_A)
    a.code('83c404 ff3424')
    a.call(NOTE_B)
    a.code('83c404')
    a.label('noted')
    a.code('85db')
    a.jump('0f85', 'fail')
    # Wild-card round: home, away, game number within the conference's numbering.
    for home, away, game in ((1, 6, 0), (2, 5, 2), (3, 4, 4)):
        a.code(f'6a01 ff7424{4 * away + 4:02x} ff7424{4 * home + 8:02x}')   # status 1, away, home
        a.code(f'8d45{game:02x} 50 8d4601 50')                              # conf + game, week + 1
        a.call(SET_GAME)
        a.code('83c414 85c0')
        a.jump('0f85', 'out')
    a.code('ff44241c')                      # inc dword [esp+0x1c]
    a.jump('e9', 'top')
    a.label('done')
    a.code('33c0')
    a.label('out')
    a.code('83c424 5f 5e 5b 5d c3')
    a.label('fail')
    a.code('8bc3')
    a.jump('e9', 'out')
    return a.bytes()


def executable(src):
    x = XBE(src)
    buf = bytearray(x.d)
    assert struct.unpack_from('<I', buf, 0x108)[0] >= 0x1000, 'needs the awareness-fixed XBE (header page mapped)'
    for va, old, new in PATCHES:
        assert len(old) == len(new), f'{va:#x}: patch changes the length'
        o = x.v2f(va)
        assert buf[o:o + len(old)] == old, f'{va:#x}: unexpected code {buf[o:o + len(old)].hex()}'
        buf[o:o + len(new)] = new
    base = struct.unpack_from('<I', buf, 0x104)[0]
    cave = seeding_cave(CAVE_VA)
    o = CAVE_VA - base
    assert CAVE_VA + len(cave) <= 0x10f00 and not any(buf[o:o + len(cave)]), 'cave space in use'
    buf[o:o + len(cave)] = cave
    o = x.v2f(SEEDING)
    assert buf[o:o + 3] == b'\x83\xec\x20', 'unexpected code at the seeding routine'
    buf[o:o + 5] = b'\xe9' + struct.pack('<i', CAVE_VA - (SEEDING + 5))
    print(f'cave: {len(cave)} bytes at {CAVE_VA:#x}')
    return buf


def league(db):
    """Two more wild-card games in both schedules, with kickoffs for all six."""
    s = db['SCHD']
    rows = s.rows()
    games = [r for r in rows if r['SEWT'] == WILD_CARD]
    assert len(games) == 8 and {r['SESI'] for r in games} == {0, 1}, 'expected 4 wild-card games per schedule'
    for sesi in (0, 1):
        mine = sorted((r for r in games if r['SESI'] == sesi), key=lambda r: r['SGNM'])
        rows += [dict(mine[-1], SGNM=len(mine) + k) for k in range(EXTRA_GAMES)]
    for r in rows:
        if r['SEWT'] == WILD_CARD:
            r['GDAT'], r['GTOD'] = KICKOFFS[r['SGNM']]
    grown = S.tdb.DB(db.resized({'SCHD': max(len(rows), s.capacity)}), 0)
    S.write(grown['SCHD'], rows)
    grown.fix()
    assert grown.verify()
    return grown.buf


def franchise(db):
    grown = S.tdb.DB(db.resized({'SCHD': db['SCHD'].capacity + EXTRA_GAMES}), 0)
    grown.fix()
    assert grown.verify()
    return grown.buf


def main(src, dst):
    buf = bytearray(open(src, 'rb').read())
    if buf[:4] == b'XBEH':
        out = executable(src)
    else:
        out = S.repack(buf, {S.LEAGUE: league(S.entry_db(buf, S.LEAGUE)),
                             S.FRANCHISE: franchise(S.entry_db(buf, S.FRANCHISE))})
    open(dst, 'wb').write(out)
    print(f'{os.path.basename(dst)}: {len(buf):,} -> {len(out):,} bytes')


if __name__ == '__main__':
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
