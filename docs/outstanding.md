# Outstanding work

A running checklist of what's still open, so work can pick up in a new chat. Last updated 2026-11-06. Background and addresses are in [roadmap.md](roadmap.md) and [findings.md](findings.md). Tick items off or delete them as they're done.

## Waiting on an Xbox test

**Kickoff alignment, one-player test.** Kicking-team spots are data in `GAMEDATA.dat`'s playbooks, not code ([findings §7](findings.md#7-tuning-table-survey-09)). `patches/kickoff_setup.py` (not committed yet) moved one coverage player 10 yards in `y` in all 50 playbooks with a kickoff. Copy these from `patched/Madden NFL 09 (USA)/kickoff_test/data/`, built on the `commentary_test3` bundles. To undo them, copy back stock `GAMEDATA.dat` and `fe.qkl` from `commentary_test3/data/`.

| File | Size | SHA-1 |
|---|---|---|
| `GAMEDATA.dat` | 4,508,032 bytes | `fcdd1323d750dc7780b03094fac3eaaeb225604d` |
| `fe.qkl` | 10,424,200 bytes | `648c4711da2dd8e2a3378790f25ce6763771bf4a` |

- [x] **Alignment in xemu (2026-11-06):** on an image of the stock game with this edit and an `fe.qkl` synced from stock, the moved player lines up at about the 35, 10 yards ahead of the line at about the 25. So one `y` unit looks like one yard and `+y` is upfield.
- [x] **Kick in xemu (2026-11-06):** the moved player ran straight to the end zone, ignoring where the ball went, so the play's script runs from his new spot.
- [x] **Hold test in xemu (2026-11-06):** with Kickoff Middle's coverage script starting with a wait (`--hold 160`, PSAL code 51; `patched/Madden NFL 09 (USA)/kickoff_hold_test/data/`, stock positions), the kicking team moved about a yard and stopped. The user could still move the kicker. Not reported: whether they ever started again.
- [x] **Short hold in xemu (2026-11-06, `--hold 64`):** the kicking team moves about a yard during the kicker's windup and stops. The kicker kicks, and the whole team starts running as the kicker lands. So code 51 is a timer running from before the kick, and the chase step then runs.
- [x] **160 hold in xemu practice mode (2026-11-06):** the coverage team stayed put until the receiving team fielded the ball. The kicker moved on his own, as his script is unchanged.
- [x] **Squib with the 160 hold (2026-11-06):** no one moved until the receiving team touched the ball, and they moved even when it wasn't caught cleanly. So a wait ends on its timer or on that touch.
- [x] **Modern lineup and hold in xemu (2026-11-06):** `kickoff_setup.py --hold 255 --lineup` (`patched/Madden NFL 09 (USA)/kickoff_modern_test/data/`) puts the kicking team on the receiving 40 and the blockers on the receiving 35 and 30, with returners near the 5 and 15. A screenshot confirms those spots, and the user reports that the hold and touch logic works. The archive repack loads.
- [x] **Play Now in xemu (2026-11-06):** the kickoff behaves the same as in practice mode, and everyone holds. The kicking team still creeps about a yard during the kicker's motion.
- [x] **Creep cause (2026-11-06):** in a split test, the half of the kicking team facing downfield (`dir_` 64) barely moved during the kicker's motion, and the half in the stock inward stance (`dir_` 0 and 128) stepped forward over the line, judging by screenshots. So the stance is the main cause.
- [x] **Downfield stance in xemu (2026-11-07):** with all ten facing downfield on the 40, they no longer step forward. Instead, each side drifts about a yard toward its sideline during the kicker's motion, visible only in instant replay. That fits a sidestep relative to their facing, one way on each side, so no facing removes it. The returners stay in place until the touch (the second returner now uses script 1195, since 43 is shared with punts), and blocking looks correct.
- [x] **Out of bounds in xemu (2026-11-07):** an untouched kick out of bounds caused no problem.
- [ ] **Untouched in the end zone:** a touchback with no touch hasn't been tried.
- [x] **Ball on the 35 in xemu (2026-11-07):** `patches/kickoff_spot.py` with `kickoff_setup.py --hold 255 --lineup --ball 35`. The ball is on the 35 in practice mode and Play Now, the scoreboard says 35, the kicking team is on the receiving 40, and a safety free kick is on the 20. Play Now's spot comes from `0x30c730`; practice uses the `[0x801c50]` paths.
- [x] **Safety kick froze (2026-11-07):** after the safety, nobody moved, because safety kicks and their returns shared the held scripts. The hold now gives kickoff and kick-return plays their own copies of their scripts (the `PSAL` table grows, and so do the entries' unpacked sizes), and the stock scripts stay as they were.
- [x] **Copied scripts in xemu (2026-11-07):** a regular kickoff still holds until the touch. On a safety free kick, the kicking team ran, but the receiving team's players ran away from the ball instead of fielding it. The safety return's data is stock (checked: no shared script or position changed). Comparison in xemu (2026-11-07): the unmodified game fields the safety free kick (a "SAFETY PUNT" from the 20). So do split image A (the new playbooks with the stock XBE) and split image B (the new XBE with stock playbooks). The full combination failed again: both returners did the "you got it?" back-off. At the user's suggestion, the kickoff returners are now stacked as in stock (the deep one on the 5 fields, the other blocks from the 15), each on a held copy of his own script, so the earlier swap of the deep returner to script 1195 is gone. On that build (2026-11-07, xemu) the user reports it "seems better".

**Ball on the 35, Xbox test.** Copy these from `patched/Madden NFL 09 (USA)/kickoff35_test/`. `default.xbe` is the optional fullback XBE plus `kickoff_spot.py`, changing the same 11 bytes tested in xemu. `fe.qkl` is synced from `commentary_test3`, and `game.qkl` is unchanged. To undo, copy back `default.xbe` from `optional_fullback_test/`, the stock `GAMEDATA.dat`, and `fe.qkl` from `commentary_test3/data/`.

| File | Size | SHA-1 |
|---|---|---|
| `default.xbe` | 7,766,016 bytes (same size as the current one) | `1c74ee87e404a2d5d0957eb247589aa85b8df2e7` |
| `data/GAMEDATA.dat` | 4,516,224 bytes | `4cc4ec02605a68454174e2b891b64c44d57edac7` |
| `data/fe.qkl` | 10,424,200 bytes (same size as the current one) | `7ff12412f3aecf27bae77b926da358f72b18d46e` |

- [x] **Xbox (2026-11-07):** the user reports everything seems fine. Players seemed a little faster, which the user put down to having just played in slow xemu.
- [x] **CPU kicker hold (xemu, 2026-11-07):** kickoff and squib kickers' copied scripts now hold right after the kick (code 45, then the wait). With the CPU kicking, he stays in place until the touch. A human-controlled kicker can't be held with data. Not on the Xbox yet.
- [ ] **Landing zone and kick results:** short of the receiving 20 and out of bounds go to the receiving 40, a touchback to the 35, and a ball that lands in the zone then is downed in the end zone to the 20. The result code is in `0x2687d0` (findings §7). Touchbacks: `kickoff_spot.py` now hooks the two touchback stores. The first version keyed on play type 0. In xemu that gave the 35 to a kickoff touchback but also to a regular punt touchback, so the play type is 0 for punts by then. The caves (`0x10e80`-`0x10ec6`) now check the snap spot `[0x803504]+0x10`, which flips sign on a change of possession. Exactly ±15.0 counts as a kickoff from the 35 and gets ±15 (the 35); anything else keeps the stock ±30 (the 20). In xemu (2026-11-08, `kick35h.iso`), a kickoff out the back of the end zone came out to the 35, and a punt out the back of the end zone (fair catch called) to the 20.

**Touchbacks and the kicker hold, Xbox test.** Copy from `patched/Madden NFL 09 (USA)/kickoff35_test2/`. The XBE is the optional fullback XBE plus `kickoff_spot.py`, the same 81 changed bytes as the xemu-tested one. `GAMEDATA.dat` is the same as xemu's. `fe.qkl` is synced from `commentary_test3`. To undo, copy back `default.xbe` from `optional_fullback_test/`, the stock `GAMEDATA.dat`, and `fe.qkl` from `commentary_test3/data/`.

| File | Size | SHA-1 |
|---|---|---|
| `default.xbe` | 7,766,016 bytes | `1a20f1a85ec65fbbb4fe183bd0f5f3344c59c028` |
| `data/GAMEDATA.dat` | 4,518,272 bytes | `d31e6fea0fdbee42542d6ee5c16eb36643862417` |
| `data/fe.qkl` | 10,424,200 bytes | `12b01c5770c5eee103d8d69f6f668c5fa607a9ac` |

- [ ] **Xbox:** a kickoff touchback on the 35, a punt touchback on the 20, and the CPU kicker held after the kick. Madden 09 has no kickoff out-of-bounds penalty: the out-of-bounds and landing-short spots aren't found yet.
- [ ] Then: the touchback spot, out-of-bounds placement, and penalties enforced on a kickoff.
- [x] **Xbox (2026-11-07):** the user reports that the modern kickoff works on hardware. Files: `GAMEDATA.dat` (4,508,672 bytes, `b3ee0324da91c23a50cb6ebca5ddcdbc86f801bf`) and `fe.qkl` (10,424,200 bytes, `1903e69bc73a552211d5350dd7ae2455ad94c928`) from `patched/Madden NFL 09 (USA)/kickoff_modern_test/data/`. `GAMEDATA.dat` is 640 bytes larger than stock. To undo, copy back the stock `GAMEDATA.dat` and `fe.qkl` from `commentary_test3/data/`.
- [ ] **Rest of the lineup test:** do blockers engage, since their run distances are stock and may overshoot? What happens on an untouched kick into the end zone or out of bounds? Does the next play load in a real game?
- [x] **Diagram lineup in xemu (2026-11-06):** the build matching the NFL hybrid kickoff diagram the user supplied loads, per the user's screenshots (`kickoff_setup.py --hold 255 --lineup`; `patched/Madden NFL 09 (USA)/kickoff_modern_test/data/`): kicking team evenly spaced at the receiving 40, seven blockers on the 35, two on the 32, and two returners side by side on the 5.
- [ ] **Still to build:** the ball on the 35 (the kicking team's `y` then becomes 25), and the touchback and landing-zone rules.

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
- [ ] **Edit screen:** edit a WR's number and note which numbers it offers.
- [ ] **Playoffs, if convenient:** play a playoff game by hand, look for a bracket screen, and check that the 8-9 Eagles type of #7 seed was really the next team in line.

## Reported, not looked at yet

- [ ] **Minicamp game (2026-11-07):** the Commanders/Redskins are missing, apparently replaced by the Cardinals. The Bengals are there, but they wear Bears uniforms and play in Chicago. Seen on the Xbox with the full build. Not yet known: whether the stock game does it (check `stock.iso` in xemu). A team-index mismatch between the minicamp data and the modern roster is the first guess.

## In progress

- [ ] **Optional fullback:** `build_all.py --optional-fullback` (`patches/optional_fullback.py`) is committed on the `optional-fullback` branch, not merged, and off by default. It changes `template.dat` and `default.xbe`. It passed a season and an offseason on hardware. If xemu screenshots are black, the display may be asleep: a one-pixel mouse nudge brought them back.

## Ready to do

- [ ] **Remove the 80 overall cap:** agreed. Take out `FREE_AGENT_CAP` at the next roster rebuild, because a player's overall resets once he signs. Older players keep their lost step.
- [ ] **Any position, any number:** set the table at `0x61ee18` and `0x61eec0` to 0-99. Decide whether rookies stay on traditional numbers (leaning yes).
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
