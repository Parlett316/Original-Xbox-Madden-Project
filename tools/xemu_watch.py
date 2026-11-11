"""Log when a game running in xemu reaches any of up to four addresses (boot --gdb).

Usage: python xemu_watch.py <log> <secs> <maxhits> <VA> [<VA> ...]

Each hit logs the time, the address, eax, ecx, edx and the return address on the stack.
Breakpoints slow the game while they're being hit, so use it only when nobody is playing.
"""
import os
import socket
import struct
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from xemu import GDB  # noqa: E402
from xemu_call import ask, wait_stop  # noqa: E402


def main(log, secs, maxhits, vas):
    g = GDB()
    ok = lambda r: r in ('OK', '') or r.startswith('E')         # noqa: E731
    regs = lambda r: len(r) >= 80 and not r.startswith('T')     # noqa: E731
    f = open(log, 'a', buffering=1)
    for v in vas:
        ask(g, f'Z1,{v:x},1', ok)
    g.send('c')
    hits, limit = 0, time.time() + secs
    while time.time() < limit and hits < maxhits:
        try:
            wait_stop(g, max(1.0, limit - time.time()))
        except socket.timeout:
            break
        r = struct.unpack_from('<10I', bytes.fromhex(ask(g, 'g', regs)))
        ret = struct.unpack('<I', g.mem(r[4], 4) or b'\0\0\0\0')[0]
        f.write(f'{time.strftime("%H:%M:%S")} {r[8]:#x} eax {r[0]:#x} ecx {r[1]:#x} edx {r[2]:#x} ret {ret:#x}\n')
        hits += 1
        for cmd in (f'z1,{r[8]:x},1', 's', f'Z1,{r[8]:x},1'):
            ask(g, cmd, lambda x: True)
        g.send('c')
    g.s.sendall(b'\x03')
    try:
        wait_stop(g, 5)
    except Exception:
        pass
    for v in vas:
        ask(g, f'z1,{v:x},1', ok)
    g.send('c')
    g.s.close()
    f.write(f'done, {hits} hits\n')
    print(hits, 'hits')


if __name__ == '__main__':
    a = sys.argv[1:]
    if len(a) < 4:
        sys.exit(__doc__)
    main(a[0], float(a[1]), int(a[2]), [int(v, 0) for v in a[3:7]])
