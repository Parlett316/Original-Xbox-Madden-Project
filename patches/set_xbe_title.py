"""Set the title name a dashboard (UnleashX, EvoX, ...) shows for an XBE.

Usage: python set_xbe_title.py <in .xbe> <out .xbe> "<title>"

Only the certificate's title name (40 UTF-16 characters) changes. The title
ID stays the same, so the game keeps sharing saves with the original.
The certificate isn't covered by the section digests; like any modified XBE,
the result needs a softmodded/modchipped console or an emulator.
"""
import struct
import sys


def main(src, dst, title):
    d = bytearray(open(src, 'rb').read())
    base = struct.unpack_from('<I', d, 0x104)[0]
    cert = struct.unpack_from('<I', d, 0x118)[0] - base
    if len(title) > 40:
        raise SystemExit('title is limited to 40 characters')
    d[cert + 0x0C:cert + 0x0C + 80] = title.encode('utf-16-le').ljust(80, b'\0')
    open(dst, 'wb').write(d)
    print(f'{dst}: "{title}" (title id {struct.unpack_from("<I", d, cert + 8)[0]:08X})')


if __name__ == '__main__':
    main(*sys.argv[1:4])
