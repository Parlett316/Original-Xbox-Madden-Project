"""A window for choosing what goes into a build, which then runs build_all.py.

Usage:
  python tools/build_gui.py            open the window
  python tools/build_gui.py --check    print each preset's build_all.py command and exit

Tick what you want (or start from a preset), choose the folders and press Build.
The log shows build_all.py's output and ends with the files to copy to the Xbox
and their sizes. Choices are remembered in build_gui_settings.json next to the
repo's README (never committed).
"""
import json
import os
import re
import queue
import subprocess
import sys
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SETTINGS = os.path.join(ROOT, 'build_gui_settings.json')
GAME09 = 'Madden NFL 09 (USA)'
OLDER = ('Madden NFL 2005 (USA)', 'Madden NFL 06 (USA)', 'Madden NFL 07 (USA)', 'Madden NFL 08 (USA)')
OVERLAY_ITEMS = {'default.xbe', 'data', 'roster_report.csv', 'stats_report.csv'}

# key, label, group                      (group: which box of the window it goes in)
CHECKS = [
    ('awareness', 'Awareness fix (ratings stop collapsing in franchise)', 'game'),
    ('season17', '17-game season, 18 weeks, 3 preseason games', 'game'),
    ('playoffs7', '7-team playoffs (needs the 17-game season)', 'game'),
    ('modern_kickoff', 'Modern kickoff: ball on the 35, hybrid lineup, touchbacks to the 35', 'game'),
    ('any_number', 'Any jersey number at any position, and uncapped free agents', 'game'),
    ('optional_fullback', 'A team can carry no fullback', 'game'),
    ('save_unlock', 'Load edited franchise saves', 'game'),
    ('career_room', 'More room for career stats in long franchises', 'game'),
    ('demo_off', 'Turn off the attract demo (leaving it freezes the console)', 'game'),
    ('music', 'Soundtracks from Madden 2005-08 (BGM.dat becomes 756 MB)', 'look'),
    ('radio_show', "Madden 07's Tony Bruno radio show in franchise (229 MB)", 'look'),
    ('commanders_commentary', 'Al Michaels says "Washington" (447 MB; needs the roster)', 'look'),
]
# key, label, 'file' or 'dir', file types, group, needs the roster
PATHS = [
    ('loadscreen', 'Loading screen', 'file', 'png', 'look', False),
    ('startscreen', 'Start screen', 'file', 'png', 'look', False),
    ('commanders_logo', "Commanders' W logo", 'file', 'png', 'look', False),
    ('roster', 'Roster (EA ratings)', 'file', 'json', 'roster', False),
    ('photos', 'Player photos', 'dir', None, 'roster', True),
    ('coach_photos', 'Coach photos', 'dir', None, 'roster', True),
    ('free_agents', 'Extra free agents', 'file', 'json', 'roster', True),
    ('player_stats', 'Real player stats', 'dir', None, 'roster', True),
    ('classic_names', 'Classic teams\' names', 'file', 'csv', 'roster', False),
    ('schedule', 'Real year 1 schedule', 'file', 'csv', 'roster', False),
]
PROGRESSIONS = ('performance', 'half', '2005', 'stock')
DEFAULTS = dict({k: False for k, _, _ in CHECKS}, **{k: '' for k, *_ in PATHS},
                games=ROOT if os.path.isdir(os.path.join(ROOT, GAME09)) else '',
                out=os.path.join(ROOT, 'patched', 'gui_build'), title='', progression='stock',
                year_on=False, year='2026', online_on=False, online_server='', online_name='')

MY_FILES = {'roster': 'roster/madden27_week7.json', 'photos': 'roster/headshots_raw',
            'coach_photos': 'roster/coach_photos', 'free_agents': 'roster/free_agent_picks.json',
            'player_stats': 'nflverse_stats', 'classic_names': 'nflverse_rosters/classic_matches.csv',
            'schedule': 'nflverse_schedule/games.csv', 'commanders_logo': 'custom/commanders_w.png'}
