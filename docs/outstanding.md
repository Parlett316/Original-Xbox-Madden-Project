# Outstanding work

A running checklist of what's still open, so work can pick up in a new chat. Last updated 2026-11-20. Background and addresses are in [roadmap.md](roadmap.md) and [findings.md](findings.md). Tick items off or delete them as they're done.

## Waiting on an Xbox test

**Release v1.0 (2026-11-20).** [release.md](release.md) has the command, which reproduces every file on the Xbox byte for byte, and the install list. Tagged `v1.0`. Next: play it as a long franchise on the Xbox (years 5 to 10, a user-run team).

**Real coaching histories and team records: work on the Xbox (2026-11-20).** The user saw wacky coach histories: each 2026 coach had taken over his slot's coach ID and with it the 2008 coach's seasons (Reid, in the Chiefs slot, had Herm Edwards' Jets and Chiefs years; Sirianni had Reid's Eagles years), and every team's records were 1977-2006 shown under shifted years. `roster/coach_history.py` (run by `build_all.py` after the roster) now writes `OCIS`, who held each role for a team each season, from `CAREERS`: every 2026 coach's NFL seasons since 1999 as head coach or coordinator, checked on the web for the special teams coordinators and 2025 jobs. It also writes `OTRS`, each team's real 1999-2025 record (playoff games included, as in the rows the game writes) and postseason result, from nflverse's schedule. The old 2008 coaches' rows are gone. This needs `--year 2026` and `--schedule`; without them the build just clears both tables. The Texans' team DB grew (its history table held 9 rows; it needs 24), so `DB_TEAMS.dat` is 64 bytes larger. Against `coach_test` only `OCIS` (template.dat and every team DB) and `OTRS` differ; `fe.qkl` stays `663c020f…`. Copy these two from `patched/Madden NFL 09 (USA)/history_test/data/`:

| File | Size | SHA-1 |
|---|---|---|
| `data/template.dat` | 2,165,760 bytes | `7fc1c6333ed50837d5cf23e25c3a4a04d0eff844` |
| `data/DB_TEAMS.dat` | 2,616,832 bytes | `05cc368662a9907cd63d6cd70e7fc5592bba1be8` |

Start a new franchise. To undo, copy back `coach_test`'s two files.

- [x] **Coach history screens (the user, 2026-11-20, first version):** Reid (Chiefs, 3 trophies), John Harbaugh (Ravens, 1) and Dan Quinn (Commanders, Cowboys DC, 1 for Seattle 2013 as DC) look right after a simmed 2026. The game's own 2026 rows counted playoff games (Reid 11-8, Harbaugh 9-9) while the first version's history didn't, so the records now include them; only `DB_TEAMS.dat`'s `OTRS` changed.
- [x] **Records with playoffs (the user, 2026-11-20):** they look right. Reid's 2023 should read 15-6 and 2024 17-3; Harbaugh's 2012 14-6.
- [x] **A team's history:** the years and records should be real (Eagles 2024: 18-3 with the playoffs, won the Super Bowl).
- [ ] **After a season:** the game adds its own row for 2026, and nothing old disappears early.

