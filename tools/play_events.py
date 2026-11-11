"""Log the play event list ([0x7405cc]) while xemu runs, polled over its gdb stub.

    python tools/play_events.py <log> <secs> [interval]    (xemu booted with tools/xemu.py boot --gdb)

Each poll halts the guest for a few milliseconds and uses no breakpoints, so the game
stays playable (a breakpoint on the play-end routine 0x2699b0 fires every frame and
leaves the guest halted if the logger dies). Entries are 32 bytes: spot x/y floats at
+0x10/+0x14, u16 type at +0x1c. Types seen: docs/findings.md section 7, "Play results".
"""
import os
import socket
import struct
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import xemu  # noqa: E402

log, secs = sys.argv[1], float(sys.argv[2])
step = float(sys.argv[3]) if len(sys.argv) > 3 else 0.5
g = xemu.GDB()              # connecting halts the guest
f = open(log, 'a', buffering=1)


def mem(a, n):
    for _ in range(5):          # a stale stop reply can arrive first
        d = g.mem(a, n)
        if d is not None:
            return d
    raise IOError(f'cannot read {a:#x}')


def u32(a):
    return struct.unpack('<I', mem(a, 4))[0]


def read():
    h = u32(u32(0x764ba8) + u32(0x7405cc) * 4)
    _, cnt, size, ncb = struct.unpack("<4I", mem(h, 16))
    return size, (mem(h + 0x10 + ncb * 4, cnt * size) if cnt else b'')


def halt():
    g.s.sendall(b'\x03')
    while True:
        try:
            if g.recv(2).startswith(('T', 'S')):
                return
        except socket.timeout:
            return


limit, last = time.time() + secs, None
try:
    while time.time() < limit:
        size, raw = read()
        if raw != last and raw:
            f.write(f'--- {time.strftime("%H:%M:%S")} {len(raw) // size} events\n')
            for i in range(len(raw) // size):
                b = raw[i * size:(i + 1) * size]
                t = struct.unpack_from('<H', b, 0x1c)[0]
                x, y = struct.unpack_from('<2f', b, 0x10)
                f.write(f'{i:2} type {t:#04x} x {x:7.2f} y {y:7.2f}  {b.hex()}\n')
        last = raw
        g.send('c')
        time.sleep(step)
        halt()
    f.write('done\n')
finally:                        # never leave the guest halted, even after a failed read
    g.send('c')
    g.s.close()
