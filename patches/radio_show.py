"""Load Madden 07's radio show (the Tony Bruno Show) speech data in Madden 09 (default.xbe). A test build.

    python radio_show.py <in default.xbe> <out default.xbe> [--show <Madden 07 default.xbe>] [--test-draft]

Copy 07's SPCHFEDT.dat to the game's data folder as spchfe07.dat (228,714,976 bytes). It holds
09's draft clips too: the same first 0xa6 sub-banks and the same event file in entry 1. The new
name keeps it out of fe.qkl, which preloads the stock file's header and first entries, and leaves
the stock file in place.

09's front-end speech loader (0x2b4680) is 08's, which stopped loading the show (findings
section 12). The patch puts back what 07's loader (0x29a9d0) did:

- the file name at 0x73dad8 becomes spchfe07.dat
- it registers 0x1151 sub-bank descriptors instead of 0xa6 (0x2b46e6)
- the first audio entry is 3 instead of 2 (0x2b4700), because entry 2 is the show's event file
- the call that loads event file 1 (0x2b46b8) goes through a cave that loads event file 2 first

The menus' sample player (0x2b3c70) turns the speech stream's volume up only for the draft's
event (ID 0xe000), so the show's samples were queued and played at zero volume. The jne at
0x2b3c9a is removed, and every menu sample sets the volume (heard in xemu, 2026-11-10).

--show <Madden 07 default.xbe> also copies 07's show code into the XBE (radio_transplant.py). It
goes at 0x81a000, in the last section, .XTLID, which grows to hold it and becomes preloaded and
writable. default.xbe gets about 16 KB larger. The menu speech update (0x2b4d20), which runs in
the franchise menus, then jumps to the show's hook: it starts the week's show if it hasn't been
played and moves it on when Tony stops talking. The menus' "start the music" (0x2a37a0) goes
through the show's gate, which keeps the music off while a show plays. The entry points are printed, for
tools/xemu_call.py.

--test-draft makes the fantasy draft's "on the clock" announcement (0x145660) fire two of the
show's events instead, with the parameters 07 was seen to use: event 7 (0x03000000) and event
0x10 (8, 2, 4). It's only there to hear whether the show's audio plays in 09.

Run after madden_awareness_fix.py, which makes the loader map the header page the cave sits in.
Like the other code patches, this doesn't recompute the digest.
"""
import struct
import sys

NAME_VA, OLD_NAME, NEW_NAME = 0x73dad8, b'spchfedt.dat\0', b'spchfe07.dat\0'
COUNT_VA, OLD_COUNT, NEW_COUNT = 0x2b46e6, 0xa6, 0x1151      # cmp esi, imm32
BASE_VA = 0x2b4700                                           # mov dword ptr [0x7f392c], imm32
LOAD_CALL_VA, LOAD_EVENTS = 0x2b46b8, 0x447d90               # call load_events(file, entry, 0)
CAVE_VA, CAVE_END = 0x10e40, 0x10e80     # header page: the unused end of playoffs7.py's space
VOLUME_VA = 0x2b3c9a                                         # jne past the volume call unless the event is 0xe000
DRAFT_VA, DRAFT_END = 0x145660, 0x1456a0                     # the draft's announcement, with its padding
MAKE_ID, ADD_EVENT_PTR = 0x447e80, 0x7bc460                  # event ID builder, pointer to SPCH_AddEventV


def file_offset(buf, va):
    base = struct.unpack_from('<I', buf, 0x104)[0]
    if base <= va < base + 0x1000:
        return va - base
    headers = struct.unpack_from('<I', buf, 0x120)[0] - base
    for k in range(struct.unpack_from('<I', buf, 0x11c)[0]):
        _, sva, _, raw, rsize = struct.unpack_from('<5I', buf, headers + 56 * k)
        if sva <= va < sva + rsize:
            return raw + va - sva
    raise ValueError(hex(va))


def put(buf, va, old, new):
    o = file_offset(buf, va)
    assert bytes(buf[o:o + len(old)]) == old, f'unexpected bytes at {va:#x}'
    buf[o:o + len(new)] = new


def rel(at, target):
    """The operand of a call or jmp whose opcode byte is at `at`."""
    return struct.pack('<i', target - (at + 5))


def loader_cave():
    # on entry: [ret] [file] [1] [0], the arguments of the call it replaces
    code = bytes.fromhex('6a00' '6a02' 'ff74240c')                  # push 0; push 2; push [esp+0xc] (file)
    code += b'\xe8' + rel(CAVE_VA + len(code), LOAD_EVENTS)         # call load_events: the show's events
    code += bytes.fromhex('83c40c')                                 # add esp, 0xc
    code += b'\xe9' + rel(CAVE_VA + len(code), LOAD_EVENTS)         # jmp load_events: entry 1, as before
    return code


