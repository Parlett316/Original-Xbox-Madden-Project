"""Read and write EA TDB databases (Madden 2005/09 Xbox) inside a larger file.

Layout (little-endian):
  DB header 0x18: 'DB\\0\\x08', u32 0, u32 db size, u32 0, u32 table count,
                  u32 CRC(header[0:0x14]); then (4-byte tag, u32 offset) entries.
  Table at base+offset: u32 CRC of the previous region, u32 flags,
                  u32 record length, u32 record bits-1, u32 0,
                  u16 capacity, u16 count, u16 0, u16 0xffff, u8 field count,
                  ..., u32 CRC(table[4:0x24]) at +0x24.
                  Field defs (u32 type, u32 bit offset, 4-byte tag, u32 bits),
                  then capacity * record length bytes of records.
  Trailer: u32 CRC of the last table's fields and records.

Table 0's leading CRC covers the index entries; table k's covers table k-1's
field defs and records. All CRCs are CRC-32/MPEG-2 (non-reflected, init
0xFFFFFFFF, no final xor). Fields are LSB-first bitfields; type 0 = string,
2 = signed, 3 = unsigned.
"""
import struct

_TAB = []
for _b in range(256):
    _c = _b << 24
    for _ in range(8):
        _c = ((_c << 1) ^ 0x04C11DB7) if _c & 0x80000000 else (_c << 1)
        _c &= 0xFFFFFFFF
    _TAB.append(_c)


def crc32(data):
    c = 0xFFFFFFFF
    for b in data:
        c = ((c << 8) & 0xFFFFFFFF) ^ _TAB[(c >> 24) ^ b]
    return c


class Field:
    def __init__(self, typ, bitoff, name, bits):
        self.typ, self.bitoff, self.name, self.bits = typ, bitoff, name, bits


