# Outstanding work

A running checklist of what's still open, so work can pick up in a new chat. Last updated 2026-11-08. Background and addresses are in [roadmap.md](roadmap.md) and [findings.md](findings.md). Tick items off or delete them as they're done.

## Waiting on an Xbox test

**Modern kickoff: works on the Xbox (2026-11-08), now `build_all.py --modern-kickoff`.** The ball is on the 35 (a safety kick stays on the 20). Kickoff touchbacks come out to the 35 and punts' stay on the 20. A kick out of bounds draws the penalty and goes to the receiving 40. Everyone, CPU kickers included, holds in the NFL's hybrid lineup until the receiving team touches the ball, with the returners stacked as in stock. A human-controlled kicker can't move before then either. Details are in [findings §7](findings.md#7-tuning-table-survey-09). The full build with the usual options plus `--modern-kickoff` reproduced every hardware-tested file byte for byte (2026-11-08): `default.xbe` and `GAMEDATA.dat` match `kickoff35_test3`, and the other 16 files match the earlier tested builds.

| File | Size | SHA-1 |
|---|---|---|
| `default.xbe` | 7,766,016 bytes | `6b7266ab6de5497a0d0e961631c3d3562a4c444c` |
| `data/GAMEDATA.dat` | 4,518,272 bytes | `d31e6fea0fdbee42542d6ee5c16eb36643862417` |
| `data/fe.qkl` | 10,424,200 bytes | `12b01c5770c5eee103d8d69f6f668c5fa607a9ac` |

- [ ] **Landing short of the receiving 20:** a new rule with no stock code, which goes to the receiving 40. It needs the spot where the kick first lands, which hasn't been found. The play-result rules are at `0x2687d0`.
- [x] **CPU catch in the end zone (2026-11-08):** it wasn't a fair catch. The CPU returner caught the ball, everyone moved after the catch (the hold worked), and he knelt for a touchback.
- [ ] **Untouched in the end zone:** a touchback with no touch hasn't been tried. Neither has a ball that lands in the landing zone and is downed in the end zone (it should go to the 20).
- [ ] **Penalties during a kickoff:** check where they're enforced from now that the ball is on the 35.
- [ ] **Rest of the lineup test:** do blockers engage, since their run distances are stock and may overshoot?
- [ ] **Known quirk:** the kicking team drifts about a yard toward the sidelines during the kicker's motion, visible only in replays. Turning them doesn't remove it.

**Any number and uncapped free agents: waiting on an Xbox test.** `build_all.py --any-number` (`patches/any_number.py`) sets the edit screen's number table to 0-99 for every position. Rookies and signings still get traditional numbers. The free agents no longer have their overall capped at 80, and their PIMP now comes from the same mapping as everyone else's, about 24 below overall (the cap had set it equal to overall). Copy these from `patched/Madden NFL 09 (USA)/any_number_test/`. Delete any `Rost-` roster saves first, and start a new franchise for the free agents. The full build matches `modern_kickoff_build` in every other file, and the XBE is `minicamp_test` plus this patch.

| File | Size | SHA-1 |
|---|---|---|
| `default.xbe` | 7,766,016 bytes (same size as the one it replaces) | `f02eeff72a24ec11b65836448ea95de7fa3f3b3d` |
| `data/template.dat` | 2,161,472 bytes | `2de08d94e582c4185de858f74c4491a7ffd2241b` |
| `data/DB_TEAMS.dat` | 2,591,680 bytes | `e922ed1904e4a80c744a646c2f77369ad163e9c2` |

- [x] **Edit screen (2026-11-08):** numbers work as intended on the Xbox.
- [ ] **PIMP:** a hidden `PLAY` field the game rewrites itself (`update PLAY set PIMP` at `0x387e8d`, `0x387f6b` and `0x39f544`), read with `POVR` in team and depth queries. Its purpose isn't traced: maybe value for signings and trades.
- [ ] **Free agents:** the best ones show their real overall (some above 80) in a new franchise, and CPU teams still sign players into roster holes.

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

- [ ] **Older-franchise guard:** on the 7-team XBE, a franchise with 4 Wild Card games sticks at the end of the regular season with no error. Detect or refuse the mismatch.
- [ ] **Make `--playoffs7` the default?** It's off by default and has worked over two simmed seasons on hardware.
- [ ] **xemu helpers:** the key-press, screenshot and snapshot scripts live only in a chat's scratchpad, and each chat rebuilds them. Move them into `tools/` to save tokens.

## To research

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
