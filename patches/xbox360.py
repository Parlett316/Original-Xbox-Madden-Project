"""Make a patched Madden 09 default.xbe run on an Xbox 360 (backward compatibility emulator).

    python xbox360.py <stock default.xbe> <in default.xbe> <out default.xbe>

The 360's emulator won't run code in the XBE's header page (tested on a hacked 360, 2026-11-22:
a 5-byte jmp there fails, the same code in the last section works). A softmodded Xbox and xemu
don't mind, so several patches put their caves in the header page's zero padding (0x10b40 to
0x11000): playoffs7.py, radio_show.py, kickoff_spot.py, optional_fullback.py,
madden_awareness_fix.py and season17.py.

This moves that block, unchanged, to 0x819b40-0x81a000: free space at the end of the last
section (.XTLID), right before the radio show's code at 0x81a000. The move is 0x809000 bytes up.
If the radio show didn't already grow the section, it grows to 0x81a000 and gets the radio
show's flags (writable, preloaded, executable; both tested on the 360).

- Inside the block, calls and jumps that leave it (rel32) are adjusted. Branches inside it move
  with it. The caves hold no absolute addresses of themselves; anything else stops the script.
- Outside it, every call or jump into the block is found among the bytes that differ from the
  stock XBE and pointed at the new place (8 in the v1.0 release: one per hook).
- The old block is zeroed, so anything missed would fail on an Xbox and in xemu too.
- Every section digest is recomputed.

Run it last, after every other default.xbe patch (online.py included).
"""
import hashlib
import struct
import sys

import capstone

LO, HI = 0x10b40, 0x11000          # the caves' part of the header page
DEST = 0x819b40                    # .XTLID's free tail, up to the radio show at 0x81a000
D = DEST - LO
# where each patch's cave starts (playoffs7, radio_show, kickoff_spot, optional_fullback,
# madden_awareness_fix, season17); the disassembly must account for every non-zero byte
STARTS = (0x10b40, 0x10e40, 0x10e80, 0x10ee0, 0x10f00, 0x10f60)
REL32 = {0xe8, 0xe9}


def sections(b):
    base = struct.unpack_from('<I', b, 0x104)[0]
    head = struct.unpack_from('<I', b, 0x120)[0] - base
    return base, head, [struct.unpack_from('<5I', b, head + 56 * k) for k in range(struct.unpack_from('<I', b, 0x11c)[0])]


def va_of(secs, o):
    for _, va, _, raw, rs in secs:
        if raw <= o < raw + rs:
            return va + o - raw


def branch(ins):
    """(offset of the rel32 within the instruction, target) for a call/jmp/jcc rel32, else None."""
    op = ins.bytes
    if op[0] in REL32 and ins.size == 5:
        return 1, ins.address + 5 + struct.unpack_from('<i', op, 1)[0]
    if op[0] == 0x0f and 0x80 <= op[1] <= 0x8f and ins.size == 6:
        return 2, ins.address + 6 + struct.unpack_from('<i', op, 2)[0]


def decode(block):
    """The block's instructions, from each cave start to the zero padding after it."""
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    insns, covered = [], bytearray(len(block))
    for s in STARTS:
        at = s
        while at < HI and any(block[at - LO:at - LO + 4]):
            ins = next(md.disasm(bytes(block[at - LO:at - LO + 16]), at), None)
            assert ins, f'{at:#x}: undecodable'
            insns.append(ins)
            covered[at - LO:at - LO + ins.size] = b'\1' * ins.size
            at += ins.size
    stray = [LO + i for i, v in enumerate(block) if v and not covered[i]]
    assert not stray, f'non-zero bytes outside the known caves: {stray[0]:#x}'
    return insns


def check_operands(insns):
    import re
    for ins in insns:
        br = branch(ins)
        vals = [int(v, 16) for v in re.findall(r'0x[0-9a-f]+', ins.op_str)]
        header = [v for v in vals if 0x10000 <= v < 0x11000]
        if br:
            continue
        if ins.mnemonic.startswith('j') or ins.mnemonic in ('call', 'loop', 'jecxz'):
            assert all(LO <= v < HI for v in vals), f'{ins.address:#x}: short branch out of the block'
            continue
        assert not header, f'{ins.address:#x}: absolute header-page address ({ins.mnemonic} {ins.op_str})'


