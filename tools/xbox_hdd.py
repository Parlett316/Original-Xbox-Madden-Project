"""Read and overwrite files on an xemu hard drive image (qcow2 + FATX), for moving saves.

Usage: python xbox_hdd.py ls <drive.qcow2> [path]
       python xbox_hdd.py get <drive.qcow2> <path> <out file>
       python xbox_hdd.py put <drive.qcow2> <path> <in file>

Paths are on the E: partition, such as UDATA/4541023b/18E7386A51EA/Fran-Fran2. Close
xemu first: it caches the drive while running. `put` replaces an existing file of the
same size in place, the only change an edited save needs (saves have a fixed size);
it never allocates clusters or touches directories. Use it on a copy of the drive.

qcow2 (v2/v3, no encryption, no compression, no backing file): a two-level table maps
guest clusters to file offsets. Guest sectors that were never written read as zeros.

FATX: partition E is at 0xABE80000 and is 0x1312D6000 bytes. Header 'FATX', u32 serial,
u32 sectors per cluster, u32 root cluster; the FAT starts at +0x1000, with 16-bit
entries under 0xFFF0 clusters and 32-bit entries otherwise; the root directory is the
first cluster after the FAT, which is padded to 4 KB. Directory entries are 64 bytes:
u8 name length (0xE5 deleted, 0xFF end), u8 attributes (0x10 = directory), 42 bytes of
name, u32 first cluster, u32 size, then timestamps.
"""
import struct
import sys

E_OFFSET = 0xABE80000
E_SIZE = 0x1312D6000


class Qcow2:
    def __init__(self, path, write=False):
        self.f = open(path, 'r+b' if write else 'rb')
        h = self.f.read(72)
        magic, ver, backing, _, bits, size, crypt, l1_n, l1_off = struct.unpack('>IIQIIQIIQ', h[:48])
        if magic != 0x514649FB or backing or crypt:
            raise ValueError(f'{path}: not a stand-alone qcow2 image')
        self.bits, self.size, self.cluster = bits, size, 1 << bits
        self.f.seek(l1_off)
        self.l1 = struct.unpack(f'>{l1_n}Q', self.f.read(8 * l1_n))
        self.l2 = {}

    def _map(self, pos):
        """File offset of guest offset `pos`, or None if it reads as zeros."""
        l2_bits = self.bits - 3
        i1 = pos >> (self.bits + l2_bits)
        i2 = (pos >> self.bits) & ((1 << l2_bits) - 1)
        l1 = self.l1[i1] & 0x00FFFFFFFFFFFE00
        if not l1:
            return None
        if l1 not in self.l2:
            self.f.seek(l1)
            self.l2[l1] = struct.unpack(f'>{1 << l2_bits}Q', self.f.read(self.cluster))
        e = self.l2[l1][i2]
        if e & (1 << 62):
            raise ValueError('compressed cluster')
        host = e & 0x00FFFFFFFFFFFE00
        if e & 1 or not host:  # zero flag, or unallocated
            return None
        return host + (pos & (self.cluster - 1))

    def read(self, pos, n):
        out = bytearray()
        while n:
            step = min(n, self.cluster - (pos & (self.cluster - 1)))
            host = self._map(pos)
            if host is None:
                out += bytes(step)
            else:
                self.f.seek(host)
                out += self.f.read(step)
            pos += step
            n -= step
        return bytes(out)

    def write(self, pos, data):
        i = 0
        while i < len(data):
            step = min(len(data) - i, self.cluster - (pos & (self.cluster - 1)))
            host = self._map(pos)
            if host is None:
                raise ValueError(f'guest offset {pos:#x} is not allocated; only rewrites are supported')
            self.f.seek(host)
            self.f.write(data[i:i + step])
            pos += step
            i += step


class Fatx:
    def __init__(self, disk, off=E_OFFSET, size=E_SIZE):
        self.d, self.off = disk, off
        h = disk.read(off, 16)
        if h[:4] != b'FATX':
            raise ValueError('no FATX partition at E:')
        self.cluster = struct.unpack_from('<I', h, 8)[0] * 512
        self.root = struct.unpack_from('<I', h, 12)[0]
        n = size // self.cluster
        self.w = 2 if n < 0xFFF0 else 4
        fat = (n + 1) * self.w
        self.fat = off + 0x1000
        self.data = self.fat + ((fat + 0xFFF) & ~0xFFF)

    def _next(self, c):
        raw = self.d.read(self.fat + c * self.w, self.w)
        v = int.from_bytes(raw, 'little')
        return None if v >= (0xFFF0 if self.w == 2 else 0xFFFFFFF0) else v

    def chain(self, c):
        while c is not None:
            yield self.data + (c - 1) * self.cluster
            c = self._next(c)

    def listdir(self, c):
        out = []
        for pos in self.chain(c):
            b = self.d.read(pos, self.cluster)
            for i in range(0, len(b), 64):
                n = b[i]
                if n == 0xFF or n == 0:
                    return out
                if n != 0xE5 and n <= 42:
                    first, size = struct.unpack_from('<II', b, i + 44)
                    out.append((b[i + 2:i + 2 + n].decode('latin1'), b[i + 1], first, size))
        return out

    def find(self, path):
        """(attributes, first cluster, size) of a path; the root for an empty path."""
        cur = (0x10, self.root, 0)
        for part in filter(None, path.replace('\\', '/').split('/')):
            for name, attr, first, size in self.listdir(cur[1]):
                if name.lower() == part.lower():
                    cur = (attr, first, size)
                    break
            else:
                raise FileNotFoundError(path)
        return cur

    def read_file(self, path):
        attr, first, size = self.find(path)
        out = bytearray()
        for pos in self.chain(first):
            out += self.d.read(pos, min(self.cluster, size - len(out)))
            if len(out) >= size:
                break
        return bytes(out)

    def overwrite_file(self, path, data):
        attr, first, size = self.find(path)
        if len(data) != size:
            raise ValueError(f'{path}: size {len(data)} differs from the drive\'s {size}')
        i = 0
        for pos in self.chain(first):
            if i >= size:
                break
            self.d.write(pos, data[i:i + self.cluster])
            i += self.cluster


def main(argv):
    if len(argv) < 2 or argv[0] not in ('ls', 'get', 'put'):
        sys.exit(__doc__)
    cmd, image = argv[0], argv[1]
    fs = Fatx(Qcow2(image, write=cmd == 'put'))
    if cmd == 'ls':
        path = argv[2] if len(argv) > 2 else ''
        for name, attr, first, size in fs.listdir(fs.find(path)[1]):
            print(f'{"d" if attr & 0x10 else "-"} {size:>10} {name}')
    elif cmd == 'get':
        data = fs.read_file(argv[2])
        with open(argv[3], 'wb') as f:
            f.write(data)
        print(f'{argv[2]}: {len(data):,} bytes')
    else:
        with open(argv[3], 'rb') as f:
            fs.overwrite_file(argv[2], f.read())
        fs.d.f.flush()
        print(f'{argv[2]}: replaced')


if __name__ == '__main__':
    main(sys.argv[1:])
