"""Drive xemu from scripts: an isolated setup, key presses, screenshots, QMP and gdb.

    python tools/xemu.py setup <work> <iso> [--pad] [--fresh-hdd]
    python tools/xemu.py boot  <work> [--gdb]          # start xemu in the background
    python tools/xemu.py keys  <work> <name> TOKENS...  # a b x y enter back up down left right,
                                                        # w<sec> waits, s screenshots
    python tools/xemu.py shot  <work> [name]            # one screenshot
    python tools/xemu.py hmp   "<monitor command>"...   # e.g. "info registers", "x /16xb 0x801c50"
    python tools/xemu.py flush                          # before reading the drive while running
    python tools/xemu.py snap  <work> <label>           # copy the newest Fran-FranN save to saves/
    python tools/xemu.py quit
    python tools/xemu.py ram   <out.bin> <start> <end>  # guest memory by VA over the gdb stub (boot --gdb)
    python tools/xemu.py break <log> <secs> <maxhits> <va> [skip-caller-va...]

A work folder holds its own xemu.toml, xbox_hdd.qcow2 and eeprom.bin, so the
user's setup is never touched. `setup` copies the user's config
(%APPDATA%/xemu/xemu/xemu.toml) and points it at the work folder's files and
the ISO. The drive and EEPROM come from the user's paths (the drive only once,
unless --fresh-hdd). Input goes to port 1 as the keyboard, unless --pad keeps
the user's gamepad there (to hand the instance to the user). xemu rewrites the
config on exit, so `boot` re-applies the settings each time.

Keys are posted to the window (no focus needed), held 0.08 s with 0.5 s after:
a longer hold can step a menu twice. Screenshots use PrintWindow (this build's
QMP has no screendump). `keys` and `shot` nudge the mouse a pixel first,
because a sleeping display gives black pictures. `keys` also writes a contact
sheet of the run's screenshots to <work>/sheet.png, to look at in one read.

QMP is on 127.0.0.1:44444 and identifies the window (the PID listening there);
`quit` closes only that instance. The gdb stub is on 127.0.0.1:1234 and reads
virtual addresses in the current context, a few MB a second, with the game
running: the game's own addresses (e.g. 0x801c50) work as they are. Physical
RAM shows at 0x80000000 + physical, but only partly (the game image's pages
read as E14 there), so `ram` fills unreadable chunks with zeros and counts them.
QMP pmemsave hangs xemu, so don't use it. Breakpoints slow the game to
unplayable, so use them only when nobody is playing.
Background and menu routes: docs/workflow.md ("Testing in xemu").
"""
import ctypes
import glob
import json
import math
import os
import re
import shutil
import socket
import struct
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
XEMU = r'C:\Xemu\xemu.exe'
USER_CFG = os.path.join(os.environ.get('APPDATA', ''), 'xemu', 'xemu', 'xemu.toml')
QMP_PORT, GDB_PORT = 44444, 1234

# ---- config -------------------------------------------------------------------


def toml_set(text, section, key, value):
    """Set key = value in [section], adding either if missing (flat TOML only)."""
    line = f"{key} = {value}"
    m = re.search(rf'^\[{re.escape(section)}\]\s*$', text, re.M)
    if not m:
        return text.rstrip('\n') + f'\n\n[{section}]\n{line}\n'
    end = re.search(r'^\[', text[m.end():], re.M)
    end = m.end() + end.start() if end else len(text)
    body = text[m.end():end]
    if re.search(rf'^{re.escape(key)}\s*=', body, re.M):
        body = re.sub(rf'^{re.escape(key)}\s*=.*$', lambda _: line, body, flags=re.M)
    else:
        body = body.rstrip('\n') + f'\n{line}\n\n' if body.strip() else f'\n{line}\n\n'
    return text[:m.end()] + body + text[end:]


def toml_get(text, key):
    m = re.search(rf"^{re.escape(key)}\s*=\s*'([^']*)'", text, re.M)
    return m and m.group(1)


def q(path):
    return "'" + os.path.abspath(path) + "'"


