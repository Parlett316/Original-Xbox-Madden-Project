"""One-command online tests in xemu: lobby server, one or two instances, driven to the Lobby.

    python tools/online_test.py <work> setup [--lan <PC's IP> <adapter GUID>] [--game <folder>] [--name NAME]  # w/, w2/, online.iso
    python tools/online_test.py <work> up [--two] [--join] [--bot]  # restart everything, drive to the Lobby
    python tools/online_test.py <work> lobby [--inst N] [--join]  # the same from the main menu
    python tools/online_test.py <work> reboot [--inst N] [--join]  # restart one stuck box (default 1)
    python tools/online_test.py <work> report [lines] [--all]  # both screens in one picture + server log
    python tools/online_test.py <work> down                # stop the server and both instances

`setup` patches the stock XBE with patches/online.py --lag-tolerant (server 10.0.2.2, the PC as seen from
xemu's NAT), packs <work>/online.iso with tools/make_xiso.py, and makes two xemu work folders
(tools/xemu.py setup; w2 gets its own MAC). Run it again after changing online.py. --game packs a
built game folder (default.xbe + data, e.g. the release on the user's Xbox) instead of the stock game,
so an xemu box can play a real Xbox that runs the same files. --name passes online.py --name (both
boxes share the ISO, so the second logs in as NAME2). With --lan
both boxes are bridged onto that network card through Npcap (they get addresses from the
router and can reach each other) and the game is pointed at the PC's LAN address instead; the
choice is kept in <work>/mode.txt, so run setup again to switch.

`up` stops any running server and instances, starts tools/aries_server.py (log
<work>/server.log), boots instance 0 (and 1 with --two), and drives each through Game Modes >
Xbox Live > Game Modes > Lobby, waiting for each login in the server log instead of a fixed
time. --join also enters the first room, so with --two both players end up in USR.Madden. It
ends with `report`.

`report` writes <work>/both.png (each running instance's screen side by side; one read shows
both) and prints the last lines of the server log without keepalives and messenger chatter.

With two instances, tools/xemu.py moves the focus between the xemu windows (xemu reads only the
focused window's keyboard), so the PC's foreground window changes while this runs.
"""
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PY = sys.executable
STOCK = os.path.join(ROOT, 'Madden NFL 09 (USA)')
NOISE = re.compile(r'~png|PSET|RGET|EPGT| raw |(->|<-) AUTH')
# the login sequence, the same every time once it works (report --all shows it)
LOGIN = re.compile(r'(->|<-) (@tic|@dir|addr|skey|news|auth|pers|sele|clgf|usld|qdef|rcat|cate|slst|uatr|\+who)')
# From the main menu: Game Modes, Xbox Live (the last item, so up from the first)
# (waits are generous: with two instances running every menu loads slower, and a key sent
# during a transition is dropped)
TO_ONLINE = 'down w2 down w2 a w8 up w2 a'
# From the online main menu: Game Modes, then Lobby (second item)
TO_LOBBY = 'down w2 down w2 a w6 down w2 a w6'


def xemu(inst, *args, check=True):
    env = dict(os.environ, XEMU_INSTANCE=str(inst))
    r = subprocess.run([PY, os.path.join(HERE, 'xemu.py'), *args], env=env,
                       capture_output=True, text=True)
    if check and r.returncode:
        raise SystemExit(f'xemu.py {args[0]} (instance {inst}) failed:\n{r.stdout}{r.stderr}')
    return r.stdout


def work_dir(work, inst):
    return os.path.join(work, 'w' if inst == 0 else 'w2')


def mode(work):
    """(server address the game uses, xemu.py --net value)"""
    try:
        server, net = open(os.path.join(work, 'mode.txt')).read().split()
        return server, net
    except (OSError, ValueError):
        return '10.0.2.2', 'nat'


def setup(work, lan=None, game=STOCK, name=None):
    down(work)                      # a running xemu holds the ISO open
    server, net = (lan[0], 'pcap:' + lan[1]) if lan else ('10.0.2.2', 'nat')
    open(os.path.join(work, 'mode.txt'), 'w').write(f'{server} {net}\n')
    os.makedirs(os.path.join(work, 'ov'), exist_ok=True)
    xbe = os.path.join(work, 'ov', 'default.xbe')
    subprocess.run([PY, os.path.join(ROOT, 'patches', 'online.py'),
                    os.path.join(game, 'default.xbe'), xbe, server, '--lag-tolerant']
                   + (['--name', name] if name else []), check=True,
                   stdin=subprocess.DEVNULL)   # no name prompt: without --name the boxes are Player1, Player2
    iso = os.path.join(work, 'online.iso')
    subprocess.run([PY, os.path.join(HERE, 'make_xiso.py'), 'pack', game,
                    os.path.join(work, 'ov'), iso], check=True)
    for inst in (0, 1):
        xemu(inst, 'setup', work_dir(work, inst), iso)    # copies the user's drive only once
    xemu(1, 'mac', work_dir(work, 1), '0f')                  # one LAN, two MACs
    print('ready:', work)


def server_pids():
    ps = ('Get-CimInstance Win32_Process -Filter "name=\'python.exe\'" | '
          "? { $_.CommandLine -like '*aries_server*' } | % { $_.ProcessId }")
    out = subprocess.run(['powershell', '-NoProfile', '-Command', ps], capture_output=True, text=True).stdout
    return [int(p) for p in out.split()]


