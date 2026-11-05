"""Give a team its own helmet logo without touching teams that share its uniforms.

Usage: python team_helmet.py <stock data dir> <logo image> <out dir> --teams FILE [FILE ...]

UNIFORMS.dat entries are indexed by UFID, and TUNI (UFID, TGID, TUCO) says which
a team may wear. The modern Washington team shares its home and away uniforms
(283, 284) with four classic Redskins teams, so this repaints those two entries
in place and moves everyone else to the near-identical 287 and 288, which the
other classic Redskins teams already wear. No UFID is added: Commanders on 292
with a new UNIF row locked on the loading screen (hardware, 2026-11-04). A
franchise keeps the TUNI rows it was created with. --teams needs template.dat
and DB_TEAMS.dat, which both hold TUNI rows.

Each entry is an LZH1-compressed MMAP with named parts. The Helmet part is 256x128
with 4 mip levels and its own palette: two side panels mirrored across the crown
stripe, the art rotated a quarter turn. Small y is the helmet's front, so mirroring
keeps the art facing forward on both sides, as the stock logo and the real helmet do.
Writes UNIFORMS.dat (same size) and each --teams file.

Flag 0x802abd makes the game load entry UFID + 343 instead. Those entries (626, 627
here) share the helmet but not the jersey and pants, so they get the logo too.

An entry's directory size must not change. The game keeps only every 20th entry's
offset and adds up the rounded sizes to find the rest (0x377030), so a shorter
size moves the following entries in that block of 20. A smaller stream is padded
with zeros under its stock size, so the header, fe.qkl and game.qkl stay stock.
"""
import argparse
import os
import struct
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(HERE, 'loadscreen'), os.path.join(HERE, '..', 'roster'), os.path.join(HERE, '..', 'tools')]
import eammap  # noqa: E402
import lzh1emu  # noqa: E402
from db_survey import find_dbs  # noqa: E402

TGID = 26
MOVES = {283: 287, 284: 288}            # repainted uniform -> where other teams go
SECOND_SET = 343                        # 0x222223: when flag 0x802abd is set, entry = UFID + this
REPAINT = [*MOVES, *(n + SECOND_SET for n in MOVES)]
HELMET_TEX = 12                         # first of 4 mip levels
OLD_LOGO = ((24, 42, 94, 106), (164, 34, 234, 106))     # left and right panel, erased
PANEL_SAMPLE = (20, 70)
CENTRE = (185, 63)                      # on the right panel; front edge level with the Falcons' and Cowboys' logos (y 39)
LOGO_LENGTH = 54                        # along the art's long side
STRIPE = (128, 70)                      # the helmet's own gold


def archive(buf):
    """(DATA position, directory position, [(offset, size)], [(type, full size)])."""
    n = struct.unpack_from('<H', buf, 14)[0]
    dir_at = struct.unpack_from('<I', buf, 4)[0]
    comp_at = dir_at + struct.unpack_from('<I', buf, dir_at + 4)[0]
    data_at = comp_at + struct.unpack_from('<I', buf, comp_at + 4)[0]
    return (data_at, dir_at,
            [struct.unpack_from('<II', buf, dir_at + 8 + 8 * i) for i in range(n)],
            [struct.unpack_from('<II', buf, comp_at + 8 + 8 * i) for i in range(n)])


def part_index(raw, name):
    at = struct.unpack_from('<I', raw, 0x20)[0]
    k = 0
    while raw[at + 16 * k:at + 16 * k + 16].split(b'\0')[0] != name:
        k += 1
    return k