def setup(work, iso, pad=False, fresh_hdd=False):
    os.makedirs(os.path.join(work, 'shots'), exist_ok=True)
    os.makedirs(os.path.join(work, 'saves'), exist_ok=True)
    user = open(USER_CFG, encoding='utf8').read()
    hdd, eeprom = os.path.join(work, 'xbox_hdd.qcow2'), os.path.join(work, 'eeprom.bin')
    if fresh_hdd or not os.path.exists(hdd):
        shutil.copyfile(toml_get(user, 'hdd_path'), hdd)
    if not os.path.exists(eeprom):
        shutil.copyfile(toml_get(user, 'eeprom_path'), eeprom)
    settings = {'iso': os.path.abspath(iso), 'pad': pad}
    json.dump(settings, open(os.path.join(work, 'settings.json'), 'w'))
    write_cfg(work)
    print('work folder ready:', os.path.abspath(work))


def write_cfg(work):
    s = json.load(open(os.path.join(work, 'settings.json')))
    t = open(USER_CFG, encoding='utf8').read()
    t = toml_set(t, 'general', 'show_welcome', 'false')
    t = toml_set(t, 'sys.files', 'eeprom_path', q(os.path.join(work, 'eeprom.bin')))
    t = toml_set(t, 'sys.files', 'hdd_path', q(os.path.join(work, 'xbox_hdd.qcow2')))
    t = toml_set(t, 'sys.files', 'dvd_path', q(s['iso']))
    if not s['pad']:
        t = toml_set(t, 'input.bindings', 'port1_driver', "'usb-xbox-gamepad'")
        t = toml_set(t, 'input.bindings', 'port1', "'keyboard'")
    open(os.path.join(work, 'xemu.toml'), 'w', encoding='utf8').write(t)


def boot(work, gdb=False):
    if listening_pid(QMP_PORT):
        raise SystemExit('an xemu with QMP on port %d is already running' % QMP_PORT)
    write_cfg(work)
    args = [XEMU, '-config_path', os.path.abspath(os.path.join(work, 'xemu.toml')),
            '-qmp', f'tcp:127.0.0.1:{QMP_PORT},server,nowait']
    if gdb:
        args += ['-gdb', f'tcp:127.0.0.1:{GDB_PORT}']
    log = open(os.path.join(work, 'run.log'), 'w')
    subprocess.Popen(args, stdout=log, stderr=log, stdin=subprocess.DEVNULL,
                     creationflags=0x00000008 | 0x00000200)  # detached, new process group
    for _ in range(60):
        if window():
            print('xemu up, pid', listening_pid(QMP_PORT))
            return
        time.sleep(1)
    raise SystemExit('xemu window did not appear; see run.log')

# ---- window, keys, screenshots ----------------------------------------------------


def listening_pid(port):
    out = subprocess.run(['netstat', '-ano', '-p', 'tcp'], capture_output=True, text=True).stdout
    for line in out.splitlines():
        if f':{port} ' in line and 'LISTEN' in line:
            return int(line.split()[-1])


def window():
    """(hwnd, width, height) of the biggest visible window of the QMP xemu."""
    import ctypes.wintypes as W
    u = ctypes.windll.user32
    pid = listening_pid(QMP_PORT)
    if not pid:
        return None
    found = []

    def cb(h, _):
        p = W.DWORD()
        u.GetWindowThreadProcessId(h, ctypes.byref(p))
        if p.value == pid and u.IsWindowVisible(h):
            r = W.RECT()
            u.GetClientRect(h, ctypes.byref(r))
            found.append((h, r.right, r.bottom))
        return True
    u.EnumWindows(ctypes.WINFUNCTYPE(ctypes.c_bool, W.HWND, W.LPARAM)(cb), 0)
    return max(found, key=lambda f: f[1] * f[2]) if found else None


def wake():
    """Keep the display on and nudge the mouse, so screenshots aren't black."""
    k, u = ctypes.windll.kernel32, ctypes.windll.user32
    k.SetThreadExecutionState(0x80000000 | 0x2 | 0x1)
    u.mouse_event(1, 1, 0, 0, 0)
    time.sleep(0.05)
    u.mouse_event(1, -1 & 0xffffffff, 0, 0, 0)