**Coach ratings by rank (2026-11-20).** Coach ratings become game-day bonuses ([findings §13](findings.md#13-overalls-coaches-and-qb-awareness-09)), and the 2026 coaches had kept their 2008 slots' ratings. `roster/coach_ratings.py` (run by `build_roster.py`) keeps 09's spread per role and hands it out by rank: each coach gets the whole rating row of the stock coach at the same rank. Head coaches rank by career win % (shrunk toward .500, plus playoff and Super Bowl wins), with the row's best numbers on their side of the ball (offense or defense, and the top 4 position ratings on their side's positions, kickers and punters last); coordinators by their 2025 unit's points rank (scored or allowed), new coordinators in the middle. Special teams coordinators and Bowles's DC slot keep their ratings. `python roster/coach_ratings.py "Madden NFL 09 (USA)/data/template.dat"` prints the plan. Against `ovr_test` only the 16 `COCH` rating fields differ; `fe.qkl` stays `663c020f…`. The full command (the "Everything" preset plus `--optional-fullback --save-unlock`) now gives the Xbox's XBE byte for byte. Copy these two from `patched/Madden NFL 09 (USA)/coach_test/data/`:

| File | Size | SHA-1 |
|---|---|---|
| `data/template.dat` | 2,165,760 bytes | `f34a4124f8e29ad8c15be72a9fee883b307aa893` |
| `data/DB_TEAMS.dat` | 2,616,768 bytes | `394036964c47b60dc853ac6d45c55c3ac07a4ba1` |

Start a new franchise. To undo, copy back `ovr_test`'s two files. (First version, 2026-11-20: head coaches' position ratings came straight from the stock row, so Ben Johnson showed QB 50 and LB 85; the user caught it on the staff screen.)

- [ ] **Coaching staff screens:** Reid, Payton and McVay should be near the top in knowledge and offense; Josh McDaniels and Grant Udinski top offensive coordinators; Aden Durde, Matt Burke and Vance Joseph top defensive coordinators; Tommy Rees and Al Golden near the bottom.
- [ ] **Play or sim a game:** nothing should look different apart from small rating bonuses in the game.

**Game overalls in the roster, three free agents swapped: work on the Xbox (2026-11-20).** `build_roster.py` now writes the game's own overall (findings §13) instead of EA's, so the Rosters screen and the free agents show what a franchise shows, with no jump at week 1. Depth charts and contracts are unchanged. Autry, Poyer and Mixon are out of the free agents; Benson, Ogbah and Wilson are in. Against the files on the Xbox (`career_room_test`, `player_stats_test`) only `POVR`, those six players, the stats rows that move with them, and the added free agents' looks and IDs differ. `fe.qkl` synced against the full set on the Xbox stays `663c020f…`, so it doesn't change. Built with the full `build_all.py` ("Everything" plus `--optional-fullback`; the XBE also needs `--save-unlock` to match the Xbox's). Copy these two from `patched/Madden NFL 09 (USA)/ovr_test/data/`:

| File | Size | SHA-1 |
|---|---|---|
| `data/template.dat` | 2,165,760 bytes | `e71dcebf02568cacbce3e5678a284dc9357e24aa` |
| `data/DB_TEAMS.dat` | 2,616,768 bytes | `d70691ca013930187b4ed7496151cf8d2c6a58b7` |

Delete any `Rost-` saves first. To undo, copy back `career_room_test/data/template.dat` and `player_stats_test/data/DB_TEAMS.dat`.

- [x] **Rosters screen (the user, 2026-11-20):** Daniels shows 87 (was 81).
- [x] **Free agents (the user, 2026-11-20):** Benson, Ogbah and Wilson are listed in a new franchise; Autry, Poyer and Mixon aren't.
- Noted: the XBE on the Xbox (`year_test`) also has `--save-unlock` (one byte at `0x5cf05`); add it to the full command to reproduce that XBE. This build's XBE isn't part of the install.

**Build window (2026-11-13).** `python tools/build_gui.py` opens a window of tick boxes and file lines that runs `build_all.py`: presets "Screens only", "Modern rules", "Fixes, no roster" and "Everything", a log, and the file list with sizes at the end. It asks before emptying an output folder that holds an earlier build, because `build_all.py` builds on files it finds there. For small builds `build_all.py` gained `--no-awareness` and `--title ""`, and it leaves `default.xbe` out when nothing patched it. The 17-game season, playoffs, kickoff, numbers, fullback, save, year, radio and roster patches use the header page the awareness fix maps, so the fix stays in with any of them. From the command line, a screens-only build gave three files (`LOADDATA.dat` and `uis_fe.dat` identical to `skins_screens_test`, plus `fe.qkl`), and a rules-only build gave `default.xbe`, `GAMEDATA.dat`, `template.dat`, `strmdata.db` and `fe.qkl`.

- [ ] **Press Build in the window:** the window opens and its presets give the right commands, but the Build and Stop buttons haven't been clicked.
- [ ] **A partial build on the Xbox or in xemu:** none has been booted. Only the full build's combination is hardware-tested; a screens-only build goes over a stock game, not over the modded one (its `fe.qkl` is synced against stock files).

**More room for career stats: works on the Xbox (2026-11-20), now the default** (`--no-career-room` opts out; it's applied whenever the build writes `template.dat`). `build_all.py` (`patches/career_room.py`) raises the franchise's career defense table `PCDE` from 1,550 to 2,400 rows and `PCNG` (career games) from 2,100 to 2,400. A full `PCDE` used to leave players with no career defensive totals from about year 5, and real stats start it at 821. In xemu a year 5 franchise went past 1,550, every missing career row was filled in, and it simmed through the playoffs, the Pro Bowl and the CPU draft with each save reloading ([findings §11](findings.md#11-long-franchises-and-full-tables-09)). The save keeps at least 97 KB of spare room (at the Pro Bowl). Test file: copy one file from `patched/Madden NFL 09 (USA)/career_room_test/data/`. It's the `player_stats_test` file with 12 bytes changed, and `fe.qkl` stays the same (synced against the full set on the Xbox, it gives the `663c020f…` already there). Only a new franchise gets the room; delete any `Rost-` saves first. To undo, copy back `player_stats_test/data/template.dat`.

| File | Size | SHA-1 |
|---|---|---|
| `data/template.dat` | 2,165,760 bytes (same size as the one it replaces) | `8bde99a6530ff5fa2e20be52357cb3f2e2070f42` |

- [x] **New franchise in xemu (2026-11-18):** on a full build with `--career-room` (plus stats, `--year 2026` and save unlock), a new franchise saved and reloaded at training camp, the end of the regular season, the Pro Bowl and after the draft, and again at the end of year 2's regular season. `PCDE` went 781 → 1,270 → 1,448, so the stock 1,550 would fill in year 3. The fullest save had about 100 KB spare.
- [x] **On the screen (xemu, 2026-11-18):** a CB whose career row is past the old limit (row 1,565) shows the right career totals on his player card.
- [x] **Full build (2026-11-18):** `build_all.py --career-room` ran step 2e after the stats, and both tables are 2,400 with checksums verified.
- [x] **Years 2 to 6 in xemu (2026-11-18):** the same franchise simmed to the year 6 Pro Bowl, with a save and reload each year. `PCDE` levelled off at 1,651 of 2,400 from year 5, `PLAY` at 2,635, and the save's spare room stayed 100,667 bytes every year ([findings §11](findings.md#11-long-franchises-and-full-tables-09)). Nothing points to a problem in making it the default after the Xbox check.
- [x] **New franchise on the Xbox (the user, 2026-11-20):** saves and reloads worked after simming week 1, after the Pro Bowl and at the start of the next season. Terry McLaurin's career receptions went 498 → 501 → 559 → 564, matching each new season row.

**Real player stats: work on the Xbox (2026-11-12), off by default.** `build_all.py --player-stats nflverse_stats` (`roster/player_stats.py`) gives the roster's players their real stats: a row for each of the last 5 seasons (2021 to 2025) and career totals since 1999, from nflverse's `players.csv` and `stats_player_reg_YYYY.csv` (downloaded by hand to `nflverse_stats/`, not committed). Of 1,747 players with a year or more in the league, 1,660 have stats, 81 matched but never played, and 6 weren't matched; rookies stay blank. Players are matched by name, then age, position, team and number, and `stats_report.csv` lists each one. Row counts stay under the franchise's table limits (`PCDE` 821 of 1,550, `PCNG` 1,660 of 2,100, `PCKP` cut to 250 of 325). A new franchise takes its stats from each team's own DB in `DB_TEAMS.dat`, and `template.dat`'s copy only feeds the main menu's Rosters screen, so the script writes both (`--teams`). The first test build changed `template.dat` alone, and on the Xbox every stat in a new franchise read N/A (the user, 2026-11-12). In xemu, with both files, Caleb Williams's card shows 3,541 yards and 20 touchdowns, then 3,942 and 27, at the main menu and inside a new franchise. Copy these from `patched/Madden NFL 09 (USA)/player_stats_test/data/`, built on the current build (`radio_build`, whose roster files are `any_number_test`'s). Delete any `Rost-` saves first and start a new franchise.

| File | Size | SHA-1 |
|---|---|---|
| `data/DB_TEAMS.dat` | 2,616,832 bytes (25,152 larger than before) | `c00c416eb34e0374471a1bd81de61e8bfb47feea` |
| `data/template.dat` | 2,165,760 bytes (4,288 larger than before; unchanged since the first test) | `a7b6bd6cbe99feae45eddde76f6d6fe1a684e2a5` |
| `data/fe.qkl` | 10,424,200 bytes (same size as the one it replaces) | `663c020f1b404d1150cf56cc666276ca167786c4` |

The first `fe.qkl` (`f5cca0f7…`) put the stock Favre start screen back on the Xbox (the user, 2026-11-12): it was synced against `radio_build`, which has no custom screens or commentary files, and `fe.qkl` carries part of `uis_fe.dat`. This one is synced against `modern_kickoff_build/data`, the full set on the Xbox (its own `fe.qkl` and `game.qkl` are reproduced from it), with the two stats files swapped in. `game.qkl` doesn't change.

- [x] **Player cards on the Xbox (the user, 2026-11-12):** stats show in a new franchise. Offensive linemen show none: their tables (`PSOL`, `PCOL`: pancakes and sacks allowed) are empty, because nflverse has no such totals.
- [x] **A simmed season (the user, 2026-11-12):** the new season's stats added to the real career totals.
- [x] **Full build (2026-11-12):** `build_all.py` with the usual roster options and `--player-stats` gave the tested `DB_TEAMS.dat` byte for byte, and a `template.dat` that differs only in the fullback minimums (the tested one was built with `--optional-fullback`).
- [x] **Tony Bruno (the user, 2026-11-12):** silent for a while after the new `fe.qkl` went on, and fine once the five files were checked by size (`year_test/default.xbe`, the three `player_stats_test` files, `spchfe07.dat`). Which file was wrong isn't known. In xemu the same set had started the show in a new franchise (state `0x81d538`: playing flag set, segment index 2, 4, 5 over two minutes).
- [x] **Years, on the Xbox (the user, 2026-11-12):** a franchise went into its next season with the stats carried on and the current year shown. Fixed in xemu first (2026-11-12) with `build_all.py --year 2026` (`patches/year_base.py`, off by default). The XBE adds 2008 to a season number at 25 places and 2007 at one; the patch changes those constants. In xemu Caleb Williams's rows read 2024 and 2025, and preseason week 1 is "Thu Aug 6", which is right for 2026. The seven `cmp reg, 2008` stay: they give 2008 its opening Thursday (the first of September) and every other year the second. Existing franchises show the new years too, because saves hold season numbers. Test file: `patched/Madden NFL 09 (USA)/year_test/default.xbe`, 7,782,400 bytes (same size as the one it replaces), SHA-1 `ef0fb12b53ae0136af2fa49af85b109515808bc5`, which is the current XBE (`radio_build`) with 26 bytes changed. To undo, copy back `radio_test/default.xbe`. Check a player card's years, the "Year" label and the schedule's dates, then sim a season into the offseason.
- [x] **Career tables fill sooner:** `PCDE` starts at 821 rows instead of 0, so it would reach 1,550 earlier than year 5. The career room, now the default, gives it 2,400.
- [x] **Leftover 2024 rows on rookies (xemu, 2026-11-20): not shown.** Retired or cut players' preloaded `PSNG` rows stay until the full table drops that season, and their `PGID`s are reused (stock does the same: 2 rookies in `FranchisePreseasonYear2`). By year 6, 8 rookies held one, but Terrence Dillon's card (Colts LT, rookie, leftover row of 14 games in 2024) shows only 2031 with N/A and career 0, on the Games view too. Nothing to fix.
- Not filled: longest plays, field goals by distance, the linemen's pancakes and sacks allowed (nflverse has no season totals), and `PICO`.

**7-team playoffs by default, with older franchises kept at 6 (2026-11-08, xemu).** `build_all.py` now builds 7-team playoffs unless given `--no-playoffs7`. The XBE reads the franchise's wild-card game count (`SEAI.SNWP`), so a franchise created before the 7-team build gets stock's 6-team postseason instead of sticking after week 18 ([findings §8](findings.md#8-season-structure-and-playoffs-09)). In xemu, a franchise created on a 6-team `template.dat` and jumped to week 18 got 4 Wild Card games and reached the Pro Bowl, and a 7-team one got 6 and reached the Super Bowl. Copy this one file from `patched/Madden NFL 09 (USA)/playoffs_guard_test/`. It's the current build's XBE (`any_number_test`) with the new `playoffs7.py`.

| File | Size | SHA-1 |
|---|---|---|
| `default.xbe` | 7,766,016 bytes (same size as the one it replaces) | `b251ae75dffe8c10ae4cc0a14cf022f6c8197227` |

- [x] **New franchise on hardware (the user, 2026-11-12):** the playoff bracket works. Whether a playoff game was played to the end by hand isn't recorded.
- **Older franchises:** checked in xemu only, and not worth a hardware test (the user, 2026-11-08). The fallback just keeps any old franchise from sticking.
- [x] **An older franchise's next season (xemu, 2026-11-12):** it becomes a 7-team franchise. `Save Files/Season4Works` (year 4 offseason, `SCHD` 284 of 285) on the current build went through the offseason and preseason to year 5, week 1 with no hang: `SCHD` 286 of 287, 17 games per team, 6 Wild Card rows, `SNWP` 6. The season's tables are remade from `template.dat`, so the 285-row table was never the limit ([findings §8](findings.md#8-season-structure-and-playoffs-09)). Not done: simming that season's playoffs (`Save Files/OldFranchiseYear5Week1` is the week 1 save).
- **Review (2026-11-09):** `playoffs_guard_test/default.xbe` differs from `any_number_test` only in the cave (`0x10b40`-`0x10d1c`) and the three patched sites, and the patch chain with `--save-unlock` and `--optional-fullback` rebuilds it byte for byte. The cave's stack use, the `SNWP` slot at `0x41b566` and the stub's buffer were checked against the disassembly. `playoffs7.py` now stops its cave at `0x10e80`, where `kickoff_spot.py`'s begins.

**Modern kickoff: works on the Xbox (2026-11-08), now `build_all.py --modern-kickoff`.** The ball is on the 35 (a safety kick stays on the 20). Kickoff touchbacks come out to the 35 and punts' stay on the 20. A kick out of bounds draws the penalty and goes to the receiving 40. Everyone, CPU kickers included, holds in the NFL's hybrid lineup until the receiving team touches the ball, with the returners stacked as in stock. A human-controlled kicker can't move before then either. Details are in [findings §7](findings.md#7-tuning-table-survey-09). The full build with the usual options plus `--modern-kickoff` reproduced every hardware-tested file byte for byte (2026-11-08): `default.xbe` and `GAMEDATA.dat` match `kickoff35_test3`, and the other 16 files match the earlier tested builds.

| File | Size | SHA-1 |
|---|---|---|
| `default.xbe` | 7,766,016 bytes | `6b7266ab6de5497a0d0e961631c3d3562a4c444c` |
| `data/GAMEDATA.dat` | 4,518,272 bytes | `d31e6fea0fdbee42542d6ee5c16eb36643862417` |
| `data/fe.qkl` | 10,424,200 bytes | `12b01c5770c5eee103d8d69f6f668c5fa607a9ac` |

- **Landing short of the receiving 20: dropped (2026-11-20).** In 09 a normal kickoff never lands short. Even at kick power 5 it carries about 44 yards, and a returner always catches it in the air. There's no squib play, and onside kicks (about 18 yards) are exempt anyway. A patch that flagged a short landing as the kickoff out of bounds penalty worked in xemu but was taken out. How it worked is in [findings §7](findings.md#7-tuning-table-survey-09) ("The ball object and its landing"), if it's ever wanted.
- [x] **CPU catch in the end zone (2026-11-08):** it wasn't a fair catch. The CPU returner caught the ball, everyone moved after the catch (the hold worked), and he knelt for a touchback.
- [x] **Untouched in the end zone (xemu, 2026-11-20):** a kick that lands in the end zone and bounces out untouched is a touchback at the 35.
- [ ] **Lands short of the goal line, then into the end zone:** goes to the 35, where the 2025 rule says the 20 (xemu, 2026-11-20: landed on the receiving 1, bounced out the back). Only happens if you run your returner away from the ball; a CPU returner always catches. Fixable by recording the landing spot in the ground-contact hook ([findings §7](findings.md#7-tuning-table-survey-09)); not done unless wanted.
- [x] **Penalties carried to a kickoff (code reading, 2026-11-20):** they're added to the new 35 (15 yards puts the kick on the 50). After such a moved kick, a touchback goes to the 20 instead of the 35, because the touchback cave only recognises a kick from exactly the 35. Rare; not fixed. Penalties during the return are enforced from the spot of the foul by stock code the patch doesn't touch (not seen in a test).
- [x] **Blockers (xemu, 2026-11-20):** return blockers and coverage engage around the 30.
- [ ] **Known quirk:** the kicking team drifts about a yard toward the sidelines during the kicker's motion, visible only in replays. Turning them doesn't remove it.

**Any number and uncapped free agents: work on the Xbox (2026-11-08).** `build_all.py --any-number` (`patches/any_number.py`) sets the edit screen's number table to 0-99 for every position. Rookies and signings still get traditional numbers. The free agents no longer have their overall capped at 80, and their PIMP now comes from the same mapping as everyone else's, about 24 below overall (the cap had set it equal to overall). Copy these from `patched/Madden NFL 09 (USA)/any_number_test/`. Delete any `Rost-` roster saves first, and start a new franchise for the free agents. The full build matches `modern_kickoff_build` in every other file, and the XBE is `minicamp_test` plus this patch.

| File | Size | SHA-1 |
|---|---|---|
| `default.xbe` | 7,766,016 bytes (same size as the one it replaces) | `f02eeff72a24ec11b65836448ea95de7fa3f3b3d` |
| `data/template.dat` | 2,161,472 bytes | `2de08d94e582c4185de858f74c4491a7ffd2241b` |
| `data/DB_TEAMS.dat` | 2,591,680 bytes | `e922ed1904e4a80c744a646c2f77369ad163e9c2` |

- [x] **Edit screen (2026-11-08):** numbers work as intended on the Xbox.
- [ ] **PIMP:** a hidden `PLAY` field the game rewrites itself (`update PLAY set PIMP` at `0x387e8d`, `0x387f6b` and `0x39f544`), read with `POVR` in team and depth queries. `0x39f310` computes it per team from the player's overall against his position's and the team's averages (findings §13); what reads it isn't traced.
- [x] **Free agents listed (2026-11-08):** they show up in a new franchise on the Xbox.
- [x] **Uncapped overalls (2026-11-08):** Wagner (96) and Milano (94) top the free agents on the Xbox.
- [x] **CPU signings (2026-11-08):** CPU teams signed the top free agents, leaving Leonard Floyd and N. Harris as the best still unsigned.

**Minicamp team mix-up: fixed on the Xbox (2026-11-08).** The minicamp, a game scenario and a city table found Washington by `TDNA` = "Redskins", a name stored in the XBE, which the roster's rename broke ([findings §4](findings.md#4-modern-rosters)). `patches/team_name_keys.py` changes the four strings to "Commanders", and `build_all.py` runs it with `--roster`. On the Xbox, the Commanders are back in the minicamp, at their practice facility. Tested file: `patched/Madden NFL 09 (USA)/minicamp_test/default.xbe` (7,766,016 bytes, SHA-1 `db28745a70779e016e951208e82928016d37b386`), which is `kickoff35_test3` plus this patch.

- [ ] **Bengals in Bears uniforms, in Chicago:** reported in the same note, but the user doesn't remember which mode it was in. No Bengals lookup uses a renamed name. If it shows up again, note the mode and check the stock game.

**Al Michaels says "Washington": works on the Xbox (2026-11-05).** Commanders are called Washington, and the '91 Redskins keep "Redskins". In Dallas @ All Redskins, Al used his city lines ("Dallas and Washington", stock behaviour) and Madden said "Cowboys and Redskins", which the user is happy with. `build_all.py --commanders-commentary` builds it, and details are in [findings §10](findings.md#10-commentary-team-names-09). The tested files are in `patched/Madden NFL 09 (USA)/commentary_test3/data/`, built on the skins screens files:

| File | Size | SHA-1 |
|---|---|---|
| `SOUNDDAT.dat` | 292,063,232 bytes | `0d33548591b6cd855bff5936b737b6d5e4da31ac` |
| `SPCHDATA.dat` | 155,363,328 bytes | `04d073afe619b52752c47c68d5b3aca4df7d5a21` |
| `fe.qkl` | 10,424,200 bytes | `4988feb59664aa7c657cb73e3dcca003f8e85207` |
| `game.qkl` | 15,884,437 bytes | `270ef90954f7c44e84f1ee38d1b0d0c7431dc657` |

- [ ] **FedEx Field:** listen for it in a Commanders home game, which wasn't reported. The patch doesn't touch that lookup.
- [x] **Full build (2026-11-05):** `build_all.py` with `--commanders-commentary`, the usual roster options, the skins art, `--free-agents`, `--playoffs7`, `--optional-fullback` and `--save-unlock` reproduces the Xbox-tested files byte for byte. The XBE was checked by applying `save_unlock.py` to a run made without that flag.

**Optional fullback, with the lock fix.** Copy these two files in binary mode from `patched/Madden NFL 09 (USA)/optional_fullback_test/` to the game folder, keeping the same layout. Everything else stays in place. To undo them, copy back `default.xbe` from `playoffs7_test/` and `template.dat` from `free_agents_test/data/`.

| File | Size | SHA-1 |
|---|---|---|
| `default.xbe` | 7,766,016 bytes (same size as the file it replaces, so check that the upload finishes) | `1b8a382f7d8aebb233df3bced8ef72e3e731c08f` |
| `data/template.dat` | 2,161,472 bytes (unchanged since the last test) | `aea181d05099264cffafd15438729bfa1fa6eecd` |

- [x] **Release (2026-11-05):** the game let the user release the Bears' fullback. The Breakdown screen then shows FB 0 active, 0 inactive, and 0 for both minimums, so the new table loaded on hardware.
- [x] **Played game (2026-11-05):** in a new franchise, the Commanders' fullback was changed to running back with no issue. On a play with a fullback, a tight end lined up there.
- [x] **Prompt (2026-11-05):** the user got through the preseason with no issue.
- [x] **Hard lock found (2026-11-05):** the first build locked on hardware at week 3 of the regular season, then in the preseason of a new franchise. xemu reproduced the second on the user's save (`Save Files/NoFullBackTest`): a divide by zero at `0x396d99`, during "Signing Free Agents" (findings §8). The fix is in the XBE. In xemu, the same save then simmed the whole preseason and regular season to the Wild Card round.
- [x] **Lock fix on hardware (2026-11-05):** `Fbtest` simmed the preseason, the regular season and the offseason with no lock. The earlier week 3 lock had no save, so it's only presumed to have had the same cause.
- [x] **CPU fullbacks (2026-11-05):** after an offseason on hardware, some CPU teams still carry fullbacks. How many wasn't counted.

**Skins loading and start screens.** Copy `LOADDATA.dat`, `uis_fe.dat` and `fe.qkl` from `patched/Madden NFL 09 (USA)/skins_screens_test/data/` to the game's `data` folder. They're built on the optional fullback build, and everything else in that build is byte-identical. Art is in `custom/`: `load_screen_640x480_skins.png` (1536×1024, for `--startscreen`) and its 4:3 crop `skins_screen_4x3.png` (for `--loadscreen`).

- [x] **xemu (2026-11-05):** the start screen shows the whole picture, then Start leads to the main menu. The cover loading screen didn't appear in the boots checked.
- [x] **Xbox (2026-11-05):** the user reports that both screens look good on hardware.

**Free agents and other checks** (the free-agent files are on the Xbox):

- [x] **New roster loads on hardware (2026-11-05):** after deleting the two roster saves (`Rost-Rost1` and `Rost-Rost2` override `template.dat`), a new franchise shows free agent kickers and punters, and Daniels at 69 awareness. Check for roster saves before any roster test.
- [x] **Free agents, one season (2026-11-05):** a full season simmed into the offseason on hardware, with CPU Sign Player handling roster holes.
- [x] **Free agents, Play Now and offseason speed (2026-11-05):** a Play Now game and a franchise game both work, and progressing through the franchise runs at normal speed.
- [x] **Free agents, year 2 (2026-11-05):** a franchise with them got through the offseason and is simming year 2 at normal speed on hardware.
- [x] **#0 on a uniform (2026-11-05):** Mike Sainristil's 0 shows cleanly on the back, front and sleeve of the white jersey on hardware, though no stock 09 player wears it. Not checked: the burgundy jersey and the menus.
- [x] **Edit screen (2026-11-08):** the numbers it offers by position are WR 10-19 and 80-89; HB/FB 20-49 and 89; TE 80-89; QB 0-19; tackles and guards 60-79; C 50-79; DE/DT 60-79 and 90-99; LB 50-59 and 90-99; S 20-49; K/P 1-19. QB already gets 0, so the table allows it. These are 2004-era rules, used as the starting point for "any position, any number".
- [ ] **Playoffs, if convenient:** play a playoff game by hand, look for a bracket screen, and check that the 8-9 Eagles type of #7 seed was really the next team in line.

## Ready to do

- [ ] **xemu franchise pilot:** `tools/xemu.py` has the basics (2026-11-08). The scripts that sim whole years unattended (`year.py`, `pilot.py`, `pick.py`) are still in an old scratchpad and need a reference screenshot of the Sign Player prompt, which can't be committed. Move them when the long-franchise test comes up.

## To research

- [x] **Radio show port (started 2026-11-10, [findings §12](findings.md#12-the-radio-show-2005-to-07)):** works on the Xbox, and since 2026-11-12 it's `build_all.py --radio-show` (off by default; needs `Madden NFL 07 (USA)` in the games folder). The full build with the usual options plus `--radio-show` (`patched/radio_build`) gave the Xbox-tested `default.xbe` below byte for byte, `spchfe07.dat` identical to 07's file, and `template.dat` and `DB_TEAMS.dat` identical to `any_number_test`'s; it boots in xemu and ran a franchise from an offseason to the next week 1. An in-game off switch or segment skip isn't wanted (the user, 2026-11-12). By hand: `python patches/radio_show.py <in default.xbe> <out> --show "Madden NFL 07 (USA)/default.xbe"`, plus 07's `SPCHFEDT.dat` copied as `data/spchfe07.dat`. Test files, in `patched/Madden NFL 09 (USA)/radio_test/`, built on `playoffs_guard_test`:

  | File | Size | SHA-1 |
  |---|---|---|
  | `default.xbe` | 7,782,400 bytes (16,384 larger than before) | `78fc04b7ce2e7686094427fb08193e4df93b40d2` |
  | `data/spchfe07.dat` | 228,714,976 bytes (new file; nothing is replaced) | 07's `SPCHFEDT.dat` |

  To undo, copy back `playoffs_guard_test/default.xbe`. `spchfe07.dat` can stay.
  - [x] **First listen (xemu, the user, 2026-11-10):** entering a new franchise, Tony ran a caller question, then brought in Andy Reid and talked training camp; the music came back after; preseason week 1 got its own show. But weeks 1 to 6 of the season and a return from a game were silent. Cause: the hook dropped a show in progress whenever `SOUNDDAT.dat` had been reopened, and a dropped show counts as played. The hook now only reloads the name tables. In xemu, with that change made in memory, a simmed week built and started a new show by itself.
  - [x] **Simmed week (xemu, the user, 2026-11-10):** a new show starts after a simmed week, and it's about the correct week.
  - [x] **A story segment with a current player (xemu, the user, 2026-11-10):** Tony said Rhamondre Stevenson of the Patriots was complaining about playing time, so 09's story rows, the Madden 27 roster and 07's surname recordings work together. Not known: what he does for a surname 07 never recorded.
  - [x] **Xbox, first build (the user, 2026-11-10):** the show plays on hardware. Three things noticed: a song plays for a few seconds before Tony starts, a song seems to play for a few seconds between his clips, and he carries on after leaving franchise mode.
  - **Changed for those (xemu only so far):** the hook now checks every 16th frame instead of every 256th, so the show starts within a fraction of a second; it asks for the game mode and stops the show outside a franchise, marking it unplayed so it starts from the top on return; and while a show plays it fades the menu music out again whenever a screen restarts it. In xemu: nothing plays at the main menu, the show is playing within 45 s of starting a franchise, and it's stopped after leaving.
  - [x] **Xbox, second build (the user, 2026-11-10):** the show started as soon as Franchise was chosen at the main menu, on the setup screen. It should wait for a loaded save or a new franchise's training camp.
  - **Changed for that (xemu only so far):** in franchise mode the hook also reads the franchise's stage (`MOIN.MCSA`) and runs the show only for 5 to 30. In xemu the show no longer starts while franchise mode loads or on the setup screens, starts when the new franchise begins, and stops on leaving.
  - [x] **Xbox, third build (the user, 2026-11-10):** leaving franchise mode stops Tony. But the show still started before a save was picked, it kept cutting off a song that was about to play, and while simming to week 6 it kept cycling through shows.
  - **Changed for those (xemu only so far):** (1) a started franchise has to be seen 12 checks in a row (about 3 s) before the show may run, because a franchise left earlier stays in memory while franchise mode loads; so a song plays first, then Tony. (2) The menus' "start the music" goes through a gate that lets a new show start instead and keeps the music off while one plays. (3) A brief wrong reading no longer stops and restarts the show: only the setup screens, or 4 checks in a row outside franchise mode, do. (4) When a show ends, the next one starts at once if a simmed week left one, and only otherwise does the music come back. In xemu: silent on the setup screen and on re-entering franchise mode after leaving; a new franchise's show started about 20 s after Begin Franchise; skipping training camp and simming a preseason week each gave one new show, starting when the old show's current segment finished, with no restart.
  - [x] **Wrong player names (Xbox, the user, 2026-11-10):** Tony called Ty Johnson of the Bills by another name and a running back "Mike Brown". Cause: the show's events took `PLAY.PCMT`, whose recordings in the show's banks are full names of 2006 players, and the Madden 27 roster gives a player the `PCMT` of an old player with the same surname (Ty Johnson 564; Chase Brown and Brittain Brown 54). 577 of 2,043 players have one.
  - **Changed for that (boots and starts in xemu; the names themselves not heard):** the copied code now always passes 999 and names players by surname. A player whose surname 07 never recorded should no longer get a story segment. Lost: Tony saying a veteran's first and last name.
  - [x] **Xbox, surname build (the user, 2026-11-11):** "Brown had 120 yards": surnames are right. Two problems left: Tony still starts in the franchise load area, before the franchise menu, and a show went through three segments and then repeated instead of handing over to music until next week.
  - **The repeat, fixed (xemu):** after loading a save whose show was already built, the first show played twice, because the state object's +0x1a flag started as 0 and `start()` only marks a show played when it's set. It now starts as 1. In xemu a loaded save's show played its five segments once, stopped, and the music came back; nothing restarted in the next two and a half minutes. The hook also remembers the week it last started a show for and won't start another for the same week.
  - [x] **Xbox, repeat fix build (the user, 2026-11-11):** NEW / LOAD is silent, a week 6 save got week 6's show, and Tony signed off once and the music came back. Still wrong: about 2 or 3 seconds after "Load successful" appeared, before A was pressed, the show started.
  - **The early start, fixed in xemu:** reproduced with the user's week 17 save on the test drive (a season save's stage is good as soon as "Load successful" shows; the new franchise saved in xemu wasn't). The hook now also waits for the franchise menu's resources: the byte at `0x774804` counts loaded menu resource sets, 5 from the main menu to "Load successful" and 6 in the franchise menu and its screens. In xemu the show stayed silent on "Load successful" for minutes, started 9 s after OK in the franchise menu, stayed silent on a new franchise's setup screen and started in its menu. The wait is back to 20 checks (about 5 s).
  - [x] **Xbox, resource-count build (the user, 2026-11-11):** silent on "Load successful". But simming from week 6 to week 18 cycled through a show for each week; a sim should have music only, with the week's show starting back at the week menu.
  - **Sims, fixed in xemu:** nothing starts while `[0x802400]` is set, which the game does for the length of any sim. With the user's week 1 save and Simulate Season: the old build started a show every week; the new one started none in two and a half minutes of simming (weeks 2 to 7), and when the sim was cancelled at week 8 that week's show started at once. A show already playing when a sim starts runs to its end.
  - [ ] **Listen again, then on the Xbox:** enter a franchise and wait a few seconds in its menu. Does Tony start, does each segment follow the last, and does the music stop while he talks and come back after?
  - [ ] **Mid-season:** load or sim to a week with story rows. Do the segments name the right teams, players and coaches?
  - [ ] **Around a game:** play or sim a week and come back. Does a new show start, and does anything break on returning to the menu while a show was playing?
  - [ ] **Other screens:** the draft's "on the clock" line (rookie draft) should still play, and the fantasy draft, main menu and Play Now should be unaffected.
  - [x] **Xbox, sim build (the user, 2026-11-11):** "works much better". Committed on branch `radio-show`.
  - [x] **Xbox, the committed build (the user, 2026-11-11):** the show works. Coming back from a played game gave music, which is right because the week hadn't advanced.
  - [x] **Fantasy draft (xemu, 2026-11-11):** silent, as the user wants. The draft is stage 3 with 5 resource sets, so the show can't start there.
  - [x] **Story event numbers (2026-11-12):** 09's `stET` numbers are 07's. The story tables keyed by them in `strmdata.db` are identical row for row in the two games (findings §12).
  - Not done: a way to turn the show off or skip a segment in the game (07 had a screen and the `OPTS.OSPR` option; 09's XBE has no query for that field). Leaving `--radio-show` out of the build is the off switch; the user doesn't want an in-game one (2026-11-12).
- [ ] **Online play (the user's idea):** private games between two boxes on the same build, through our own lobby server, without Xbox Live or Insignia ([findings §14](findings.md#14-online-play-without-xbox-live-09)). In xemu, `patches/online.py <in> <out> <server IP>` (syslink mode, the server's address in place of `xblmadden09.ea.com`, two XNet filters opened, the OSDK's online checks satisfied, voice startup no longer crashing, and the online roster check always passing) and `tools/aries_server.py` (directory, login, config, rankings setup, EA Messenger, pings) get Game Modes > Xbox Live to the online main menu ("Welcome Player1!", 2026-11-21). Rooms work (2026-11-21): the Lobby lists them, joining and Create Room work (`online.py` change 9), and two xemu instances (`tools/online_test.py`) sit in one room and see each other. Invites work against a fake server-side player (`--bot`): the host reaches Game Setup and, after Ready, "Connecting ...". Two xemu boxes now share the LAN through Npcap (`online_test.py setup --lan`; checksum offload off on the PC's card), log in, meet in a room and get each other's invites; receiving one crashed the guest until `online.py` change 10. The guest accepts and both reach Game Setup with each other's team. The direct link between the boxes now works (2026-11-21, `online.py` changes 11 and 12: ConnApi keeps the lobby's address instead of asking Live matchmaking, and XNet lets plain UDP in): both show the other's Ready, the host presses Start Game (`gsta`, `+ses`) and both start loading the game. Both now reach the kickoff screen (2026-11-21, `online.py` change 13: the load crash was a slot store past the end of an 11-entry table that broke a STATE heap block, findings §14). Then the guest is "removed from the game due to excessive controller pulls" and the host warns that controller port 4 is disconnected: the local player is put on port 4 while xemu's pad is on port 1. Next: where the online game picks the local controller port. Open: a room one player creates isn't drawn in the other's Lobby. Not on the Xbox yet, and not in `build_all.py`.
- [x] **Keep career stats in long franchises:** raising the capacity works in xemu (2026-11-18). See "More room for career stats" above.
- [ ] **Long franchise with the free agents, on hardware:** years 5 to 10 passed in xemu on the build without them (findings §11). Test the current build, and a user-run team, when convenient.
- [x] **Coaches and progression (2026-11-20, [findings §13](findings.md#13-overalls-coaches-and-qb-awareness-09)):** no direct effect. Coaches add game-day bonuses (`OPRA`: +1 to +3 for a coach rating of 85+, −2 at 73 or lower) to a temporary copy of the players, and the progression code reads no coach table. Our 2026 coaches carry 2008 slot ratings, so most give little. Open: whether a simmed game gets the bonuses too.
- [x] **Overall recalculation (2026-11-20, findings §13):** a weighted average of 17 ratings per position from `PORC`, rescaled to 12–99 (`tools/overall.py`, which matches 2,038 of 2,043 stock overalls). It runs when a mode builds its teams and in the weekly progression, so free agents keep the file's value. Our roster's overalls come from EA's and only 348 of 2,100 match it.
  - [x] **Done (2026-11-20):** `build_roster.py` writes the formula's overall (`roster/game_overall.py`); depth charts and contracts still rank by EA's. Test below.
- [x] **QB awareness floor (2026-11-20, findings §13):** across 111 simmed QB seasons in the saves, each awareness point is worth about +0.5 passer rating (fewer interceptions, more completions), so the floor gives Daniels about +4, Murray +3, Ward +1.6 and Willis +0.5. It has been in every build since `free_agents_test` (2026-11-05). A no-floor copy of `career_full` for an A/B sim in xemu was made in the session scratchpad, not run: one season per side can't separate effects this size from chance.
- [x] **Free-agent retirements (2026-11-20):** against nflverse's 2026 rosters (through week 11), 48 of the 97 have been on a team this season (none marked retired) and 49 haven't. News searches found three of those 49 finished: Denico Autry (reported expected to retire), Jordan Poyer (said he'd retire after 2025) and Joe Mixon (told teammates his career is over; no papers filed). The rest (Prater, Gano, Wagner, Decker, Beachum, Hughlett, Glasgow and others) are unsigned, not retired. Jimmie Ward was on the commissioner's exempt list.
  - [x] **Done (2026-11-20):** they're in `RETIRED`; the re-pick added Trey Benson (HB), Emmanuel Ogbah (RE) and Donovan Wilson (SS). Test below.
- [ ] **Fullbacks in free agency:** only 1 was left at week 1 in xemu. This matters less if the minimum goes to 0.
- [ ] **Year jump for `save_jump.py`:** setting the year half-advanced the franchise, and the cause is unknown.
- [ ] **Jumped-save slowdown:** the offseason and next preseason ran slowly after a jump. `TPMN` is one lead. It only affects testing.

## On hold or later

These are in [roadmap.md](roadmap.md): the Commanders' alternate helmets and stadium art, classic-team photos, overtime and kickoff rules, and the rest of its future work.
