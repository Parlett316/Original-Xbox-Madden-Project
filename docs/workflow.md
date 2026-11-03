# Workflow: building, installing and testing

The practical rules for working on these mods. Most of them were learned the hard way on real hardware.

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

    python tools/build_all.py --games . --out patched/build --roster roster/madden27.json \
        --photos roster/headshots_raw --progression performance --loadscreen my.png --startscreen my_start.png

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

## Testing a change

- **Bisect on the console.** If something breaks, restore one group of files at a time from the stock folder (UnleashX can copy between folders on the box) and retest:
  - music: `BGM.dat`, `strmdata.db`, `fe.qkl`
  - screens: `LOADDATA.dat`, `uis_fe.dat`, `fe.qkl`
  - roster: `template.dat`, `DB_TEAMS.dat`, `uis_plyr.dat`, `uis_coac.dat`
  - XBE: `default.xbe`

  Always test the untouched game too. The demo freeze above turned out to be stock behaviour.
- **Diagnostic builds.** When something fails in a way the code doesn't explain, build a small variant that separates the hypotheses. Example: a `strmdata.db` that lists one new track inside 09's own soundtrack and one 09 track inside a new soundtrack. That proved the problem was track numbers past 47, and led to the `fe.qkl` directory copy.

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

- `tools/xdis.py <xbe> <start> <end>` disassembles with string annotations. Use `--find "<text>"` for strings and their code references, and `--callers <VA>` for direct call sites.
- EA's DB queries are byte-reversed tags in SQL-like strings: `'YALP'` = `PLAY`, `'OSUM'` = `MUSO`. Search for the reversed tag to find the code that reads a table.
- Full-image Ghidra analysis of a 7 MB XBE timed out. capstone over targeted ranges was enough for everything here.
- Verify every writer against stock data first: rebuilding with no changes must reproduce the original bytes (`tdb.DB.resized({})`, `qkl_sync.py` with stock inputs, the awareness patcher's 09 output SHA-1 `3814c23e…`).
