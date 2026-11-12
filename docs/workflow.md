# Workflow: building, installing and testing

The practical rules for working on these mods. Most of them were learned the hard way on real hardware.

## Starting a new chat

Copy this in to pick up where the last chat stopped, and change the last line:

```text
Read CLAUDE.md and docs/outstanding.md first. Only open other docs when the task needs them: search findings.md, formats.md and roadmap.md for the part you need rather than reading them whole. Don't re-derive what they already record.

To save tokens:
- Use tools/ scripts and existing saves before writing new analysis.
- Limit command output, and run long builds and sims in the background.
- Take xemu screenshots only at the steps that matter.
- Don't spawn subagents unless I ask.
- Keep replies short, and tell me when you need the Xbox tested.

When something's finished, update docs/outstanding.md.

Today's task: <what to do, or "tell me what's next">
```

Starting a new chat for each big task also saves tokens, because a long chat's history is resent with every message. `docs/outstanding.md` is what makes that safe: keep it current before ending a chat.

## Working folder layout

The scripts expect the extracted games next to the repository folders (or pass paths explicitly):

```
MaddenProject/
  Madden NFL 2005 (USA)/   DATA/...          (uppercase names on this disc)
  Madden NFL 06 (USA)/     DATA/...
  Madden NFL 07 (USA)/     data/...
  Madden NFL 08 (USA)/     data/...
  Madden NFL 09 (USA)/     default.xbe, data/...   <- never modified
  patches/  roster/  tools/  docs/
  patched/                 build output (ignored by git)
```

Stock game folders are read-only inputs. Every script writes to a separate output path.

## Build

Everything at once:

    python tools/build_all.py --games . --out patched/build --roster roster/madden27_week7.json \
        --photos roster/headshots_raw --coach-photos roster/coach_photos \
        --classic-names nflverse_rosters/classic_matches.csv --schedule nflverse_schedule/games.csv \
        --commanders-logo custom/commanders_w.png --loadscreen my.png --startscreen my_start.png

This full command, without the two screens, reproduced the hardware-tested files byte for byte (2026-11-04). `custom/` holds personal art and is never committed.

7-team playoffs are on by default with the 17-game season (`--no-playoffs7` opts out). Optional additions, each working on hardware: `--save-unlock` (load edited saves), `--commanders-commentary` (Al Michaels says "Washington"; adds 447 MB of files to the overlay), and `--free-agents roster/free_agent_picks.json` (97 extra free agents; make the file first with `python roster/pick_free_agents.py roster/madden26_superbowl.json roster/madden27_week7.json roster/free_agent_picks.csv`). `--modern-kickoff` (ball on the 35, hybrid lineup and hold, touchbacks to the 35, out of bounds to the 40) works on hardware too. `--any-number` (any jersey number at any position in the edit screen) works on hardware as well. `--radio-show` (Madden 07's Tony Bruno show in the franchise menus, once per week) works on hardware; it needs `Madden NFL 07 (USA)` in the games folder, makes `default.xbe` 16 KB larger and adds `data/spchfe07.dat` (229 MB). `--player-stats nflverse_stats` (real stats for the last 5 seasons and career totals; download nflverse's `players.csv` and `stats_player_reg_1999.csv` to `_2025.csv` into that folder first) works on hardware. `--year 2026` (the game counts its years from 2026 instead of 2008) is tested in xemu only. `--optional-fullback` (a team can carry no fullback) is partly tested on hardware; see [outstanding](outstanding.md). Before testing a roster, delete any `Rost-` save folders on the Xbox, because they override `template.dat`.

Or step by step. The commands are in each component README ([patches](../patches/README.md), [roster](../roster/README.md), [loadscreen](../patches/loadscreen/README.md)). After changing any data file by hand, always re-run `patches/qkl_sync.py` for `fe.qkl` and `game.qkl`; see the rules below.

## Install on the Xbox

The user's setup is a softmodded Xbox with the UnleashX dashboard, with files sent over FTP on Ethernet.

