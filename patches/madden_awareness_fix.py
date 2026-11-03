"""Franchise awareness-inflation fix for Madden NFL 07, 08 and 09 (Xbox, USA).

Root cause (same in all three):
  Player roles (Team Leader, Mentor, Franchise QB, ...) are applied by writing
  rating bonuses straight into the stored PLAY ratings. Assigning a role calls
  the self-bonus and teammate-bonus routines with remove=0; removing a role
  calls them with remove=1 and then clears the slot. But when a player who
  already holds two roles earns a better one, the role pass frees a slot by
  writing "no role" to PROL/PRL2 directly, without the remove calls. The
  displaced role's bonuses stay baked in and are applied again the next time
  the role is earned, so awareness ratchets toward 99.

Fix 1: the direct slot clear jumps to a code cave that first reverses the
       displaced role's bonuses (the game's own routines, remove=1), then does
       the original clear and returns.
Fix 2: the teammate-bonus handlers clamp with an unsigned compare, so a rating
       pushed below 0 wrapped to 99. "mov eax,99" becomes
       "cdq / inc edx / imul eax,edx,99", clamping to 0..99.

The cave sits in the XBE header page's zero padding (VA 0x10f00);
SizeOfHeaders is raised to 0x1000 so the loader maps it, and the .text digest
is recomputed. The header RSA signature can't be regenerated, so the result
needs a softmodded/modchipped console or an emulator.

Usage: python madden_awareness_fix.py <original default.xbe> <output .xbe>
The game is identified by its .text digest; any other build is refused.
"""
import hashlib
import struct
import sys

BASE = 0x10000
CAVE_VA = 0x10F00
CLAMP_OLD = bytes.fromhex('b863000000')   # mov eax, 0x63
CLAMP_NEW = bytes.fromhex('99426bc263')   # cdq; inc edx; imul eax, edx, 0x63

# Per game: the slot-clear site (24 bytes replaced), where to resume, the
# remove routines (cdecl: role, player, remove), the DB exec routine and the
# "update PLAY set <field> = ? where PGID = ?" query, the "no role" value,
# how the old role is found on the stack, and the clamp sites.
GAMES = {
    'dc5a24213bf36d52357e275db5db1c808768c602': dict(
        name='Madden NFL 09', site=0x3E1CE5, resume=0x3E1CFD,
        remove_self=0x3E08B0, remove_team=0x3E0A50, dbexec=0x427EB0, query=0x63D8BC,
        none=0x2D, player=0x38, field_reg='ebp', role_from='tag', role_base=0x28,
        tail='mov_edi_eax', clamps=(0x3DFFD8, 0x3E01D8, 0x3E03D8)),
    '0a60f542ff05a3d93734120aecb3e8c8253cfea2': dict(
        name='Madden NFL 08', site=0x3CCC85, resume=0x3CCC9D,
        remove_self=0x3CB850, remove_team=0x3CB9F0, dbexec=0x411230, query=0x612F04,
        none=0x2D, player=0x38, field_reg='ebp', role_from='tag', role_base=0x28,
        tail='mov_edi_eax', clamps=(0x3CB108, 0x3CB308, 0x3CB508)),
    '715f2804984309ff7576e07d697a9c6459329f8c': dict(
        name='Madden NFL 07', site=0x3A75A0, resume=0x3A75BC,
        remove_self=0x3A6400, remove_team=0x3A65A0, dbexec=0x3E5FB0, query=0x5F1FE4,
        none=0x1F, player=0x30, field_reg='edi', role_from='slot', role_base=0x1C,
        slot=0x14, tail=None, clamps=(0x3A58A8, 0x3A5AA8, 0x3A5C9C, 0x3A5EB8, 0x3A60B8)),
}
PUSH_FIELD = {'ebp': b'\x55', 'edi': b'\x57'}


def rel32(src_next, dst):
    return struct.pack('<i', dst - src_next)


def original_clear(g):
    """The 24 replaced bytes: mov edx,[esp+player]; push edx; push none;
    push field; push query; push ebx(0); call dbexec; add esp,0x14; +tail."""
    return (bytes.fromhex('8b5424') + bytes([g['player']]) + b'\x52' +
            b'\x6a' + bytes([g['none']]) + PUSH_FIELD[g['field_reg']] +
            b'\x68' + struct.pack('<I', g['query']) + b'\x53')


