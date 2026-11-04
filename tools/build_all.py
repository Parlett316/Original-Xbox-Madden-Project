"""Build the complete "Madden NFL 09 Modded" overlay from stock game files.

Usage:
  python tools/build_all.py --games <dir> --out <dir> [options]

  --games DIR        folder holding the extracted games, named as on disc:
                     "Madden NFL 09 (USA)" (required), plus "Madden NFL 2005 (USA)",
                     "Madden NFL 06 (USA)", "Madden NFL 07 (USA)", "Madden NFL 08 (USA)"
                     for music and 2005 progression
  --out DIR          output overlay: default.xbe + data/ with only the changed files
  --title TEXT       dashboard name (default "Madden NFL 09 Modded")
  --roster JSON      EA ratings file from roster/fetch_ea_ratings.py; builds the modern roster
  --photos DIR       EA headshots from roster/fetch_headshots.py (with --roster)
  --coach-photos DIR coach headshots from roster/fetch_coach_photos.py (with --roster;
                     the roster always gets the 2026 coaching staffs, roster/coaches.py)
  --progression M    stock | 2005 | half | performance   (default performance)
  --no-music         skip the 2005-08 soundtrack import
  --loadscreen PNG   640x480 image for the loading screen (LOADDATA.dat)
  --startscreen PNG  image for the "Press START" background (uis_fe.dat)
  --demo-delay MS    idle time on Press START before the attract-mode demo, in ms
                     (default 86400000 = 24 h, i.e. off; stock 75000; 0 = leave stock)
  --classic-names CSV real names for the classic teams' players, from
                     roster/classic_names.py (high and medium matches)
  --no-season17      keep the stock 16-game season (the default is 17 games over
                     18 weeks; existing franchises need the matching build)
  --schedule CSV     year 1 is a real NFL season from nflverse's
                     games.csv (github.com/nflverse/nfldata, data/games.csv)
  --schedule-season YEAR  which season (default: the latest complete one)

Steps: awareness fix + rename, roster, 17-game season, music, progression, screens, demo, then
fe.qkl/game.qkl are re-synced from every changed file. Copy the overlay over a
copy of the game folder on the Xbox (keep the stock folder as is).
"""
import argparse
import filecmp
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable


def run(*args):
    print('>', ' '.join(os.path.basename(a) if os.path.isabs(a) else a for a in args[:2]), *args[2:3], '...')
    subprocess.run([PY, *args], check=True)