def paint(base, logo):
    """The helmet with its old logo erased and `logo` on both panels, mirrored."""
    im = base.copy()
    fill = base.getpixel(PANEL_SAMPLE)
    for box in OLD_LOGO:
        im.paste(fill, box)
    # the helmet logo is the art inverted: gold panels, burgundy seams and edge
    outline = np.asarray(logo.getchannel('G'), dtype=np.float32)
    gold = 1 - np.clip((outline - 12) / (183 - 12), 0, 1)[..., None]   # the art's green: burgundy 12, gold 183
    rgb = np.array(fill[:3], dtype=np.float32) * (1 - gold) + np.array(base.getpixel(STRIPE)[:3], dtype=np.float32) * gold
    art = Image.fromarray(rgb.astype(np.uint8), 'RGB')
    art.putalpha(logo.getchannel('A'))
    k = LOGO_LENGTH / max(logo.size)
    art = art.resize((round(logo.width * k), round(logo.height * k)), Image.BOX)
    side = art.transpose(Image.ROTATE_90)
    at = (CENTRE[0] - side.width // 2, CENTRE[1] - side.height // 2)
    alpha = im.getchannel('A')
    rgb = im.convert('RGB')
    rgb.paste(side.convert('RGB'), at, side.getchannel('A'))
    mirrored = side.transpose(Image.FLIP_LEFT_RIGHT)
    rgb.paste(mirrored.convert('RGB'), (im.width - at[0] - side.width, at[1]), mirrored.getchannel('A'))
    rgb.putalpha(alpha)
    return rgb


def mip_at(texs, level):
    """Where a helmet mip's pixels start: only the top level follows the 0x80-byte header."""
    return texs[HELMET_TEX + level][4] + (0 if level else 0x80)


def read_indices(raw, texs, level):
    w, h = texs[HELMET_TEX + level][:2]
    xs, ys = eammap.morton_tables(w, h)
    at = mip_at(texs, level)
    return np.array([[raw[at + xs[x] + ys[y]] for x in range(w)] for y in range(h)], dtype=np.int32)


def repaint(raw, logo):
    """Return the MMAP with the logo area of its helmet replaced and all else left stock.

    The palette stays stock: the logo is drawn in colours it already has, because
    the pixels' indices are also read through the separate SpecHelm palette.
    """
    texs, pals = eammap.parse(raw)
    base = eammap.render(raw, HELMET_TEX, part_index(raw, b'Helmet'))
    im = paint(base, logo)
    bgra = np.frombuffer(raw, np.uint8, 1024, pals[part_index(raw, b'Helmet')]).reshape(256, 4)
    pal = bgra[:, [2, 1, 0, 3]].astype(np.int32)
    new = np.asarray(im, dtype=np.int32)
    changed = (new != np.asarray(base, dtype=np.int32)).any(axis=2)
    out = bytearray(raw)
    for level in range(4):
        w, h = texs[HELMET_TEX + level][:2]
        step = 1 << level
        touched = np.array([[changed[y * step:(y + 1) * step, x * step:(x + 1) * step].any()
                             for x in range(w)] for y in range(h)])
        mip = im.resize((w, h), Image.BOX) if level else im
        px = np.asarray(mip, dtype=np.int32)[touched]
        idx = read_indices(raw, texs, level)
        idx[touched] = ((px[:, None, :] - pal[None, :, :]) ** 2).sum(axis=2).argmin(axis=1)
        xs, ys = eammap.morton_tables(w, h)
        at = mip_at(texs, level)
        for y in range(h):
            for x in range(w):
                out[at + xs[x] + ys[y]] = idx[y, x]
    return bytes(out)


def move_rows(path, out):
    """Write a copy of a file with every other team's TUNI rows moved off the repainted uniforms."""
    with open(path, 'rb') as f:
        buf = bytearray(f.read())
    for db in find_dbs(buf):
        if 'TUNI' not in db.tables:
            continue
        t = db['TUNI']
        changed = False
        for i in range(t.count):
            if t.get(i, 'TGID') != TGID and t.get(i, 'UFID') in MOVES:
                print(os.path.basename(path), hex(db.off), 'TUNI TGID', t.get(i, 'TGID'), t.get(i, 'UFID'), '->', MOVES[t.get(i, 'UFID')])
                t.set(i, 'UFID', MOVES[t.get(i, 'UFID')])
                changed = True
        if changed:
            db.fix()
            assert db.verify()
    with open(os.path.join(out, os.path.basename(path)), 'wb') as f:
        f.write(buf)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('stock')
    ap.add_argument('logo')
    ap.add_argument('out')
    ap.add_argument('--teams', nargs='*', default=[])
    a = ap.parse_args()
    logo = Image.open(a.logo).convert('RGBA')
    logo = logo.crop(logo.getchannel('A').getbbox())
    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.stock, 'UNIFORMS.dat'), 'rb') as f:
        buf = bytearray(f.read())
    data_at, _, entries, comp = archive(buf)
    for n in REPAINT:
        eo, es = entries[n]
        raw = lzh1emu.decompress(bytes(buf[data_at + eo:data_at + eo + es]), comp[n][1])[0]
        new = repaint(raw, logo)
        _, _, (_, used), output = lzh1emu.compress(new)
        packed = output[:used]
        print('entry', n, len(packed), 'bytes, stock size', es)
        assert len(packed) <= es, 'larger than the stock entry'
        padded = packed + bytes(es - len(packed))
        assert lzh1emu.decompress(padded, comp[n][1])[0] == new
        buf[data_at + eo:data_at + eo + es] = padded
    with open(os.path.join(a.out, 'UNIFORMS.dat'), 'wb') as f:
        f.write(buf)
    print('UNIFORMS.dat', len(buf), 'bytes')
    for path in a.teams:
        move_rows(path, a.out)


if __name__ == '__main__':
    main()
