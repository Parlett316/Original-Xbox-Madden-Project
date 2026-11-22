r"""A step-by-step installer for the Madden NFL 09 mods, for people new to all this.

Usage:
  python tools/installer.py              open the window (or double-click "Install Madden 09 Mods.bat")
  python tools/installer.py --selftest   check the parts that need no window or Xbox

The window has four steps:
  1. Where is your Madden? A folder on this PC (it looks on every drive, two folders deep, and in the
     Desktop, Downloads and Documents folders; Browse also looks one level down, so C:\Games works
     for C:\Games\Madden09), or the Xbox's hard drive over FTP (UnleashX, Avalaunch, XBMC; user and
     password usually xbox/xbox). Madden 09 must be the untouched original (its default.xbe is checked
     against the stock SHA-1). Madden 2005-08 are optional, from either place, and unlock the music,
     the radio show and progression.
  2. What mods? Plain words; a mod that needs another Madden year or the roster says so.
  3. Mod it: choose the destination (a new folder on the Xbox, or on this PC) and press one button.
     It copies the games it needs from the Xbox, downloads the EA ratings and photos, coach photos and
     nflverse stats, runs tools/build_all.py with the same arguments the build window (tools/build_gui.py)
     uses, then makes the destination hold the whole modded game, checking every file's size. A list of
     what's there (mod_install.txt) means the next run only copies what changed.
  4. Profit! What to do next, and (on the Xbox) moving Rost- roster saves that would hide the new roster.

Everything goes in installer_files/ in the repository folder (never committed): the games copied
from the Xbox, the downloads, the build and the save backups. The stock game folders are only read.
"""
import ftplib
import hashlib
import http.client
import json
import os
import queue
import re
import shutil
import struct
import subprocess
import sys
import threading
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_gui as bg  # noqa: E402  (choices -> build_all.py arguments, and the checks)

ROOT = bg.ROOT
WORK = os.path.join(ROOT, 'installer_files')
GAMES_DIR = os.path.join(WORK, 'games')
DL = os.path.join(WORK, 'downloads')
OUT = os.path.join(WORK, 'build')
BACKUPS = os.path.join(WORK, 'save_backups')
SETTINGS = os.path.join(WORK, 'settings.json')
MANIFEST = 'mod_install.txt'
NO_WINDOW = getattr(subprocess, 'CREATE_NO_WINDOW', 0)

STOCK_09_SHA1 = 'eda937d7b62f75030aa4feb66c7a2ffe306c8eee'
TITLE_09 = 0x4541023b
# title ID -> the folder name build_all.py expects, and what that game is used for
GAMES = {
    0x4541023b: ('Madden NFL 09 (USA)', 'the game being modded'),
    0x4541004d: ('Madden NFL 2005 (USA)', 'realistic progression, and its songs'),
    0x45410075: ('Madden NFL 06 (USA)', 'its songs'),
    0x4541009f: ('Madden NFL 07 (USA)', 'the Tony Bruno radio show, and its songs'),
    0x454100ac: ('Madden NFL 08 (USA)', 'its songs'),
}
ORDER = [TITLE_09, 0x4541004d, 0x45410075, 0x4541009f, 0x454100ac]
NFLVERSE = 'https://github.com/nflverse/nflverse-data/releases/download/'
SCHEDULE_URL = 'https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv'
LAST_SEASON = 2025


# ---------------------------------------------------------------- small helpers

def xbe_title(head):
    """(title ID, title name) from the first few KB of an XBE, or None."""
    if len(head) < 0x180 or head[:4] != b'XBEH':
        return None
    base, cert = struct.unpack_from('<I', head, 0x104)[0], struct.unpack_from('<I', head, 0x118)[0]
    c = cert - base
    if not 0 <= c <= len(head) - 92:
        return None
    tid = struct.unpack_from('<I', head, c + 8)[0]
    return tid, head[c + 12:c + 92].decode('utf-16le', 'replace').split('\0')[0]


def sha1_file(path, chunk=1 << 20):
    h = hashlib.sha1()
    with open(path, 'rb') as f:
        while b := f.read(chunk):
            h.update(b)
    return h.hexdigest()


def nice(n):
    for unit in ('bytes', 'KB', 'MB', 'GB'):
        if n < 1024 or unit == 'GB':
            return f'{n:,} bytes' if unit == 'bytes' else f'{n:.1f} {unit}'
        n /= 1024


def local_game(path):
    """The title ID of a game folder on this PC, or None."""
    try:
        with open(os.path.join(path, 'default.xbe'), 'rb') as f:
            t = xbe_title(f.read(8192))
        return t and os.path.isdir(os.path.join(path, 'data')) and t[0]
    except OSError:
        return None


def is_link(path):
    return os.path.islink(path) or (hasattr(os.path, 'isjunction') and os.path.isjunction(path))


def link_game(src, name):
    """Make installer_files/games/<name> point at a folder on this PC (a junction: no copy, no admin)."""
    os.makedirs(GAMES_DIR, exist_ok=True)
    dst = os.path.join(GAMES_DIR, name)
    if os.path.normcase(os.path.abspath(src)) == os.path.normcase(os.path.abspath(dst)):
        return
    if is_link(dst):
        os.rmdir(dst)                    # removes the link only, never the folder it points at
    elif os.path.exists(dst):
        raise RuntimeError(f'{dst} already holds a copy of the game. Delete it first to use another folder.')
    r = subprocess.run(['cmd', '/c', 'mklink', '/J', dst, os.path.abspath(src)], capture_output=True, text=True,
                       creationflags=NO_WINDOW)
    if r.returncode:
        raise RuntimeError('Could not link the folder: ' + (r.stderr or r.stdout).strip())


def tree_files(top):
    """{relative path with / : full path} of every file under top."""
    out = {}
    for d, _, files in os.walk(top):
        for f in files:
            p = os.path.join(d, f)
            out[os.path.relpath(p, top).replace(os.sep, '/')] = p
    return out


class HashCache:
    """SHA-1s of local files, remembered by path, size and time so 2 GB isn't re-read every install."""
    def __init__(self, path):
        self.path = path
        try:
            self.d = json.load(open(path, encoding='utf8'))
        except (OSError, ValueError):
            self.d = {}

    def get(self, p):
        st = os.stat(p)
        key = os.path.normcase(os.path.abspath(p))
        hit = self.d.get(key)
        if hit and hit[0] == st.st_size and hit[1] == st.st_mtime_ns:
            return hit[2]
        h = sha1_file(p)
        self.d[key] = [st.st_size, st.st_mtime_ns, h]
        return h

    def save(self):
        try:
            json.dump(self.d, open(self.path, 'w', encoding='utf8'))
        except OSError:
            pass


class Cancelled(Exception):
    pass


# ---------------------------------------------------------------- the Xbox, over FTP

UNIX = re.compile(r'^([dl-])\S{9}\S?\s+\d+\s+\S+\s+(?:\S+\s+)?(\d+)\s+\w{3}\s+\d+\s+[\d:]+\s+(.+)$')
DOS = re.compile(r'^\d\d-\d\d-\d{2,4}\s+\d\d:\d\d\s*(?:[AP]M)?\s+(<DIR>|\d+)\s+(.+)$', re.I)


def parse_list(lines):
    """[(name, is_dir, size)] from LIST output, Unix or DOS style."""
    out = []
    for ln in lines:
        m = UNIX.match(ln)
        if m:
            out.append((m.group(3), m.group(1) == 'd', int(m.group(2))))
            continue
        m = DOS.match(ln)
        if m:
            d = m.group(1).upper() == '<DIR>'
            out.append((m.group(2), d, 0 if d else int(m.group(1))))
    return [x for x in out if x[0] not in ('.', '..')]


def join(*parts):
    return '/' + '/'.join(p.strip('/') for p in parts if p.strip('/'))


