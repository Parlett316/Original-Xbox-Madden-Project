"""Copy Madden 07's radio show code out of its XBE, relocated to run inside Madden 09's.

Used by radio_show.py; on its own it prints what it would move:

    python radio_transplant.py <Madden 07 default.xbe> [<new base VA, default 0x81a000>]

07's show is one block (docs/findings.md section 12): the event stubs, the builder that gives the
week's stRS rows their slots and adds filler, the player, the step function, and start and stop.
The block is found by following the code from its function starts, so jump tables and padding
are never mistaken for instructions. Then:

- calls and jumps that stay inside the block keep their displacement
- calls to the rest of 07 go to 09's copy of the same function (FUNCS, matched with
  tools/xmatch.py), and the name-table search 0x290960, which 09 inlines, is copied as well
- addresses of the block's own code, jump tables and query strings move with it
- 07's globals become 09's (GLOBALS, matched with tools/xglobal.py), and the show's own
  variables get new slots after the strings (OWN)
- any other value that looks like an address stops the build, so nothing is left pointing at 07

The show's state object, which 07's radio screen allocated, is a fixed 0x40 bytes here, and the
pointer to it is set from the start. `init` loads the two name tables 07 kept loaded (SOUNDDAT.dat
entries 7 and 8, team nicknames and cities). `hook` is new code for 09's menu speech update: it
starts the week's show and moves it from segment to segment.
"""
import struct
import sys

CODE = (0x4f000, 0x51410)          # stubs, builder, player, step, start, stop
SEARCH = (0x290960, 0x290996)      # name-table search (inlined in 09)
STRINGS = (0x649f28, 0x64b000)     # the block's query strings

# 07 function -> 09 function
FUNCS = {
    0x405f80: 0x447e80,   # event ID from (project, dat, event)
    0x3e5fb0: 0x427eb0,   # run a DB query
    0x3e3900: 0x425800,
    0x335270: 0x36efb0,
    0x4e670: 0x4e800,     # upper-case a name
    0x41ba73: 0x45d9e3,   # stack cookie check
    0x41ab0e: 0x45ca7e,   # bsearch
    0x33e690: 0x3783d0,   # load an archive entry
    0x33cbc0: 0x376900,   # release an archive entry
    0x3635c0: 0x39e640,   # create a temporary table
    0x363650: 0x39e6d0,   # drop it
    0x2896d0: 0x2a3470,
    0x289900: 0x2a3740,
    0x289960: 0x2a37a0,
    0x341ec0: 0x37bc00,   # stream status
    0x341d10: 0x37ba50,
    0x290910: 0x2aa700,   # name comparer (pushed as an address)
}
# 07 global -> 09 global
GLOBALS = {
    0x790250: 0x7f2c80,   # SOUNDDAT.dat handle
    0x75b720: 0x7bc460,   # pointer to SPCH_AddEventV
    0x6cd3b8: 0x72aae8,   # stack cookie
    0x79ee40: 0x80195c,
    0x7a2ca8: 0x805ea4,
    0x790354: 0x7f2d84,   # menu speech stream
    0x790450: 0x7f2e80,   # music stream
    0x7902d8: 0x7f2d08,   # table being searched
}
# the show's own variables: 07 address -> size
OWN = {0x79f1e0: 4, 0x76e240: 4, 0x791998: 4, 0x7919a4: 4}
# plain numbers that fall in the address range: instruction address -> value
CONSTANTS = {}
STATE, STATE_SIZE = 0x79f1e0, 0x60          # 07's object is 0x24 bytes; the rest is the hook's own variables
ENTRIES = {'start': 0x51220, 'step': 0x51170, 'stop': 0x513b0, 'playing': 0x51200, 'play': 0x50e60}
SOUNDDAT, LOAD_ENTRY = 0x7f2c80, 0x3783d0
GAME_MODE = 0xffe50            # returns the mode: 2 in a franchise, 0x1f at the main menu (xemu)
STAGE_QUERY = 0x61d214          # 09's own "select MCSA from MOIN"
FIRST_STAGE = 5                 # MCSA: 2 on the franchise setup screens, 5 at training camp, 9 in the season (xemu)
UNSET_STAGE = 0x1f              # MCSA while franchise mode is still loading, before the setup screen (xemu)
MUSIC_STATE = 0x7f3010          # menu music state: 1 asked to start, 5 fading out
MUSIC_START = 0x2a37a0          # the menus' "start the music"; its first instruction sets the state to 1
IN_GAME = 0x7dd09d              # set during a game (the speech code tests it)
GOOD_CHECKS = 20                # checks in a row, 16 frames apart (about 5 s), before a started franchise counts
MENU_SETS = 0x774804            # byte: menu resource sets loaded; one more inside the franchise menu
SIMULATING = 0x802400           # nonzero from the start of any simulation to its end (0x178ddc sets it, 0x178f60 clears it)
WEEK_QUERY = 0x64a928           # 07's "select SEWN, SEWT from SEAI", one of the copied strings