OFF = {k: v for k, v in DEFAULTS.items()
       if k not in ('games', 'out', 'loadscreen', 'startscreen', 'year', 'online_server', 'online_name')}


def my_files():
    return {k: os.path.join(ROOT, *p.split('/')) for k, p in MY_FILES.items()
            if os.path.exists(os.path.join(ROOT, *p.split('/')))}


# Each preset sets every choice except the folders and the two screen pictures.
PRESETS = {
    'Screens only': lambda: dict(OFF),
    'Modern rules': lambda: dict(OFF, awareness=True, season17=True, playoffs7=True, modern_kickoff=True,
                                 any_number=True, career_room=True),
    'Fixes, no roster': lambda: dict(OFF, awareness=True, demo_off=True, progression='performance',
                                     title='Madden NFL 09 Modded'),
    'Everything': lambda: dict(OFF, **my_files(), awareness=True, season17=True, playoffs7=True,
                               modern_kickoff=True, any_number=True, demo_off=True, music=True,
                               radio_show=True, year_on=True, career_room=True, progression='performance',
                               title='Madden NFL 09 Modded'),
}
HINTS = {'Screens only': 'Now choose the loading and start screen pictures.'}


def command(v):
    """build_all.py's arguments for a dict of choices."""
    c = ['--games', v['games'], '--out', v['out'], '--title', v['title'].strip(),
         '--progression', v['progression'], '--demo-delay', '86400000' if v['demo_off'] else '0']
    if not v['awareness']:
        c.append('--no-awareness')
    if not v['music']:
        c.append('--no-music')
    if not v['season17']:
        c.append('--no-season17')
    elif not v['playoffs7']:
        c.append('--no-playoffs7')
    c.append('--career-room' if v['career_room'] else '--no-career-room')
    for k in ('modern_kickoff', 'any_number', 'optional_fullback', 'save_unlock', 'radio_show'):
        if v[k]:
            c.append('--' + k.replace('_', '-'))
    if v['commanders_commentary'] and v['roster']:
        c.append('--commanders-commentary')
    if v['year_on']:
        c += ['--year', v['year'].strip()]
    if v['online_on']:
        c += ['--online', v['online_server'].strip()]
        if v['online_name'].strip():
            c += ['--online-name', v['online_name'].strip()]
    for k, _, _, _, _, needs_roster in PATHS:
        if v[k] and (v['roster'] or not needs_roster) and (k != 'schedule' or v['season17']):
            c += ['--' + k.replace('_', '-'), v[k]]
    return c


def problems(v):
    """What stops this build, as a list of sentences."""
    bad = []
    games, out = v['games'], v['out']
    have = lambda g: os.path.isdir(os.path.join(games, g))
    if not games or not have(GAME09):
        bad.append(f'The games folder needs a "{GAME09}" folder in it.')
    if not out:
        bad.append('Choose an output folder.')
    elif games and any(os.path.abspath(out).lower().startswith(os.path.join(os.path.abspath(games), g).lower())
                       for g in (GAME09,) + OLDER):
        bad.append('The output folder is inside a stock game folder. Choose another.')
    if v['music'] and not all(have(g) for g in OLDER):
        bad.append('The soundtracks need the Madden 2005, 06, 07 and 08 folders in the games folder.')
    if v['progression'] != 'stock' and not have(OLDER[0]):
        bad.append(f'Progression "{v["progression"]}" needs "{OLDER[0]}" in the games folder.')
    if v['radio_show'] and not have(OLDER[2]):
        bad.append(f'The radio show needs "{OLDER[2]}" in the games folder.')
    if v['year_on'] and not (v['year'].strip().isdigit() and 1900 <= int(v['year']) <= 2100):
        bad.append('The year must be a number such as 2026.')
    if v['online_on']:
        sys.path.insert(0, os.path.join(ROOT, 'patches'))
        from online import server_ok
        if not server_ok(v['online_server'].strip()):
            bad.append("Online play needs the lobby server's address, such as 192.168.1.4, or a name of up to "
                       "18 characters, such as md09.duckdns.org.")
    if v['online_on'] and v['online_name'].strip() and not re.fullmatch(r'[A-Za-z0-9_-]{1,15}', v['online_name'].strip()):
        bad.append('The online name is 1 to 15 letters, digits, _ or -.')
    if len(v['title'].strip()) > 40:
        bad.append('The dashboard name is limited to 40 characters.')
    for k, label, kind, *_ in PATHS:
        if v[k] and not (os.path.isdir if kind == 'dir' else os.path.isfile)(v[k]):
            bad.append(f'{label}: {v[k]} not found.')
    return bad


