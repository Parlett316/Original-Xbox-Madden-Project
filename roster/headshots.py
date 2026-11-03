"""Madden 09 (Xbox) menu headshots in data/uis_plyr.dat.

uis_plyr.dat is a TERF archive (DIR1 offsets relative to the DATA chunk) of
fixed 17,948-byte MMAP entries, one per photo: a 128x128 P8 texture (Xbox
format 0x0B, Morton-swizzled) at +0x100 and a 256-entry BGRA palette at
+0x4200. The photo itself is a 66x66 head-and-shoulders crop at (15,15) with
a thin light outline; the rest of the texture is transparent.

A player's PSXP selects entry PSXP + 1; PSXP 0 selects entry 1, which is blank.
"""
import statistics, struct

from PIL import Image, ImageFilter

SLOT_SIZE = 17948
TEX_OFF, PAL_OFF = 0x100, 0x4200
SIZE, PHOTO, AT = 128, 66, 15
EA_CROP = (116, 98, 396, 378)   # head and shoulders in EA's 512x512 portraits
OUTLINE = (225, 225, 225)


def terf_entries(buf):
    """Return (DATA chunk position, [(offset, size)]) of a TERF archive."""
    n = struct.unpack_from('<H', buf, 14)[0]
    pos = struct.unpack_from('<I', buf, 4)[0]
    chunks = {}
    while pos < len(buf):
        tag, size = bytes(buf[pos:pos + 4]), struct.unpack_from('<I', buf, pos + 4)[0]
        chunks[tag] = pos
        if tag == b'DATA':
            break
        pos += size
    d = chunks[b'DIR1']
    return chunks[b'DATA'], [struct.unpack_from('<II', buf, d + 8 + 8 * i) for i in range(n)]


def _morton(n):
    t = [0] * n
    for v in range(n):
        r, bit = 0, 0
        while v >> bit:
            r |= ((v >> bit) & 1) << (2 * bit)
            bit += 1
        t[v] = r
    return t


_M = _morton(SIZE)
SWIZZLE_X = _M                       # x bits go to even positions
SWIZZLE_Y = [m << 1 for m in _M]     # y bits to odd positions


def ea_photo(path):
    """EA portrait -> 66x66 RGBA crop framed like 09's photos."""
    im = Image.open(path).convert('RGBA')
    if im.size != (512, 512):
        im = im.resize((512, 512), Image.LANCZOS)
    return im.crop(EA_CROP).resize((PHOTO, PHOTO), Image.LANCZOS)


def skin_brightness(photo):
    """Median luma of the cheek/nose area of a 66x66 photo (None if unclear)."""
    c = photo.crop((24, 24, 42, 40))
    px = [(r, g, b) for r, g, b, a in c.getdata() if a > 200]
    if len(px) < 30:
        return None
    return statistics.median(0.299 * r + 0.587 * g + 0.114 * b for r, g, b in px)


def encode(slot, photo):
    """Return a copy of MMAP entry `slot` with its texture replaced by `photo`."""
    canvas = Image.new('RGBA', (SIZE, SIZE), (0, 0, 0, 0))
    canvas.paste(photo, (AT, AT))
    alpha = canvas.getchannel('A').point(lambda a: 255 if a >= 128 else 0)
    halo = alpha.filter(ImageFilter.MaxFilter(3))
    rgb = Image.new('RGB', (SIZE, SIZE), OUTLINE)
    rgb.paste(canvas.convert('RGB'), (0, 0), alpha)
    # 255 colours for the opaque pixels, index 0 = transparent
    q = rgb.quantize(255, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    pal = q.getpalette()[:255 * 3]
    idx, hmask = q.load(), halo.load()
    out = bytearray(slot)
    tex = bytearray(SIZE * SIZE)
    for y in range(SIZE):
        sy = SWIZZLE_Y[y]
        for x in range(SIZE):
            tex[SWIZZLE_X[x] | sy] = idx[x, y] + 1 if hmask[x, y] else 0
    out[TEX_OFF:TEX_OFF + len(tex)] = tex
    p = bytearray(1024)
    for i in range(255):
        r, g, b = pal[3 * i:3 * i + 3] if 3 * i + 2 < len(pal) else (0, 0, 0)
        p[4 * (i + 1):4 * (i + 2)] = bytes((b, g, r, 255))
    out[PAL_OFF:PAL_OFF + 1024] = p
    return bytes(out)


def decode(slot):
    """Render an MMAP entry's texture to RGBA (for checking)."""
    pal = slot[PAL_OFF:PAL_OFF + 1024]
    im = Image.new('RGBA', (SIZE, SIZE))
    px = im.load()
    for y in range(SIZE):
        for x in range(SIZE):
            c = slot[TEX_OFF + (SWIZZLE_X[x] | SWIZZLE_Y[y])] * 4
            px[x, y] = (pal[c + 2], pal[c + 1], pal[c], pal[c + 3])
    return im