def build_cave(g):
    c = bytearray()

    def here():
        return CAVE_VA + len(c)

    if g['role_from'] == 'tag':
        # 08/09: old role = (ebp == 'PROL') ? [esp+base-4] : [esp+base]
        c += bytes.fromhex('0fbae510')                    # bt   ebp, 16 (CF=1 for PROL)
        c += bytes.fromhex('1bc0')                        # sbb  eax, eax
        c += bytes.fromhex('8b4484') + bytes([g['role_base']])  # mov eax, [esp+eax*4+base]
    else:
        # 07: old role = [esp + base + 4*[esp+slot]]
        c += bytes.fromhex('8b4424') + bytes([g['slot']])        # mov eax, [esp+slot]
        c += bytes.fromhex('8b4484') + bytes([g['role_base']])  # mov eax, [esp+eax*4+base]
    c += b'\x83\xf8' + bytes([g['none']])                 # cmp  eax, none
    je_at = len(c)
    c += bytes.fromhex('7400')                            # je   clear
    c += b'\x50'                                          # push eax           ; keep role
    c += bytes.fromhex('6a01')                            # push 1             ; remove
    c += bytes.fromhex('ff7424') + bytes([g['player'] + 8])  # push [player]
    c += b'\x50'                                          # push eax           ; role
    c += b'\xe8' + rel32(here() + 5, g['remove_self'])
    c += bytes.fromhex('83c40c')                          # add  esp, 0xc
    c += b'\x58'                                          # pop  eax
    c += bytes.fromhex('6a01')                            # push 1
    c += bytes.fromhex('ff7424') + bytes([g['player'] + 4])  # push [player]
    c += b'\x50'                                          # push eax
    c += b'\xe8' + rel32(here() + 5, g['remove_team'])
    c += bytes.fromhex('83c40c')                          # add  esp, 0xc
    c[je_at + 1] = len(c) - (je_at + 2)
    # original slot clear
    c += original_clear(g)
    c += b'\xe8' + rel32(here() + 5, g['dbexec'])
    c += bytes.fromhex('83c414')                          # add  esp, 0x14
    if g['tail'] == 'mov_edi_eax':
        c += bytes.fromhex('8bf8')                        # mov  edi, eax
    c += b'\xe9' + rel32(here() + 5, g['resume'])
    return bytes(c)


def expected_site(g):
    s = original_clear(g) + b'\xe8????' + bytes.fromhex('83c414')
    s += bytes.fromhex('8bf8') if g['tail'] == 'mov_edi_eax' else b'\xeb?'
    return s


def matches(data, pattern):
    return len(data) == len(pattern) and all(p == ord('?') or p == d for d, p in zip(data, pattern))


def main(src, dst):
    b = bytearray(open(src, 'rb').read())
    u32 = lambda o: struct.unpack_from('<I', b, o)[0]
    assert b[:4] == b'XBEH', 'not an XBE'
    assert u32(0x104) == BASE
    text_hdr = u32(0x120) - BASE
    t_va, t_vs, t_ra, t_rs = struct.unpack_from('<4I', b, text_hdr + 4)
    g = GAMES.get(bytes(b[text_hdr + 0x24:text_hdr + 0x38]).hex())
    if g is None or t_va != 0x11000:
        sys.exit('unrecognised XBE: this script targets retail Madden NFL 07/08/09 (USA) default.xbe')
    off = lambda va: va - t_va + t_ra

    site = bytes(b[off(g['site']):off(g['site']) + 24])
    assert matches(site, expected_site(g)), 'unexpected code at the slot-clear site'
    call = struct.unpack_from('<i', site, 15)[0]
    assert g['site'] + 19 + call == g['dbexec']
    if g['tail'] is None:  # 07: short jmp to resume
        assert g['site'] + 24 + struct.unpack_from('<b', site, 23)[0] == g['resume']
    else:
        assert g['site'] + 24 == g['resume']
    for a in g['clamps']:
        assert b[off(a) - 5:off(a) + 5] == bytes.fromhex('83f8637605') + CLAMP_OLD

    cave = build_cave(g)
    cave_off = CAVE_VA - BASE
    assert u32(0x108) <= cave_off and cave_off + len(cave) <= 0x1000 <= t_ra
    assert not any(b[cave_off:cave_off + len(cave)])

    b[cave_off:cave_off + len(cave)] = cave
    struct.pack_into('<I', b, 0x108, 0x1000)
    b[off(g['site']):off(g['site']) + 24] = b'\xe9' + rel32(g['site'] + 5, CAVE_VA) + b'\x90' * 19
    for a in g['clamps']:
        b[off(a):off(a) + 5] = CLAMP_NEW

    dig = hashlib.sha1(struct.pack('<I', t_rs) + bytes(b[t_ra:t_ra + t_rs])).digest()
    b[text_hdr + 0x24:text_hdr + 0x38] = dig

    open(dst, 'wb').write(b)
    print(f"{g['name']}: wrote {dst}")
    print('cave %d bytes at VA %#x; hook at %#x; clamp fixes at %s'
          % (len(cave), CAVE_VA, g['site'], ', '.join(hex(a) for a in g['clamps'])))


if __name__ == '__main__':
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
