"""Make a game running in xemu call one of its own functions, over the gdb stub (boot --gdb).

Usage: python xemu_call.py <VA to call> <VA the main thread passes> [<secs to watch> <watch VA>...]

The function must take no arguments and end in a plain ret (an event stub, say). The game is
stopped at the second address, sent through the function with that address as the return, and
put back with every register restored. Each watch address (up to 3) is logged when hit, during
the call (with eax, ecx and edx) and for the given seconds after it,
with the text its first stack argument points to: 09's speech library reports problems through
0x449551 and 0x44917c. In 09's menus the main thread passes 0x34d16e every frame.
"""
import os
import socket
import struct
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from xemu import GDB  # noqa: E402


def ask(g, cmd, want=lambda r: True):
    g.send(cmd)
    r = g.recv(10)
    while not want(r):
        r = g.recv(10)
    return r


def wait_stop(g, secs):
    while True:
        r = g.recv(secs)
        if r.startswith(('T', 'S')):
            return r


def main(target, at, secs=0.0, watch=()):
    g = GDB()
    ok = lambda r: r in ('OK', '') or r.startswith('E')         # noqa: E731
    regs = lambda r: len(r) >= 80 and not r.startswith('T')     # noqa: E731
    ask(g, f'Z1,{at:x},1', ok)
    g.send('c')
    wait_stop(g, 30)
    saved = ask(g, 'g', regs)
    r = list(struct.unpack_from('<10I', bytes.fromhex(saved)))
    assert r[8] == at, hex(r[8])
    esp = r[4] - 4
    ask(g, f'M{esp:x},4:{struct.pack("<I", at).hex()}', ok)
    r[4], r[8] = esp, target
    ask(g, 'G' + struct.pack('<10I', *r).hex() + saved[80:], ok)
    for w in watch:                      # watched during the call too
        ask(g, f'Z1,{w:x},1', ok)
    while True:
        g.send('c')
        wait_stop(g, 30)
        back = struct.unpack_from('<10I', bytes.fromhex(ask(g, 'g', regs)))
        if back[8] == at:
            break
        print(f'during the call: hit {back[8]:#x}, eax {back[0]:#x} ecx {back[1]:#x} edx {back[2]:#x}')
        for cmd in (f'z1,{back[8]:x},1', 's', f'Z1,{back[8]:x},1'):
            ask(g, cmd, lambda x: True)
    for w in watch:
        ask(g, f'z1,{w:x},1', ok)
    print(f'returned to {back[8]:#x}, esp {back[4]:#x} (expected {at:#x}, {esp + 4:#x}), eax {back[0]:#x}')
    ask(g, 'G' + saved, ok)
    ask(g, f'z1,{at:x},1', ok)
    for w in watch:
        ask(g, f'Z1,{w:x},1', ok)
    g.send('c')
    limit = time.time() + secs
    while watch and time.time() < limit:
        try:
            wait_stop(g, max(1.0, limit - time.time()))
        except socket.timeout:
            break
        r = struct.unpack_from('<10I', bytes.fromhex(ask(g, 'g', regs)))
        ret, arg = struct.unpack('<2I', g.mem(r[4], 8))
        text = (g.mem(arg, 96) or b'').split(b'\0')[0].decode('latin1')
        print(f'{time.strftime("%H:%M:%S")} hit {r[8]:#x} from {ret:#x}: {text!r}')
        for cmd in (f'z1,{r[8]:x},1', 's', f'Z1,{r[8]:x},1'):
            ask(g, cmd, lambda x: True)
        g.send('c')
    if watch:
        g.s.sendall(b'\x03')
        wait_stop(g, 5)
        for w in watch:
            ask(g, f'z1,{w:x},1', ok)
        g.send('c')
    g.s.close()


if __name__ == '__main__':
    a = sys.argv[1:]
    if len(a) < 2:
        sys.exit(__doc__)
    main(int(a[0], 0), int(a[1], 0), float(a[2]) if len(a) > 2 else 0.0, [int(v, 0) for v in a[3:6]])
