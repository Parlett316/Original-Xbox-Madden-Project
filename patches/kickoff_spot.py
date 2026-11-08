"""Move the Madden 09 kickoff to the kicking team's 35 (default.xbe).

    python kickoff_spot.py <in default.xbe> <out default.xbe>

Field positions are yards from midfield, with the kicking team's own half
negative: its 30 is -20 and its 35 is -15 (findings section 7, read from xemu
memory). The ball spot goes through the setter 0x294180.

- Practice mode keeps its state at [0x801c50] (+0x34 across, +0x38 downfield).
  Six paths there set a kickoff to (0, -20.0) before calling the setter.
- Games use 0x1b83f7, which picks -20.0 for situation 0 before the setter call
  at 0x1b8589.
- Play Now's kickoff is 0x30c730: an adjustment ([[0x8034f0]+0x4c], normally
  0) minus 20.0 from the shared constant 0x6fc624. That fsub now reads a
  read-only 15.0 at 0x69653c instead, so the shared 20.0 stays as it is.
- 0x293e4d moves a spot still at -20.0 back to -30.0 for a safety kick; it now
  compares against -15.0, so safety kicks stay on the 20.

Touchbacks: 0x268eab in the play-result rules (0x2687d0) puts every touchback
on the 20, +30.0 at 0x268ecc or -30.0 at 0x268efa depending on direction.
Interceptions and punts share it. The play type ([0x803504]+0x40) is 0 for
punts too by then (tested), so the cave checks where the ball was snapped
instead: [0x803504]+0x10, negated when the field flips on a change of
possession. A snap at exactly +-15.0 is a kickoff from the 35, and gets half
the stock value (the 35); anything else keeps the stock value (the 20). A punt
snapped from exactly the 35 would also get the 35, and a kickoff moved by a
penalty keeps the 20.

Out of bounds: 0x291611 is the 2008 penalty for a kickoff out of bounds: the
receiving team's ball 30 yards from the kick (kick spot - 30.0, in its own
coordinates), or where the ball went out if that's better for it. From the 35
that gave the receiving 35. The modern rule is the receiving 40, so the first
part now loads -10.0 (the read-only constant at 0x709408) instead. Safety
kicks out of bounds probably go through it too.

Run after madden_awareness_fix.py, which identifies the stock .text by its
digest and makes the loader map the header page the caves sit in. Like the
other code patches, this doesn't recompute the digest.
Use patches/kickoff_setup.py --ball 35 with it so the lineup follows the ball.
"""
import struct
import sys

NEW_SPOT = -15.0
STOCK = struct.pack('<f', -20.0)
NEW = struct.pack('<f', NEW_SPOT)
# VA of the instruction, and its bytes before the float
SITES = (
    (0x45bef, 'c74238'),     # mov dword ptr [edx+0x38], -20.0
    (0x45fbd, 'c74038'),     # mov dword ptr [eax+0x38], -20.0
    (0x4660d, 'c74038'),
    (0x4715e, 'c74038'),
    (0x16a96d, 'c74238'),
    (0x293bc9, 'c74038'),
    (0x1b83f7, 'c7442410'),  # mov dword ptr [esp+0x10], -20.0 (situation 0, games)
    (0x293e4d, '817e10'),    # cmp dword ptr [esi+0x10], -20.0 (safety kick)
)

# fsub dword ptr [0x6fc624] (20.0) -> fsub dword ptr [0x69653c] (15.0)
FSUB_VA = 0x30c73c
FSUB_STOCK = bytes.fromhex('d82524c66f00')
FSUB_NEW = bytes.fromhex('d8253c656900')
FIFTEEN_VA = 0x69653c

# touchback stores: mov dword ptr [ebp+8], +-30.0 (7 bytes) -> call cave; nop; nop
TOUCHBACK_CAVE_VA = 0x10e80          # header page: after playoffs7's cave, before optional_fullback's
TOUCHBACK_CAVE_END = 0x10ee0
TOUCHBACKS = ((0x268ecc, 30.0), (0x268efa, -30.0))


def file_offset(buf, va):
    base = struct.unpack_from('<I', buf, 0x104)[0]
    headers = struct.unpack_from('<I', buf, 0x120)[0] - base
    for k in range(struct.unpack_from('<I', buf, 0x11c)[0]):
        _, sva, vsize, raw, rsize = struct.unpack_from('<5I', buf, headers + k * 56)
        if sva <= va < sva + min(vsize, rsize):
            return va - sva + raw
    raise SystemExit(f'no section holds {va:#x}')