def game_file(games, game, name):
    folder = os.path.join(games, game)
    for sub in ('data', 'DATA'):
        d = os.path.join(folder, sub)
        if os.path.isdir(d):
            for f in os.listdir(d):
                if f.lower() == name.lower():
                    return os.path.join(d, f)
    raise SystemExit(f'{game}: {name} not found')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--games', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--title', default='Madden NFL 09 Modded')
    ap.add_argument('--roster')
    ap.add_argument('--photos')
    ap.add_argument('--coach-photos')
    ap.add_argument('--progression', default='performance', choices=('stock', '2005', 'half', 'performance'))
    ap.add_argument('--no-music', action='store_true')
    ap.add_argument('--loadscreen')
    ap.add_argument('--startscreen')
    ap.add_argument('--demo-delay', type=int, default=86400000)
    ap.add_argument('--no-season17', dest='season17', action='store_false')
    ap.add_argument('--classic-names')
    ap.add_argument('--schedule')
    ap.add_argument('--schedule-season')
    a = ap.parse_args()
    for k in ('games', 'out', 'roster', 'photos', 'coach_photos', 'loadscreen', 'startscreen', 'classic_names', 'schedule'):
        if getattr(a, k):
            setattr(a, k, os.path.abspath(getattr(a, k)))

    g09 = os.path.join(a.games, 'Madden NFL 09 (USA)')
    stock = os.path.join(g09, 'data')
    out_data = os.path.join(a.out, 'data')
    os.makedirs(out_data, exist_ok=True)
    P, R, L = (os.path.join(ROOT, d) for d in ('patches', 'roster', os.path.join('patches', 'loadscreen')))

    # 1. awareness fix, renamed for the dashboard
    xbe = os.path.join(a.out, 'default.xbe')
    run(os.path.join(P, 'madden_awareness_fix.py'), os.path.join(g09, 'default.xbe'), xbe)
    run(os.path.join(P, 'set_xbe_title.py'), xbe, xbe, a.title)
    if a.season17:                        # offseason start follows the Pro Bowl, now a week later
        run(os.path.join(P, 'season17.py'), xbe, xbe)

    # 2. roster (template.dat, DB_TEAMS.dat, uis_plyr.dat, uis_coac.dat)
    if a.roster:
        with tempfile.TemporaryDirectory() as t:
            args = [os.path.join(R, 'build_roster.py'), a.roster, g09, t]
            if a.photos:
                args += ['--photos', a.photos]
            if a.coach_photos:
                args += ['--coach-photos', a.coach_photos]
            run(*args)
            for f in os.listdir(os.path.join(t, 'data')):
                shutil.copy(os.path.join(t, 'data', f), out_data)
            shutil.copy(os.path.join(t, 'roster_report.csv'), a.out)

    # 2a. classic teams' real names (DB_TEAMS.dat; only the classic teams' DBs change)
    if a.classic_names:
        teams = os.path.join(out_data, 'DB_TEAMS.dat')
        run(os.path.join(R, 'classic_names.py'), '--apply',
            teams if os.path.exists(teams) else os.path.join(stock, 'DB_TEAMS.dat'), a.classic_names, teams)

    # 2b. 17-game season: shifts template.dat's later DBs, so it comes after the roster
    if a.season17:
        tpl = os.path.join(out_data, 'template.dat')
        real = [a.schedule] + ([a.schedule_season] if a.schedule_season else []) if a.schedule else []
        run(os.path.join(P, 'season17.py'), tpl if os.path.exists(tpl) else os.path.join(stock, 'template.dat'), tpl, *real)

    # 3. music (BGM.dat + strmdata.db)
    strm = os.path.join(stock, 'strmdata.db')
    if not a.no_music:
        run(os.path.join(P, 'music_import.py'), os.path.join(stock, 'BGM.dat'), strm, out_data, a.games)
        strm = os.path.join(out_data, 'strmdata.db')

    # 4. progression (strmdata.db, on top of the music tables if any)
    if a.progression != 'stock':
        mode = {'2005': '1', 'half': '0.5', 'performance': 'performance'}[a.progression]
        src05 = game_file(a.games, 'Madden NFL 2005 (USA)', 'STREAMEDDATA.DB')
        with tempfile.TemporaryDirectory() as t:
            tmp = os.path.join(t, 'strmdata.db')
            run(os.path.join(P, 'progression_2005.py'), src05, strm, tmp, mode)
            shutil.copy(tmp, os.path.join(out_data, 'strmdata.db'))

    # 4b. 17-game season: one more week in strmdata.db's per-week owner tables
    if a.season17:
        sdb = os.path.join(out_data, 'strmdata.db')
        run(os.path.join(P, 'season17.py'), sdb if os.path.exists(sdb) else strm, sdb)

    # 5. screens (LZH1 runs the stock XBE's own code)
    os.environ['MADDEN09_XBE'] = os.path.join(g09, 'default.xbe')
    if a.loadscreen:
        run(os.path.join(L, 'pack_loadscreen.py'), os.path.join(stock, 'LOADDATA.dat'),
            os.path.join(out_data, 'LOADDATA.dat'), a.loadscreen)
    if a.startscreen:
        cwd = os.getcwd()
        os.chdir(L)                       # packstart.py imports its neighbours
        try:
            run('packstart.py', os.path.join(stock, 'uis_fe.dat'), os.path.join(out_data, 'uis_fe.dat'), a.startscreen)
        finally:
            os.chdir(cwd)

    # 6. attract-mode demo delay (uis_all.dat); leaving the demo hard-locks the console
    if a.demo_delay:
        run(os.path.join(P, 'press_start_timer.py'), os.path.join(stock, 'uis_all.dat'),
            os.path.join(out_data, 'uis_all.dat'), str(a.demo_delay))

    # 7. quick-load bundles: copy preloaded parts of every changed file
    for qkl in ('fe.qkl', 'game.qkl'):
        dst = os.path.join(out_data, qkl)
        run(os.path.join(P, 'qkl_sync.py'), os.path.join(stock, qkl), stock, out_data, dst)
        if filecmp.cmp(dst, os.path.join(stock, qkl), shallow=False):
            os.remove(dst)                # unchanged: no need to ship it

    print('\noverlay ready in', a.out)
    for f in sorted(os.listdir(out_data)):
        print(f'  data/{f:16} {os.path.getsize(os.path.join(out_data, f)):>12,} bytes')


if __name__ == '__main__':
    main()