class Image:
    def __init__(self, data):
        self.d = data
        base = struct.unpack_from('<I', data, 0x104)[0]
        heads = struct.unpack_from('<I', data, 0x120)[0] - base
        self.secs = [struct.unpack_from('<5I', data, heads + 56 * k)[1:] for k in range(struct.unpack_from('<I', data, 0x11c)[0])]

    def at(self, va, n):
        for sva, _, raw, rsize in self.secs:
            if sva <= va < sva + rsize:
                return self.d[raw + va - sva:raw + va - sva + n]
        raise ValueError(hex(va))


def walk(img, lo, hi):
    """Return ({address: instruction}, {jump table address: [targets]}) for the code in [lo, hi)."""
    import capstone
    from capstone import x86
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    md.detail = True
    code = img.at(lo, hi - lo)
    starts = {lo}
    for i in range(lo + 16 - lo % 16 if lo % 16 else lo, hi, 16):
        if code[i - lo - 1] in (0xcc, 0xc3) and code[i - lo] != 0xcc:
            starts.add(i)
    insns, tables, work = {}, {}, sorted(starts)
    while work:
        a = work.pop()
        while lo <= a < hi and a not in insns:
            ins = next(md.disasm(code[a - lo:a - lo + 16], a), None)
            assert ins is not None, f'bad instruction at {a:#x}'
            insns[a] = ins
            ops = ins.operands
            if ins.id == x86.X86_INS_INT3 or ins.id in (x86.X86_INS_RET, x86.X86_INS_RETF):
                break
            if ins.id == x86.X86_INS_CALL:
                if ops[0].type == x86.X86_OP_IMM and lo <= ops[0].imm < hi:
                    work.append(ops[0].imm)
            elif ins.id == x86.X86_INS_JMP:
                if ops[0].type == x86.X86_OP_IMM:
                    if lo <= ops[0].imm < hi:
                        work.append(ops[0].imm)
                elif ops[0].type == x86.X86_OP_MEM and ops[0].mem.scale == 4 and lo <= ops[0].mem.disp < hi:
                    t, targets = ops[0].mem.disp, []
                    while t + 4 <= hi and t not in insns:
                        v = struct.unpack_from('<I', code, t - lo)[0]
                        if not lo <= v < hi:
                            break
                        targets.append(v)
                        t += 4
                    tables[ops[0].mem.disp] = targets
                    work.extend(targets)
                break
            elif x86.X86_INS_JAE <= ins.id <= x86.X86_INS_JS and ops and ops[0].type == x86.X86_OP_IMM:
                if lo <= ops[0].imm < hi:
                    work.append(ops[0].imm)
            a += ins.size
    return insns, tables


