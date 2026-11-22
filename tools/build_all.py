"""Build the complete "Madden NFL 09 Modded" overlay from stock game files.

Usage:
  python tools/build_all.py --games <dir> --out <dir> [options]

  --games DIR        folder holding the extracted games, named as on disc:
                     "Madden NFL 09 (USA)" (required), plus "Madden NFL 2005 (USA)",
                     "Madden NFL 06 (USA)", "Madden NFL 07 (USA)", "Madden NFL 08 (USA)"
                     for music and 2005 progression
  --out DIR          output overlay: default.xbe + data/ with only the changed files
  --title TEXT       dashboard name (default "Madden NFL 09 Modded"; "" keeps the stock name)
  --no-awareness     leave out the awareness fix (for a build with only screens, music or
                     progression; any other default.xbe patch needs it and keeps it)
  --roster JSON      EA ratings file from roster/fetch_ea_ratings.py; builds the modern roster
  --photos DIR       EA headshots from roster/fetch_headshots.py (with --roster)
  --free-agents JSON extra free agents from roster/pick_free_agents.py (with --roster)
  --coach-photos DIR coach headshots from roster/fetch_coach_photos.py (with --roster;
                     the roster always gets the 2026 coaching staffs, roster/coaches.py)
  --progression M    stock | 2005 | half | performance   (default performance)
  --no-music         skip the 2005-08 soundtrack import
  --loadscreen PNG   640x480 image for the loading screen (LOADDATA.dat)
  --startscreen PNG  image for the "Press START" background (uis_fe.dat)
  --demo-delay MS    idle time on Press START before the attract-mode demo, in ms
                     (default 86400000 = 24 h, i.e. off; stock 75000; 0 = leave stock)
  --player-stats DIR real stats for the roster's players: the last 5 seasons and career
                     totals, from nflverse files in DIR (roster/player_stats.py)
  --year YYYY        the year a franchise's first season is shown as (stock 2008), e.g.
                     2026 with --player-stats (patches/year_base.py, default.xbe)
  --no-career-room   keep the stock career stat tables (by default PCDE 1,550 -> 2,400 and
                     PCNG 2,100 -> 2,400, so long franchises keep career totals; done whenever
                     template.dat is built, or always with --career-room; patches/career_room.py)
  --classic-names CSV real names for the classic teams' players, from
                     roster/classic_names.py (high and medium matches)
  --save-unlock      let the game load edited saves (skips their signature check)
  --no-season17      keep the stock 16-game season (the default is 17 games over
                     18 weeks; existing franchises need the matching build)
  --no-playoffs7     keep 6 playoff teams per conference (the default is 7, with one
                     bye, on the 17-game season; a franchise created before keeps 6
                     until its next season)
  --optional-fullback  a team can carry no fullback (lowers the position minimums)
  --schedule CSV     year 1 is a real NFL season from nflverse's
                     games.csv (github.com/nflverse/nfldata, data/games.csv)
  --schedule-season YEAR  which season (default: the latest complete one)
  --commanders-logo PNG  W with transparency, gold outline on burgundy: menu logo and the
                     helmet of Washington's white and burgundy uniforms; classic Redskins keep theirs
  --commanders-commentary  Al Michaels says "Washington" for the Commanders; classic Redskins
                     keep their line (adds SOUNDDAT.dat and SPCHDATA.dat, 447 MB; needs --roster)
  --modern-kickoff   kick from the 35 with the NFL's hybrid lineup, everyone held until the
                     receiving team touches the ball; touchbacks to the 35, out of bounds to
                     the receiving 40 (default.xbe and GAMEDATA.dat)
  --any-number       the edit screen offers any jersey number, 0-99, at any position
                     (rookies and signings still get traditional numbers)
  --radio-show       Madden 07's Tony Bruno radio show in the franchise menus, once per week
                     (default.xbe grows by 16 KB; adds data/spchfe07.dat, 229 MB; needs
                     "Madden NFL 07 (USA)" in the games folder)
  --online SERVER    Game Modes > Xbox Live goes to our own lobby server at this IPv4 address
                     (tools/aries_server.py) instead of Xbox Live (patches/online.py, default.xbe;
                     offline play is unchanged). Same build on every box that plays together.
  --online-name NAME this box's name in the lobby (1-15 letters, digits, _ or -; default Player<n>)
  --online-lag-tolerant  never end a game for lag (only for playing an xemu box, which stalls)

Steps: awareness fix + rename, roster, 17-game season, music, progression, screens, demo, logo, commentary, kickoff, radio show, online, then
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
    ap.add_argument('--no-awareness', dest='awareness', action='store_false')
    ap.add_argument('--roster')
    ap.add_argument('--photos')
    ap.add_argument('--coach-photos')
    ap.add_argument('--progression', default='performance', choices=('stock', '2005', 'half', 'performance'))
    ap.add_argument('--no-music', action='store_true')
    ap.add_argument('--loadscreen')
    ap.add_argument('--startscreen')
    ap.add_argument('--demo-delay', type=int, default=86400000)
    ap.add_argument('--no-season17', dest='season17', action='store_false')
    ap.add_argument('--save-unlock', action='store_true')
    ap.add_argument('--no-playoffs7', dest='playoffs7', action='store_false')
    ap.add_argument('--playoffs7', action='store_true', help=argparse.SUPPRESS)   # the default now
    ap.add_argument('--optional-fullback', action='store_true')
    ap.add_argument('--free-agents')
    ap.add_argument('--classic-names')
    ap.add_argument('--player-stats')
    ap.add_argument('--schedule')
    ap.add_argument('--schedule-season')
    ap.add_argument('--commanders-logo')
    ap.add_argument('--commanders-commentary', action='store_true')
    ap.add_argument('--modern-kickoff', action='store_true')
    ap.add_argument('--any-number', action='store_true')
    ap.add_argument('--year', type=int)
    ap.add_argument('--radio-show', action='store_true')
    ap.add_argument('--online')
    ap.add_argument('--online-name')
    ap.add_argument('--online-lag-tolerant', action='store_true')
    ap.add_argument('--career-room', action='store_true', default=None)
    ap.add_argument('--no-career-room', dest='career_room', action='store_false')
    a = ap.parse_args()
    a.playoffs7 = a.playoffs7 and a.season17   # 7 teams need the 17-game season
    if not a.awareness and (a.season17 or a.save_unlock or a.optional_fullback or a.roster or a.modern_kickoff
                            or a.any_number or a.year or a.radio_show):
        print('the other default.xbe patches use the header page the awareness fix maps: keeping the fix')
        a.awareness = True
    for k in ('games', 'out', 'roster', 'photos', 'coach_photos', 'loadscreen', 'startscreen', 'classic_names', 'player_stats', 'schedule', 'commanders_logo', 'free_agents'):
        if getattr(a, k):
            setattr(a, k, os.path.abspath(getattr(a, k)))

    g09 = os.path.join(a.games, 'Madden NFL 09 (USA)')
    stock = os.path.join(g09, 'data')
    out_data = os.path.join(a.out, 'data')
    os.makedirs(out_data, exist_ok=True)
    P, R, L = (os.path.join(ROOT, d) for d in ('patches', 'roster', os.path.join('patches', 'loadscreen')))

    # 1. awareness fix, renamed for the dashboard
    xbe = os.path.join(a.out, 'default.xbe')
    if a.awareness:
        run(os.path.join(P, 'madden_awareness_fix.py'), os.path.join(g09, 'default.xbe'), xbe)
    else:
        shutil.copyfile(os.path.join(g09, 'default.xbe'), xbe)
    if a.title:
        run(os.path.join(P, 'set_xbe_title.py'), xbe, xbe, a.title)
    if a.season17:                        # offseason start follows the Pro Bowl, now a week later
        run(os.path.join(P, 'season17.py'), xbe, xbe)
    if a.save_unlock:
        run(os.path.join(P, 'save_unlock.py'), xbe, xbe)
    if a.playoffs7:
        run(os.path.join(P, 'playoffs7.py'), xbe, xbe)
    if a.optional_fullback:
        run(os.path.join(P, 'optional_fullback.py'), xbe, xbe)
    if a.roster:                          # the XBE's "Redskins" lookups follow the rename
        run(os.path.join(P, 'team_name_keys.py'), xbe, xbe)
    if a.modern_kickoff:                  # ball on the 35, touchbacks and out of bounds
        run(os.path.join(P, 'kickoff_spot.py'), xbe, xbe)
    if a.any_number:
        run(os.path.join(P, 'any_number.py'), xbe, xbe)
    if a.year:                            # years count from this one instead of 2008
        run(os.path.join(P, 'year_base.py'), xbe, xbe, str(a.year))
    if a.radio_show:                      # last: it grows the XBE's final section
        g07 = os.path.join(a.games, 'Madden NFL 07 (USA)')
        run(os.path.join(P, 'radio_show.py'), xbe, xbe, '--show', os.path.join(g07, 'default.xbe'))
        shutil.copyfile(os.path.join(g07, 'data', 'SPCHFEDT.dat'), os.path.join(out_data, 'spchfe07.dat'))
    if a.online:                          # after the rest: the order tested on the Xbox (release XBE + online.py)
        args = [os.path.join(P, 'online.py'), xbe, xbe, a.online]
        args += ['--name', a.online_name] if a.online_name else []
        args += ['--lag-tolerant'] if a.online_lag_tolerant else []
        print('> online.py', a.online, '...')
        subprocess.run([PY, *args], check=True, stdin=subprocess.DEVNULL)   # no name prompt
    elif a.online_name or a.online_lag_tolerant:
        raise SystemExit('--online-name and --online-lag-tolerant need --online SERVER')

    # 2. roster (template.dat, DB_TEAMS.dat, uis_plyr.dat, uis_coac.dat)
    if a.roster:
        with tempfile.TemporaryDirectory() as t:
            args = [os.path.join(R, 'build_roster.py'), a.roster, g09, t]
            if a.photos:
                args += ['--photos', a.photos]
            if a.coach_photos:
                args += ['--coach-photos', a.coach_photos]
            if a.free_agents:
                args += ['--free-agents', a.free_agents]
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
    if a.playoffs7:
        run(os.path.join(P, 'playoffs7.py'), tpl, tpl)

    # 2c. optional fullback: position minimums in template.dat (same size)
    if a.optional_fullback:
        tpl = os.path.join(out_data, 'template.dat')
        run(os.path.join(P, 'optional_fullback.py'), tpl if os.path.exists(tpl) else os.path.join(stock, 'template.dat'), tpl)

    # 2d. real stats for the roster's players (template.dat and the team DBs in DB_TEAMS.dat)
    if a.player_stats:
        tpl = os.path.join(out_data, 'template.dat')
        assert os.path.exists(tpl), '--player-stats needs a built roster (--roster)'
        teams = os.path.join(out_data, 'DB_TEAMS.dat')
        run(os.path.join(R, 'player_stats.py'), tpl, a.player_stats, tpl, '--teams', teams, teams,
            '--report', os.path.join(a.out, 'stats_report.csv'))

    # 2e. room for career rows in long franchises (template.dat's franchise DB; same size)
    tpl = os.path.join(out_data, 'template.dat')
    if a.career_room or (a.career_room is None and os.path.exists(tpl)):   # default: whenever template.dat is built
        run(os.path.join(P, 'career_room.py'), tpl if os.path.exists(tpl) else os.path.join(stock, 'template.dat'), tpl)

    # 2f. the 2026 coaches' real histories and the teams' real records (template.dat, DB_TEAMS.dat);
    # they only line up with a 2026 year base, so without --year and --schedule the old rows are cleared
    if a.roster:
        teams = os.path.join(out_data, 'DB_TEAMS.dat')
        if a.year and a.schedule:
            run(os.path.join(R, 'coach_history.py'), tpl, teams, a.schedule, '--year', str(a.year))
        else:
            run(os.path.join(R, 'coach_history.py'), tpl, teams, '--clear')

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

    # 6b. Commanders' menu logo and helmet (UNIFORMS.dat's LZH1 also runs the stock XBE's code)
    if a.commanders_logo:
        def current(name):
            f = os.path.join(out_data, name)
            return f if os.path.exists(f) else os.path.join(stock, name)
        run(os.path.join(P, 'team_logo.py'), stock, a.commanders_logo, out_data, '--teams',
            current('template.dat'), current('DB_TEAMS.dat'), current('strmdata.db'))
        run(os.path.join(P, 'team_helmet.py'), stock, a.commanders_logo, out_data, '--teams',
            current('template.dat'), current('DB_TEAMS.dat'))

    # 6c. Al Michaels says "Washington" for the Commanders
    if a.commanders_commentary:
        run(os.path.join(P, 'commentary_team.py'), stock, out_data)

    # 6d. modern kickoff: lineup and hold in the playbooks (LZH1 runs the stock XBE's code)
    if a.modern_kickoff:
        run(os.path.join(P, 'kickoff_setup.py'), os.path.join(stock, 'GAMEDATA.dat'),
            os.path.join(out_data, 'GAMEDATA.dat'), '--hold', '255', '--lineup', '--ball', '35')

    # 7. quick-load bundles: copy preloaded parts of every changed file
    for qkl in ('fe.qkl', 'game.qkl'):
        dst = os.path.join(out_data, qkl)
        run(os.path.join(P, 'qkl_sync.py'), os.path.join(stock, qkl), stock, out_data, dst)
        if filecmp.cmp(dst, os.path.join(stock, qkl), shallow=False):
            os.remove(dst)                # unchanged: no need to ship it

    if filecmp.cmp(xbe, os.path.join(g09, 'default.xbe'), shallow=False):
        os.remove(xbe)                    # nothing patched it: the stock one stays on the Xbox

    print('\noverlay ready in', a.out)
    if os.path.exists(xbe):
        print(f'  {"default.xbe":21} {os.path.getsize(xbe):>12,} bytes')
    for f in sorted(os.listdir(out_data)):
        print(f'  data/{f:16} {os.path.getsize(os.path.join(out_data, f)):>12,} bytes')


if __name__ == '__main__':
    main()
