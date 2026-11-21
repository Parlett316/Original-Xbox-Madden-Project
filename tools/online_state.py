"""Read Madden 09's online state from a running xemu box over its gdb stub (boot --gdb).

    python online_state.py conn     # ConnApi: the game link's clients and their status
    python online_state.py heaps    # the game's heaps (find which one ran out)
    python online_state.py cpu      # EIP and the top of the stack (EIP 0x800151ef = bugcheck)

Set XEMU_INSTANCE=1 for the second box. Each call pauses the box for well under a second.
Addresses: docs/findings.md §14. Session manager = [[[main+0x18]+0x30]+0xb4], main = [0x7c5f18];
ConnApi handle at session manager +0x7c; clients are 0xbc bytes at ConnApi +0x15c (count +0x154),
status at +0x90 (game link) and +0x98 (voice): 0 idle, 1 connecting, 2 resolving, 3 active,
5 failed.
"""
import os
import struct
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from xemu import GDB  # noqa: E402
from xemu_call import ask  # noqa: E402


def attach():
    g = GDB()
    g.s.sendall(b'\x03')
    time.sleep(0.5)
    try:
        g.s.recv(4096)
    except OSError:
        pass
    return g


def dword(g, a):
    return struct.unpack('<I', g.mem(a, 4) or bytes(4))[0]


def conn(g):
    main = dword(g, 0x7c5f18)
    sm = dword(g, dword(g, dword(g, main + 0x18) + 0x30) + 0xb4)
    ca = dword(g, sm + 0x7c)
    print('session manager %x  sessions %d  ConnApi %x' % (sm, dword(g, sm + 0x40), ca))
    if not ca:
        return
    print('state %d  clients %d  self %d  timeout %d ms' % (
        dword(g, ca + 0x150), dword(g, ca + 0x154), dword(g, ca + 0xb4), dword(g, ca + 0xc0)))
    for i in range(min(dword(g, ca + 0x154), 8)):
        b = g.mem(ca + 0x15c + i * 0xbc, 0xbc) or bytes(0xbc)
        addr, laddr = struct.unpack_from('<II', b)
        game, port, vport, _, voice = struct.unpack_from('<5H', b, 0x90)
        link, vlink = struct.unpack_from('<II', b, 0xa0)
        print(' %d %-12s addr %08x local %08x  MADDR %s  game %d voice %d  port %d/%d  link %x/%x' % (
            i, b[0x50:0x70].split(b'\0')[0].decode(errors='replace'), addr, laddr,
            b[0x10:0x50].split(b'\0')[0].decode(errors='replace'), game, voice, port, vport, link, vlink))


def heaps(g):
    h, n = dword(g, 0x7b6124), 0
    print('current heap %x' % dword(g, 0x7b6128))
    while h and n < 40:
        b = g.mem(h, 0x100) or bytes(0x100)
        w = struct.unpack('<64I', b)
        name = next((s.decode() for s in b.split(b'\0') if len(s) >= 4 and all(32 <= c < 127 for c in s)), '')
        print('%08x id %-3x %-8s %08x-%08x size %x  +20..+2c %s' % (
            h, w[0], name, w[5], w[6], w[7], ' '.join('%x' % x for x in w[8:12])))
        h, n = w[2], n + 1


def cpu(g):
    r = struct.unpack_from('<10I', bytes.fromhex(ask(g, 'g', lambda r: len(r) >= 80 and not r.startswith('T'))))
    eip, esp = r[8], r[4]
    top = struct.unpack('<16I', g.mem(esp, 64) or bytes(64))
    print('eip %x esp %x  stack %s' % (eip, esp, ' '.join('%x' % v for v in top)))
    if eip == 0x800151ef:
        print('bugcheck: code %x, parameters %s' % (top[5], ' '.join('%x' % v for v in top[6:10])))


if __name__ == '__main__':
    what = {'conn': conn, 'heaps': heaps, 'cpu': cpu}
    if len(sys.argv) != 2 or sys.argv[1] not in what:
        raise SystemExit(__doc__)
    g = attach()
    try:
        what[sys.argv[1]](g)
    finally:
        g.send('c')
        g.s.close()