def grow_last(b, secs, head, base):
    """Make the last section reach 0x81a000, writable, preloaded and executable."""
    k = len(secs) - 1
    fl, va, vs, raw, rs = secs[k]
    assert va < DEST and 0 <= len(b) - (raw + rs) < 0x1000, 'last section is not .XTLID at the end'
    if va + vs >= HI + D:
        assert fl & 0x07 == 0x07, 'last section is not executable'
        return
    assert struct.unpack_from('<I', b, 0x10c)[0] == va + vs - base, 'image size'
    del b[raw + rs:]
    b.extend(bytes(raw + (HI + D - va) - len(b)))
    b.extend(bytes(-len(b) % 0x1000))
    size = len(b) - raw
    struct.pack_into('<5I', b, head + 56 * k, 0x07, va, size, raw, size)
    struct.pack_into('<I', b, 0x10c, va + size - base)


def patch(stock, b):
    base, head, secs = sections(b)
    assert base == 0x10000, 'unexpected base address'
    block = bytearray(b[LO - base:HI - base])
    if struct.unpack_from('<I', b, 0x108)[0] < HI - base or not any(block):
        print('no code in the header page: unchanged')
        return 0
    insns = decode(block)
    check_operands(insns)

    # hooks: rel32 calls/jumps into the block, among the bytes that differ from stock
    hooks = []
    for o in range(0x1000, len(b) - 6):
        if o + 6 <= len(stock) and b[o:o + 6] == stock[o:o + 6]:
            continue
        v = va_of(secs, o)
        if v is None or LO <= v < HI:
            continue
        if b[o] in REL32:
            t = v + 5 + struct.unpack_from('<i', b, o + 1)[0]
            if LO <= t < HI:
                hooks.append((o + 1, v + 5, t))
        elif b[o] == 0x0f and 0x80 <= b[o + 1] <= 0x8f:
            t = v + 6 + struct.unpack_from('<i', b, o + 2)[0]
            if LO <= t < HI:
                hooks.append((o + 2, v + 6, t))
        d = struct.unpack_from('<I', b, o)[0]
        if LO <= d < HI and not (b[o - 1] == 0x0f and 0x80 <= b[o] <= 0x8f):   # a jcc's opcode, not an address
            raise SystemExit(f'{v:#x}: possible absolute pointer into the header page ({d:#x})')
    assert hooks, 'no calls into the header page'

    grow_last(b, secs, head, base)
    base, head, secs = sections(b)
    dest = next(raw + DEST - va for _, va, vs, raw, rs in secs if va <= DEST < va + rs)
    assert not any(b[dest:dest + len(block)]), 'the destination is in use'

    moved = bytearray(block)
    for ins in insns:
        br = branch(ins)
        if br and not LO <= br[1] < HI:
            at = ins.address - LO + br[0]
            struct.pack_into('<i', moved, at, struct.unpack_from('<i', moved, at)[0] - D)
    for at, _, _ in hooks:
        struct.pack_into('<i', b, at, struct.unpack_from('<i', b, at)[0] + D)
    b[LO - base:HI - base] = bytes(len(block))
    b[dest:dest + len(moved)] = moved

    # the moved code must say the same thing at its new address
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    for ins in insns:
        new = next(md.disasm(bytes(moved[ins.address - LO:ins.address - LO + 16]), ins.address + D))
        assert new.mnemonic == ins.mnemonic and new.size == ins.size, f'{ins.address:#x}: decodes differently'
        old_t, new_t = branch(ins), branch(new)
        if old_t:
            want = old_t[1] + D if LO <= old_t[1] < HI else old_t[1]
            assert new_t[1] == want, f'{ins.address:#x}: branch target'
        elif not ins.mnemonic.startswith('j'):
            assert new.op_str == ins.op_str, f'{ins.address:#x}: operands changed'
    for at, end, t in hooks:
        assert end + struct.unpack_from('<i', b, at)[0] == t + D, f'{end:#x}: hook target'

    for k, (_, _, _, raw, rs) in enumerate(secs):
        b[head + 56 * k + 36:head + 56 * k + 56] = hashlib.sha1(struct.pack('<I', rs) + bytes(b[raw:raw + rs])).digest()
    for _, end, t in hooks:
        print(f'  hook at {end:#x} -> {t + D:#x} (was {t:#x})')
    return len(hooks)


def main(stock_path, src, dst):
    stock = open(stock_path, 'rb').read()
    b = bytearray(open(src, 'rb').read())
    n = patch(stock, b)
    open(dst, 'wb').write(b)
    print(f'{dst}: header-page code moved to {DEST:#x} ({n} hooks), {len(b):,} bytes' if n else f'{dst}: unchanged')


if __name__ == '__main__':
    if len(sys.argv) != 4:
        raise SystemExit(__doc__)
    main(*sys.argv[1:4])
