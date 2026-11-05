"""Pack a game folder plus an overlay into an Xbox disc image for xemu, or read one back.

Usage: python make_xiso.py pack <game folder> <overlay folder> <out.iso>
       python make_xiso.py list <image.iso>
       python make_xiso.py verify <image.iso> <game folder> <overlay folder>

Files in the overlay replace the game's, matched without regard to case, and new
ones are added. Inputs are only read. Overlay files outside default.xbe and data/
(a build's roster_report.csv) are left out.

XDVDFS: 2,048-byte sectors, volume descriptor at sector 32 ('MICROSOFT*XBOX*MEDIA',
u32 root sector, u32 root size, FILETIME, and the magic again at +0x7EC). A directory
is a binary tree of entries: u16 left and u16 right (offsets in 4-byte units, 0 =
none), u32 sector, u32 size, u8 attributes, u8 name length, name, padded with 0xFF to
4 bytes. An entry never crosses a sector, and the root entry is first. Names sort by
their upper-case bytes, as the kernel compares them.
"""
import hashlib
import os
import struct
import sys

SECTOR = 2048
MAGIC = b'MICROSOFT*XBOX*MEDIA'
DIR, FILE = 0x10, 0x20
BLOCK = 1 << 20


def key(name):
    return name.upper().encode('ascii')


def tree_order(names):
    """(pre-order list, {name: (left, right)}) of a balanced tree over sorted names."""
    order, links = [], {}

    def build(lo, hi):
        if lo >= hi:
            return None
        mid = (lo + hi) // 2
        name = names[mid]
        order.append(name)
        left = build(lo, mid)
        right = build(mid + 1, hi)
        links[name] = (left, right)
        return name
    build(0, len(names))
    return order, links


def entry_size(name):
    return (14 + len(name) + 3) & ~3