def notes(v):
    """Things the build will do that the ticks don't say."""
    n = []
    xbe = any(v[k] for k in ('season17', 'modern_kickoff', 'any_number', 'optional_fullback', 'save_unlock',
                             'radio_show', 'year_on', 'roster', 'online_on'))
    if not v['awareness'] and xbe:
        n.append('The awareness fix stays in: the other default.xbe patches are built on it.')
    if v['playoffs7'] and not v['season17']:
        n.append('7-team playoffs are left out: they need the 17-game season.')
    return n


def gui():
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    root = tk.Tk()
    root.title('Madden NFL 09 build')
    saved = dict(DEFAULTS)
    try:
        saved.update({k: v for k, v in json.load(open(SETTINGS, encoding='utf8')).items() if k in DEFAULTS})
    except (OSError, ValueError):
        pass
    var = {k: (tk.BooleanVar if isinstance(d, bool) else tk.StringVar)(value=saved[k]) for k, d in DEFAULTS.items()}
    values = lambda: {k: x.get() for k, x in var.items()}
    state = {'proc': None}
    lines = queue.Queue()

    def path_row(parent, row, key, label, kind, ext):
        def browse():
            start = os.path.dirname(var[key].get()) or ROOT
            p = (filedialog.askdirectory(initialdir=var[key].get() or ROOT) if kind == 'dir' else
                 filedialog.askopenfilename(initialdir=start, filetypes=[(ext.upper(), '*.' + ext), ('All', '*.*')]))
            if p:
                var[key].set(os.path.normpath(p))
        ws = [ttk.Label(parent, text=label), ttk.Entry(parent, textvariable=var[key], width=46),
              ttk.Button(parent, text='Browse', width=7, command=browse),
              ttk.Button(parent, text='Clear', width=5, command=lambda: var[key].set(''))]
        for col, w in enumerate(ws):
            w.grid(row=row, column=col, sticky='we' if col == 1 else 'w', padx=2, pady=1)
        parent.columnconfigure(1, weight=1)
        return ws[1:]

    top = ttk.LabelFrame(root, text='Folders')
    top.pack(fill='x', padx=8, pady=4)
    path_row(top, 0, 'games', 'Games folder (holds "Madden NFL 09 (USA)")', 'dir', None)
    path_row(top, 1, 'out', 'Output folder (the files to copy to the Xbox)', 'dir', None)
    found = ttk.Label(top, foreground='#555')
    found.grid(row=2, column=0, columnspan=4, sticky='w', padx=2)

    bar = ttk.Frame(root)
    bar.pack(fill='x', padx=8)
    ttk.Label(bar, text='Start from:').pack(side='left')

    def preset(name):
        for k, x in PRESETS[name]().items():
            var[k].set(x)
        status.set(HINTS.get(name, ''))
    for name in PRESETS:
        ttk.Button(bar, text=name, command=lambda n=name: preset(n)).pack(side='left', padx=2, pady=2)

    mid = ttk.Frame(root)
    mid.pack(fill='x', padx=8)
    boxes = {'game': ttk.LabelFrame(mid, text='Game and rules'), 'look': ttk.LabelFrame(mid, text='Look and sound')}
    boxes['game'].pack(side='left', fill='both', expand=True, padx=(0, 4), pady=4)
    boxes['look'].pack(side='left', fill='both', expand=True, pady=4)
    boxes['roster'] = ttk.LabelFrame(root, text='Roster and franchise data (leave a line empty to skip it)')
    boxes['roster'].pack(fill='x', padx=8, pady=4)
    widget = {}
    for key, label, group in CHECKS:
        widget[key] = [ttk.Checkbutton(boxes[group], text=label, variable=var[key])]
        widget[key][0].pack(anchor='w', padx=4)

    f = ttk.Frame(boxes['game'])
    f.pack(anchor='w', padx=4)
    ttk.Checkbutton(f, text='Years count from', variable=var['year_on']).pack(side='left')
    ttk.Entry(f, textvariable=var['year'], width=6).pack(side='left')
    ttk.Label(f, text='instead of 2008').pack(side='left', padx=4)
    f = ttk.Frame(boxes['game'])
    f.pack(anchor='w', padx=4)
    ttk.Checkbutton(f, text='Online play, lobby server at', variable=var['online_on']).pack(side='left')
    ttk.Entry(f, textvariable=var['online_server'], width=14).pack(side='left')
    ttk.Label(f, text='name').pack(side='left', padx=4)
    ttk.Entry(f, textvariable=var['online_name'], width=15).pack(side='left')
    f = ttk.Frame(boxes['game'])
    f.pack(anchor='w', padx=4, pady=2)
    ttk.Label(f, text='Player progression').pack(side='left')
    ttk.Combobox(f, textvariable=var['progression'], values=PROGRESSIONS, state='readonly', width=12).pack(side='left', padx=4)
    f = ttk.Frame(boxes['game'])
    f.pack(anchor='w', padx=4, pady=2)
    ttk.Label(f, text='Dashboard name (empty: stock)').pack(side='left')
    ttk.Entry(f, textvariable=var['title'], width=28).pack(side='left', padx=4)

    grids = {g: ttk.Frame(boxes[g]) for g in ('look', 'roster')}
    for g in grids.values():
        g.pack(fill='x', padx=2, pady=2)
    rows = {'look': 0, 'roster': 0}
    for key, label, kind, ext, group, _ in PATHS:
        widget[key] = path_row(grids[group], rows[group], key, label, kind, ext)
        rows[group] += 1

    def refresh(*_):
        v = values()
        on = lambda ws, yes: [w.configure(state='normal' if yes else 'disabled') for w in ws]
        on(widget['playoffs7'], v['season17'])
        on(widget['schedule'], v['season17'])
        on(widget['commanders_commentary'], bool(v['roster']))
        for key, *_, needs_roster in PATHS:
            if needs_roster:
                on(widget[key], bool(v['roster']))
        g = v['games']
        names = [n.split()[2] for n in OLDER + (GAME09,) if g and os.path.isdir(os.path.join(g, n))]
        found.configure(text='Games found: ' + (', '.join(names) if names else 'none'))
    for x in var.values():
        x.trace_add('write', refresh)

    run_bar = ttk.Frame(root)
    run_bar.pack(fill='x', padx=8)
    build_btn = ttk.Button(run_bar, text='Build')
    build_btn.pack(side='left', pady=2)
    stop_btn = ttk.Button(run_bar, text='Stop', state='disabled')
    stop_btn.pack(side='left', padx=4)
    ttk.Button(run_bar, text='Open output folder',
               command=lambda: os.path.isdir(var['out'].get()) and os.startfile(var['out'].get())).pack(side='left')
    status = tk.StringVar()
    ttk.Label(run_bar, textvariable=status, foreground='#555').pack(side='left', padx=8)

    logf = ttk.Frame(root)
    logf.pack(fill='both', expand=True, padx=8, pady=(2, 8))
    log = tk.Text(logf, height=14, wrap='none', font=('Consolas', 9), state='disabled')
    sb = ttk.Scrollbar(logf, command=log.yview)
    log.configure(yscrollcommand=sb.set)
    sb.pack(side='right', fill='y')
    log.pack(side='left', fill='both', expand=True)

    def say(text):
        log.configure(state='normal')
        log.insert('end', text + '\n')
        log.see('end')
        log.configure(state='disabled')

    def save():
        try:
            json.dump(values(), open(SETTINGS, 'w', encoding='utf8'), indent=1)
        except OSError:
            pass

    def clear_output(out):
        """An output folder must start empty: build_all.py builds on files it finds there."""
        items = os.listdir(out) if os.path.isdir(out) else []
        if not items:
            return True
        if not set(items) <= OVERLAY_ITEMS:
            messagebox.showerror('Output folder', f'{out}\nholds files that are not from a build. Choose an empty folder.')
            return False
        if not messagebox.askyesno('Output folder', f'{out}\nholds an earlier build, which has to go first.\n\nDelete it?'):
            return False
        import shutil
        for i in items:
            p = os.path.join(out, i)
            shutil.rmtree(p) if os.path.isdir(p) else os.remove(p)
        return True

    def build():
        v = values()
        bad = problems(v)
        if bad:
            messagebox.showerror('Cannot build yet', '\n'.join(bad))
            return
        v['games'], v['out'] = os.path.abspath(v['games']), os.path.abspath(v['out'])
        if not clear_output(v['out']):
            return
        save()
        log.configure(state='normal')
        log.delete('1.0', 'end')
        log.configure(state='disabled')
        args = command(v)
        say('python tools/build_all.py ' + subprocess.list2cmdline(args) + '\n')
        for n in notes(v):
            say(n)
        env = dict(os.environ, PYTHONUNBUFFERED='1', PYTHONIOENCODING='utf8')
        state['proc'] = p = subprocess.Popen(
            [sys.executable, '-u', os.path.join(ROOT, 'tools', 'build_all.py'), *args], cwd=ROOT, env=env,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf8', errors='replace',
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))

        def pump():
            for line in p.stdout:
                lines.put(line.rstrip('\n'))
            lines.put(p.wait())
        threading.Thread(target=pump, daemon=True).start()
        build_btn.configure(state='disabled')
        stop_btn.configure(state='normal')
        status.set('Building...')

    def stop():
        p = state['proc']
        if p and p.poll() is None:      # the tree: build_all.py runs each step as a child
            subprocess.run(['taskkill', '/F', '/T', '/PID', str(p.pid)], capture_output=True,
                           creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))

    def poll():
        try:
            while True:
                x = lines.get_nowait()
                if isinstance(x, int):
                    build_btn.configure(state='normal')
                    stop_btn.configure(state='disabled')
                    if x == 0:
                        status.set('Done.')
                        say('\nCopy these over the game folder on the Xbox, in binary mode, and check each size.\n'
                            'Nothing listed means nothing changed. A file left out of this build is not removed\n'
                            'from the Xbox: to undo an earlier change, copy the stock file back.')
                    else:
                        status.set('Stopped or failed: nothing in the output folder is safe to copy.')
                        say(f'\nbuild_all.py ended with code {x}')
                else:
                    say(x)
        except queue.Empty:
            pass
        root.after(100, poll)

    def close():
        save()
        stop()
        root.destroy()

    build_btn.configure(command=build)
    stop_btn.configure(command=stop)
    root.protocol('WM_DELETE_WINDOW', close)
    refresh()
    poll()
    root.minsize(900, 640)
    root.mainloop()


if __name__ == '__main__':
    if '--check' in sys.argv:
        for name, make in PRESETS.items():
            v = dict(DEFAULTS, **make())
            print(f'{name}:\n  build_all.py {subprocess.list2cmdline(command(v))}')
            for line in problems(v) + notes(v):
                print('  !', line)
    else:
        gui()
