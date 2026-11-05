"""Replace a team's menu logo in Madden 09's two logo archives.

Usage: python team_logo.py <stock data dir> <image> <out dir> [--entry 26] [--white-bg] [--teams FILE ... --classic-entry 37]

Writes uis_tmlo.dat (64x64) and UIS_TMLL.dat (128x128) to the out dir. Only one
entry changes and the file sizes stay the same. Entry = TEAM.TLGL + 1, so the
modern Washington team is 26 and the classic Redskins are 37, a separate image.
fe.qkl and game.qkl list both files but don't preload entry 26, so qkl_sync.py
leaves them unchanged. Another entry may differ: run it to check.

--white-bg is for a logo on a white background with no white in the art: alpha
comes from the blue channel, so it only suits art whose edge colour has little
blue (the Commanders' gold does).

--teams F [F ...] with --classic-entry N writes those files to the out dir with
any other team using this logo moved to entry N. Stock "All Redskins" (TGID 208)
is 25/25 in TLGL/TLGS in template.dat and strmdata.db, which is what the menus
read; DB_TEAMS.dat's copy doesn't decide it.
"""
import argparse
import os
import sys

from PIL import Image, ImageFilter

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'loadscreen'))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'roster'))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'tools'))
import eammap  # noqa: E402
from db_survey import find_dbs  # noqa: E402
from headshots import terf_entries  # noqa: E402

ARCHIVES = ('uis_tmlo.dat', 'UIS_TMLL.dat')
MARGIN = 1 / 32                         # stock logos nearly fill the slot
SHADOW = (0, 0, 0, 150)                 # like the stock logos' soft drop shadow
OPAQUE_B = 40                           # --white-bg: blue at or below this is solid art


def load(path, white_bg):
    im = Image.open(path).convert('RGBA')
    if not white_bg:
        return im.crop(im.getchannel('A').getbbox())
    px = im.load()
    for y in range(im.height):
        for x in range(im.width):
            r, g, b, _ = px[x, y]
            a = min(1, (255 - b) / (255 - OPAQUE_B))
            if not a:
                px[x, y] = (0, 0, 0, 0)
                continue
            px[x, y] = tuple(max(0, min(255, round((c - (1 - a) * 255) / a))) for c in (r, g, b)) + (round(a * 255),)
    return im


def fit(art, size):
    """The art scaled into a size x size canvas, centred, with a drop shadow."""
    room = size - 2 * round(size * MARGIN) - size // 32
    w, h = art.size
    scale = room / max(w, h)
    small = art.resize((round(w * scale), round(h * scale)), Image.BOX)  # no ringing at the art's hard edges
    at = ((size - small.width) // 2, (size - small.height) // 2)
    canvas = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    mask = Image.new('L', (size, size), 0)
    off = size // 32
    mask.paste(small.getchannel('A'), (at[0] + off, at[1] + off))
    mask = mask.filter(ImageFilter.GaussianBlur(size / 96)).point(lambda a: a * SHADOW[3] // 255)
    canvas.paste(SHADOW[:3], (0, 0), mask)
    canvas.putalpha(mask)
    canvas.alpha_composite(small, at)
    return canvas


def encode(slot, im):
    """Return a copy of an 8-bit MMAP entry with its texture replaced by `im`."""
    texs, pals = eammap.parse(slot)
    w, h, _, _, off = texs[0]
    assert im.size == (w, h)
    tex_at, pal_at = off + 0x80, pals[0]
    q = im.quantize(256, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.NONE)
    pal = q.getpalette('RGBA')
    pal += [0] * (1024 - len(pal))
    xs, ys = eammap.morton_tables(w, h)
    out, idx = bytearray(slot), q.load()
    for y in range(h):
        for x in range(w):
            out[tex_at + xs[x] + ys[y]] = idx[x, y]
    p = bytearray(1024)
    for i in range(256):
        r, g, b, a = pal[4 * i:4 * i + 4]
        p[4 * i:4 * i + 4] = bytes((b, g, r, 255 if a >= 250 else a))  # solid art must stay solid
    out[pal_at:pal_at + 1024] = p
    return bytes(out)


def unshare(path, out, entry, classic_entry):
    """Write a copy of a TEAM-holding file with other teams moved off logo `entry`."""
    with open(path, 'rb') as f:
        buf = bytearray(f.read())
    logo, classic = entry - 1, classic_entry - 1
    for db in find_dbs(buf):
        if 'TEAM' not in db.tables:
            continue
        team = db['TEAM']
        changed = False
        for i in range(team.count):
            if team.get(i, 'TGID') == entry:    # the modern team keeps it (TGID = TLGL + 1)
                continue
            for field in ('TLGL', 'TLGS'):
                if team.get(i, field) == logo:
                    print(os.path.basename(path), hex(db.off), team.get(i, 'TDNA'), field, logo, '->', classic)
                    team.set(i, field, classic)
                    changed = True
        if changed:
            db.fix()
            assert db.verify()
    with open(os.path.join(out, os.path.basename(path)), 'wb') as f:
        f.write(buf)
    print(os.path.basename(path), len(buf), 'bytes')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('stock')
    ap.add_argument('image')
    ap.add_argument('out')
    ap.add_argument('--entry', type=int, default=26)
    ap.add_argument('--white-bg', action='store_true')
    ap.add_argument('--teams', nargs='*', default=[])
    ap.add_argument('--classic-entry', type=int, default=37)
    a = ap.parse_args()
    art = load(a.image, a.white_bg)
    os.makedirs(a.out, exist_ok=True)
    for name in ARCHIVES:
        buf = bytearray(open(os.path.join(a.stock, name), 'rb').read())
        data_at, entries = terf_entries(buf)
        eo, es = entries[a.entry]
        slot = bytes(buf[data_at + eo:data_at + eo + es])
        w = eammap.parse(slot)[0][0][0]
        new = encode(slot, fit(art, w))
        assert len(new) == es
        buf[data_at + eo:data_at + eo + es] = new
        with open(os.path.join(a.out, name), 'wb') as f:
            f.write(buf)
        print(name, len(buf), 'bytes, entry', a.entry, 'at', hex(data_at + eo))
    for path in a.teams:
        unshare(path, a.out, a.entry, a.classic_entry)


if __name__ == '__main__':
    main()