def layout_dir(names):
    """{name: offset} and the table's size in bytes, with no entry crossing a sector."""
    order, links = tree_order(names)
    at, pos = {}, 0
    for name in order:
        size = entry_size(name)
        if pos // SECTOR != (pos + size - 1) // SECTOR:
            pos = (pos // SECTOR + 1) * SECTOR
        at[name] = pos
        pos += size
    return order, links, at, max(pos, 1)


def sectors(size):
    return (size + SECTOR - 1) // SECTOR


def merged(game, overlay):
    """A tree of {name: path or subtree}: the game's files with the overlay's on top."""
    def scan(folder):
        out = {}
        for f in os.listdir(folder):
            p = os.path.join(folder, f)
            out[f] = scan(p) if os.path.isdir(p) else p
        return out

    def merge(base, top):
        names = {n.lower(): n for n in base}
        for n, v in top.items():
            have = names.get(n.lower())
            if have is None:
                base[n] = v
            elif isinstance(v, dict):
                merge(base[have], v)
            else:
                base[have] = v              # keeps the game's spelling of the name
    tree = scan(game)
    top = {n: v for n, v in scan(overlay).items() if n.lower() in ('default.xbe', 'data')}
    merge(tree, top)
    return tree


def pack(game, overlay, out):
    tree = merged(game, overlay)
    next_sector = 33
    plans, files = {}, []

    def plan_dirs(node, path):
        nonlocal next_sector
        names = sorted(node, key=key)
        assert names, f'empty folder: {path}'
        order, links, at, size = layout_dir(names)
        plan = {'order': order, 'links': links, 'at': at, 'size': size, 'sector': next_sector, 'node': node}
        plans[path] = plan
        next_sector += sectors(size)
        for n in names:
            if isinstance(node[n], dict):
                plan_dirs(node[n], path + (n,))

    plan_dirs(tree, ())
    for path, plan in plans.items():
        plan['where'] = {}
        for n in plan['order']:
            v = plan['node'][n]
            if isinstance(v, dict):
                sub = plans[path + (n,)]
                plan['where'][n] = (sub['sector'], sectors(sub['size']) * SECTOR, DIR)
            else:
                size = os.path.getsize(v)
                plan['where'][n] = (next_sector, size, FILE)
                files.append((next_sector, v, size))
                next_sector += sectors(size)
    root = plans[()]
    with open(out, 'wb') as f:
        f.write(bytes(32 * SECTOR))
        f.write(volume(root['sector'], sectors(root['size']) * SECTOR))
        for plan in plans.values():
            table = bytearray(b'\xff' * (sectors(plan['size']) * SECTOR))
            for n in plan['order']:
                left, right = plan['links'][n]
                sector, size, attr = plan['where'][n]
                raw = n.encode('ascii')
                entry = struct.pack('<HHIIBB', plan['at'][left] // 4 if left else 0, plan['at'][right] // 4 if right else 0,
                                    sector, size, attr, len(raw)) + raw
                table[plan['at'][n]:plan['at'][n] + len(entry)] = entry
            f.seek(plan['sector'] * SECTOR)
            f.write(table)
        for sector, path, size in files:
            f.seek(sector * SECTOR)
            with open(path, 'rb') as src:
                while chunk := src.read(BLOCK):
                    f.write(chunk)
            f.write(bytes(-size % SECTOR))
        end = next_sector * SECTOR
        f.truncate((end + 0xffff) & ~0xffff)
    print(out, os.path.getsize(out), 'bytes,', len(files), 'files')


def volume(root_sector, root_size):
    v = bytearray(SECTOR)
    v[:20] = MAGIC
    struct.pack_into('<II', v, 20, root_sector, root_size)
    v[0x7ec:0x800] = MAGIC
    return bytes(v)


def walk(f):
    """Yield (path, sector, size, attributes) for every entry, checking the tree's order."""
    f.seek(32 * SECTOR)
    v = f.read(SECTOR)
    assert v[:20] == MAGIC and v[0x7ec:0x800] == MAGIC, 'no XDVDFS volume descriptor'
    root_sector, root_size = struct.unpack_from('<II', v, 20)

    def table(sector, size, prefix):
        f.seek(sector * SECTOR)
        t = f.read(size)
        if t[:4] == b'\xff\xff\xff\xff':
            return

        def node(off, low, high):
            left, right, s, z, attr, n = struct.unpack_from('<HHIIBB', t, off)
            assert off // SECTOR == (off + 13 + n) // SECTOR, 'entry crosses a sector'
            name = t[off + 14:off + 14 + n].decode('ascii')
            k = key(name)
            assert (low is None or low < k) and (high is None or k < high), f'tree out of order at {name}'
            if left:
                yield from node(left * 4, low, k)
            path = prefix + '/' + name if prefix else name
            yield path, s, z, attr
            if attr & DIR and z:
                yield from table(s, z, path)
            if right:
                yield from node(right * 4, k, high)
        yield from node(0, None, None)
    yield from table(root_sector, root_size, '')


def show(iso):
    with open(iso, 'rb') as f:
        entries = list(walk(f))
    names = [e for e in entries if not e[3] & DIR]
    print(iso, os.path.getsize(iso), 'bytes,', len(names), 'files,', len(entries) - len(names), 'folders')
    for path, sector, size, attr in entries[:40]:
        print(f'  {attr:02x} sector {sector:8} size {size:11,} {path}')


def verify(iso, game, overlay):
    def flat(node, prefix=''):
        for n, v in node.items():
            p = prefix + '/' + n if prefix else n
            if isinstance(v, dict):
                yield from flat(v, p)
            else:
                yield p, v
    want = dict(flat(merged(game, overlay)))
    bad = 0
    with open(iso, 'rb') as f:
        got = {p: (s, z) for p, s, z, a in walk(f) if not a & DIR}
        if set(got) != set(want):
            print('file lists differ:', sorted(set(got) ^ set(want))[:20])
            bad += 1
        for p, (s, z) in got.items():
            if p not in want:
                continue
            f.seek(s * SECTOR)
            a, b = hashlib.sha1(), hashlib.sha1()
            left = z
            with open(want[p], 'rb') as src:
                while chunk := src.read(BLOCK):
                    b.update(chunk)
            while left:
                chunk = f.read(min(left, BLOCK))
                a.update(chunk)
                left -= len(chunk)
            if a.digest() != b.digest():
                print('differs:', p)
                bad += 1
    print(f'{len(got)} files checked, {bad} problems')
    return bad


if __name__ == '__main__':
    args = sys.argv[1:]
    if args[:1] == ['pack'] and len(args) == 4:
        pack(*args[1:])
    elif args[:1] == ['list'] and len(args) == 2:
        show(args[1])
    elif args[:1] == ['verify'] and len(args) == 4:
        sys.exit(1 if verify(*args[1:]) else 0)
    else:
        sys.exit(__doc__)