# fld dword ptr [esi]; fsub dword ptr [0x7093e4] (30.0) -> fld dword ptr [0x709408] (-10.0); nop; nop
OOB_VA = 0x291618
OOB_STOCK = bytes.fromhex('d906d825e4937000')
OOB_NEW = bytes.fromhex('d905089470009090')
MINUS_TEN_VA = 0x709408


def touchback_cave(stock, kickoff):
    # eax and the flags are dead after both hooked stores (0x268f01 reloads eax)
    return (bytes.fromhex('a1') + struct.pack('<I', 0x803504)      # mov eax, [0x803504]
            + bytes.fromhex('8b4010')                               # mov eax, [eax+0x10] (snap spot)
            + bytes.fromhex('25ffffff7f')                           # and eax, 0x7fffffff (abs)
            + bytes.fromhex('3d') + struct.pack('<f', -NEW_SPOT)    # cmp eax, 15.0
            + bytes.fromhex('c74508') + struct.pack('<f', stock)    # mov dword ptr [ebp+8], stock
            + bytes.fromhex('7507')                                 # jne done
            + bytes.fromhex('c74508') + struct.pack('<f', kickoff)  # mov dword ptr [ebp+8], kickoff
            + bytes.fromhex('c3'))                                  # done: ret


def patch_touchbacks(buf):
    base = struct.unpack_from('<I', buf, 0x104)[0]
    loaded = base + struct.unpack_from('<I', buf, 0x108)[0]
    at = TOUCHBACK_CAVE_VA
    for site, stock in TOUCHBACKS:
        cave = touchback_cave(stock, stock / 2)
        o = at - base
        assert at + len(cave) <= TOUCHBACK_CAVE_END <= loaded, 'needs the awareness fix first'
        assert not any(buf[o:o + len(cave)]), 'cave space in use'
        buf[o:o + len(cave)] = cave
        so = file_offset(buf, site)
        assert bytes(buf[so:so + 7]) == bytes.fromhex('c74508') + struct.pack('<f', stock), f'unexpected code at {site:#x}'
        buf[so:so + 7] = bytes([0xe8]) + struct.pack('<i', at - (site + 5)) + bytes([0x90, 0x90])
        at += len(cave)
    print(f'kickoff touchbacks -> the 35, caves {TOUCHBACK_CAVE_VA:#x}-{at:#x}')


def patch_out_of_bounds(buf):
    o = file_offset(buf, MINUS_TEN_VA)
    assert bytes(buf[o:o + 4]) == struct.pack('<f', -10.0), 'no -10.0 constant'
    o = file_offset(buf, OOB_VA)
    assert bytes(buf[o:o + 8]) == OOB_STOCK, 'unexpected code at the out-of-bounds kickoff rule'
    buf[o:o + 8] = OOB_NEW
    print(f'kickoff out of bounds -> the receiving 40 at {OOB_VA:#x}')


def patch(buf):
    patch_touchbacks(buf)
    patch_out_of_bounds(buf)
    o = file_offset(buf, FIFTEEN_VA)
    assert bytes(buf[o:o + 4]) == struct.pack('<f', 15.0), 'no 15.0 constant'
    o = file_offset(buf, FSUB_VA)
    assert bytes(buf[o:o + 6]) == FSUB_STOCK, 'unexpected code at the Play Now kickoff'
    buf[o:o + 6] = FSUB_NEW
    for va, opcode in SITES:
        o = file_offset(buf, va)
        op = bytes.fromhex(opcode)
        assert bytes(buf[o:o + len(op)]) == op, f'unexpected instruction at {va:#x}'
        at = o + len(op)
        assert bytes(buf[at:at + 4]) == STOCK, f'{va:#x} is not -20.0'
        buf[at:at + 4] = NEW
    print(f'kickoff spot -20.0 -> -15.0 at {len(SITES)} sites and the Play Now kickoff at {FSUB_VA:#x}')


def main(src, dst):
    with open(src, 'rb') as f:
        buf = bytearray(f.read())
    size = len(buf)
    patch(buf)
    assert len(buf) == size
    with open(dst, 'wb') as f:
        f.write(buf)


if __name__ == '__main__':
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    main(*sys.argv[1:])
