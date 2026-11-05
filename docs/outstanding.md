# Outstanding work

A running checklist of what's still open, so work can pick up in a new chat. Last updated 2026-11-05. Background and addresses are in [roadmap.md](roadmap.md) and [findings.md](findings.md). Tick items off or delete them as they're done.

## Waiting on an Xbox test

Copy these in binary mode from `patched/Madden NFL 09 (USA)/free_agents_test/data/` to the game's `data` folder, then start a new franchise. The `default.xbe` and `fe.qkl` from the 7-team test stay in place.

| File | Size |
|---|---|
| `DB_TEAMS.dat` | 2,591,680 bytes (was 2,585,792) |
| `template.dat` | 2,161,472 bytes (same size as the 7-team test file, so check that the upload finishes) |

- [x] **New roster loads on hardware (2026-11-05):** after deleting the two roster saves (`Rost-Rost1` and `Rost-Rost2` override `template.dat`), a new franchise shows free agent kickers and punters, and Daniels at 69 awareness. Check for roster saves before any roster test.
- [x] **Free agents, one season (2026-11-05):** a full season simmed into the offseason on hardware, with CPU Sign Player handling roster holes.
- [x] **Free agents, Play Now and offseason speed (2026-11-05):** a Play Now game and a franchise game both work, and progressing through the franchise runs at normal speed.
- [x] **Free agents, year 2 (2026-11-05):** a franchise with them got through the offseason and is simming year 2 at normal speed on hardware.
- [x] **#0 on a uniform (2026-11-05):** Mike Sainristil's 0 shows cleanly on the back, front and sleeve of the white jersey on hardware, though no stock 09 player wears it. Not checked: the burgundy jersey and the menus.
- [ ] **Edit screen:** edit a WR's number and note which numbers it offers.
- [ ] **Playoffs, if convenient:** play a playoff game by hand, look for a bracket screen, and check that the 8-9 Eagles type of #7 seed was really the next team in line.

## In progress

- [ ] **Optional fullback:** test not finished. Set the fullback's `PLPS.PPIR` to 0 in `template.dat` (the only copy; saves don't carry `PLPS`) and sim preseason week 3 from `pre3.bin`, the save where the Bears' only fullback is injured, using the 4 Wild Card build with `--save-unlock`. If the refusal is gone, check that a team with no fullback can play a game, and how the CPU and depth chart cope. The test files are in the 2026-11-05 chat's scratchpad (`overlay_fb`, `jump.iso`, `x/`, `saves/pre3.bin`). xemu screenshots came back black after the PC sat idle for about 40 minutes, probably because the display was asleep, so run this while the PC is in use.

## Ready to do

- [ ] **Merge the free agents:** the `free-agents` PR is open for review.
- [ ] **Remove the 80 overall cap:** agreed. Take out `FREE_AGENT_CAP` at the next roster rebuild, because a player's overall resets once he signs. Older players keep their lost step.
- [ ] **Any position, any number:** set the table at `0x61ee18` and `0x61eec0` to 0-99. Decide whether rookies stay on traditional numbers (leaning yes).
- [ ] **Older-franchise guard:** on the 7-team XBE, a franchise with 4 Wild Card games sticks at the end of the regular season with no error. Detect or refuse the mismatch.
- [ ] **Make `--playoffs7` the default?** It's off by default and has worked over two simmed seasons on hardware.
- [ ] **Custom start screen:** the Xbox shows the stock screen (Favre) because of the test `fe.qkl`. The next full build can use `--startscreen`. Ask which image, and leave JP out unless asked.
- [ ] **xemu helpers:** the key-press, screenshot and snapshot scripts live only in a chat's scratchpad, and each chat rebuilds them. Move them into `tools/` to save tokens.
- [ ] **Docs:** add `playoffs7.py` to `patches/README.md`.

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
