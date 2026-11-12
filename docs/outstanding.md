# Outstanding work

A running checklist of what's still open, so work can pick up in a new chat. Last updated 2026-11-12. Background and addresses are in [roadmap.md](roadmap.md) and [findings.md](findings.md). Tick items off or delete them as they're done.

## Waiting on an Xbox test

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
- [ ] **No Tony Bruno after the new `fe.qkl` (the user, 2026-11-12):** not reproduced. In xemu, with `modern_kickoff_build/data`, the stats files, the new `fe.qkl`, `spchfe07.dat` and `year_test/default.xbe`, a new franchise's show started and its segment index (state `0x81d538` +0x18) went 2, 4, 5 over two minutes with the playing flag set. Sound itself can't be checked in xemu. Ask where in the franchise it was silent: a week whose show has already played and a sim are silent by design, and the offseason hasn't been listened to.
- [x] **Years, on the Xbox (the user, 2026-11-12):** a franchise went into its next season with the stats carried on and the current year shown. Fixed in xemu first (2026-11-12) with `build_all.py --year 2026` (`patches/year_base.py`, off by default). The XBE adds 2008 to a season number at 25 places and 2007 at one; the patch changes those constants. In xemu Caleb Williams's rows read 2024 and 2025, and preseason week 1 is "Thu Aug 6", which is right for 2026. The seven `cmp reg, 2008` stay: they give 2008 its opening Thursday (the first of September) and every other year the second. Existing franchises show the new years too, because saves hold season numbers. Test file: `patched/Madden NFL 09 (USA)/year_test/default.xbe`, 7,782,400 bytes (same size as the one it replaces), SHA-1 `ef0fb12b53ae0136af2fa49af85b109515808bc5`, which is the current XBE (`radio_build`) with 26 bytes changed. To undo, copy back `radio_test/default.xbe`. Check a player card's years, the "Year" label and the schedule's dates, then sim a season into the offseason.
- [ ] **Career tables fill sooner:** `PCDE` starts at 821 rows instead of 0, so it reaches 1,550 earlier than the year 5 seen before (see "Keep career stats in long franchises" below).
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

- [ ] **Landing short of the receiving 20:** a new rule with no stock code, which goes to the receiving 40. It needs the spot where the kick first lands. The play-result rules are at `0x2687d0`. The play event list is decoded (2026-11-08, [findings §7](findings.md#7-tuning-table-survey-09), `tools/play_events.py`), but it has no landing event: `0x0e` is gaining possession. Next, find the ball's first ground contact through the incomplete-pass check or the ball object. A human kickoff (after a score, aimed short) will test it.
- [x] **CPU catch in the end zone (2026-11-08):** it wasn't a fair catch. The CPU returner caught the ball, everyone moved after the catch (the hold worked), and he knelt for a touchback.
- [ ] **Untouched in the end zone:** a touchback with no touch hasn't been tried. Neither has a ball that lands in the landing zone and is downed in the end zone (it should go to the 20).
- [ ] **Penalties during a kickoff:** check where they're enforced from now that the ball is on the 35.
- [ ] **Rest of the lineup test:** do blockers engage, since their run distances are stock and may overshoot?
- [ ] **Known quirk:** the kicking team drifts about a yard toward the sidelines during the kicker's motion, visible only in replays. Turning them doesn't remove it.

**Any number and uncapped free agents: work on the Xbox (2026-11-08).** `build_all.py --any-number` (`patches/any_number.py`) sets the edit screen's number table to 0-99 for every position. Rookies and signings still get traditional numbers. The free agents no longer have their overall capped at 80, and their PIMP now comes from the same mapping as everyone else's, about 24 below overall (the cap had set it equal to overall). Copy these from `patched/Madden NFL 09 (USA)/any_number_test/`. Delete any `Rost-` roster saves first, and start a new franchise for the free agents. The full build matches `modern_kickoff_build` in every other file, and the XBE is `minicamp_test` plus this patch.

| File | Size | SHA-1 |
|---|---|---|
| `default.xbe` | 7,766,016 bytes (same size as the one it replaces) | `f02eeff72a24ec11b65836448ea95de7fa3f3b3d` |
| `data/template.dat` | 2,161,472 bytes | `2de08d94e582c4185de858f74c4491a7ffd2241b` |
| `data/DB_TEAMS.dat` | 2,591,680 bytes | `e922ed1904e4a80c744a646c2f77369ad163e9c2` |

- [x] **Edit screen (2026-11-08):** numbers work as intended on the Xbox.
- [ ] **PIMP:** a hidden `PLAY` field the game rewrites itself (`update PLAY set PIMP` at `0x387e8d`, `0x387f6b` and `0x39f544`), read with `POVR` in team and depth queries. Its purpose isn't traced: maybe value for signings and trades.
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
- [ ] **Online play (the user's idea):** a private server for just this game. The 09 XBE links `XONLINE` and `XNET` and names `xblmadden09.ea.com`, so it needs an answer for both Xbox Live sign-in (Insignia's layer) and EA's own server, whose protocol isn't documented. Start by checking Insignia's list and what the game sends to that address in xemu.
- [ ] **Keep career stats in long franchises:** `PCDE` fills by year 5, and players after that lose career rows (findings §11). Check it on the screen, then see if raising its capacity is safe.
- [ ] **Long franchise with the free agents, on hardware:** years 5 to 10 passed in xemu on the build without them (findings §11). Test the current build, and a user-run team, when convenient.
- [ ] **Coaches and progression:** do better coaches improve ratings over a season or more? Compare multi-season saves or trace the code.
- [ ] **Overall recalculation:** by week 1, players on teams have new overalls with no rating changes, and unsigned free agents don't. Confirm the formula in the code.
- [ ] **QB awareness floor:** compare sim stats for Daniels, Murray, Ward and Willis with and without it.
- [ ] **Free-agent retirements:** 50 of the 97 aren't on any 2026 roster, and some may have quietly retired. `RETIRED` in `pick_free_agents.py` holds the confirmed ones.
- [ ] **Fullbacks in free agency:** only 1 was left at week 1 in xemu. This matters less if the minimum goes to 0.
- [ ] **Year jump for `save_jump.py`:** setting the year half-advanced the franchise, and the cause is unknown.
- [ ] **Jumped-save slowdown:** the offseason and next preseason ran slowly after a jump. `TPMN` is one lead. It only affects testing.

## On hold or later

These are in [roadmap.md](roadmap.md): the Commanders' alternate helmets and stadium art, classic-team photos, overtime and kickoff rules, and the rest of its future work.