1. Copy the stock game folder to a second folder on the hard drive, for example `E:\Games\Madden NFL 09 Modded\`.
2. Copy the overlay (`default.xbe` + `data/…`) over it. Replace only the listed files; never delete the `data` folder, since the overlay holds only the changed files.
3. Check file sizes after upload. A truncated `BGM.dat` (756 MB) is easy to miss.
4. Use binary transfer mode.

## Rules that bite

1. **Quick-load bundles.** `data/fe.qkl` and `data/game.qkl` keep copies of some files' headers and archive entries, and the game reads those copies at startup instead of the files. Patch a file whose preloaded part changes without syncing the bundle, and the game half-ignores the patch: the new start screen doesn't show, and new music tracks stay silent. Always run:

       python patches/qkl_sync.py <stock fe.qkl> <stock data dir> <patched data dir> <out fe.qkl>

   (and the same for `game.qkl`). It reproduces the stock bundle exactly when nothing changed. `build_all.py` does this automatically.
2. **Matching file sets.** These must come from the same build:
   - `template.dat`, `DB_TEAMS.dat` and `uis_plyr.dat` (photo numbers are assigned per build)
   - `BGM.dat` and `strmdata.db` (song entries point into BGM.dat), plus the synced `fe.qkl`
3. **The memory-card roster wins.** If a roster save (`Rost-Rost1`, title `4541023b`) is on the memory card or hard drive, Madden auto-loads it instead of the default roster in `template.dat`. To use a built roster, move that save off.
4. **2008 vs. modern roster photos.** The modern roster reuses the 2008 players' photo slots in `uis_plyr.dat`. With the modern photo file installed, a 2008 roster save shows wrong faces in menus. For the 2008 roster, use the stock `template.dat`, `DB_TEAMS.dat` and `uis_plyr.dat`.
5. **The Z: cache.** The game copies 36 data files (template.dat, strmdata.db, uis_plyr.dat, the qkl bundles…; not BGM.dat) to the hard drive's cache partition and refreshes them when the source changes. That's been reliable; nothing needs clearing by hand.
6. **The EA Trax playlist lives in the profile.** Switching back to a `strmdata.db` without the extra songs, while the profile has them enabled, makes the now-playing banner show garbage. Turn the extra songs off first, or use another profile.
7. **The attract-mode demo can hard-lock.** Pressing a button to leave the demo freezes the console. This also happens on the untouched stock game, so it isn't caused by any of these mods. The build delays the demo by 24 hours (`--demo-delay`); if you ship `uis_all.dat`, ship `fe.qkl` with it.
8. **Don't change a TERF entry's size in place.** The game finds most entries by adding up directory sizes, so a shorter entry breaks later entries that were never edited. Keep the stock size and pad with zeros ([formats](formats.md#terf-archives-dat-asset-files)).
9. **Leaving a custom file out doesn't remove it from the Xbox.** An overlay holds only changed files. To go back to a stock screen, copy the stock `LOADDATA.dat` and `uis_fe.dat` over the custom ones and upload the new `fe.qkl`.
10. **Base a test overlay on the current build.** A test file from an older build quietly replaces newer work on the console. Helmet tests based on a pre-17-game `template.dat` removed the 17-game data until it was restored. Compare sizes with a full build first (`template.dat` is 2,161,408 bytes with the 17-game season and 2,160,320 without).
11. **Franchises keep the data they were created with.** New `TUNI` rows don't reach an existing franchise, so classic Redskins teams in it keep pointing at the uniforms that now have the W.

## Testing a change

- **Bisect on the console.** If something breaks, restore one group of files at a time from the stock folder (UnleashX can copy between folders on the box) and retest:
  - music: `BGM.dat`, `strmdata.db`, `fe.qkl`
  - screens: `LOADDATA.dat`, `uis_fe.dat`, `fe.qkl`
  - roster: `template.dat`, `DB_TEAMS.dat`, `uis_plyr.dat`, `uis_coac.dat`
  - XBE: `default.xbe`

  Always test the untouched game too. The demo freeze above turned out to be stock behaviour.
- **Diagnostic builds.** When something fails in a way the code doesn't explain, build a small variant that separates the hypotheses. Example: a `strmdata.db` that lists one new track inside 09's own soundtrack and one 09 track inside a new soundtrack. That proved the problem was track numbers past 47, and led to the `fe.qkl` directory copy.

## Testing in xemu

xemu is a quick first check before an FTP upload. A pass doesn't replace the Xbox: timing, disc and drive speed, and graphics all differ.

1. Pack an image, which only reads its inputs: `python tools/make_xiso.py pack "<game folder>" "<overlay>" out.iso`, then `python tools/make_xiso.py verify out.iso "<game folder>" "<overlay>"`.
2. Boot it with a modded BIOS such as Complex 4627. An untouched XBE signature check would reject our XBE.
3. To keep your own setup separate, copy `xemu.toml` and the `.qcow2` drive, point the copy at them, and run `xemu.exe -config_path <copy.toml>`. The game writes its cache and saves to the drive. xemu rewrites its config when it exits, so check the settings before each run.

To drive it from a script (tested on xemu 0.8.139), use `tools/xemu.py`: `setup` makes a work folder with its own config, drive and EEPROM, then `boot`, `keys` (key presses, waits and screenshots, with a contact sheet), `hmp`, `flush`, `snap` (copy the newest franchise save), `quit`, and `ram`/`break` over the gdb stub. What it relies on:

- Set `port1 = 'keyboard'` under `[input.bindings]`. A/B/X/Y are their own letter keys, Enter is Start, and the arrows are the D-pad.
- Post `WM_KEYDOWN` and `WM_KEYUP` to the xemu window. It doesn't need focus. Hold a key for about 0.1 s, because 0.25 s can move a menu two steps.
- Take screenshots with `PrintWindow`. This build's QMP has no `screendump`. If they come back black, the display may be asleep: a one-pixel mouse nudge brings it back.
- Add `-qmp tcp:127.0.0.1:44444,server,nowait` to read the status and to close that one instance with `quit`. The PID listening on the port identifies its window.
- `tools/xbox_hdd.py` lists, copies and overwrites files on the drive image, so saves can move without FTP. It can read while xemu runs, but send the monitor command `qemu-io ide0-hd0 flush` first (`human-monitor-command` over QMP); otherwise a new file reads as zeros. Close xemu before `put`, and boot again before loading what you wrote.
- Franchise menus: from the root menu, My Week → Play Week → Weekly Schedule. Press `Y` to untick your game, or Simulate Week stops at it, but not in a week your team doesn't play, because `Y` then ticks another game. Start opens Play/Simulate, where Simulate Week is the fourth item (the Super Bowl and Pro Bowl menus have three items, and Simulate Game is the third). Allow about 2 s between menu moves. Week 6 asks about the trade deadline once, and after 8 saves the last slot has to be overwritten.

## Jumping a franchise to a later week

To test the end of a season without simming it:

    python tools/save_jump.py Fran-Fran1 Fran-Fran1.jumped --week 18
    python tools/save_jump.py Fran-Fran1.jumped --show

The save must already be in the regular season, and the XBE must be built with `--save-unlock`. The file stays 1,490,944 bytes. Back up the save, then upload the output over the original under its original name (`Fran-Fran1`), because the save's name is checked and the jump keeps it. A save folder holds one save plus its `SaveMeta.xbx` (which names it) and `saveimage.xbx`, and the folder name depends on the save's name: `Fran-Fran2` goes in `18E7386A51EA`, not `Fran1`'s `18E7386A51E9`. In the wrong folder or alongside another save, the game showed it as a damaged "???" save on hardware. Sim the last regular-season week to get the playoffs. Scores for skipped weeks are made up, and player stats stay empty, so this suits schedule, playoff and offseason-entry tests, not progression or awards.

An overlay holds only changed files. Leaving out `--loadscreen` or `--startscreen` puts the stock screen in an image, but on an Xbox that already has custom screens you must also copy the stock `LOADDATA.dat` and `uis_fe.dat` over them and upload the new `fe.qkl`.

## Franchise progression tests

Used to compare progression tables. The setup that gives a clean comparison:

1. Same awareness-fixed XBE and same starting roster (the 2008 roster save on the memory card) for every run.
2. Only `strmdata.db` differs between runs. The user runs tests from the "original" game folder, with the awareness XBE (unrenamed) and the test `strmdata.db` copied in, and stock roster files.
3. Sim everything, the same way each time, and save right after each Super Bowl (week 21) for two seasons.
4. Copy the save folder (`E:\UDATA\4541023b\…`) to the PC, one folder per snapshot, and compare:

       python tools/franchise_report.py MemoryCard/I/4541023b/F02F301C3DB7/Rost-Rost1 \
           "stock=FranchisePreseasonYear2/.../Fran-Fran1,FranchisePreseasonYear3/.../Fran-Fran1" \
           "perf=FranchisePerfYear2/.../Fran-Fran2,FranchisePerfYear3/.../Fran-Fran2"

   It reports the rating spread (90+/95+/99 counts), season-2 changes by overall group, and whether starters' progression follows their production (top vs. bottom third at their position).

Within a franchise, player IDs (`PGID`) are stable. The franchise renumbers everyone at creation, so compare against the starting roster by name and position, or only in totals.

## Reverse-engineering tips

- `tools/xdis.py <xbe> <start> <end>` disassembles with string annotations. Use `--find "<text>"` for strings and their code references, and `--callers <VA>` for direct call sites. `tools/xcallers.py` finds call sites of unaligned library functions, `tools/xrefs.py` every mention of an address, and `tools/spch_trace.py` logs speech events from a game running in xemu.
- EA's DB queries are byte-reversed tags in SQL-like strings: `'YALP'` = `PLAY`, `'OSUM'` = `MUSO`. Search for the reversed tag to find the code that reads a table.
- Full-image Ghidra analysis of a 7 MB XBE timed out. capstone over targeted ranges was enough for everything here.
- Verify every writer against stock data first: rebuilding with no changes must reproduce the original bytes (`tdb.DB.resized({})`, `qkl_sync.py` with stock inputs, the awareness patcher's 09 output SHA-1 `3814c23e…`).
