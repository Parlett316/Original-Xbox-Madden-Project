# Outstanding work

A running checklist of what's still open, so work can pick up in a new chat. Last updated 2026-11-05. Background and addresses are in [roadmap.md](roadmap.md) and [findings.md](findings.md). Tick items off or delete them as they're done.

## Waiting on an Xbox test

**Al Michaels says "Washington": works on the Xbox (2026-11-05).** Commanders are called Washington, and the '91 Redskins keep "Redskins". In Dallas @ All Redskins, Al used his city lines ("Dallas and Washington", stock behaviour) and Madden said "Cowboys and Redskins", which the user is happy with. `build_all.py --commanders-commentary` builds it, and details are in [findings §10](findings.md#10-commentary-team-names-09). The tested files are in `patched/Madden NFL 09 (USA)/commentary_test3/data/`, built on the skins screens files:

| File | Size | SHA-1 |
|---|---|---|
| `SOUNDDAT.dat` | 292,063,232 bytes | `0d33548591b6cd855bff5936b737b6d5e4da31ac` |
| `SPCHDATA.dat` | 155,363,328 bytes | `04d073afe619b52752c47c68d5b3aca4df7d5a21` |
| `fe.qkl` | 10,424,200 bytes | `4988feb59664aa7c657cb73e3dcca003f8e85207` |
| `game.qkl` | 15,884,437 bytes | `270ef90954f7c44e84f1ee38d1b0d0c7431dc657` |

- [ ] **FedEx Field:** listen for it in a Commanders home game, which wasn't reported. The patch doesn't touch that lookup.
- [ ] **Full build:** run `build_all.py --commanders-commentary` through a whole build. So far the patcher and `qkl_sync.py` have only been run directly.
- [ ] **Madden in a Commanders game:** his team references aren't changed or traced. Note what he says, if it matters.

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

## In progress

- [ ] **Optional fullback:** `build_all.py --optional-fullback` (`patches/optional_fullback.py`) is committed on the `optional-fullback` branch, not merged, and off by default. It changes `template.dat` and `default.xbe`. It passed a season and an offseason on hardware. If xemu screenshots are black, the display may be asleep: a one-pixel mouse nudge brought them back.

## Ready to do

- [ ] **Remove the 80 overall cap:** agreed. Take out `FREE_AGENT_CAP` at the next roster rebuild, because a player's overall resets once he signs. Older players keep their lost step.
- [ ] **Any position, any number:** set the table at `0x61ee18` and `0x61eec0` to 0-99. Decide whether rookies stay on traditional numbers (leaning yes).
- [ ] **Older-franchise guard:** on the 7-team XBE, a franchise with 4 Wild Card games sticks at the end of the regular season with no error. Detect or refuse the mismatch.
- [ ] **Make `--playoffs7` the default?** It's off by default and has worked over two simmed seasons on hardware.
- [ ] **xemu helpers:** the key-press, screenshot and snapshot scripts live only in a chat's scratchpad, and each chat rebuilds them. Move them into `tools/` to save tokens.

## To research

- [ ] **Long franchises (recommended next):** the franchise `PLAY` table has 2,754 rows, reaches 2,634 by the end of year 4, and starts about 97 higher with the free agents. Find out what happens when it fills.
- [ ] **Coaches and progression:** do better coaches improve ratings over a season or more? Compare multi-season saves or trace the code.
- [ ] **Overall recalculation:** by week 1, players on teams have new overalls with no rating changes, and unsigned free agents don't. Confirm the formula in the code.
- [ ] **QB awareness floor:** compare sim stats for Daniels, Murray, Ward and Willis with and without it.
- [ ] **Free-agent retirements:** 50 of the 97 aren't on any 2026 roster, and some may have quietly retired. `RETIRED` in `pick_free_agents.py` holds the confirmed ones.
- [ ] **Fullbacks in free agency:** only 1 was left at week 1 in xemu. This matters less if the minimum goes to 0.
- [ ] **Year jump for `save_jump.py`:** setting the year half-advanced the franchise, and the cause is unknown.
- [ ] **Jumped-save slowdown:** the offseason and next preseason ran slowly after a jump. `TPMN` is one lead. It only affects testing.

## On hold or later

These are in [roadmap.md](roadmap.md): the Commanders' alternate helmets and stadium art, classic-team photos, overtime and kickoff rules, and the rest of its future work.