def build(m07, base):
    """Return (bytes to place at `base`, {name: address}) for the relocated show."""
    img = Image(m07)
    code_at = base
    search_at = code_at + (CODE[1] - CODE[0] + 15 & ~15)
    strings_at = search_at + (SEARCH[1] - SEARCH[0] + 15 & ~15)
    own_at = strings_at + (STRINGS[1] - STRINGS[0])
    moved = ((CODE, code_at), (SEARCH, search_at), (STRINGS, strings_at))
    own, at = {}, own_at
    for va, size in OWN.items():
        own[va] = at
        at += size
    state_at = at
    init_at = state_at + STATE_SIZE

    def place(v):
        """Where a 07 address lives in 09, or None if it isn't an address we know."""
        for (lo, hi), new in moved:
            if lo <= v < hi:
                return new + v - lo
        for table in (FUNCS, GLOBALS, own):
            if v in table:
                return table[v]
        return None

    def value(v, where):
        new = place(v)
        if new is not None:
            return new
        if 0x10000 <= v < 0x900000 and v & (v - 1) and CONSTANTS.get(where) != v:     # single bits are flag masks
            unknown.append((where, v))
        return v

    unknown = []
    out = bytearray(init_at - base)
    for (lo, hi), new in moved:
        out[new - base:new - base + hi - lo] = img.at(lo, hi - lo)
    for (lo, hi), new in moved[:2]:
        insns, tables = walk(img, lo, hi)
        for a, ins in insns.items():
            o = new - base + a - lo
            if ins.imm_size and ins.mnemonic[0] in 'jc' and ins.operands[0].type == 2 and ins.mnemonic != 'cmp':   # branch to an address
                target = ins.operands[0].imm
                if lo <= target < hi:
                    continue
                dest = place(target)
                assert dest is not None and ins.imm_size == 4, f'call to unknown {target:#x} at {a:#x}'
                struct.pack_into('<i', out, o + ins.imm_offset, dest - (new + a - lo + ins.size))
                continue
            if ins.disp_size == 4:
                struct.pack_into('<I', out, o + ins.disp_offset, value(ins.disp & 0xffffffff, a))
            if ins.imm_size == 4:
                v = struct.unpack_from('<I', out, o + ins.imm_offset)[0]
                struct.pack_into('<I', out, o + ins.imm_offset, value(v, a))
        for t, targets in tables.items():
            for k, v in enumerate(targets):
                struct.pack_into('<I', out, new - base + t - lo + 4 * k, place(v))
    assert not unknown, 'values that look like addresses: ' + ', '.join(f'{v:#x} at {a:#x}' for a, v in unknown)
    struct.pack_into('<I', out, own[STATE] - base, state_at)
    # 07's radio screen set up the state object; "stopped at the start" (+0x1a) has to begin as 1.
    # With 0, a show that was already built when its save was loaded played twice: start() only
    # marks a show played when that flag is set (xemu and the Xbox, 2026-11-11).
    out[state_at + 0x1a - base] = 1

    # init: load SOUNDDAT.dat entries 7 and 8, the tables 07 kept in 0x791998 and 0x7919a4
    saved = state_at + 0x34            # the SOUNDDAT.dat handle the tables were loaded from (spare state bytes)
    init = b'\xa1' + struct.pack('<I', SOUNDDAT) + b'\xa3' + struct.pack('<I', saved)           # mov eax, [handle]; mov [saved], eax
    for entry, slot in ((7, own[0x791998]), (8, own[0x7919a4])):
        init += bytes([0x6a, 1, 0x6a, entry, 0xff, 0x35]) + struct.pack('<I', SOUNDDAT)         # push 1; push n; push [handle]
        init += b'\xe8' + struct.pack('<i', LOAD_ENTRY - (init_at + len(init) + 5))            # call load
        init += bytes.fromhex('83c40c') + b'\xa3' + struct.pack('<I', slot)                     # add esp, 0xc; mov [slot], eax
    init += b'\xc3'

    # Players are always named by surname. 07 passed PLAY.PCMT, the commentary ID, to the events,
    # and the show's banks for it are full names of that year's players ("Mike Brown"). The
    # Madden 27 roster gives a player the ID of an old player with the same surname, so Tony said
    # the old player's name (the user, 2026-11-10). With 999, "no spoken name", the sentences
    # fall back to the surname found in SOUNDDAT.dat's table, as they did for a rookie in 07.
    for va, old, new in (
            (0x4f68b, '7525', '9090'),                              # eligibility: always check the surname is recorded
            (0x50e25, '8b442410' '56' '50', '56' '68e7030000'),     # event 2: push esi; push 999
            (0x50d12, '8b4c2440' '52' '8b94248c000000' '575356' '50' '51' '52',
                      '52' '8b94248c000000' '575356' '50' '68e7030000' '52')):   # event 0xb: push 999 in PCMT's place
        o = place(va) - base
        assert out[o:o + len(old) // 2] == bytes.fromhex(old), hex(va)
        out[o:o + len(new) // 2] = bytes.fromhex(new)

    # start() falls back to restarting the menu music in the offseason or when its query fails.
    # 07 ran it on entering a menu; here it runs on a timer, so that branch just returns.
    o = place(0x51386) - base
    out[o:o + 5] = b'\xe9' + struct.pack('<i', place(0x513ab) - (place(0x51386) + 5))

    # hook: the tail of 09's menu speech update (0x2b4d20), which jumps here in place of its
    # "add esp, 0xc; ret". That update runs every frame on every menu screen. 07 started and
    # stopped the show from screen commands 09 doesn't have, so the hook decides instead.
    #
    # Every 16th call it reads the game mode (0xffe50: 2 is franchise, 0x1f the main menu) and,
    # in franchise mode, the stage (MOIN.MCSA): 2 on the setup screens, 5 from training camp on,
    # 0x1f while franchise mode is loading. The mode is already 2 on the setup screens, and a
    # franchise left earlier stays in memory, so:
    # - a started franchise (stage 5 to 0x1e) has to be seen GOOD_CHECKS times in a row before
    #   the show may run ("inside")
    # - the setup screens, or 4 checks in a row outside franchise mode, end that: a show in
    #   progress is stopped and marked unplayed, so it starts from the top next time
    # - an unreadable or unset stage changes nothing
    # A loaded save's stage is good as soon as "Load successful" comes up, before OK, and the
    # show started there on the Xbox (2026-11-11). So a started franchise only counts once the
    # franchise menu's own resources are in: the byte at 0x774804 counts loaded menu resource
    # sets (0x35eb3c adds one, 0x35f4ca drops one), and it is 5 from the main menu to "Load
    # successful" and 6 in the franchise menu and its screens (xemu). The hook notes the count
    # whenever it is outside and waits for more than that.
    # Inside, with nothing playing, the week's show is started, once: try_start remembers the
    # week it last started a show for (SEAI.SEWN and SEWT, and whether it's training camp) and
    # does nothing for the same week again. 07's own "already played" flag isn't enough here,
    # because start(0) builds a new show, unplayed, whenever no row has segment type 0, and a
    # show repeated after three segments on the Xbox (2026-11-11). Leaving the franchise forgets
    # the week, so the show starts from the top on coming back.
    # Nothing starts while the game is simulating: [0x802400] is set for the length of any sim
    # (game, week, season or playoffs; the sim loops call this update themselves) and cleared at
    # its end. Without that, a season sim started a new show every week (the Xbox, 2026-11-11).
    # A show already playing runs on until its rows are replaced; the next starts after the sim.
    # While a show plays, the menu music is faded out again if something restarted it.
    #
    # Every call, as 07's update did, step(stream is idle) moves the show to the next segment.
    # When that ends the show, start(0) runs at once in case a simmed week has left a new one,
    # and only otherwise does the music come back. (stop()'s own music calls are removed.)
    #
    # gate: the first instruction of the menus' "start the music" (0x2a37a0) jumps here. Inside
    # a franchise, in the menus, it first gives start(0) the chance to begin a new show, and
    # leaves the music off while one plays. That keeps a song from starting and being cut off
    # after every simmed week.
    #
    # If SOUNDDAT.dat has been reopened (it is after a game) or never read, the name tables are
    # loaded again first; a show in progress carries on, because the builder and player read the
    # tables through their slots each time. Dropping the show there instead silenced it for the
    # rest of the week (2026-11-10). While the file is closed, nothing runs.
    for va in (0x513fb, 0x51400):                  # stop(): call stop the music; call start the music
        o = place(va) - base
        assert out[o] == 0xe8
        out[o:o + 5] = b'\x90' * 5
    hook_at = init_at + len(init)
    playing, played = state_at + 0x19, state_at + 0x1c
    timer, stage = state_at + 0x30, state_at + 0x38        # these are in spare bytes of the state object
    good, inside, away, before = state_at + 0x3c, state_at + 0x3d, state_at + 0x3e, state_at + 0x3f
    week, week_type, last_key, new_key = (state_at + 0x40 + 4 * k for k in range(4))
    base_sets = state_at + 0x50
    struct.pack_into('<i', out, last_key - base, -1)
    h, labels, fixups = bytearray(), {}, []

    def abs32(v):
        return struct.pack('<I', v)

    def call(target):
        if isinstance(target, str):
            h.extend(b'\xe8\0\0\0\0')
            fixups.append((len(h), target))
        else:
            h.extend(b'\xe8' + struct.pack('<i', target - (hook_at + len(h) + 5)))

    def jump(cc, label):                # cc is the short-form opcode (0x74 je, 0xeb jmp); always assembled near
        h.extend(b'\xe9\0\0\0\0' if cc == 0xeb else bytes([0x0f, cc + 0x10, 0, 0, 0, 0]))
        fixups.append((len(h), label))

    def cmp_byte(addr, value):
        h.extend(b'\x80\x3d' + abs32(addr) + bytes([value]))

    def set_byte(addr, value):
        h.extend(b'\xc6\x05' + abs32(addr) + bytes([value]))

    def start_show():
        call('try_start')                                      # call try_start

    h += b'\xa1' + abs32(SOUNDDAT)                             # mov eax, [handle]
    h += b'\x85\xc0'                                           # test eax, eax
    jump(0x74, 'out')                                          # jz out
    h += b'\x3b\x05' + abs32(saved)                            # cmp eax, [saved]
    jump(0x74, 'current')                                      # je current
    call(init_at)                                              # call init
    labels['current'] = len(h)
    h += b'\xff\x05' + abs32(timer)                            # inc dword ptr [timer]
    h += b'\xf6\x05' + abs32(timer) + b'\x0f'                  # test byte ptr [timer], 0xf
    jump(0x75, 'frame')                                        # jnz frame
    call(GAME_MODE)                                            # call game mode
    h += b'\x83\xf8\x02'                                       # cmp eax, 2 (franchise)
    jump(0x75, 'elsewhere')                                    # jne elsewhere
    set_byte(away, 0)                                          # mov byte ptr [away], 0
    h += b'\x68' + abs32(stage) + b'\x68' + abs32(STAGE_QUERY) + b'\x6a\x00'    # push &stage; push query; push 0
    call(FUNCS[0x3e5fb0])                                      # call query: MOIN.MCSA, the franchise's stage
    h += b'\x83\xc4\x0c'                                       # add esp, 0xc
    h += b'\x85\xc0'                                           # test eax, eax
    jump(0x75, 'frame')                                        # jnz frame (no such table: change nothing)
    h += b'\xa1' + abs32(stage)                                # mov eax, [stage]
    h += bytes([0x83, 0xf8, UNSET_STAGE])                      # cmp eax, 0x1f
    jump(0x7d, 'frame')                                        # jge frame (still loading: change nothing)
    h += bytes([0x83, 0xf8, FIRST_STAGE])                      # cmp eax, 5
    jump(0x7c, 'outside')                                      # jl outside (the setup screens)
    h += bytes([0xa0]) + abs32(MENU_SETS)                      # mov al, [menu resource sets loaded]
    h += bytes([0x3a, 0x05]) + abs32(base_sets)                # cmp al, [the count outside a franchise]
    jump(0x76, 'not_yet')                                      # jbe not_yet: the franchise menu isn't loaded
    cmp_byte(good, GOOD_CHECKS)                                # cmp byte ptr [good], 12
    jump(0x73, 'is_inside')                                    # jae is_inside
    h += b'\xfe\x05' + abs32(good)                             # inc byte ptr [good]
    jump(0xeb, 'frame')                                        # jmp frame
    labels['is_inside'] = len(h)
    set_byte(inside, 1)                                        # mov byte ptr [inside], 1
    cmp_byte(playing, 0)                                       # cmp byte ptr [playing], 0
    jump(0x75, 'music')                                        # jne music
    start_show()                                               # start(0)
    jump(0xeb, 'frame')                                        # jmp frame
    labels['music'] = len(h)
    h += b'\x83\x3d' + abs32(MUSIC_STATE) + b'\x05'            # cmp dword ptr [music state], 5 (fading out)
    jump(0x74, 'frame')                                        # je frame
    call(FUNCS[0x2896d0])                                      # call fade the music out
    jump(0xeb, 'frame')                                        # jmp frame
    labels['not_yet'] = len(h)
    set_byte(good, 0)                                          # mov byte ptr [good], 0
    jump(0xeb, 'frame')                                        # jmp frame
    labels['elsewhere'] = len(h)
    cmp_byte(away, 4)                                          # cmp byte ptr [away], 4
    jump(0x73, 'outside')                                      # jae outside
    h += b'\xfe\x05' + abs32(away)                             # inc byte ptr [away]
    jump(0xeb, 'frame')                                        # jmp frame
    labels['outside'] = len(h)
    h += bytes([0xa0]) + abs32(MENU_SETS) + bytes([0xa2]) + abs32(base_sets)   # mov al, [sets loaded]; mov [base], al
    set_byte(good, 0)                                          # mov byte ptr [good], 0
    set_byte(inside, 0)                                        # mov byte ptr [inside], 0
    h += bytes([0xc7, 0x05]) + abs32(last_key) + abs32(0xffffffff)     # mov dword ptr [last key], -1
    cmp_byte(playing, 0)                                       # cmp byte ptr [playing], 0
    jump(0x74, 'frame')                                        # je frame
    call(place(ENTRIES['stop']))                               # call stop
    set_byte(played, 0)                                        # mov byte ptr [played], 0
    call(FUNCS[0x289900])                                      # call stop the music
    call('real')                                               # call start the music
    labels['frame'] = len(h)
    h += b'\xa0' + abs32(playing) + b'\xa2' + abs32(before)    # mov al, [playing]; mov [before], al
    h += b'\xa1' + abs32(GLOBALS[0x790354])                    # mov eax, [speech stream]
    h += b'\x8d\x14\x24\x52\x50'                               # lea edx, [esp]; push edx; push eax
    call(FUNCS[0x341ec0])                                      # call stream status
    h += b'\x8b\x54\x24\x08\x83\xc4\x08'                       # mov edx, [esp+8]; add esp, 8
    h += b'\x85\xd2\x0f\x94\xc0\x50'                           # test edx, edx; sete al; push eax
    call(place(ENTRIES['step']))                               # call step
    h += b'\x83\xc4\x04'                                       # add esp, 4
    cmp_byte(before, 0)                                        # cmp byte ptr [before], 0
    jump(0x74, 'out')                                          # je out
    cmp_byte(playing, 0)                                       # cmp byte ptr [playing], 0
    jump(0x75, 'out')                                          # jne out
    cmp_byte(inside, 0)                                        # the show has just ended: cmp byte ptr [inside], 0
    jump(0x74, 'resume')                                       # je resume
    start_show()                                               # start(0): a new week's show?
    cmp_byte(playing, 0)                                       # cmp byte ptr [playing], 0
    jump(0x75, 'out')                                          # jne out
    labels['resume'] = len(h)
    call(FUNCS[0x289900])                                      # call stop the music
    call('real')                                               # call start the music
    labels['out'] = len(h)
    h += b'\x83\xc4\x0c\xc3'                                   # add esp, 0xc; ret

    labels['gate'] = len(h)
    cmp_byte(inside, 0)                                        # cmp byte ptr [inside], 0
    jump(0x74, 'real')                                         # je real
    cmp_byte(IN_GAME, 0)                                       # cmp byte ptr [in a game], 0
    jump(0x75, 'real')                                         # jne real
    cmp_byte(playing, 0)                                       # cmp byte ptr [playing], 0
    jump(0x75, 'quiet')                                        # jne quiet
    start_show()                                               # start(0)
    cmp_byte(playing, 0)                                       # cmp byte ptr [playing], 0
    jump(0x74, 'real')                                         # je real
    labels['quiet'] = len(h)
    h += b'\xc3'                                               # ret
    labels['real'] = len(h)
    h += b'\xc7\x05' + abs32(MUSIC_STATE) + abs32(1)           # mov dword ptr [music state], 1 (the replaced instruction)
    h += b'\xe9' + struct.pack('<i', MUSIC_START + 10 - (hook_at + len(h) + 5))             # jmp back into start the music

    labels['try_start'] = len(h)
    h += bytes([0x83, 0x3d]) + abs32(SIMULATING) + bytes([0])      # cmp dword ptr [simulating], 0
    jump(0x75, 'tried')                                        # jne tried: no show starts during a sim
    h += bytes([0x68]) + abs32(week_type) + bytes([0x68]) + abs32(week)        # push &type; push &week
    h += bytes([0x68]) + abs32(place(WEEK_QUERY)) + bytes([0x6a, 0])           # push query; push 0
    call(FUNCS[0x3e5fb0])                                      # call query: SEAI.SEWN and SEWT
    h += bytes([0x83, 0xc4, 0x10])                             # add esp, 0x10
    h += bytes([0x85, 0xc0])                                   # test eax, eax
    jump(0x75, 'tried')                                        # jnz tried
    h += bytes([0xa1]) + abs32(week)                           # mov eax, [week]
    h += bytes([0xc1, 0xe0, 0x08])                             # shl eax, 8
    h += bytes([0x0b, 0x05]) + abs32(week_type)                # or eax, [type]
    h += bytes([0x83, 0x3d]) + abs32(stage) + bytes([FIRST_STAGE])             # cmp dword ptr [stage], 5 (training camp)
    h += bytes([0x75, 0x05])                                   # jne +5
    h += bytes([0x0d]) + abs32(0x10000)                        # or eax, 0x10000
    h += bytes([0x3b, 0x05]) + abs32(last_key)                 # cmp eax, [last key]
    jump(0x74, 'tried')                                        # je tried: this week's show has been started
    h += bytes([0xa3]) + abs32(new_key)                        # mov [new key], eax
    h += bytes([0x6a, 0x00])                                   # push 0
    call(place(ENTRIES['start']))                              # call start
    h += bytes([0x83, 0xc4, 0x04])                             # add esp, 4
    cmp_byte(playing, 0)                                       # cmp byte ptr [playing], 0
    jump(0x74, 'tried')                                        # je tried
    h += bytes([0xa1]) + abs32(new_key) + bytes([0xa3]) + abs32(last_key)      # mov eax, [new key]; mov [last key], eax
    labels['tried'] = len(h)
    h += bytes([0xc3])                                         # ret
    for at, label in fixups:
        struct.pack_into('<i', h, at - 4, labels[label] - at)
    names = {name: place(va) for name, va in ENTRIES.items()}
    names.update(init=init_at, state=state_at, search=search_at, strings=strings_at, hook=hook_at,
                 gate=hook_at + labels['gate'])
    return bytes(out) + init + bytes(h), names


if __name__ == '__main__':
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    base = int(sys.argv[2], 0) if len(sys.argv) > 2 else 0x81a000
    blob, names = build(open(sys.argv[1], 'rb').read(), base)
    print(f'{len(blob):,} bytes at {base:#x}')
    for name, va in sorted(names.items(), key=lambda kv: kv[1]):
        print(f'  {name:8} {va:#x}')