class Xbox:
    def __init__(self, host, user='xbox', password='xbox', port=21):
        self.host, self.user, self.password, self.port = host, user, password, port
        self.passive = True
        self.ftp = None

    def connect(self):
        self.close()
        f = ftplib.FTP(encoding="latin-1")   # Xbox folder names are Latin-1, not UTF-8
        f.connect(self.host, self.port, timeout=20)
        f.login(self.user, self.password)
        f.set_pasv(self.passive)
        self.ftp = f
        return f.getwelcome()

    def close(self):
        if self.ftp:
            try:
                self.ftp.quit()
            except Exception:
                try:
                    self.ftp.close()
                except Exception:
                    pass
            self.ftp = None

    def _again(self, fn):
        """Run fn(ftp); reconnect once if the connection dropped, and fall back to active mode."""
        for attempt in range(3):
            try:
                if not self.ftp:
                    self.connect()
                return fn(self.ftp)
            except ftplib.error_perm:
                raise
            except (OSError, EOFError, ftplib.Error):
                if attempt == 2:
                    raise
                if attempt == 1:
                    self.passive = not self.passive
                self.ftp = None
                time.sleep(1)

    @staticmethod
    def _in(f, path):
        """Change to path's folder and return its last part. UnleashX's LIST ignores a path argument
        and lists the current folder, so every folder-relative command goes through here."""
        folder, name = path.rsplit('/', 1)
        f.cwd(folder or '/')
        return name

    def listdir(self, path):
        def go(f):
            lines = []
            f.cwd(path)                 # a missing folder raises error_perm: None below
            f.retrlines('LIST', lines.append)
            return parse_list(lines)
        try:
            return self._again(go)
        except ftplib.error_perm:
            return None

    def walk(self, top):
        """[(relative path, size)] of every file under top."""
        out, todo = [], ['']
        while todo:
            rel = todo.pop()
            for name, d, size in self.listdir(join(top, rel)) or []:
                r = f'{rel}/{name}' if rel else name
                (todo.append(r) if d else out.append((r, size)))
        return out

    def head(self, path, n=8192):
        """The first n bytes of a file, on a connection of its own (abort is unreliable on Xbox servers)."""
        f = ftplib.FTP(encoding="latin-1")   # Xbox folder names are Latin-1, not UTF-8
        f.connect(self.host, self.port, timeout=20)
        f.login(self.user, self.password)
        f.set_pasv(self.passive)
        f.voidcmd('TYPE I')
        data = b''
        try:
            s = f.transfercmd('RETR ' + path)
            while len(data) < n:
                b = s.recv(n - len(data))
                if not b:
                    break
                data += b
            s.close()
        except (ftplib.Error, OSError):
            pass
        finally:
            f.close()
        return data

    def read(self, path):
        buf = []
        try:
            self._again(lambda f: f.retrbinary('RETR ' + path, buf.append))
        except ftplib.error_perm:
            return None
        return b''.join(buf)

    def download(self, path, local, progress=None, cancel=None):
        tmp = local + '.part'
        os.makedirs(os.path.dirname(local), exist_ok=True)

        def go(f):
            with open(tmp, 'wb') as out:
                def chunk(b):
                    if cancel and cancel.is_set():
                        raise Cancelled()
                    out.write(b)
                    progress and progress(len(b))
                f.retrbinary('RETR ' + path, chunk, blocksize=1 << 16)
        self._again(go)
        os.replace(tmp, local)

    def size(self, path):
        def go(f):
            f.voidcmd('TYPE I')
            return f.size(path)
        try:
            return self._again(go)
        except ftplib.Error:
            parent, name = path.rsplit('/', 1)
            for n, d, s in self.listdir(parent or '/') or []:
                if n == name and not d:
                    return s
            return None

    def upload(self, local, path, progress=None, cancel=None):
        def go(f):
            with open(local, 'rb') as src:
                def chunk(b):
                    if cancel and cancel.is_set():
                        raise Cancelled()
                    progress and progress(len(b))
                f.storbinary('STOR ' + self._in(f, path), src, blocksize=1 << 16, callback=chunk)
        self._again(go)

    def write(self, path, data):
        import io
        self._again(lambda f: f.storbinary('STOR ' + self._in(f, path), io.BytesIO(data)))

    def mkdirs(self, path):
        cur = ''
        for part in path.strip('/').split('/'):
            cur += '/' + part
            try:
                self._again(lambda f: f.mkd(self._in(f, cur)))
            except ftplib.error_perm:
                pass                     # already there

    def delete(self, path):
        self._again(lambda f: f.delete(self._in(f, path)))

    def delete_tree(self, path):
        for name, d, _ in self.listdir(path) or []:
            p = join(path, name)
            if d:
                self.delete_tree(p)
            else:
                self.delete(p)
        self._again(lambda f: f.rmd(self._in(f, path)))

    # -- finding things

    def drives(self):
        skip = {'C', 'X', 'Y', 'Z', 'D'}         # system, cache and the DVD drive
        names = [n for n, d, _ in self.listdir('/') or [] if d]
        return [n for n in names if n.rstrip(':').upper() not in skip and len(n.rstrip(':')) == 1]

    def find_games(self, report=None, quick=False):
        """[{path, tid, title, ours}] for every folder with a default.xbe, two levels deep.

        Reading a title takes a login of its own (about 2 s), so quick looks only in folders whose
        name has MADDEN or NFL in it; the window tries that first and searches everything after.
        """
        found = []
        for drive in self.drives():
            report and report(f'Looking on drive {drive.rstrip(":")}...')
            for name, d, _ in self.listdir(join(drive)) or []:
                if not d or name.upper() in ('UDATA', 'TDATA', 'CACHE'):
                    continue
                top = join(drive, name)
                entries = self.listdir(top) or []
                dirs = [top] + [join(top, n) for n, sub, _ in entries if sub]
                for folder in dirs:
                    if quick and not re.search(r'madden|nfl', folder.rsplit('/', 1)[-1], re.I):
                        continue
                    names = {n.lower(): n for n, sub, _ in (entries if folder == top else self.listdir(folder) or [])
                             if not sub}
                    if 'default.xbe' not in names:
                        continue
                    report and report(f'Looking on drive {drive.rstrip(":")}: {folder.split("/")[-1]}')
                    t = xbe_title(self.head(join(folder, names['default.xbe'])))
                    if t and t[0] in GAMES:
                        found.append(dict(path=folder, tid=t[0], title=t[1], ours=MANIFEST.lower() in names))
        return found

    def roster_saves(self):
        """Folders starting with Rost- in Madden 09's save area (E:\\UDATA\\4541023b)."""
        out = []
        for drive in self.drives():
            base = None
            for n, d, _ in self.listdir(join(drive, 'UDATA')) or []:
                if d and n.lower() == f'{TITLE_09:08x}':
                    base = join(drive, 'UDATA', n)
            if not base:
                continue
            for n, d, _ in self.listdir(base) or []:
                if not d:
                    continue
                p = join(base, n)
                if n.lower().startswith('rost-'):
                    out.append(p)
                else:
                    out += [join(p, m) for m, sub, _ in self.listdir(p) or [] if sub and m.lower().startswith('rost-')]
        return out


# ---------------------------------------------------------------- the install plan

def read_manifest(text):
    m = {}
    for ln in (text or '').splitlines():
        parts = ln.split('\t')
        if len(parts) == 3 and parts[1].isdigit():
            m[parts[0]] = (int(parts[1]), parts[2])
    return m


def write_manifest(m):
    return ''.join(f'{k}\t{s}\t{h}\n' for k, (s, h) in sorted(m.items())).encode('utf8')


def plan(stock, overlay, hashes, remote_sizes, manifest):
    """What to upload so the target holds stock + overlay.

    Returns (want, send, remove): want {rel: (size, sha1, local path)}; send the paths that must go up
    (missing, wrong size, or not known from the manifest to be the same file); remove the files an
    earlier install put there that this one doesn't have (only ever files listed in the manifest).
    """
    files = tree_files(stock)
    # the build's reports (roster_report.csv, stats_report.csv) stay on the PC
    files.update({rel: p for rel, p in tree_files(overlay).items() if not (rel.endswith('.csv') and '/' not in rel)})
    want = {}
    for rel, p in files.items():
        want[rel] = (os.path.getsize(p), hashes.get(p), p)
    send = [rel for rel, (size, h, _) in sorted(want.items())
            if remote_sizes.get(rel.lower()) != size or manifest.get(rel) != (size, h)]
    remove = [rel for rel in manifest if rel not in want and rel != MANIFEST]
    return want, send, remove


def install_game(box, stock, overlay, target, say, busy, progress, cancel, confirm_replace):
    """Make target on the Xbox hold stock + overlay, sending only what isn't already there.

    The manifest is rewritten first without the files about to be sent, so a stopped install
    sends them again next time; it gets its final form once everything is checked.
    """
    busy('Looking at the Xbox folder')
    existing = box.listdir(target)
    remote = {rel.lower(): s for rel, s in box.walk(target)} if existing is not None else {}
    manifest = read_manifest((box.read(join(target, MANIFEST)) or b'').decode('utf8', 'replace'))
    if existing and not manifest and not confirm_replace(target):
        raise Cancelled()
    busy('Checking the files on this PC (the first time takes a minute)')
    hashes = HashCache(os.path.join(WORK, 'hashes.json'))
    want, send, remove = plan(stock, overlay, hashes, remote, manifest)
    hashes.save()
    keep = {k: v for k, v in manifest.items() if k in want and k not in send}
    box.mkdirs(target)
    box.write(join(target, MANIFEST), write_manifest(keep))
    total = sum(want[r][0] for r in send)
    say(f'{len(send)} of {len(want)} files to send, {nice(total)}.')
    done = [0, time.time()]

    def prog(n):
        done[0] += n
        if time.time() - done[1] > 0.3:
            done[1] = time.time()
            progress(done[0] / max(total, 1))
    made = set()
    for rel in send:
        size, h, local = want[rel]
        d = rel.rsplit('/', 1)[0] if '/' in rel else ''
        if d and d not in made:
            box.mkdirs(join(target, d))
            made.add(d)
        busy(f'Sending {rel} ({nice(size)})')
        for _ in range(3):
            start = done[0]
            box.upload(local, join(target, rel), prog, cancel)
            got = box.size(join(target, rel))
            if got == size:
                break
            done[0] = start
            say(f'  {rel}: {got} bytes on the Xbox instead of {size:,}, sending again')
        else:
            raise RuntimeError(f'{rel} would not upload completely. Check the Xbox has free space.')
        keep[rel] = (size, h)
        say(f'  ✔ {rel}  {size:,} bytes')
    for rel in remove:
        try:
            box.delete(join(target, rel))
            say(f'  removed {rel} (left from an earlier install)')
        except ftplib.Error:
            pass
    box.write(join(target, MANIFEST), write_manifest(keep))
    progress(1)
    return target, len(send), len(want)


