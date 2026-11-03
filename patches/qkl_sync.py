"""Bring a Madden 09 quick-load bundle (fe.qkl / game.qkl) in line with patched data files.

Usage: python qkl_sync.py <original .qkl> <stock data dir> <patched data dir> <out .qkl>

At startup the game reads some files' headers and archive entries from these
bundles instead of the files themselves, so a patched file whose preloaded
parts differ is half-ignored (e.g. a new BGM.dat directory, or the start
screen in uis_fe.dat). Format (little-endian):
  'QL01', u32 header size; then chunks (tag, u32 size):
  FILS  u32 count, then 48-byte entries: file name (NUL-padded)
  DTLS  u32 count, then 12-byte entries: u16 kind, u16 file index (into FILS),
        u32 n, u32 offset of the copy from the end of DTLS.
        kind 0: the file's header (TERF header + directory + DATA chunk head),
        kind 1: entry n of the file's TERF archive.
  DATA  the copies, each padded up to the next one.
Header copies have no stored length, so each one's length is measured as
the part that matches the stock file. Every region of a file that differs
between the stock and patched dirs is rewritten from the patched file; the
copy must keep its size.
"""
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'roster'))
from headshots import terf_entries  # noqa: E402


def parse(q):
    assert q[:4] == b'QL01', 'not a QL01 bundle'
    pos, chunks = struct.unpack_from('<I', q, 4)[0], {}
    while pos < len(q):
        tag, size = bytes(q[pos:pos + 4]), struct.unpack_from('<I', q, pos + 4)[0]
        chunks[tag] = (pos, size)
        if tag == b'DATA':
            break
        pos += size
    fp, _ = chunks[b'FILS']
    names = [bytes(q[fp + 12 + 48 * k:fp + 44 + 48 * k]).split(b'\0')[0].decode()
             for k in range(struct.unpack_from('<I', q, fp + 8)[0])]
    dp, ds = chunks[b'DTLS']
    regions = [struct.unpack_from('<HHII', q, dp + 12 + 12 * k)
               for k in range(struct.unpack_from('<I', q, dp + 8)[0])]
    return names, regions, dp + ds


def entry(src, n):
    data_at, entries = terf_entries(src)
    eo, es = entries[n]
    return src[data_at + eo:data_at + eo + es]


def listing(d):
    return {f.lower(): os.path.join(d, f) for f in os.listdir(d)}


def main(src_qkl, stock_dir, patched_dir, dst_qkl):
    q = bytearray(open(src_qkl, 'rb').read())
    names, regions, base = parse(q)
    ends = sorted(set(r[3] for r in regions)) + [len(q) - base]
    stock_files, patched_files = listing(stock_dir), listing(patched_dir)
    pairs, changed = {}, 0
    for kind, fi, n, off in regions:
        name = names[fi].lower()
        if name not in patched_files or name not in stock_files:
            continue
        if name not in pairs:
            pairs[name] = (open(stock_files[name], 'rb').read(), open(patched_files[name], 'rb').read())
        stock, new_src = pairs[name]
        if stock == new_src:
            continue
        gap = ends[ends.index(off) + 1] - off
        copy = q[base + off:base + off + gap]
        if kind == 0:
            size = 0
            while size < gap and copy[size] == stock[size]:
                size += 1
            new = new_src[:size]
        else:
            old = entry(stock, n)
            assert copy[:len(old)] == old, f'{name} entry {n}: copy differs from the stock file'
            new = entry(new_src, n)
            assert len(new) == len(old), f'{name} entry {n}: size changed'
        if q[base + off:base + off + len(new)] != new:
            q[base + off:base + off + len(new)] = new
            changed += 1
            print(f'  {names[fi]} {"header" if kind == 0 else f"entry {n}"}: updated')
    open(dst_qkl, 'wb').write(q)
    print(f'wrote {dst_qkl}: {changed} region(s) updated')


if __name__ == '__main__':
    if len(sys.argv) != 5:
        sys.exit(__doc__)
    main(*sys.argv[1:5])