class Table:
    def __init__(self, db, name, pos):
        self.db, self.name, self.pos = db, name, pos
        b = db.buf
        self.reclen = struct.unpack_from('<I', b, pos + 8)[0]
        self.capacity = struct.unpack_from('<H', b, pos + 0x14)[0]
        nfields = b[pos + 0x1c]
        self.fields = {}
        for j in range(nfields):
            typ, off, nm, bits = struct.unpack_from('<II4sI', b, pos + 0x28 + 16 * j)
            nm = nm.decode('latin1')
            self.fields[nm] = Field(typ, off, nm, bits)
        self.recpos = pos + 0x28 + 16 * nfields

    @property
    def count(self):
        return struct.unpack_from('<H', self.db.buf, self.pos + 0x16)[0]

    @count.setter
    def count(self, n):
        assert 0 <= n <= self.capacity
        struct.pack_into('<H', self.db.buf, self.pos + 0x16, n)

    def _rec(self, i):
        a = self.recpos + i * self.reclen
        return a

    def get(self, i, name):
        f = self.fields[name]
        a = self._rec(i)
        rec = self.db.buf[a:a + self.reclen]
        if f.typ == 0:
            s = bytes(rec[f.bitoff // 8:(f.bitoff + f.bits) // 8])
            return s.split(b'\0', 1)[0].decode('latin1')
        v = int.from_bytes(rec, 'little') >> f.bitoff & ((1 << f.bits) - 1)
        if f.typ == 2 and v >> (f.bits - 1):
            v -= 1 << f.bits
        return v

    def set(self, i, name, value):
        f = self.fields[name]
        a = self._rec(i)
        buf = self.db.buf
        if f.typ == 0:
            n = f.bits // 8
            s = value.encode('latin1')[:n]  # full width allowed, no terminator needed
            buf[a + f.bitoff // 8:a + f.bitoff // 8 + n] = s + b'\0' * (n - len(s))
            return
        lo, hi = (-(1 << (f.bits - 1)), (1 << (f.bits - 1)) - 1) if f.typ == 2 else (0, (1 << f.bits) - 1)
        if not lo <= value <= hi:
            raise ValueError(f'{self.name}.{name}={value} out of range {lo}..{hi}')
        mask = ((1 << f.bits) - 1) << f.bitoff
        rec = int.from_bytes(buf[a:a + self.reclen], 'little')
        rec = rec & ~mask | (value & ((1 << f.bits) - 1)) << f.bitoff
        buf[a:a + self.reclen] = rec.to_bytes(self.reclen, 'little')

    def row(self, i):
        return {n: self.get(i, n) for n in self.fields}

    def rows(self):
        return [self.row(i) for i in range(self.count)]

    def raw(self, i):
        a = self._rec(i)
        return bytes(self.db.buf[a:a + self.reclen])

    def set_raw(self, i, data):
        assert len(data) == self.reclen
        a = self._rec(i)
        self.db.buf[a:a + self.reclen] = data


class DB:
    """A TDB at offset `off` inside bytearray `buf` (edited in place)."""

    def __init__(self, buf, off):
        assert buf[off:off + 4] == b'DB\x00\x08'
        self.buf, self.off = buf, off
        self.size = struct.unpack_from('<I', buf, off + 8)[0]
        n = struct.unpack_from('<I', buf, off + 0x10)[0]
        self.base = off + 0x18 + 8 * n
        self.order = []
        self.tables = {}
        for k in range(n):
            nm = buf[off + 0x18 + 8 * k:off + 0x1c + 8 * k].decode('latin1')
            o = struct.unpack_from('<I', buf, off + 0x1c + 8 * k)[0]
            t = Table(self, nm, self.base + o)
            self.order.append(t)
            self.tables[nm] = t

    def __getitem__(self, name):
        return self.tables[name]

    def checksums(self):
        """Return the checksums as they should be, in file order."""
        b, off = self.buf, self.off
        out = [(off + 0x14, crc32(b[off:off + 0x14]))]
        prev = (off + 0x18, self.base)
        ends = [t.pos for t in self.order[1:]] + [off + self.size - 4]
        for t, end in zip(self.order, ends):
            out.append((t.pos, crc32(b[prev[0]:prev[1]])))
            out.append((t.pos + 0x24, crc32(b[t.pos + 4:t.pos + 0x24])))
            prev = (t.pos + 0x28, end)
        out.append((off + self.size - 4, crc32(b[prev[0]:prev[1]])))
        return out

    def verify(self):
        return all(struct.unpack_from('<I', self.buf, p)[0] == v for p, v in self.checksums())

    def fix(self):
        # Header CRCs first: each table's leading CRC covers only records,
        # and each +0x24 CRC covers bytes after the leading one.
        for p, v in self.checksums():
            if p == self.off + 0x14 or any(p == t.pos + 0x24 for t in self.order):
                struct.pack_into('<I', self.buf, p, v)
        for p, v in self.checksums():
            struct.pack_into('<I', self.buf, p, v)

    def resized(self, capacities):
        """Return this DB rebuilt as a new bytearray, with the tables named in
        `capacities` ({name: new capacity}) grown; records and all other
        tables are kept. Tables are packed back to back, as EA lays them out.
        Most tables store every slot; some (flags 0x1a, e.g. in the franchise
        DB) store only their current rows, so only the capacity changes."""
        b, off = self.buf, self.off
        n = len(self.order)
        out = bytearray(b[off:off + 0x18 + 8 * n])
        body = bytearray()
        ends = [t.pos for t in self.order[1:]] + [off + self.size - 4]
        for k, (t, end) in enumerate(zip(self.order, ends)):
            cap = capacities.get(t.name, t.capacity)
            assert cap >= t.capacity, f'{t.name}: shrinking is not supported'
            struct.pack_into('<I', out, 0x1c + 8 * k, len(body))
            head = bytearray(b[t.pos:t.recpos])
            struct.pack_into('<H', head, 0x14, cap)
            body += head + b[t.recpos:end]
            if end - t.recpos == t.reclen * t.capacity:
                body += bytes(t.reclen * (cap - t.capacity))
        out += body + bytes(4)
        struct.pack_into('<I', out, 8, len(out))
        db = DB(out, 0)
        db.fix()
        return out