# ---------------------------------------------------------------- downloads

def fetch(url, dest, cancel=None, tries=5):
    """Download url to dest unless it's there already; retried with a growing wait if the connection drops."""
    if os.path.isfile(dest) and os.path.getsize(dest) > 0:
        return False
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=120) as r, open(dest + '.part', 'wb') as out:
                while b := r.read(1 << 16):
                    if cancel and cancel.is_set():
                        raise Cancelled()
                    out.write(b)
            os.replace(dest + '.part', dest)
            return True
        except (OSError, http.client.HTTPException):
            if attempt == tries - 1:
                raise
            for _ in range(3 * 2 ** attempt):
                if cancel and cancel.is_set():
                    raise Cancelled()
                time.sleep(1)


def stats_files():
    return [('players.csv', NFLVERSE + 'players/players.csv')] + [
        (f'stats_player_reg_{y}.csv', NFLVERSE + f'stats_player/stats_player_reg_{y}.csv')
        for y in range(1999, LAST_SEASON + 1)]


# ---------------------------------------------------------------- the mods, in plain words

# key, section, label, explanation
MODS = [
    ('awareness', 'Fixes (recommended)', 'Awareness fix',
     "Stops players' awareness from collapsing over a franchise, the stock game's worst bug."),
    ('progression', 'Fixes (recommended)', 'Realistic player progression',
     'Players improve or decline by how they actually play. Fewer 99 overalls after a few seasons.'),
    ('career_room', 'Fixes (recommended)', 'Room for long franchises',
     'Career stats keep adding up past year 5 instead of stopping.'),
    ('demo_off', 'Fixes (recommended)', 'No attract demo',
     'The demo that starts on the title screen can freeze the console when you leave it (stock game too).'),
    ('season17', 'Modern NFL rules', '17-game season',
     '18 weeks with a bye, and a 3-game preseason, like today\'s NFL.'),
    ('playoffs7', 'Modern NFL rules', '7-team playoffs',
     'Seven teams per conference make the playoffs; only the top seed gets a bye.'),
    ('modern_kickoff', 'Modern NFL rules', 'Modern kickoff',
     'Kick from the 35, the new lineup, touchbacks to the 35, out of bounds to the 40.'),
    ('any_number', 'Modern NFL rules', 'Any jersey number',
     'Give any player any number in the edit screen. Free agents are no longer capped at 80 overall.'),
    ('roster', 'Today\'s rosters (downloads about 300 MB)', '2026 rosters with photos',
     "Every team's current players, ratings and headshots, the 2026 coaching staffs with photos, "
     'and today\'s team names.'),
    ('history', 'Today\'s rosters (downloads about 300 MB)', 'Real stats, schedule and years',
     "Players' real stats from the last 5 seasons with career totals, 2026's real schedule, and years "
     'counted from 2026. Coaches get their real histories.'),
    ('commanders_commentary', 'Today\'s rosters (downloads about 300 MB)', 'Al Michaels says "Washington"',
     'The announcers call the Commanders "Washington" (adds 447 MB).'),
    ('music', 'Sound', 'Soundtracks from Madden 2005 to 08',
     'All 154 songs from the older games, in the music menu as four extra soundtracks.'),
    ('radio_show', 'Sound', 'Tony Bruno radio show',
     "Madden 07's sports-radio show plays in the franchise menus, once a week, with your league's news."),
    ('save_unlock', 'Extras', 'Load edited saves',
     'Lets the game load franchise saves changed with PC tools. Leave it off unless you edit saves.'),
    ('optional_fullback', 'Extras', 'Teams without a fullback',
     'A team can carry no fullback; a tight end fills in. Partly tested.'),
]
RECOMMENDED = {'awareness', 'progression', 'career_room', 'demo_off', 'season17', 'playoffs7', 'modern_kickoff',
               'any_number', 'roster', 'history', 'commanders_commentary', 'music', 'radio_show'}


def unavailable(key, have, choice):
    """Why a mod can't be chosen right now, or None."""
    name = lambda tid: GAMES[tid][0].replace(' (USA)', '')
    if key == 'progression' and 0x4541004d not in have:
        return f'needs {name(0x4541004d)}'
    if key == 'music':
        miss = [name(t) for t in ORDER[1:] if t not in have]
        return 'needs ' + ', '.join(miss) if miss else None
    if key == 'radio_show' and 0x4541009f not in have:
        return f'needs {name(0x4541009f)}'
    if key in ('history', 'commanders_commentary') and not choice.get('roster'):
        return 'needs the 2026 rosters'
    if key == 'playoffs7' and not choice.get('season17'):
        return 'needs the 17-game season'
    return None


def build_values(choice, extras):
    """build_gui's dict of choices for build_all.py."""
    v = dict(bg.DEFAULTS, games=GAMES_DIR, out=OUT)
    for k in ('awareness', 'season17', 'playoffs7', 'modern_kickoff', 'any_number', 'optional_fullback',
              'save_unlock', 'career_room', 'demo_off', 'music', 'radio_show', 'commanders_commentary'):
        v[k] = bool(choice.get(k))
    v['commanders_commentary'] = v['commanders_commentary'] and bool(choice.get('roster'))
    v['progression'] = 'performance' if choice.get('progression') else 'stock'
    v['title'] = extras.get('title', '')
    v['loadscreen'] = extras.get('loadscreen', '')
    v['startscreen'] = extras.get('startscreen', '')
    if choice.get('roster'):
        v.update(roster=os.path.join(DL, 'ea_ratings.json'), photos=os.path.join(DL, 'headshots'),
                 coach_photos=os.path.join(DL, 'coach_photos'))
        if choice.get('history'):
            v.update(player_stats=os.path.join(DL, 'nflverse_stats'), schedule=os.path.join(DL, 'games.csv'),
                     year_on=True, year='2026')
    return v


# ---------------------------------------------------------------- finding games on this PC

SKIP_DIRS = {'windows', 'program files', 'program files (x86)', 'programdata', '$recycle.bin', 'appdata',
             'system volume information', 'recovery', 'perflogs', 'msocache', 'node_modules', '$windows.~bt',
             '$windows.~ws', 'windowsapps', 'installer_files'}


def find_local_games(extra=()):
    """[(folder, title ID)] for Madden folders on this PC: two levels into every drive, and into the
    Desktop, Downloads and Documents folders (C:\\Madden09, D:\\Games\\Madden NFL 09, ...)."""
    home = os.path.expanduser('~')
    starts = [f'{d}:\\' for d in 'CDEFGHIJKLMNOPQRSTUVWXYZ' if os.path.isdir(f'{d}:\\')]
    starts += [os.path.join(home, s) for s in ('Desktop', 'Downloads', 'Documents', 'OneDrive\\Desktop',
                                               'OneDrive\\Documents')]
    starts += list(extra)
    seen, found = set(), []
    work = os.path.normcase(os.path.abspath(WORK))

    def visit(d, depth):
        key = os.path.normcase(os.path.abspath(d))
        if key in seen or key.startswith(work):
            return
        seen.add(key)
        try:
            entries = list(os.scandir(d))
        except OSError:
            return
        if any(e.name.lower() == 'default.xbe' for e in entries):
            tid = local_game(d)
            if tid in GAMES:
                found.append((d, tid))
                return
        if depth:
            for e in entries:
                try:
                    if (e.is_dir(follow_symlinks=False) and not e.name.startswith(('.', '$'))
                            and e.name.lower() not in SKIP_DIRS):
                        visit(e.path, depth - 1)
                except OSError:
                    pass
    for s in starts:
        visit(s, 2)
    return found


def win_to_xbox(p):
    """'E:\\Games\\Madden NFL 09 Modded' -> '/E/Games/Madden NFL 09 Modded', or None."""
    m = re.fullmatch(r'([A-Za-z]):[\\/]*(.*)', p.strip().replace('/', '\\'))
    return join(m.group(1).upper(), *m.group(2).split('\\')) if m and m.group(2).strip('\\') else None


def xbox_to_win(p):
    parts = p.strip('/').split('/')
    return parts[0] + ':\\' + '\\'.join(parts[1:])


class LocalBox:
    """The Xbox class's file calls on a folder of this PC, so a modded copy here is made, checked and
    updated exactly like one on the Xbox. Paths look like '/C:/Games/Madden NFL 09 Modded'."""
    def _p(self, path):
        return path.lstrip('/').replace('/', os.sep)

    def listdir(self, path):
        try:
            return [(e.name, e.is_dir(), 0 if e.is_dir() else e.stat().st_size) for e in os.scandir(self._p(path))]
        except OSError:
            return None

    def walk(self, top):
        return [(rel, os.path.getsize(p)) for rel, p in tree_files(self._p(top)).items()]

    def read(self, path):
        try:
            return open(self._p(path), 'rb').read()
        except OSError:
            return None

    def write(self, path, data):
        open(self._p(path), 'wb').write(data)

    def mkdirs(self, path):
        os.makedirs(self._p(path), exist_ok=True)

    def size(self, path):
        try:
            return os.path.getsize(self._p(path))
        except OSError:
            return None

    def delete(self, path):
        os.remove(self._p(path))

    def upload(self, local, path, progress=None, cancel=None):
        with open(local, 'rb') as src, open(self._p(path), 'wb') as out:
            while b := src.read(1 << 20):
                if cancel and cancel.is_set():
                    raise Cancelled()
                out.write(b)
                progress and progress(len(b))