def screenshot(path):
    import ctypes.wintypes as W
    from PIL import Image
    u, g = ctypes.windll.user32, ctypes.windll.gdi32
    u.SetProcessDPIAware()
    h, w, hh = window()
    dc = u.GetDC(h)
    m = g.CreateCompatibleDC(dc)
    b = g.CreateCompatibleBitmap(dc, w, hh)
    g.SelectObject(m, b)
    u.PrintWindow(h, m, 3)

    class BI(ctypes.Structure):
        _fields_ = [('s', W.DWORD), ('w', W.LONG), ('h', W.LONG), ('p', W.WORD), ('b', W.WORD),
                    ('c', W.DWORD), ('i', W.DWORD), ('x', W.LONG), ('y', W.LONG), ('u', W.DWORD), ('v', W.DWORD)]
    bi = BI(ctypes.sizeof(BI), w, -hh, 1, 32, 0, 0, 0, 0, 0, 0)
    buf = ctypes.create_string_buffer(w * hh * 4)
    g.GetDIBits(m, b, 0, hh, buf, ctypes.byref(bi), 0)
    g.DeleteObject(b)
    g.DeleteDC(m)
    u.ReleaseDC(h, dc)
    im = Image.frombuffer('RGB', (w, hh), buf, 'raw', 'BGRX', 0, 1)
    if path:
        im.save(path)
    return im


VK = {'a': (0x41, 0x1e), 'b': (0x42, 0x30), 'x': (0x58, 0x2d), 'y': (0x59, 0x15),
      'enter': (0x0d, 0x1c), 'back': (0x08, 0x0e), 'up': (0x26, 0x48), 'down': (0x28, 0x50),
      'left': (0x25, 0x4b), 'right': (0x27, 0x4d)}
EXTENDED = {'up', 'down', 'left', 'right'}


def press(key, hold=0.08, after=0.5):
    u = ctypes.windll.user32
    h = window()[0]
    vk, sc = VK[key]
    ex = (1 << 24) if key in EXTENDED else 0
    u.PostMessageW(h, 0x100, vk, 1 | (sc << 16) | ex)
    time.sleep(hold)
    u.PostMessageW(h, 0x101, vk, 1 | (sc << 16) | ex | (3 << 30))
    time.sleep(after)


def keys(work, name, tokens):
    wake()
    for p in glob.glob(os.path.join(work, 'shots', f'{name}_*.png')):
        os.remove(p)
    n = 0
    for tok in tokens:
        if tok == 's':
            screenshot(os.path.join(work, 'shots', f'{name}_{n:02d}.png'))
            n += 1
        elif re.fullmatch(r'w\d+(\.\d+)?', tok):
            time.sleep(float(tok[1:]))
        elif tok in VK:
            press(tok)
        else:
            raise SystemExit(f'unknown token {tok!r}')
    if n:
        sheet(work, name)
    print(n, 'shots')