def fire(at, event, params):
    """AddEventV(make_id(0, 0, event), count, params...)."""
    code = b''.join(b'\x68' + struct.pack('<I', p) if p > 0x7f else bytes([0x6a, p]) for p in reversed(params))
    code += bytes([0x6a, len(params), 0x6a, event, 0x6a, 0, 0x6a, 0])
    code += b'\xe8' + rel(at + len(code), MAKE_ID)
    code += bytes.fromhex('83c40c' '50' 'ff15') + struct.pack('<I', ADD_EVENT_PTR)
    return code + bytes([0x83, 0xc4, 4 * (len(params) + 2)])


SHOW_VA = 0x81a000
UPDATE_TAIL_VA = 0x2b4d47      # end of the menu speech update, 0x2b4d20
MUSIC_START_VA = 0x2a37a0      # the menus' "start the music"


def add_show(buf, m07):
    """Grow the last section to hold 07's show code at SHOW_VA. Returns its entry points."""
    import os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import radio_transplant
    blob, names = radio_transplant.build(m07, SHOW_VA)
    base = struct.unpack_from('<I', buf, 0x104)[0]
    head = struct.unpack_from('<I', buf, 0x120)[0] - base + 56 * (struct.unpack_from('<I', buf, 0x11c)[0] - 1)
    flags, va, vsize, raw, rsize = struct.unpack_from('<5I', buf, head)
    assert raw + rsize <= len(buf) and va + vsize <= SHOW_VA and len(buf) - raw <= SHOW_VA - va, 'last section is not at the end'
    assert struct.unpack_from('<I', buf, 0x10c)[0] == va + vsize - base, 'image size'
    del buf[raw + SHOW_VA - va:]
    buf.extend(bytes(raw + SHOW_VA - va - len(buf)))
    buf.extend(blob)
    buf.extend(bytes(-len(buf) % 0x1000))
    size = len(buf) - raw
    struct.pack_into('<5I', buf, head, 0x07, va, size, raw, size)       # writable, preloaded, executable
    struct.pack_into('<I', buf, 0x10c, va + size - base)
    # the menu speech update ends "add esp, 0xc; ret" and padding: jump to the show's hook instead
    put(buf, UPDATE_TAIL_VA, bytes.fromhex('83c40cc3cc'), bytes([0xe9]) + rel(UPDATE_TAIL_VA, names['hook']))
    # the menus' "start the music" begins "mov dword ptr [0x7f3010], 1": go through the show's gate
    put(buf, MUSIC_START_VA, bytes.fromhex('c70510307f0001000000'), bytes([0xe9]) + rel(MUSIC_START_VA, names['gate']) + bytes([0x90] * 5))
    return names


def patch(buf, test_draft=False):
    put(buf, NAME_VA, OLD_NAME, NEW_NAME)
    put(buf, COUNT_VA, bytes.fromhex('81fe') + struct.pack('<I', OLD_COUNT), bytes.fromhex('81fe') + struct.pack('<I', NEW_COUNT))
    put(buf, BASE_VA, bytes.fromhex('c7052c397f00') + struct.pack('<I', 2), bytes.fromhex('c7052c397f00') + struct.pack('<I', 3))
    cave = loader_cave()
    assert CAVE_VA + len(cave) <= CAVE_END
    put(buf, CAVE_VA, bytes(len(cave)), cave)
    put(buf, LOAD_CALL_VA, b'\xe8' + rel(LOAD_CALL_VA, LOAD_EVENTS), b'\xe8' + rel(LOAD_CALL_VA, CAVE_VA))
    put(buf, VOLUME_VA, bytes.fromhex('752b'), bytes.fromhex('9090'))
    if test_draft:
        code = fire(DRAFT_VA, 7, [0x03000000])
        code += fire(DRAFT_VA + len(code), 0x10, [8, 2, 4]) + b'\xc3'
        assert DRAFT_VA + len(code) <= DRAFT_END, len(code)
        put(buf, DRAFT_VA, bytes.fromhex('5657e8'), code)


def main(src, dst, test_draft=False, m07=None):
    with open(src, 'rb') as f:
        buf = bytearray(f.read())
    size = len(buf)
    patch(buf, test_draft)
    assert len(buf) == size
    names = {}
    if m07:
        with open(m07, 'rb') as f:
            names = add_show(buf, f.read())
    with open(dst, 'wb') as f:
        f.write(buf)
    print(f'wrote {dst} ({len(buf):,} bytes)' + (', with the draft test' if test_draft else ''))
    for name, va in sorted(names.items(), key=lambda kv: kv[1]):
        print(f'  {name:8} {va:#x}')


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if a != '--test-draft']
    m07 = None
    if '--show' in args:
        i = args.index('--show')
        m07 = args[i + 1]
        del args[i:i + 2]
    if len(args) != 2:
        raise SystemExit(__doc__)
    main(args[0], args[1], '--test-draft' in sys.argv, m07)