def down(work):
    for inst in (1, 0):
        xemu(inst, 'quit', check=False)
    for pid in server_pids():
        subprocess.run(['taskkill', '/F', '/PID', str(pid)], capture_output=True)
    time.sleep(3)


def log_path(work):
    return os.path.join(work, 'server.log')


def count(work, text):
    try:
        return open(log_path(work), encoding='latin1').read().count(text)
    except FileNotFoundError:
        return 0


def logins(work):
    """Completed lobby logins so far (uatr is the last command of the login sequence)."""
    return count(work, '-> uatr')


def drive(work, inst, join, from_title=True):
    w = work_dir(work, inst)
    before = logins(work)
    start = ['enter', 'w30'] if from_title else []     # Start, then the profile and menu load
    for attempt in range(2):
        xemu(inst, 'keys', w, 'nav', *start, *TO_ONLINE.split())
        for _ in range(60):         # login takes 10-20 s
            if logins(work) > before:
                break
            time.sleep(1)
        else:   # a key went missing; the main menu keeps its cursor and wraps, so reboot this box
            print(f'instance {inst}: no login after 60 s' + (', rebooting it' if not attempt else ''))
            if not attempt:
                xemu(inst, 'quit', check=False)
                time.sleep(3)
                xemu(inst, 'boot', w, '--net', mode(work)[1], '--gdb')
                time.sleep(45)
                start = ['enter', 'w30']
            continue
        break
    else:
        return
    time.sleep(3)
    xemu(inst, 'keys', w, 'nav', *TO_LOBBY.split(), 'w3')
    if join:                        # a key can be lost when another window takes the focus: retry
        for _ in range(2):
            moves = count(work, '-> move')
            xemu(inst, 'keys', w, 'nav', 'a', 'w5')
            if count(work, '-> move') > moves:
                break
        else:
            print(f'instance {inst}: no move in the server log after two tries')


def up(work, two, join, bot=False):
    down(work)
    open(log_path(work), 'w').close()
    out = open(os.path.join(work, 'server.out'), 'w')
    server, net = mode(work)
    subprocess.Popen([PY, os.path.join(HERE, 'aries_server.py'), log_path(work), '--host', server,
                      *(['--bot'] if bot else [])],
                     stdout=out,
                     stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                     creationflags=0x00000008 | 0x00000200)
    # one box at a time: booting both together slows them, and a box left on the title screen
    # starts the attract demo, which eats the keys
    for inst in ((0, 1) if two else (0,)):
        xemu(inst, 'boot', work_dir(work, inst), '--net', net, '--gdb')
        time.sleep(45)              # to the title screen
        drive(work, inst, join)
    report(work)


def report(work, lines=25, everything=False):
    from PIL import Image
    shots = []
    for inst in (0, 1):
        xemu(inst, 'shot', work_dir(work, inst), 'report', check=False)   # fails if not running
        p = os.path.join(work_dir(work, inst), 'shots', 'report.png')
        if os.path.exists(p) and time.time() - os.path.getmtime(p) < 30:
            shots.append(Image.open(p).resize((640, 480)))
    if shots:
        s = Image.new('RGB', (640 * len(shots), 480))
        for i, im in enumerate(shots):
            s.paste(im, (640 * i, 0))
        s.save(os.path.join(work, 'both.png'))
        print('screens:', os.path.join(work, 'both.png'), f'({len(shots)} instance(s), left = 0)')
    try:
        log = [l for l in open(log_path(work), encoding='latin1')
               if everything or not (NOISE.search(l) or LOGIN.search(l))]
    except FileNotFoundError:
        log = []
    print(f'server log ({len(log)} lines, last {lines}):')
    for l in log[-lines:]:
        print(' ', l.rstrip()[:220])


def main(argv):
    if len(argv) < 2:
        raise SystemExit(__doc__)
    work, cmd, rest = os.path.abspath(argv[0]), argv[1], argv[2:]
    os.makedirs(work, exist_ok=True)
    if cmd == 'setup':
        setup(work, rest[rest.index('--lan') + 1:rest.index('--lan') + 3] if '--lan' in rest else None,
              os.path.abspath(rest[rest.index('--game') + 1]) if '--game' in rest else STOCK,
              rest[rest.index('--name') + 1] if '--name' in rest else None)
    elif cmd == 'up':
        up(work, '--two' in rest, '--join' in rest, '--bot' in rest)
    elif cmd == 'lobby':            # from the main menu (e.g. after a failed `up`)
        insts = [int(rest[rest.index('--inst') + 1])] if '--inst' in rest else [0, 1]
        for inst in insts:
            drive(work, inst, '--join' in rest, from_title=False)
        report(work)
    elif cmd == 'reboot':           # one stuck box: restart it and drive it back to the lobby
        inst = int(rest[rest.index('--inst') + 1]) if '--inst' in rest else 1
        xemu(inst, 'quit', check=False)
        time.sleep(3)
        xemu(inst, 'boot', work_dir(work, inst), '--net', mode(work)[1], '--gdb')
        time.sleep(45)
        drive(work, inst, '--join' in rest)
        report(work)
    elif cmd == 'report':
        n = [int(a) for a in rest if a.isdigit()]
        report(work, n[0] if n else 25, '--all' in rest)
    elif cmd == 'down':
        down(work)
    else:
        raise SystemExit(__doc__)


if __name__ == '__main__':
    main(sys.argv[1:])