def needed_games(choice):
    """The older games the chosen mods read (the others needn't be copied)."""
    need = {TITLE_09}
    if choice.get('progression') or choice.get('music'):
        need.add(0x4541004d)
    if choice.get('radio_show') or choice.get('music'):
        need.add(0x4541009f)
    if choice.get('music'):
        need |= {0x45410075, 0x454100ac}
    return need


# ---------------------------------------------------------------- the window

def gui():
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    os.makedirs(WORK, exist_ok=True)
    try:
        cfg = json.load(open(SETTINGS, encoding='utf8'))
    except (OSError, ValueError):
        cfg = {}
    cfg.setdefault('host', '')
    cfg.setdefault('user', 'xbox')
    cfg.setdefault('password', 'xbox')
    cfg.setdefault('where', 'pc')
    cfg.setdefault('pc_games', {})
    cfg.setdefault('choice', {k: k in RECOMMENDED for k, *_ in MODS})
    cfg.setdefault('extras', {'title': 'Madden NFL 09 Modded', 'loadscreen': '', 'startscreen': ''})
    cfg.setdefault('dest', '')
    cfg.setdefault('xbox_target', 'E:\\Games\\Madden NFL 09 Modded')
    cfg.setdefault('pc_target', '')

    def save():
        try:
            json.dump(cfg, open(SETTINGS, 'w', encoding='utf8'), indent=1)
        except OSError:
            pass

    root = tk.Tk()
    root.title('Madden NFL 09 mod installer')
    root.minsize(960, 680)
    style = ttk.Style()
    style.configure('H.TLabel', font=('Segoe UI', 18, 'bold'))
    style.configure('Sub.TLabel', font=('Segoe UI', 10), foreground='#444')
    style.configure('Step.TLabel', font=('Segoe UI', 12), foreground='#888', padding=(14, 8))
    style.configure('StepOn.TLabel', font=('Segoe UI', 12, 'bold'), foreground='#0b5394', padding=(14, 8))
    style.configure('Big.TButton', font=('Segoe UI', 11), padding=(14, 6))
    style.configure('Huge.TButton', font=('Segoe UI', 14, 'bold'), padding=(24, 10))
    style.configure('Sec.TLabel', font=('Segoe UI', 11, 'bold'))
    style.configure('Opt.TRadiobutton', font=('Segoe UI', 11, 'bold'))
    style.configure('Why.TLabel', foreground='#666')
    style.configure('Bad.TLabel', foreground='#b00020')
    style.configure('Good.TLabel', foreground='#1b7d1b')
    style.configure('Profit.TLabel', font=('Segoe UI', 12))

    # where each game comes from: {tid: ('pc', folder) or ('xbox', path on the Xbox)}
    src = {}
    xbox = {'box': None, 'found': []}
    events, replies = queue.Queue(), queue.Queue()
    task = {'cancel': None, 'busy': False}
    result = {}

    def run_task(fn, done):
        if task['busy']:
            return False
        task['busy'] = True
        task['cancel'] = threading.Event()
        for b_ in (back_btn, next_btn):
            b_.configure(state='disabled')

        def body():
            try:
                events.put(('done', done, fn(task['cancel']), None))
            except Cancelled:
                events.put(('done', done, None, 'Stopped.'))
            except Exception as e:  # shown to the user, never swallowed
                events.put(('done', done, None, f'{type(e).__name__}: {e}'))
        threading.Thread(target=body, daemon=True).start()
        return True

    def post(*ev):
        events.put(ev)

    def ask(kind, *a):
        """A yes/no question from a worker thread, answered by the window."""
        post('ask', kind, *a)
        return replies.get()

    # -- layout: steps on the left, the page on the right, Back/Next at the bottom
    side = ttk.Frame(root, padding=(0, 20))
    side.pack(side='left', fill='y')
    ttk.Separator(root, orient='vertical').pack(side='left', fill='y')
    main = ttk.Frame(root, padding=(24, 16, 24, 10))
    main.pack(side='left', fill='both', expand=True)
    pages_frame = ttk.Frame(main)
    pages_frame.pack(fill='both', expand=True)
    pages_frame.rowconfigure(0, weight=1)
    pages_frame.columnconfigure(0, weight=1)
    nav = ttk.Frame(main)
    nav.pack(fill='x', pady=(8, 0))
    back_btn = ttk.Button(nav, text='< Back', style='Big.TButton')
    back_btn.pack(side='left')
    next_btn = ttk.Button(nav, text='Next >', style='Big.TButton')
    next_btn.pack(side='right')

    STEPS = ['1. Where is your Madden?', '2. What mods?', '3. Mod it', '4. Profit!']
    step_lbls = [ttk.Label(side, text=s, style='Step.TLabel', width=24) for s in STEPS]
    for l_ in step_lbls:
        l_.pack(anchor='w')
    pages = []

    def page(title, sub):
        f = ttk.Frame(pages_frame)
        f.grid(row=0, column=0, sticky='nsew')
        ttk.Label(f, text=title, style='H.TLabel').pack(anchor='w')
        if sub:
            ttk.Label(f, text=sub, style='Sub.TLabel', wraplength=660, justify='left').pack(anchor='w', pady=(4, 10))
        body = ttk.Frame(f)
        body.pack(fill='both', expand=True)
        pages.append(f)
        return body

    def label(parent, text='', style='Why.TLabel', **kw):
        l_ = ttk.Label(parent, text=text, style=style, wraplength=kw.pop('wrap', 640), justify='left')
        l_.pack(anchor='w', **kw)
        return l_

    def log_box(parent, height=10):
        fr = ttk.Frame(parent)
        fr.pack(fill='both', expand=True, pady=(6, 0))
        t = tk.Text(fr, height=height, wrap='word', font=('Consolas', 9), state='disabled', relief='flat',
                    background='#f6f6f6')
        sb_ = ttk.Scrollbar(fr, command=t.yview)
        t.configure(yscrollcommand=sb_.set)
        sb_.pack(side='right', fill='y')
        t.pack(side='left', fill='both', expand=True)

        def say(line='', clear=False):
            t.configure(state='normal')
            if clear:
                t.delete('1.0', 'end')
            t.insert('end', line + '\n')
            t.see('end')
            t.configure(state='disabled')
        return say

    host_v = tk.StringVar(value=cfg['host'])
    user_v = tk.StringVar(value=cfg['user'])
    pass_v = tk.StringVar(value=cfg['password'])
    conn_status = []          # labels that show the connection, on pages 1 and 3

    def xbox_form(parent, button_text):
        f = ttk.Frame(parent)
        f.pack(anchor='w', padx=28, pady=(2, 0))
        ttk.Label(f, text='Xbox IP address').grid(row=0, column=0, sticky='w')
        ttk.Entry(f, textvariable=host_v, width=16).grid(row=0, column=1, padx=(6, 14))
        ttk.Label(f, text='user').grid(row=0, column=2)
        ttk.Entry(f, textvariable=user_v, width=8).grid(row=0, column=3, padx=(6, 14))
        ttk.Label(f, text='password').grid(row=0, column=4)
        ttk.Entry(f, textvariable=pass_v, width=8, show='*').grid(row=0, column=5, padx=(6, 14))
        ttk.Button(f, text=button_text, command=lambda: connect()).grid(row=0, column=6)
        st = ttk.Label(parent, text='', style='Why.TLabel', wraplength=640, justify='left')
        st.pack(anchor='w', padx=28)
        conn_status.append(st)
        return f

    def set_conn(text, style='Why.TLabel'):
        for st in conn_status:
            st.configure(text=text, style=style)

    # ================= page 1: where is your Madden?
    b = page('Where is your Madden?', 'Madden NFL 09 has to be the original game, copied off the disc as a folder '
             '(it holds default.xbe and a data folder). The mods go into a new copy; your original is never changed.')
    where_v = tk.StringVar(value=cfg['where'])
    ttk.Radiobutton(b, text='On this PC', value='pc', variable=where_v, style='Opt.TRadiobutton',
                    command=lambda: refresh_where()).pack(anchor='w', pady=(4, 0))
    pcf = ttk.Frame(b)
    pcf.pack(anchor='w', padx=28, fill='x')
    pc09_lbl = ttk.Label(pcf, text='', wraplength=520, justify='left')
    pc09_lbl.pack(side='left')
    ttk.Button(pcf, text='Browse...', command=lambda: browse_game(TITLE_09)).pack(side='left', padx=10)
    pc_scan_lbl = label(b, 'Looking for Madden on this PC...', padx=28)
    pc_pick = ttk.Frame(b)
    pc_pick.pack(anchor='w', padx=28)
    ttk.Radiobutton(b, text="On my Xbox's hard drive", value='xbox', variable=where_v, style='Opt.TRadiobutton',
                    command=lambda: refresh_where()).pack(anchor='w', pady=(12, 0))
    label(b, 'Turn on the Xbox and leave it on its dashboard (UnleashX, Avalaunch, XBMC). The dashboard shows its '
          'IP address. User and password are usually xbox and xbox. The game is copied to this PC when you mod it.',
          padx=28)
    xbox_form(b, 'Find my games')
    ttk.Separator(b).pack(fill='x', pady=12)
    label(b, 'Got other Maddens? (optional)', 'Sec.TLabel')
    label(b, 'Madden 2005, 06, 07 and 08 unlock extra mods: all their music, the Tony Bruno radio show (07) and '
          'realistic progression (2005). They can be on this PC or the Xbox.')
    older = ttk.Frame(b)
    older.pack(anchor='w', fill='x', pady=(4, 0))
    older_lbl = {}
    for r, tid in enumerate(ORDER[1:]):
        ttk.Label(older, text=GAMES[tid][0].replace(' (USA)', ''), width=16).grid(row=r, column=0, sticky='w')
        older_lbl[tid] = ttk.Label(older, text='', wraplength=460, justify='left')
        older_lbl[tid].grid(row=r, column=1, sticky='w', padx=6)
        ttk.Button(older, text='Browse...', width=10, command=lambda t=tid: browse_game(t)).grid(
            row=r, column=2, sticky='e', pady=1)
    older.columnconfigure(1, weight=1)

    def describe(tid):
        s = src.get(tid)
        if not s:
            return 'not found'
        return s[1] if s[0] == 'pc' else 'on the Xbox, ' + xbox_to_win(s[1])

    def use_pc_game(path, tid, quiet=False):
        """Check a folder on this PC and use it for that game. True if it's usable."""
        if tid == TITLE_09:
            if sha1_file(os.path.join(path, 'default.xbe')) != STOCK_09_SHA1:
                if not quiet:
                    messagebox.showerror('Madden NFL 09', f'{path}\nhas been modded already (its default.xbe is '
                                         'not the original). Choose the untouched game.')
                return False
        src[tid] = ('pc', os.path.normpath(path))
        cfg['pc_games'][str(tid)] = src[tid][1]
        if tid == TITLE_09:
            where_v.set('pc')
        return True

    def browse_game(tid):
        s = src.get(tid)
        p = filedialog.askdirectory(title=f'Choose the {GAMES[tid][0]} folder (it holds default.xbe)',
                                    initialdir=s[1] if s and s[0] == 'pc' else 'C:\\')
        if not p:
            return
        got = local_game(p)
        if got != tid:
            # maybe they chose the folder above it (C:\Games): look one level down
            inside = [(d, t) for d, t in find_local_games(extra=[p]) if t == tid and
                      os.path.normcase(d).startswith(os.path.normcase(os.path.abspath(p)))]
            if inside:
                p = inside[0][0]
            else:
                messagebox.showerror('Not found', f'{GAMES[tid][0]} is not in\n{p}\n\nChoose the folder that holds '
                                     'its default.xbe and data folder.' if not got else
                                     f'{p}\nis {GAMES[got][0]}, not {GAMES[tid][0]}.')
                return
        use_pc_game(p, tid)
        refresh_where()
        save()

    def refresh_where():
        cfg['where'] = where_v.get()
        s = src.get(TITLE_09)
        pc09_lbl.configure(text=('\u2714 ' + s[1]) if s and s[0] == 'pc' else 'Not chosen yet',
                           style='Good.TLabel' if s and s[0] == 'pc' else 'TLabel')
        if where_v.get() == 'xbox':
            g = xbox_copy_of(TITLE_09)
            if g:
                src[TITLE_09] = ('xbox', g['path'])
            elif s and s[0] == 'pc':
                del src[TITLE_09]
        elif s and s[0] == 'xbox':
            p = cfg['pc_games'].get(str(TITLE_09))
            if p and local_game(p) == TITLE_09:
                src[TITLE_09] = ('pc', p)
            else:
                del src[TITLE_09]
        for tid, l_ in older_lbl.items():
            ok = tid in src
            l_.configure(text=('\u2714 ' if ok else '') + describe(tid), style='Good.TLabel' if ok else 'Why.TLabel')

    def scanned(found, err):
        for w in pc_pick.winfo_children():
            w.destroy()
        if err:
            pc_scan_lbl.configure(text='')
            return
        stock = []
        for d, tid in found:
            if tid == TITLE_09:
                if sha1_file(os.path.join(d, 'default.xbe')) == STOCK_09_SHA1:
                    stock.append(d)
            elif tid not in src:
                src[tid] = ('pc', d)
        if not stock:
            pc_scan_lbl.configure(text='No original Madden NFL 09 found on the drives, Desktop, Downloads or '
                                  'Documents. Press Browse to choose its folder.')
        else:
            pc_scan_lbl.configure(text='Found on this PC:' if len(stock) > 1 or TITLE_09 in src else
                                  'Found on this PC, and chosen:')
            for d in stock:
                ttk.Button(pc_pick, text='Use ' + d, command=lambda d=d: (use_pc_game(d, TITLE_09), refresh_where(),
                                                                         save())).pack(anchor='w', pady=1)
            if TITLE_09 not in src and len(stock) == 1 and where_v.get() == 'pc':
                use_pc_game(stock[0], TITLE_09)
        refresh_where()

    def xbox_copy_of(tid):
        cand = [g for g in xbox['found'] if g['tid'] == tid and not g['ours']]
        if tid == TITLE_09:     # the original, not an earlier modded copy
            cand.sort(key=lambda g: g['title'] != 'Madden NFL 09')
        return cand[0] if cand else None

    def connect():
        host = host_v.get().strip()
        if not re.fullmatch(r'[\w.\-]+', host):
            messagebox.showerror('Xbox IP address', 'Type the IP address the Xbox dashboard shows, such as '
                                 '192.168.1.20.')
            return
        cfg.update(host=host, user=user_v.get().strip() or 'xbox', password=pass_v.get())
        save()
        set_conn(f'Connecting to {host}...')

        def work(cancel):
            box = Xbox(host, cfg['user'], cfg['password'])
            box.connect()
            found = box.find_games(lambda s: post('conn', s), quick=True)
            if not any(g['tid'] == TITLE_09 and not g['ours'] for g in found):
                post('conn', 'No folder named Madden or NFL holds Madden NFL 09: checking every game '
                     '(a couple of minutes)...')
                found = box.find_games(lambda s: post('conn', s))
            return box, found
        if not run_task(work, connected):
            set_conn('Busy: wait for the current job to finish.')

    def connected(r, err):
        if err:
            set_conn(f'Could not connect ({err}). Check the IP address, that the Xbox is on its dashboard, and '
                     'the user and password. Some dashboards need FTP turned on in their settings.', 'Bad.TLabel')
            return
        box, found = r
        xbox.update(box=box, found=found)
        mine = [g for g in found if not g['ours']]
        if not mine:
            set_conn('Connected, but no Madden games were found on the hard drive.', 'Good.TLabel')
        else:
            set_conn('Connected. Found: ' + '; '.join(f"{g['title']} in {xbox_to_win(g['path'])}" for g in mine),
                     'Good.TLabel')
        for tid in ORDER[1:]:
            g = xbox_copy_of(tid)
            if g and tid not in src:
                src[tid] = ('xbox', g['path'])
        g = xbox_copy_of(TITLE_09)
        if g:
            if TITLE_09 not in src or where_v.get() == 'xbox':
                where_v.set('xbox')
                src[TITLE_09] = ('xbox', g['path'])
            # a new folder beside the original, never one holding a game the installer didn't make
            taken = {x['path'].lower() for x in found if not x['ours']}
            cur_t = (win_to_xbox(xtarget_v.get()) or '').lower()
            if cur_t in taken or xtarget_v.get() == 'E:\\Games\\Madden NFL 09 Modded':
                parent = g['path'].rsplit('/', 1)[0]
                for n in ['Madden NFL 09 Modded'] + [f'Madden NFL 09 Installer{"" if i == 1 else " " + str(i)}'
                                                     for i in range(1, 20)]:
                    if join(parent, n).lower() not in taken:
                        xtarget_v.set(xbox_to_win(join(parent, n)))
                        break
        if not cfg['dest']:
            dest_v.set('xbox')
        refresh_where()
        refresh_dest()

    # ================= page 2: mods
    b = page('What mods do you want?', 'The recommended ones are ticked. A greyed-out mod says what it needs. You can '
             'come back, change your mind and mod again at any time.')
    canvas = tk.Canvas(b, highlightthickness=0)
    sb = ttk.Scrollbar(b, command=canvas.yview)
    inner = ttk.Frame(canvas)
    inner.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
    canvas.create_window((0, 0), window=inner, anchor='nw')
    canvas.configure(yscrollcommand=sb.set)
    sb.pack(side='right', fill='y')
    canvas.pack(side='left', fill='both', expand=True)
    canvas.bind_all('<MouseWheel>', lambda e: canvas.yview_scroll(-e.delta // 120, 'units')
                    if cur['i'] == 1 else None)
    mod_var, mod_w, section = {}, {}, None
    for key, sec, text, why in MODS:
        if sec != section:
            section = sec
            ttk.Label(inner, text=sec, style='Sec.TLabel').pack(anchor='w', pady=(10, 2))
        mod_var[key] = tk.BooleanVar(value=cfg['choice'].get(key, False))
        cb = ttk.Checkbutton(inner, text=text, variable=mod_var[key], command=lambda: refresh_mods())
        cb.pack(anchor='w', padx=8)
        lbl = ttk.Label(inner, text=why, style='Why.TLabel', wraplength=600, justify='left')
        lbl.pack(anchor='w', padx=32)
        mod_w[key] = (cb, lbl, why)
    ttk.Label(inner, text='Look', style='Sec.TLabel').pack(anchor='w', pady=(10, 2))
    ex_var = {k: tk.StringVar(value=cfg['extras'].get(k, '')) for k in ('title', 'loadscreen', 'startscreen')}
    f = ttk.Frame(inner)
    f.pack(anchor='w', padx=8, fill='x')
    ttk.Label(f, text='Name on the dashboard').grid(row=0, column=0, sticky='w', pady=2)
    ttk.Entry(f, textvariable=ex_var['title'], width=40).grid(row=0, column=1, sticky='w', padx=6)
    for r, (k, text) in enumerate((('loadscreen', 'Loading screen picture'), ('startscreen', 'Start screen picture')),
                                  1):
        ttk.Label(f, text=text).grid(row=r, column=0, sticky='w', pady=2)
        ttk.Entry(f, textvariable=ex_var[k], width=40).grid(row=r, column=1, sticky='w', padx=6)
        ttk.Button(f, text='Browse', width=7, command=lambda k=k: ex_var[k].set(os.path.normpath(p)) if (
            p := filedialog.askopenfilename(filetypes=[('PNG picture', '*.png')])) else None).grid(row=r, column=2)
        ttk.Button(f, text='Clear', width=6, command=lambda k=k: ex_var[k].set('')).grid(row=r, column=3, padx=2)
    ttk.Label(inner, text='Pictures are optional: a 640x480 PNG. Leave them empty to keep the stock screens.',
              style='Why.TLabel').pack(anchor='w', padx=32)

    def choice():
        return {k: v.get() for k, v in mod_var.items()}

    def refresh_mods():
        have, c = set(src), choice()
        for key, (cb_, lbl_, why) in mod_w.items():
            reason = unavailable(key, have, c)
            cb_.configure(state='disabled' if reason else 'normal')
            lbl_.configure(text=f'{why}  ({reason})' if reason else why)
        cfg['choice'] = c
        cfg['extras'] = {k: v.get() for k, v in ex_var.items()}

    def effective_choice():
        have, c = set(src), choice()
        for _ in range(2):          # "history" depends on "roster", "playoffs7" on "season17"
            c = {k: v and not unavailable(k, have, c) for k, v in c.items()}
        return c

    # ================= page 3: mod it
    b = page('Mod it', None)
    label(b, 'Where should the modded game go?', 'Sec.TLabel', pady=(2, 2))
    dest_v = tk.StringVar(value=cfg['dest'] or 'pc')
    xtarget_v = tk.StringVar(value=cfg['xbox_target'])
    ptarget_v = tk.StringVar(value=cfg['pc_target'])
    ttk.Radiobutton(b, text='Onto my Xbox', value='xbox', variable=dest_v, style='Opt.TRadiobutton',
                    command=lambda: refresh_dest()).pack(anchor='w', pady=(4, 0))
    xf = ttk.Frame(b)
    xf.pack(anchor='w', padx=28)
    ttk.Label(xf, text='New folder on the Xbox').pack(side='left')
    ttk.Entry(xf, textvariable=xtarget_v, width=44).pack(side='left', padx=6)
    xbox_form(b, 'Connect')
    ttk.Radiobutton(b, text='Into a folder on this PC', value='pc', variable=dest_v, style='Opt.TRadiobutton',
                    command=lambda: refresh_dest()).pack(anchor='w', pady=(10, 0))
    pf = ttk.Frame(b)
    pf.pack(anchor='w', padx=28)
    ttk.Label(pf, text='New folder').pack(side='left')
    ttk.Entry(pf, textvariable=ptarget_v, width=50).pack(side='left', padx=6)
    ttk.Button(pf, text='Browse...', command=lambda: ptarget_v.set(os.path.normpath(p)) if (
        p := filedialog.askdirectory(title='Folder for the modded game')) else None).pack(side='left')
    label(b, 'For xemu, or to copy to the Xbox yourself later.', padx=28)
    go = ttk.Frame(b)
    go.pack(fill='x', pady=(14, 4))
    go_btn = ttk.Button(go, text='Mod my game!', style='Huge.TButton', command=lambda: mod_it())
    go_btn.pack(side='left')
    stop_btn = ttk.Button(go, text='Stop', state='disabled', command=lambda: task['cancel'] and task['cancel'].set())
    stop_btn.pack(side='left', padx=10)
    status = ttk.Label(go, text='', style='Sec.TLabel', wraplength=460)
    status.pack(side='left', padx=6)
    bar = ttk.Progressbar(b, mode='determinate', maximum=1000)
    bar.pack(fill='x', pady=(4, 0))
    label(b, 'The first time takes 15 to 45 minutes: downloads, the build, and copying about 2 GB. After that, only '
          'what changed. You can stop and start again; finished parts are kept.', pady=(4, 0))
    say = log_box(b, 9)

    def refresh_dest():
        cfg['dest'] = dest_v.get()
        if not ptarget_v.get():
            s = src.get(TITLE_09)
            base = os.path.dirname(s[1]) if s and s[0] == 'pc' else os.path.join(os.path.expanduser('~'), 'Desktop')
            ptarget_v.set(os.path.join(base, 'Madden NFL 09 Modded'))

    def check_targets():
        """The destination, as (kind, path for the box), or None after telling the user what's wrong."""
        if dest_v.get() == 'xbox':
            if not xbox['box']:
                messagebox.showerror('Xbox', 'Connect to the Xbox first (type its IP address and press Connect).')
                return None
            t = win_to_xbox(xtarget_v.get())
            if not t or not re.fullmatch(r'[A-Za-z0-9 ()._\-/]{3,120}', t) or len(t.rsplit('/', 1)[1]) > 42:
                messagebox.showerror('Folder on the Xbox', 'Type a folder such as E:\\Games\\Madden NFL 09 Modded '
                                     '(letters, digits, spaces and ( ) . _ - ; the last part up to 42 characters).')
                return None
            if t.count('/') < 2 or t.split('/')[1].upper() in ('C', 'D', 'X', 'Y', 'Z'):
                messagebox.showerror('Folder on the Xbox', 'Put it in a folder on E:, F: or G:, such as '
                                     'E:\\Games\\Madden NFL 09 Modded.')
                return None
            if any(g['path'].lower() == t.lower() and not g['ours'] for g in xbox['found']):
                messagebox.showerror('Folder on the Xbox', 'That folder holds a Madden game this installer didn\'t '
                                     'make (your original, or a modded copy of your own). Choose a new folder so '
                                     'it stays as it is.')
                return None
            return 'xbox', t
        t = ptarget_v.get().strip()
        if not t or not os.path.isabs(t) or os.path.dirname(os.path.abspath(t)) == os.path.abspath(t):
            messagebox.showerror('Folder', 'Choose a folder for the modded game, such as C:\\Madden NFL 09 Modded.')
            return None
        tn = os.path.normcase(os.path.realpath(t))
        for tid, s in src.items():
            if s[0] == 'pc':
                g = os.path.normcase(os.path.realpath(s[1]))
                if tn == g or tn.startswith(g + os.sep) or g.startswith(tn + os.sep):
                    messagebox.showerror('Folder', 'The modded game needs its own folder, apart from the original '
                                         f'games.\n\n{t}\noverlaps\n{s[1]}')
                    return None
        if tn.startswith(os.path.normcase(os.path.realpath(WORK))):
            messagebox.showerror('Folder', 'Choose a folder outside the installer\'s own files.')
            return None
        return 'pc', '/' + os.path.abspath(t).replace(os.sep, '/')

    def mod_it():
        refresh_mods()
        c = effective_choice()
        ex = {k: v.get().strip() for k, v in ex_var.items()}
        if TITLE_09 not in src:
            messagebox.showerror('Madden NFL 09', 'Go back to step 1 and choose where Madden NFL 09 is.')
            return
        for k in ('loadscreen', 'startscreen'):
            if ex[k] and not os.path.isfile(ex[k]):
                messagebox.showerror('Picture', f'{ex[k]} not found. Clear it or choose another (step 2).')
                return
        if len(ex['title']) > 40:
            messagebox.showerror('Name', 'The dashboard name is limited to 40 characters (step 2).')
            return
        dest = check_targets()
        if not dest:
            return
        cfg.update(xbox_target=xtarget_v.get(), pc_target=ptarget_v.get())
        if any(src[t][0] == 'xbox' for t in needed_games(c) if t in src) and not xbox['box']:
            messagebox.showerror('Xbox', 'Some games are on the Xbox: connect to it first (step 1).')
            return
        v = build_values(c, ex)
        say('', clear=True)
        save()
        go_btn.configure(state='disabled')
        stop_btn.configure(state='normal')

        def child(cancel, args, text):
            post('status', text, None)
            env = dict(os.environ, PYTHONUNBUFFERED='1', PYTHONIOENCODING='utf8')
            p = subprocess.Popen([sys.executable, '-u', *args], cwd=ROOT, env=env, stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT, text=True, encoding='utf8', errors='replace',
                                 stdin=subprocess.DEVNULL, creationflags=NO_WINDOW)
            threading.Thread(target=lambda: (cancel.wait(), p.poll() is None and subprocess.run(
                ['taskkill', '/F', '/T', '/PID', str(p.pid)], capture_output=True, creationflags=NO_WINDOW)),
                daemon=True).start()
            for line in p.stdout:
                post('say', line.rstrip('\n'))
                if line.startswith('>'):
                    post('status', text + ': ' + line[1:].strip()[:50], None)
            code = p.wait()
            if cancel.is_set():
                raise Cancelled()
            if code:
                raise RuntimeError(f'{text} failed (code {code}). The lines above say why.')

        def work(cancel):
            # 1. the games, on this PC
            for tid in ORDER:
                if tid not in needed_games(c) or tid not in src:
                    continue
                kind, path = src[tid]
                name = GAMES[tid][0]
                dest_dir = os.path.join(GAMES_DIR, name)
                if kind == 'pc':
                    link_game(path, name)
                    continue
                if is_link(dest_dir):
                    os.rmdir(dest_dir)
                box = xbox['box']
                files = box.walk(path)
                total = sum(s_ for _, s_ in files)
                done = [0, 0.0]
                post('say', f'Copying {name} from the Xbox: {len(files)} files, {nice(total)}')

                def prog(n):
                    done[0] += n
                    if time.time() - done[1] > 0.3:
                        done[1] = time.time()
                        post('status', f'Copying {name.replace(" (USA)", "")} from the Xbox: {nice(done[0])} of '
                             f'{nice(total)}', done[0] / max(total, 1))
                for rel, size in files:
                    local = os.path.join(dest_dir, *rel.split('/'))
                    if os.path.isfile(local) and os.path.getsize(local) == size:
                        done[0] += size
                        continue
                    box.download(join(path, rel), local, prog, cancel)
                    if os.path.getsize(local) != size:
                        raise RuntimeError(f'{rel} came over short. Press Mod my game! again.')
                if tid == TITLE_09 and sha1_file(os.path.join(dest_dir, 'default.xbe')) != STOCK_09_SHA1:
                    raise RuntimeError('The Madden NFL 09 on the Xbox has been modded already (its default.xbe is '
                                       'not the original). Copy the original game to the Xbox first.')
            # 2. downloads
            if c.get('roster'):
                ratings = os.path.join(DL, 'ea_ratings.json')
                os.makedirs(DL, exist_ok=True)
                if not os.path.isfile(ratings):
                    child(cancel, [os.path.join(ROOT, 'roster', 'fetch_ea_ratings.py'), ratings],
                          'Downloading the 2026 ratings from EA')
                child(cancel, [os.path.join(ROOT, 'roster', 'fetch_headshots.py'), ratings,
                               os.path.join(DL, 'headshots')], 'Downloading player photos')
                child(cancel, [os.path.join(ROOT, 'roster', 'fetch_coach_photos.py'),
                               os.path.join(DL, 'coach_photos')], 'Downloading coach photos')
                if c.get('history'):
                    todo = stats_files()
                    for i, (name, url) in enumerate(todo, 1):
                        post('status', f'Downloading real stats ({i} of {len(todo)})', i / len(todo))
                        if fetch(url, os.path.join(DL, 'nflverse_stats', name), cancel):
                            post('say', 'downloaded ' + name)
                    post('status', 'Downloading the schedule', None)
                    fetch(SCHEDULE_URL, os.path.join(DL, 'games.csv'), cancel)
            # 3. the build
            bad = bg.problems(v)
            if bad:
                raise RuntimeError('\n'.join(bad))
            if os.path.isdir(OUT):
                shutil.rmtree(OUT)      # build_all.py builds on files it finds in its output folder
            args = bg.command(v)
            post('say', '\npython tools/build_all.py ' + subprocess.list2cmdline(args) + '\n')
            for n in bg.notes(v):
                post('say', n)
            child(cancel, [os.path.join(ROOT, 'tools', 'build_all.py'), *args], 'Building')
            # 4. the install
            box = xbox['box'] if dest[0] == 'xbox' else LocalBox()
            where = 'the Xbox' if dest[0] == 'xbox' else 'the new folder'
            r = install_game(box, os.path.join(GAMES_DIR, GAMES[TITLE_09][0]), OUT, dest[1],
                             lambda m: post('say', m), lambda m: post('status', m.replace('Sending', 'Copying to ' +
                                                                                           where + ':'), None),
                             lambda x: post('status', None, x), cancel,
                             lambda t: ask('replace', xbox_to_win(t) if dest[0] == 'xbox' else t.lstrip('/')))
            saves = xbox['box'].roster_saves() if dest[0] == 'xbox' else []
            return dict(kind=dest[0], target=dest[1], sent=r[1], total=r[2], saves=saves, title=ex['title'])
        run_task(work, modded)

    def modded(r, err):
        go_btn.configure(state='normal')
        stop_btn.configure(state='disabled')
        if err:
            say('\n' + err)
            status.configure(text='Not finished. ' + ('' if err == 'Stopped.' else 'See the last lines below.'),
                             style='Bad.TLabel')
            return
        status.configure(text='\u2714 Done!', style='Good.TLabel')
        bar['value'] = 1000
        result.clear()
        result.update(r)
        show_profit()
        show(3)

    # ================= page 4: profit
    b = page('Profit!', None)
    profit_lbl = ttk.Label(b, text='', style='Profit.TLabel', wraplength=660, justify='left')
    profit_lbl.pack(anchor='w', pady=(4, 10))
    pb = ttk.Frame(b)
    pb.pack(anchor='w')
    open_btn = ttk.Button(pb, text='Open the folder', command=lambda: os.startfile(os.path.normpath(result['target'].lstrip('/'))))
    saves_btn = ttk.Button(pb, text='Move the roster saves to this PC', command=lambda: remove_saves())
    profit_say = log_box(b, 8)

    def show_profit():
        r = result
        name = r['title'] or 'Madden NFL 09'
        if r['kind'] == 'xbox':
            where = xbox_to_win(r['target'])
            text = (f'Your modded Madden is on the Xbox in {where}.\n\n'
                    f'\u2022  On the Xbox, find "{name}" in the dashboard\'s game list (refresh the list or '
                    'restart the dashboard if it isn\'t there yet).\n'
                    '\u2022  Start a NEW franchise. A franchise started on the original game, or on an older '
                    'build, needs that game.\n'
                    '\u2022  Your original game is still in its own folder, unchanged.')
        else:
            where = r['target'].lstrip('/').replace('/', '\\')
            text = (f'Your modded Madden is in {where}.\n\n'
                    '\u2022  For xemu: make it into a disc image (tools/make_xiso.py) or load it as you load the '
                    'original.\n'
                    '\u2022  For the Xbox: copy the whole folder to E:\\Games with FTP, in binary mode, and check the '
                    'sizes. Or run this installer again with "Onto my Xbox", which does that for you.\n'
                    '\u2022  Start a NEW franchise. A franchise started on the original game needs that game.')
        text += f'\n\n{r["sent"]} of {r["total"]} files copied this time; every file was checked.'
        profit_lbl.configure(text=text)
        open_btn.pack_forget()
        saves_btn.pack_forget()
        profit_say('', clear=True)
        if r['kind'] == 'pc':
            open_btn.pack(side='left')
        elif r['saves']:
            profit_say('One more thing: these roster saves on the Xbox would load old rosters instead of the new ones:')
            for p in r['saves']:
                profit_say('    ' + xbox_to_win(p))
            profit_say('Press the button to copy them to this PC and remove them from the Xbox. Franchise saves '
                       'are not touched. (A roster saved on a memory card wins too: take the card out.)')
            saves_btn.pack(side='left')
        else:
            profit_say('No roster saves on the Xbox\'s hard drive, so the new rosters will show. (A roster saved on '
                       'a memory card would still win: take the card out.)')

    def remove_saves():
        found = result.get('saves') or []
        if not found or not messagebox.askyesno('Roster saves', 'Copy these to this PC and remove them from the '
                                                'Xbox?\n\n' + '\n'.join(map(xbox_to_win, found))):
            return
        dest = os.path.join(BACKUPS, time.strftime('%Y%m%d-%H%M%S'))

        def work(cancel):
            box = xbox['box']
            for p in found:
                for rel, size in box.walk(p):
                    local = os.path.join(dest, p.strip('/').replace('/', os.sep), *rel.split('/'))
                    box.download(join(p, rel), local, None, cancel)
                    if os.path.getsize(local) != size:
                        raise RuntimeError(f'the copy of {p} came over short; nothing was removed')
            for p in found:
                box.delete_tree(p)
            return dest

        def done(d, err):
            if err:
                profit_say('Could not move them: ' + err)
            else:
                profit_say(f'\u2714 Copied to {d} and removed from the Xbox.')
                result['saves'] = []
                saves_btn.pack_forget()
        run_task(work, done)

    # ---------------- events and navigation
    def poll():
        try:
            while True:
                ev = events.get_nowait()
                if ev[0] == 'done':
                    task['busy'] = False
                    update_nav()
                    ev[1](ev[2], ev[3])
                elif ev[0] == 'call':
                    ev[1](ev[2], ev[3])
                elif ev[0] == 'say':
                    say(ev[1])
                elif ev[0] == 'conn':
                    set_conn(ev[1])
                elif ev[0] == 'status':
                    if ev[1] is not None:
                        status.configure(text=ev[1], style='Sec.TLabel')
                    if ev[2] is None:
                        if str(bar['mode']) != 'indeterminate':
                            bar.configure(mode='indeterminate')
                            bar.start(12)
                    else:
                        if str(bar['mode']) != 'determinate':
                            bar.stop()
                            bar.configure(mode='determinate')
                        bar['value'] = int(ev[2] * 1000)
                elif ev[0] == 'ask':
                    replies.put(messagebox.askyesno(
                        'Folder already there', f'{ev[2]}\nalready exists, and this installer did not make it.\n\n'
                        'Put the modded game in it, replacing its files?'))
        except queue.Empty:
            pass
        if not task['busy'] and str(bar['mode']) == 'indeterminate':
            bar.stop()
            bar.configure(mode='determinate')
        root.after(80, poll)

    cur = {'i': 0}

    def leave_ok(i):
        if i == 0 and TITLE_09 not in src:
            messagebox.showinfo('Madden NFL 09', 'Choose where Madden NFL 09 is: a folder on this PC (Browse), or '
                                'your Xbox (type its IP address and press Find my games).')
            return False
        return True

    def show(i):
        cur['i'] = i
        pages[i].tkraise()
        for j, l_ in enumerate(step_lbls):
            l_.configure(style='StepOn.TLabel' if j == i else 'Step.TLabel')
        if i == 0:
            refresh_where()
        if i == 1:
            refresh_mods()
        if i == 2:
            refresh_dest()
        update_nav()

    def update_nav():
        i = cur['i']
        busy = task['busy']
        back_btn.configure(state='normal' if i > 0 and not busy else 'disabled')
        next_btn.configure(text='Close' if i == 3 else 'Next >',
                           state='disabled' if busy or (i == 2 and not result) else 'normal')

    def go_next():
        if cur['i'] == 1:
            refresh_mods()
        save()
        if cur['i'] == 3:
            close()
        elif leave_ok(cur['i']):
            show(cur['i'] + 1)

    def go_back():
        if cur['i'] == 1:
            refresh_mods()
        save()
        show(max(0, cur['i'] - 1))

    def close():
        if task['busy'] and not messagebox.askyesno('Quit', 'Something is still running. Stop it and quit?'):
            return
        if task['cancel']:
            task['cancel'].set()
        refresh_mods()
        cfg.update(xbox_target=xtarget_v.get(), pc_target=ptarget_v.get(), where=where_v.get())
        save()
        if xbox['box']:
            xbox['box'].close()
        root.destroy()

    # games chosen last time, if they're still there
    for k, p in list(cfg['pc_games'].items()):
        if local_game(p) == int(k) and not (int(k) == TITLE_09 and not use_pc_game(p, int(k), quiet=True)):
            src[int(k)] = ('pc', p)
        else:
            del cfg['pc_games'][k]
    where_v.set(cfg['where'])
    threading.Thread(target=lambda: events.put(('call', scanned, find_local_games(extra=[ROOT]), None)),
                     daemon=True).start()
    back_btn.configure(command=go_back)
    next_btn.configure(command=go_next)
    root.protocol('WM_DELETE_WINDOW', close)
    show(0)
    poll()
    root.mainloop()


# ---------------------------------------------------------------- checks without a window

def selftest():
    import tempfile
    ok = True

    def check(cond, what):
        nonlocal ok
        print(('ok   ' if cond else 'FAIL ') + what)
        ok &= bool(cond)

    unix = ['drwxr-xr-x   1 xbox     xbox            0 Jan 01  2005 Games',
            '-rw-r--r--   1 xbox     xbox      7766016 Nov 22 10:14 default.xbe',
            '-rw-r--r-- 1 root 2165760 Nov 22 2026 template.dat',
            '11-22-26  10:14AM       <DIR>          data',
            '11-22-26  10:14AM              7766016 my file.xbe']
    check(parse_list(unix) == [('Games', True, 0), ('default.xbe', False, 7766016), ('template.dat', False, 2165760),
                               ('data', True, 0), ('my file.xbe', False, 7766016)], 'LIST parsing, Unix and DOS')
    check(join('E', '/Games/', 'Madden') == '/E/Games/Madden', 'path joining')
    stock = os.path.join(ROOT, GAMES[TITLE_09][0])
    if os.path.isdir(stock):
        check(local_game(stock) == TITLE_09, 'stock 09 folder recognised')
        check(sha1_file(os.path.join(stock, 'default.xbe')) == STOCK_09_SHA1, 'stock 09 SHA-1')
    for k, *_ in MODS:
        check(k in RECOMMENDED or k in ('save_unlock', 'optional_fullback'), f'mod {k} has a default')
    have = set(ORDER)
    c = {k: k in RECOMMENDED for k, *_ in MODS}
    v = build_values(c, {'title': 'Madden NFL 09 Modded'})
    args = bg.command(v)
    print('  build_all.py', subprocess.list2cmdline(args))
    for flag in ('--modern-kickoff', '--any-number', '--radio-show', '--commanders-commentary', '--year', '--schedule',
                 '--player-stats', '--roster', '--photos', '--coach-photos', '--career-room'):
        check(flag in args, f'recommended build has {flag}')
    check('--no-music' not in args and '--no-awareness' not in args, 'recommended build keeps music and awareness')
    check(unavailable('history', have, dict(c, roster=False)) and unavailable('radio_show', {TITLE_09}, c),
          'mods that need something say so')
    v = build_values(dict.fromkeys(c, False), {'title': ''})
    check('--no-music' in bg.command(v) and '--no-awareness' in bg.command(v), 'nothing chosen: a bare build')

    with tempfile.TemporaryDirectory() as t:
        s, o = os.path.join(t, 's'), os.path.join(t, 'o')
        for p, data in ((os.path.join(s, 'default.xbe'), b'a'), (os.path.join(s, 'data', 'x.dat'), b'bb'),
                        (os.path.join(o, 'default.xbe'), b'ccc'), (os.path.join(o, 'data', 'new.dat'), b'd'),
                        (os.path.join(o, 'roster_report.csv'), b'r')):
            os.makedirs(os.path.dirname(p), exist_ok=True)
            open(p, 'wb').write(data)
        h = HashCache(os.path.join(t, 'h.json'))
        want, send, remove = plan(s, o, h, {}, {})
        check(sorted(want) == ['data/new.dat', 'data/x.dat', 'default.xbe'] and want['default.xbe'][0] == 3,
              'plan: overlay replaces stock files')
        check(send == sorted(want), 'plan: empty target gets everything')
        man = {k: (sz, hh) for k, (sz, hh, _) in want.items()}
        man['data/old.dat'] = (5, 'x')
        sizes = {k.lower(): sz for k, (sz, _, _) in want.items()}
        want, send, remove = plan(s, o, h, sizes, man)
        check(send == [] and remove == ['data/old.dat'], 'plan: unchanged files stay, stale ones go')
        sizes['data/x.dat'] = 1
        check(plan(s, o, h, sizes, man)[1] == ['data/x.dat'], 'plan: a short file is sent again')
        check(read_manifest(write_manifest(man).decode()) == man, 'manifest round trip')
    check(win_to_xbox('E:\\Games\\Madden NFL 09 Modded') == '/E/Games/Madden NFL 09 Modded'
          and xbox_to_win('/E/Games/Madden NFL 09 Modded') == 'E:\\Games\\Madden NFL 09 Modded'
          and win_to_xbox('E:\\') is None, 'Xbox paths to and from E:\\...')
    check(needed_games({'radio_show': True}) == {TITLE_09, 0x4541009f} and len(needed_games({'music': True})) == 5,
          'only the older games a mod needs are copied')
    with tempfile.TemporaryDirectory() as t:
        s, o = os.path.join(t, 'Madden09'), os.path.join(t, 'build')
        for p, data in ((os.path.join(s, 'default.xbe'), b'stock'), (os.path.join(s, 'data', 'a.dat'), b'aa'),
                        (os.path.join(o, 'default.xbe'), b'modded'), (os.path.join(o, 'data', 'fe.qkl'), b'q')):
            os.makedirs(os.path.dirname(p), exist_ok=True)
            open(p, 'wb').write(data)
        target = '/' + os.path.join(t, 'Madden09 Modded').replace(os.sep, '/')
        quiet = lambda *a: None
        old_work = globals()['WORK']
        globals()['WORK'] = t
        try:
            r1 = install_game(LocalBox(), s, o, target, quiet, quiet, quiet, None, lambda _: False)
            r2 = install_game(LocalBox(), s, o, target, quiet, quiet, quiet, None, lambda _: False)
        finally:
            globals()['WORK'] = old_work
        got = tree_files(os.path.join(t, 'Madden09 Modded'))
        check(r1[1] == 3 and r2[1] == 0 and sorted(got) == ['data/a.dat', 'data/fe.qkl', 'default.xbe', MANIFEST]
              and open(got['default.xbe'], 'rb').read() == b'modded', 'a modded copy in a folder on this PC')
        check(open(os.path.join(s, 'default.xbe'), 'rb').read() == b'stock', 'the original folder is untouched')
    found = find_local_games(extra=[ROOT])
    if os.path.isdir(stock):
        check(any(os.path.normcase(d) == os.path.normcase(stock) for d, _ in found), 'finds Madden on this PC')
    print('all good' if ok else 'SOME CHECKS FAILED')
    return ok


if __name__ == '__main__':
    if '--selftest' in sys.argv:
        sys.exit(0 if selftest() else 1)
    gui()
