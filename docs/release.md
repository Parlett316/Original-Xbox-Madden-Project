# Release v1.0 (2026-11-20)

The build that's on the Xbox, reproduced from the repository in one command. Every file below was compared byte for byte with the files on the Xbox before tagging (`spchfe07.dat` against Madden 07's `SPCHFEDT.dat`, which it copies).

## What's in it

- The 09 awareness fix and "performance" progression (production drives ratings).
- The Madden 27 roster with headshots, real overalls from the game's own formula, 97 extra free agents, and real stats for the last 5 seasons with career totals.
- The 2026 coaching staffs with photos, ratings by rank, real coaching histories since 1999 and every team's real 1999-2025 records.
- Modern team names (classic teams keep theirs), the Commanders' W on menus and helmets, and Al Michaels saying "Washington".
- The 17-game, 18-week season with 7-team playoffs; years counted from 2026, with 2026's real schedule in year 1.
- The modern kickoff, any jersey number in the edit screen, an optional fullback, more room for career stats, and loading of edited saves.
- All 154 music tracks, the Tony Bruno radio show from Madden 07, the Skins loading and start screens, and the dashboard name "Madden NFL 09 Modded".

## Build

Since 2026-11-22 the command's `default.xbe` differs from the release's in the 17-game cave (an out-of-range short jump on an error path, fixed; findings §15). Every data file is unchanged.

Needs the stock game folders (`Madden NFL 09 (USA)`, `Madden NFL 07 (USA)` for the radio show, `Madden NFL 2005 (USA)` for progression), the downloads listed in [workflow.md](workflow.md), and the personal art in `custom/` (not committed):

    python tools/build_all.py --games . --out patched/release_v1 --title "Madden NFL 09 Modded"         --progression performance --demo-delay 86400000 --career-room --modern-kickoff --any-number         --radio-show --year 2026 --optional-fullback --save-unlock --commanders-commentary         --commanders-logo custom/commanders_w.png --loadscreen custom/skins_screen_4x3.png         --startscreen custom/load_screen_640x480_skins.png --roster roster/madden27_week7.json         --photos roster/headshots_raw --coach-photos roster/coach_photos         --free-agents roster/free_agent_picks.json --player-stats nflverse_stats         --classic-names nflverse_rosters/classic_matches.csv --schedule nflverse_schedule/games.csv

## Install

Copy the stock game folder to a second folder on the Xbox, then copy these 19 files over it (binary FTP). Never delete the `data` folder: the overlay holds only changed files. Check every size after the upload. Delete any `Rost-` roster saves first, and start a new franchise.

| File | Size | SHA-1 |
|---|---|---|
| `default.xbe` | 7,782,400 bytes | `ef0fb12b53ae0136af2fa49af85b109515808bc5` |
| `data/BGM.dat` | 755,718,144 bytes | `479b2a626e88dfffad69eaf315a0826538b13865` |
| `data/DB_TEAMS.dat` | 2,616,832 bytes | `05cc368662a9907cd63d6cd70e7fc5592bba1be8` |
| `data/GAMEDATA.dat` | 4,518,272 bytes | `d31e6fea0fdbee42542d6ee5c16eb36643862417` |
| `data/LOADDATA.dat` | 2,337,152 bytes | `94dc69b663dfe7b70fb19795563dc36d3745b9f3` |
| `data/SOUNDDAT.dat` | 292,063,232 bytes | `0d33548591b6cd855bff5936b737b6d5e4da31ac` |
| `data/SPCHDATA.dat` | 155,363,328 bytes | `04d073afe619b52752c47c68d5b3aca4df7d5a21` |
| `data/UIS_TMLL.dat` | 5,129,856 bytes | `5f9b78d25ace9c51b84d5d34b964291730ee59d3` |
| `data/UNIFORMS.dat` | 193,114,624 bytes | `456192e462e1ad29cba2554cf84c1d14b22ffb32` |
| `data/fe.qkl` | 10,424,200 bytes | `663c020f1b404d1150cf56cc666276ca167786c4` |
| `data/game.qkl` | 15,884,437 bytes | `270ef90954f7c44e84f1ee38d1b0d0c7431dc657` |
| `data/spchfe07.dat` | 228,714,976 bytes | `d689a7e425f09c83ceb3e463e8a07b2725c1ccec` |
| `data/strmdata.db` | 5,176,208 bytes | `9c82ce7e7782802ac1ce32fdd96df56fb08634b4` |
| `data/template.dat` | 2,165,760 bytes | `7fc1c6333ed50837d5cf23e25c3a4a04d0eff844` |
| `data/uis_all.dat` | 10,343,652 bytes | `5d5a83bda965cb08769a990142c4d5c4a8c0f895` |
| `data/uis_coac.dat` | 4,283,840 bytes | `7474a89ba350565be8f3a39429b35fdd132b04bf` |
| `data/uis_fe.dat` | 4,155,008 bytes | `a215f20c95755c830324e5e7efe028da7dbaf9f5` |
| `data/uis_plyr.dat` | 59,089,344 bytes | `a3e9eda23fa6d5c2fda8cee5b0a232d0f1e83896` |
| `data/uis_tmlo.dat` | 1,640,064 bytes | `ff6db561d31dbb5444653fae3566fac4e52e49e4` |

Total: 1,760,521,329 bytes.
