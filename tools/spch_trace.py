"""Log speech events as a game fires them, over xemu's gdb stub (boot --gdb).

Usage: python spch_trace.py <log> <secs> <maxhits> <VA of SPCH_AddCsisEvent> [<text start> <text end>]
       python spch_trace.py <log> <secs> <maxhits> <VA of SPCH_AddEvent> --block

SPCH_AddCsisEvent(params, event) is 0x4093f4 in 07, and SPCH_AddEvent(block) is 0x4064e1, where
the block is the event ID followed by its parameters. Each hit logs the event ID, its first 8
parameter words, and the stack words that look like return addresses (inside the text range,
default 0x11000-0x600000), which lead back to the game code that asked for the line. A
breakpoint slows the game, so use it only when nobody is playing.
"""
import socket
import struct
import sys
import time
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from xemu import GDB  # noqa: E402


def main(log, secs, maxhits, va, block=False, lo=0x11000, hi=0x600000):
    g, hits, limit = GDB(), 0, time.time() + secs
    f = open(log, 'a', buffering=1)
    g.send(f'Z1,{va:x},1')
    r = g.recv(10)
    while r.startswith(('T', 'S')):      # a stop reply left over from connecting
        r = g.recv(10)
    f.write(f'break {va:#x}: {r}\n')
    g.send('c')
    while time.time() < limit and hits < maxhits:
        try:
            r = g.recv(max(1.0, limit - time.time()))
        except socket.timeout:
            break
        if not r.startswith('T'):
            continue
        g.send('g')
        esp = struct.unpack_from('<I', bytes.fromhex(g.recv(10)), 16)[0]
        stack = struct.unpack('<96I', g.mem(esp, 384))
        ret, params, event = stack[:3]
        p = g.mem(params, 36) if params else None
        if block and p:     # SPCH_AddEvent(block): the event ID, then its parameters
            event, p = struct.unpack_from('<I', p)[0], p[4:]
        words = ' '.join('%x' % v for v in struct.unpack_from('<8I', p)) if p else '?'
        rets = ' '.join('%x' % v for v in stack[3:] if lo <= v < hi)
        f.write(f'{time.strftime("%H:%M:%S")} event {event:#x} from {ret:#x} params {words} | stack {rets}\n')
        hits += 1
        for cmd in (f'z1,{va:x},1', 's', f'Z1,{va:x},1'):     # step off the breakpoint, or it fires again
            g.send(cmd)
            g.recv(10)
        g.send('c')
    g.s.sendall(b'\x03')
    for cmd in (None, f'z1,{va:x},1'):
        if cmd:
            g.send(cmd)
        try:
            g.recv(5)
        except Exception:
            pass
    g.send('c')
    g.s.close()
    f.write(f'done, {hits} hits\n')
    print(hits, 'hits')


if __name__ == '__main__':
    a = sys.argv[1:]
    block = '--block' in a
    if block:
        a.remove('--block')
    if len(a) < 4:
        sys.exit(__doc__)
    main(a[0], float(a[1]), int(a[2]), int(a[3], 0), block, *[int(v, 0) for v in a[4:6]])