def sheet(work, name):
    from PIL import Image
    ps = sorted(glob.glob(os.path.join(work, 'shots', f'{name}_*.png')))
    c = 1 if len(ps) == 1 else 2 if len(ps) <= 4 else 3
    r = math.ceil(len(ps) / c)
    W, H = (800, 600) if c == 1 else (640, 480) if c == 2 else (426, 320)
    s = Image.new('RGB', (W * c, H * r))
    for i, p in enumerate(ps):
        s.paste(Image.open(p).resize((W, H)), ((i % c) * W, (i // c) * H))
    s.save(os.path.join(work, 'sheet.png'))

# ---- QMP ------------------------------------------------------------------------


class QMP:
    def __init__(self):
        self.f = socket.create_connection(('127.0.0.1', QMP_PORT), 10).makefile('rwb')
        self.f.readline()
        self.cmd('qmp_capabilities')

    def cmd(self, name, **args):
        self.f.write(json.dumps({'execute': name, 'arguments': args}).encode() + b'\n')
        self.f.flush()
        while True:
            r = json.loads(self.f.readline())
            if 'return' in r or 'error' in r:
                return r

    def hmp(self, line):
        return self.cmd('human-monitor-command', **{'command-line': line}).get('return')


def snap(work, label):
    sys.path.insert(0, HERE)
    sys.path.insert(0, os.path.join(HERE, '..', 'roster'))
    import xbox_hdd
    import tdb
    QMP().hmp('qemu-io ide0-hd0 flush')
    fs = xbox_hdd.Fatx(xbox_hdd.Qcow2(os.path.join(work, 'xbox_hdd.qcow2')))
    best = None
    for name, attr, _, _ in fs.listdir(fs.find('UDATA/4541023b')[1]):
        if attr & 0x10:
            for n, _, _, _ in fs.listdir(fs.find(f'UDATA/4541023b/{name}')[1]):
                m = re.fullmatch(r'Fran-Fran(\d+)', n)
                if m and (best is None or int(m[1]) > best[0]):
                    best = (int(m[1]), f'UDATA/4541023b/{name}/{n}')
    if not best:
        raise SystemExit('no franchise save on the drive')
    d = fs.read_file(best[1])
    out = os.path.join(work, 'saves', f'{label}.bin')
    open(out, 'wb').write(d)
    b = bytearray(d)
    db = tdb.DB(b, b.find(b'DB\x00\x08'))
    a = db['SEAI'].row(0)
    print(out, 'from', best[1].split('/')[-1], 'crc ok' if db.verify() else 'CRC BAD',
          'year', a['SEYR'], 'week', a['SEWN'], 'type', a['SEWT'])

# ---- gdb stub -------------------------------------------------------------------


class GDB:
    def __init__(self):
        self.s = socket.create_connection(('127.0.0.1', GDB_PORT), 30)
        self.buf = b''
        self.s.sendall(b'+')
        self.send('?')
        self.recv(10)

    def send(self, cmd):
        body = cmd.encode()
        self.s.sendall(b'$' + body + b'#' + b'%02x' % (sum(body) & 0xff))

    def recv(self, timeout=None):
        self.s.settimeout(timeout)
        while True:
            i = self.buf.find(b'$')
            j = self.buf.find(b'#', i + 1) if i >= 0 else -1
            if i >= 0 and j >= 0 and len(self.buf) >= j + 3:
                data, self.buf = self.buf[i + 1:j], self.buf[j + 3:]
                self.s.sendall(b'+')
                return data.decode()
            chunk = self.s.recv(65536)
            if not chunk:
                raise EOFError
            self.buf += chunk

    def mem(self, va, n):
        self.send(f'm{va:x},{n:x}')
        r = self.recv(10).replace('+', '')
        return bytes.fromhex(r) if len(r) == 2 * n else None

    def detach(self):
        self.send('D')
        try:
            self.recv(5)
        except Exception:
            pass
        self.s.close()


def ram(out, start, end, chunk=0x800):
    g, bad, t0 = GDB(), 0, time.time()
    with open(out, 'wb') as o:
        for a in range(start, end, chunk):
            d = g.mem(a, chunk)
            bad += d is None
            o.write(d or b'\0' * chunk)
    g.detach()
    print(f'saved {start:#x}-{end:#x}, unreadable chunks {bad}, {time.time() - t0:.1f} s')


def breakpoint_log(log, secs, maxhits, va, skip):
    """Log each call of the function at va: its caller and the first two stack args as floats."""
    g, hits, limit = GDB(), 0, time.time() + secs
    f = open(log, 'a', buffering=1)
    g.send(f'Z1,{va:x},1')
    f.write(f'break {va:#x}: {g.recv(10)}\n')
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
        ret, a1, a2 = struct.unpack('<I2f', g.mem(esp, 12))
        if ret - 5 not in skip:
            f.write(f'{time.strftime("%H:%M:%S")} from {ret - 5:#x} args {a1:.3f} {a2:.3f}\n')
            hits += 1
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


def main(argv):
    if not argv:
        raise SystemExit(__doc__)
    c, a = argv[0], argv[1:]
    if c == 'setup':
        setup(a[0], a[1], '--pad' in a, '--fresh-hdd' in a)
    elif c == 'boot':
        boot(a[0], '--gdb' in a)
    elif c == 'keys':
        keys(a[0], a[1], a[2:])
    elif c == 'shot':
        wake()
        time.sleep(1)
        p = os.path.join(a[0], 'shots', (a[1] if len(a) > 1 else 'now') + '.png')
        screenshot(p)
        print(p)
    elif c == 'hmp':
        m = QMP()
        for line in a:
            print('>', line)
            print(m.hmp(line))
    elif c == 'flush':
        print(QMP().hmp('qemu-io ide0-hd0 flush') or 'flushed')
    elif c == 'snap':
        snap(a[0], a[1])
    elif c == 'quit':
        print(QMP().cmd('quit'))
        time.sleep(4)
    elif c == 'ram':
        ram(a[0], int(a[1], 0), int(a[2], 0))
    elif c == 'break':
        breakpoint_log(a[0], float(a[1]), int(a[2]), int(a[3], 0), {int(x, 0) for x in a[4:]})
    else:
        raise SystemExit(__doc__)


if __name__ == '__main__':
    main(sys.argv[1:])
