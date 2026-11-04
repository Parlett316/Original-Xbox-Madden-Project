"""Let Madden 09 load edited saves: skip the signature check on a save's contents.

    python save_unlock.py <in default.xbe> <out default.xbe>

A save is: name (17 bytes), signature of the name, data, signature of the data,
padding, signature of the padding (the last 20 bytes of the file). All three are
XCalculateSignature values, keyed from the kernel, so they can't be recomputed
off the console. Saves load through a stream driver (0x73b5f0) whose close
(0x5d0c0) checks the data signature and then the padding's, both in 0x5ce00.
This makes that one compare always pass (je -> jmp); the name check stays, so an
edited save has to keep its name. The game still writes valid signatures when
it saves.

An edited save still needs correct database CRCs (tdb.DB.fix) and must keep its
file size.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'loadscreen'))
from xbe import XBE  # noqa: E402

COMPARES = (0x5cf05,)  # je after the signature compare in the stream driver's close


def main(src, dst):
    x = XBE(src)
    buf = bytearray(x.d)
    for va in COMPARES:
        o = x.v2f(va)
        assert buf[o] == 0x74, f'{va:#x}: unexpected code'
        buf[o] = 0xeb
    open(dst, 'wb').write(buf)
    print(f'{os.path.basename(dst)}: {len(buf):,} bytes, {len(COMPARES)} checks skipped')


if __name__ == '__main__':
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(*sys.argv[1:])
