# Research findings

What was found, how it was confirmed, and the numbers behind each change. Addresses are virtual addresses in the retail USA XBEs.

## 1. The awareness bug (07, 08, 09)

**Symptom:** in franchise mode, awareness creeps toward 99 season after season. The user reports it in 2006–09; 2005 is the reference game without it.

**Cause:** player roles (Team Leader, Mentor, Franchise QB, weapon roles…) don't apply at game time. Their rating bonuses are **written into the stored ratings**:

| Event (09) | Code | Effect |
|---|---|---|
| Role assigned | `0x3e1a50` | adds self bonuses (`RLPM`) and teammate bonuses (`RLTM`) via `0x3e08b0(role, player, 0)` and `0x3e0a50(role, player, 0)` |
| Role removed | `0x3e2390` | the same calls with remove = 1, then clears the slot |
| Role **displaced** | `0x3e1b10` @ `0x3e1ce5` | clears the slot (`PROL`/`PRL2` = 0x2D) **without** the remove calls |

A player holds at most two roles. When he earns a better one, the worse one is displaced and its bonuses stay baked in, and for Leader/Mentor so do every qualifying teammate's. When the role is earned again, the bonus is added again. A second defect: the teammate-bonus handlers clamp with an unsigned compare, so a rating pushed below 0 wrapped around to 99.

**Fix** (`patches/madden_awareness_fix.py`):
- The slot clear jumps to a code cave that calls the game's own remove routines for the displaced role, then does the original clear.
- `mov eax,99` → `cdq / inc edx / imul eax,edx,99` in each handler, clamping to 0–99.
- The full remover `0x3e2390` isn't used: its Team Captain branch frees the shared role-pass buffer at `0x7b9e94`, which the assignment pass then dereferences.

| | 07 | 08 | 09 |
|---|---|---|---|
| Slot clear | `0x3a75a0` (none = 0x1F, old role via slot index `[esp+0x14]`) | `0x3ccc85` | `0x3e1ce5` |
| Remove self / teammates | `0x3a6400` / `0x3a65a0` | `0x3cb850` / `0x3cb9f0` | `0x3e08b0` / `0x3e0a50` |
| Clamp sites | 5 | 3 | 3 |

08 is instruction-for-instruction identical to 09. 06 and 2005 have no role system.

**Verified on hardware (09):** a franchise with the fix and stock progression, two simmed seasons. League awareness rose about +0.6 a season, and role holders gained the same as non-holders (+0.8 for two roles, +0.6 one, +0.5 none). The user's tracked veterans aged normally: London Fletcher 94 → 94 → 92. 07 and 08 have only been checked by disassembly.

## 2. How in-season progression works (2005–09)

Applied at the `SCWE` checkpoints (identical in 2005 and 09): preseason week 3, weeks 4, 10 and 16, playoff weeks 19 and 20.
- **Grade:** each player gets a per-game performance score from position-specific code. A running average is compared with `PLLO` thresholds for (position group `PDRP`, overall group `PRGR`, career phase `PCPH`, and in 09 checkpoint `PPRD`): ≥ `PL3P` best, ≥ `PL2P` good, ≥ `PL1P` ok, ≥ `PLSP` neutral, below `PLSP` bad. Players who don't play are scored at exactly `PLSP`.
- **Change:** `PWRA` gives signed changes to 11 ratings for (position group, overall group, grade), plus checkpoint and career phase in 09. The weekly routine is at `0x4134c0`; overall groups are 90+, 82–89, 76–81, 70–75, 60–69, under 60.
- The loader (`0x411ab9`) indexes rows by their key fields, so row order doesn't matter. Stock 09 has one mis-keyed row (group 14 stored as 1 at checkpoint 1, phase 1).
- **`PLSP` is 0 in almost every row of both games**, so the bad grade practically never fires. Poor players don't decline in-season; they just don't gain.
- **Offseason:** `PYRA` scales only physical ratings, by about 0.985–0.999 a year. Awareness and skill ratings only move in-season.
- The franchise scorecard's "Player Progression" is the team total of in-season and yearly changes (counter at `0x7ba4c4`). It's unrelated to roles.
- The preseason checkpoint in stock 09 can only lower ratings (gains 0, bad −1). That's why "everyone went negative" after a simmed preseason.

## 3. Progression experiments

Same roster (the 2008 roster save), awareness fix on, everything simmed, saves after each Super Bowl. Compared with `tools/franchise_report.py`.

| | Start | Stock 09, season 1 / 2 | Performance v1, season 1 / 2 | Performance v2, season 1 / 2 |
|---|---|---|---|---|
| 99 overall | 5 | 17 / 31 | 7 / 8 | 6 / 11 |
| 95+ overall | 79 | 95 / 109 | 84 / 83 | 68 / 63 |
| 90+ overall | 241 | 264 / 285 | 285 / 324 | 235 / 252 |
| OVR mean | 80.3 | 81.2 / 81.1 | 81.0 / 81.6 | 80.0 / 79.9 |
| Awareness mean | 68.7 | 69.9 / 70.4 | 70.7 / 71.9 | 68.8 / 68.8 |

Season-2 starters (8+ starts), top vs. bottom third by production at their position:

| | Stock | v1 | v2 |
|---|---|---|---|
| OVR change, top / bottom | +0.80 / +0.07 | +0.85 / +0.68 | +0.13 / −0.73 |
| AWR change, top / bottom | +1.81 / +0.93 | +2.88 / +2.56 | +1.65 / +0.04 |
| Bottom third that declined | 20 of 169 (12%) | 15 of 162 (9%) | 78 of 158 (49%) |

- **Stock 09** piles up 99s: 16 of 95 players rated 95–98 reached 99 in season 2, and 2 dropped back. The league average barely moves.
- **Performance v1** (2005 gains with a top-end brake, 2005 thresholds) kept 99s rare. But season-2 starters gained about the same whatever their production: top third +2.9 awareness, bottom third +2.6 (stock: +1.8 vs +0.9). Two causes: the bad grade never fires (`PLSP` = 0), and 2005's thresholds are on a different scale from 09's scoring, so most starters landed in the top grades.
- **Performance v2** (current `progression_2005.py performance`): 09's own thresholds, `PLSP` = half of `PL1P` so poor starters get the bad grade, the same gains and brake, and a neutral preseason. Tested 2026-11-03: production now drives progression (the best of the three on separation and declines), the league stays flat (OVR mean 80.3 → 79.9, 95+ shrinking), and the 11 players at 99 after season 2 are all established stars who were already 96–99 (Manning, Brady, Gates, Ware, Sanders…), with no rookies or young breakouts. Stock had 31.

Awareness per regular season (prime career phase):

| Grade | 90+ stock / v2 | 82–89 | 76–81 | under 60 |
|---|---|---|---|---|
| Best | +3.2 / +2.0 | +5.5 / +7.1 | +5.6 / +17.1 | +5.1 / +32.3 |
| Bad | −3.9 / −5.5 | −3.9 / −5.2 | −3.9 / −3.9 | −3.9 / −3.9 |

Young players get ×1.25 on gains; veterans get ×0.75 on gains and ×1.25 on losses.

## 4. Modern rosters

- EA's ratings site: the live game comes from the Next.js page-data route (100 players a page, with team and position). Archived seasons come from `drop-api.ea.com/rating/madden-nfl?iteration=…`, which returns team and position as null but filters on `team=` / `position=`. Headshots are 512×512 PNGs on `ratings-images-prod.pulse.ea.com`.
- Ratings are mapped by percentile within position onto 09's own distribution, so the league keeps 09's shape (the overall histogram matches the 2008 roster's almost exactly).
- Menu photos: `PSXP` selects `uis_plyr.dat` entry PSXP+1. Skin tone (`PSKI`) is estimated from the EA photo's face brightness, split in 09's own proportions. The appearance donor is a 2008 player with the same position and skin tone and a generic face.
- Team names: `TEAM_RENAMES` changes only TGIDs 8/23/24/26 (LA Chargers, Las Vegas Raiders, LA Rams, Commanders). The classic teams (87/91 Redskins, 90 LA Raiders, 94 SD Chargers…) have their own TGIDs and keep their names.
- The XBE finds some teams by nickname (`TDNA`), with names stored in the XBE: the minicamp (`0x6e5dc8`, queried at `0x1f18b0`), the 32 game scenarios (eight groups of four at `0x746e58`, loaded at `0x1f0c50`) and a city table (`0x6ac618`, read at `0x140d4b`). Only Washington's nickname changes, so `patches/team_name_keys.py` renames its four "Redskins" keys. The city renames don't matter to these lookups, but the city table's own labels still say St. Louis, San Diego and Oakland.
- Coaches (`COCH`, 229 rows): three copies in `template.dat` (DBs at `0x3c200`, `0x96580`, `0xab500`; the last has extra fields, so rows differ in length) and one 4-row table per team in `DB_TEAMS.dat`. Each team has four rows, role `COPS` 0 HC / 1 OC / 2 DC / 3 ST; TGID 1023 is the coach pool, 1010/1011 the Pro Bowl coaches. `CLNA` "B.Johnson" style, 16 bytes with no terminator needed. The menu photo is `uis_coac.dat` entry `CSXP`+1 (like players' `PSXP`); `CSXP` 15 → entry 16 is the silhouette. A hardware test showed `CHID` is *not* the photo: renaming Zorn's row to Quinn with a generic `CHID` still showed Zorn. `CHID` is probably the 3D head (14, 6, 13, 15, 18, 22 shared; Reid 106, Payton 114, McCarthy 113 unique). Skin is `CSKI` (0–2). Career record (from Reid's 88-54): `CCWI` wins, `CCLO` losses, `CCPW`/`CCPL` playoffs, `CSBW`/`CSBL` Super Bowls. `roster/coaches.py` holds the 2026 staffs. Record fields are 10 bits (6 for Super Bowls), `CAGE` 7. Record sources: ESPN's core API files a season's playoffs under the next year after about 2014 (under the same year before that) and has gaps (Baltimore's 2018 loss, a Payton season), so Wikipedia's season tables are used and checked against ESPN's regular-season totals. `uis_coac.dat`: 239 entries, the same 128×128 MMAP format as `uis_plyr.dat` (photo at 16,16, about 64 px), so `headshots.encode` writes them. 138 entries are free once the replaced 2008 coaches' photos are reused, enough for every new coach. `game.qkl` preloads only part of `uis_coac.dat` that isn't touched. Team-site headshots come from the NFL CDN cropped by `c_fill,g_face,w_512,h_512`. Skin tone from photo brightness was unreliable under studio lighting, so `coaches.py` lists it.
- A first build that numbered photos by roster order showed other players' faces; the cause was a mismatched `template.dat` from an older build. The three roster files must come from one build.

## 5. Music

- Each song points at its `BGM.dat` entry through `MUSO.MSOR`. Playback streams entry `MSOR` from the archive handle (`0x2a2b60`). The preview builds a one-entry playlist (`0x2aa260` → `0x2a3c90`).
- **Why new tracks were silent at first:** `fe.qkl` holds a copy of `BGM.dat`'s header and 47-entry directory. A test build split the cause: an old track in a new soundtrack played; a new track in 09's soundtrack didn't. Syncing the copy (`qkl_sync.py`) fixed it.
- The UI supports multiple soundtracks natively. Indices past `count(MUST)` are treated as Xbox custom soundtracks.
- At most 40 songs can be on at once: the `MUPL` capacity, a hard-coded 40 at `0x18cebb`, and a 55-entry playback array at `[0x7f2d10]`.

## 6. Miscellaneous

- **Attract-mode demo:** pressing a button to leave it hard-locks the console on the stock game too. Not caused by these mods. The idle delay is the first constant (75000 ms) in the Press START screen script's table at +0x1a0 (`uis_all.dat` sub-archive 0, entry 3; that sub-archive is preloaded in `fe.qkl`). Setting 15000 started the demo after about 15 s on hardware, which confirmed it. The build sets 86,400,000 (24 h).
- **Roster saves override the default roster:** the memory-card roster is auto-loaded.
- **Z: cache:** 36 files are cached (list at `0x739fc8`, copy routine `0x35e50`) and refreshed when they change.
- **2005 roster and progression formats** are close to 09's (PLAY has 115 fields vs 110; `PWRA`/`PLLO` without the checkpoint key). 07 and 08 PLAY layouts are identical to 09's.

## 7. Tuning-table survey (09)

`tools/db_survey.py <file>` lists every table in a file. `strmdata.db` has 213 tables; `template.dat` has 4 DBs (the league roster DB, a settings/league DB at `0x3c200`, and franchise working DBs). Confirmed values:

| What | Where | Stock values |
|---|---|---|
| Salary cap and pay rules | `template.dat` DB @`0x3c200`, `SLRI` (1 row) | `SCAD` cap $116,000,000; `SMAD` 16,000,000 (likely max salary); `RFA1–4` 850k–2.35M (restricted-FA tenders) |
| Minimum salary by years pro | same DB, `SAYP` (`PYRP` → `SMID`) | $285k (rookie) → $820k (10+ yrs) |
| Rookie contracts by pick | same DB, `SADP` (170 rows, keyed by `PDRP`, `SRRI`) | top pick: $6M salary, $3.84M bonus |
| Player value → contract tier | `strmdata.db` `PCVR`, `PCCS`, `PCCT` | tiers by value 0–124 … 225–255 |
| Draft-grade spread per round | `strmdata.db` `DRGR` (`DRND`, `DGRA`, `DGPO`) | `DGPO` 50, 35, 25, 20, 15, 10, 5… |
| Draft-class ratings and looks | `strmdata.db` `SPAD`, `SPAS`, `SPAI`; names `SPNM`/`DRYR`, colleges `SPCO` | see below |
| Scouting/position-coach text | `PRCT` (2,209 rows, rating range → comment) | text only |

**Draft-class generator** (code at `0x3d0200–0x3d1900`): each prospect gets a first name from `SPNM`, a last name from `DRYR` and a college from `SPCO` (keyed by the commentary slot `SPSL`). Ratings and looks come from `SPAD` (4,894 rows): for each position group `PDRP` (0–16; 0 = QB) and attribute `SPAI`, a weighted list of value ranges [`SPAM`, `SPAA`] with weights `SPAP` summing to about 10,000. `SPAI` 0–25 and 64–69 are appearance codes, 28 is height in inches, 29 is weight (−160 offset), and 30–63 are ratings (QB: 37/38 = throw power/accuracy, mean 92/84). `SPAS` holds the skin-tone-dependent pieces (`SPAS` 0–2). `DRGR` is read by the same code after the players are made: per round, the draft-grade spread used for scouting.

**Measured from the stock franchise saves:** generated classes are *not* what inflates the league. The 218 drafted rookies in `FranchisePreseasonYear2` average 76.5 OVR (top 88, 12 at 85+, none at 90+), the same as the real 2008 rookies (76.7, top 86). One season later they average 76.3 with three at 90+. The 90+ players come from years 3–4 (15–28 per class), so they're made by progression, not the draft. `SPAD` is the lever if weaker or more varied classes are wanted, but it isn't needed for the 99 problem.

`NIRA` (two tiers A/B × 17 groups × 16 attributes, ranges near 97–100, queried at `0x3b839`) is not draft classes; it looks like Superstar-mode or created-player ranges. Injury frequency doesn't appear to be table-driven (only `INJY`, the live injury list, and the `PINJ` rating); it's probably code or the in-game sliders.

## 8. Season structure and playoffs (09)

Investigated 2026-11-03 for modern rules (17-game season, 7-team playoffs). The 18-week season is done (below); the playoffs aren't.

**Schedules are data.** `template.dat` DB @`0x164480` holds `SCHD` (664/664 rows, full): two complete seasons, `SESI` 0 and 1. `SESI` 0 is year 1's only: at the preseason `0x41f2d7` sets `SESI` = (`SEYR` > 0), so every later year uses `SESI` 1. At creation and each new season the game copies the matching rows into the franchise DB (`insert into SCHD … where SEST = ? and SESI = ?`, `0x3dd718`). Week types `SEWT`: 0 preseason (`SEST` 9, weeks 0–3), 25 regular season (weeks 0–16 = 16 games + bye), 50 wild card (week 17, 4 games), 75 divisional (18), 100 conference (19), 125 Super Bowl (20), 150 Pro Bowl (21, teams 214/215). `strmdata.db` `SCHD` (320 rows, dated 2004) looks like a leftover.

**Season counts are derived from the schedule.** `0x3c0ff0` counts `SCHD` rows by `SEWT` and writes `SEAI` (`SERW` regular-season weeks, `SEFP` first playoff week, `SNWP`/`SNDP`/`SNCP` games per round, …). A stock year-3 save has `SERW` 17, `SEFP` 17, 4/4/2. So the number of weeks and games per round isn't a constant in that path.

**Bracket rows hold seeds, not teams.** The wild-card rows are `GHTG`/`GATG` = 2/5 and 3/4 (0-based seeds: #6 at #3, #5 at #4), one pair per conference. Later rounds hold 1023 and are filled as winners advance.

**Seeding is hardcoded to 6 per conference** (`0x41b590`, per conference):
- `0x41aa10` lists division winners (`SDST` = 0, ordered by `scst`) into the seed array.
- `0x41ab00` adds wild cards (`SDST` > 0); the count is `6 − divisions` (`mov ecx, 6` at `0x41b5e5`).
- Limits of 6 at `0x41aa88` and `0x41ab7b`; the re-sort by seed at `0x41a810` scans 6 entries (`0x41a87b`, `0x41a882`).
- The seed array is a global at `0x7ba428`: 2 × 6 words, ending at `0x7ba43e`. `0x7ba440` onwards belongs to other code (`0x41d58e…`, `0x41dfa9…`), so 7 seeds means moving the array.
- `TEAM.TMPS` (`'SPMT'`) stores each team's seed. Advancement (`0x41abf0` collects a round's winners per conference; `0x41b6f0` writes the next round's rows via `0x3d7a80`) assumes two byes.

**Per-week table capacities** in the franchise DB (`template.dat` @`0xab500`): `SCHD` 269 (a full stock season uses 268), `SCWE` 25, `OTIW` 672 (32 × 21), `OTGO` 704 (32 × 22, full), `OWGP` 22, `PONF` 22. A 17-game season with 14 playoff teams needs 272 + 14 = 286 `SCHD` rows, so these need `resized()`. Whether a bigger franchise save still fits the memory-card save is untested.

**What an 18-week season needed (hardware-verified 2026-11-03):**
- **Advancing:** after each sim, `0x135b80` calls advance-week (`0x3c4350`), which runs the end-of-week chain (`0x3c3f10`) and only then sets the next week (`0x3c38e0`; the last week + 1 becomes `SEWT` 175, the offseason marker). Any database error in the chain cancels the advance silently.
- **The Super Bowl lock:** the weekly fan step (`0x3d96d3`) reads `strmdata.db` `OWFW` for the current week. Its rows stop at week 20, since stock's week 21 is the Pro Bowl and has no team games. That missing row was what locked the Super Bowl at week 21.
- **Weekly owner values:** `OACI`/`OFAC` (weeks 0–16) are read without an error check, so a missing week just leaves stale values.
- **Offseason marker:** the offseason start (`0x3a9530`) hardcodes week 22 for `SEAI.SEWN` and its marker game, so with the Pro Bowl at week 22 it has to become 23.
- **Box scores** (`BOFF`, `BDEF`, …) only hold the current week, so the Pro Bowl week is where the Super Bowl's stats can be viewed.
- **Year 2+ is generated** (`0x41b8c0` → `0x41e280` when the year is > 0): copy the `SESI` 1 rows, then build 256 matchups from a formula (`0x41e150`: division games, the intra-conference rotation by `year & 1`, interconference by `(year + 6) & 3` through the table at `0x7261bc`, AFC division a vs NFC division `T[4a + k]`), place them in 17 weeks (`0x40c2e0`, per-week counts at `0x7261a8`: 16,16,14×8,16×7) and write them over the data (`0x41d970`). A stock year-2 save keeps 196 of the data's 256 matchups and only 14 in the same week. `0x41d970` deletes the Sunday-afternoon games (`GDAT` 3, `GTOD` 750–1097) and every regular-season game from week 17 on. Its cursor over the remaining rows (`0x41dc6b`) steps back after each row and only advances when a row is filled, so a row it has no game for hangs "Advancing To Regular Season" (hardware). The 18-week fix inserts week 17 after this step instead (`season17.py`, cave at `0x10f60`).
- **Preseason from year 2:** stock stops at franchise stage 6 (`MOIN.MCSA`, `0x41feb0`) for a picker, which writes `SCSE`, then generates 4 weeks (`0x40aa60`: `0x40a550` setup, `0x40a000` matchups with caps for 4 games, the same solver `0x40c2e0`). `season17.py` sends those years down year 1's path (`0x41ff2c`, `0x404656`): the data's preseason, no picker, with the real year still stored in `SEAI.SSYE`, which is what turns the regular-season generator on.
- **Day and time:** `GDAT` counts days from Thursday (0 Thu, 1 Fri, 2 Sat, 3 Sun, 4 Mon); `GTOD` is minutes, Eastern (780 = 1:00 pm). `GFTG` = 1 marks the Thanksgiving games.
- **Front end:** the stats screens label week 21 as the Pro Bowl (`0x130060`, `0x1300ec`); that's cosmetic. The `16, 17, 20, 21, 22` constants found in nearly every menu script are shared library code, not weeks.

**What a week changes, and jumping weeks** (2026-11-04, from a save taken after every week in xemu; `tools/save_diff.py` compares two saves, `tools/save_jump.py` does the jump):
- **`SCHD`:** `GSTA` 1 unplayed, 2 away team won, 3 home team won, 0 for playoff rows that haven't been reached. `GFHU` clears on played games. `SEAI.SGOW` is the `SGNM` of the week's featured game.
- **`TEAM`:** `TSWI`/`TSLO`/`TSTI`, `TWPC` (1000 × win share, ties half), `TCWP`, `TDWP`, `TSPF`/`TSPA`, `TCPF`/`TCPA`, `TDPF`/`TDPA`, `TSCS` (signed streak), and `tsaw`/`tsal`/`tsat` (away), `tshw`/`tshl`/`tsht` (home), `tscw`/`tscl`/`tsct` (conference), `tsdw`/`tsdl`/`tsdi` (division). Calculated from the real scores of 17 weeks, all of these matched the game for all 32 teams. `TSDS` (division rank) matched except for one tied pair: the Giants and Commanders had the same record, division and conference percentages, and the game ranked the Commanders higher despite a worse point difference, so its tiebreak goes further than those. `tscs` and `tsns` (conference and league rank) differ only among tied teams.
- **`OTIW` is what a week jump needs.** It has 32 rows per week in week order, up to and including the current week, and the current week's rows are zero placeholders filled in when the week ends. If the current week's rows are missing, Simulate Week returns at once and plays nothing. Variants split this: a save jumped by 17 weeks with `OTIW` from a real save simmed, and a real week 17 save jumped one week without new `OTIW` rows didn't. The table is stored at full capacity, so adding rows moves nothing.
- **Not needed to continue the season:** box scores, season stats (`PS*`, `PC*`, `B*`), `NEPO`, `AWPL` and `PPBS` can stay empty; the season still reaches the offseason. They do matter for awards and performance progression, so don't judge those on a jumped save.
- **Save slots:** the game lists at most 8 franchise files. The folder name comes from the save name: `Fran1` is `18E7386A51E9`, and each later number adds 1.
- **A later year isn't just `SEYR`.** With `SEYR` and `SSYE` set to 2 in a year 1 preseason save, advancing generated 272 games but left `SEWN` 2, `SEWT` 10 and `SERW` 0, with My Week saying Regular Season and the schedule screen saying Preseason, so `0x3c0ff0` didn't finish. Its rotation was column 3 of `ROTATION`, which is what `SEYR` 1 uses, not column 0 as in a real year 3. The cause isn't known.

**Seven playoff teams** (2026-11-05, xemu; `patches/playoffs7.py`). The seed array moved to the unused padding after `.data` (`0x80dea4`), a cave replaces the seeding routine `0x41b590`, and `0x41b6f0` collects 3 wild-card winners per conference. Things worth knowing:
- **Game numbers alternate by conference.** A round's games are AFC 0, 2, 4 and NFC 1, 3, 5, with the conference index added to the slot. The rows live out of order in `SCHD`: the two new wild-card rows sit after the Super Bowl's.
- **`TEAM.TMPS` is playoff status:** 4 home field, 3 division winner, 2 wild card, 1 still in contention, 0 out. A week's jumped-in `TMPS` of 15 is replaced at the next sim.
- **The draft order needs that status.** `0x3d42d0` runs after each playoff round and builds a 32-team list: teams with no 2-4 status, then the playoff losers, then the rest. A playoff team without a status goes in twice, overruns the heap block, and the game hangs on "Simulating Week" at the next `free`, with the music still playing. xemu showed it as `ECX = 0xC0000005` at `0x371fb5`. Stock's clinch step (`0x41aee0`, called at `0x41b56d`) marked only 2 wild cards, so `0x41b566` now passes 3.
- **Round counts come from the data.** With 6 wild-card rows in the schedule, `SEAI.SNWP` became 6 by itself, and the schedule screen listed all 6.
- **Older franchises.** A franchise with 4 wild-card rows (`SCHD` capacity 285) on the first 7-team XBE stopped at the end of the last regular-season week on hardware: all scores were in, and the week never advanced. The stuck save had AFC games 0 and 2 and the #1 seed's next game filled in, and nothing for the NFC, so the seeding stopped at AFC game 4, which has no row. A 7-team franchise has `SCHD` capacity 287 and `SEAI.SNWP` 6 (4 in an older one). Stock's clinch call passed `TPOM.TWNO` / 2 as the wild cards per conference. It now passes `SNWP` / 2 from the same routine's query. The seeding cave and the wild-card winners' collection (`0x41b746`, now a call to a stub) read `SNWP` with the query at `0x650370`, and with 4 they run stock's code and counts. In xemu (2026-11-08) a franchise created on a 6-team `template.dat` and jumped to week 18 got 4 Wild Card games and reached the Pro Bowl. A 7-team one got 6 and reached the Super Bowl. The stuck save itself still crashes after the divisional round (`0x371fb5`, the draft-order overrun), because the old XBE left it with a #7 seed marked in `TMPS` and the Jaguars, a playoff team, unmarked. **Not tested: an older franchise's next season.** Each season's rows are copied from `template.dat` (`0x3dd718`, DB `SCHE`), which now has 286 for a table with room for 285, so the copy may fail or leave 5 wild-card rows (`SNWP` 5 counts as a 6-team franchise in the stubs). In the preseason and offseason `SNWP` is 0, which the clinch step already skips.
- **Finding a crash in xemu:** QMP's `info registers` plus `x /64xw <esp>` show the exception code and return addresses on the stack.

**Roster minimums** (2026-11-05, xemu). Three tables in `template.dat`'s stats DB, none in saves, hold `PPIR` (roster minimum) and `PPIA` (active minimum, counting healthy players): `PLPS` by position (21 rows), `DRPS` by position group (17, keyed by `PDRP`) and `POSG` by wider group (10, keyed by `PPGR`). They load into 40-byte rows at `0x723298`, `0x7235e0` and `0x723888`, with `PPIR` at +0xD and `PPIA` at +0xE, and are read through `0x386b20` and `0x386bc0`. The "do not meet the minimum requirements" prompt follows `DRPS`: with `PLPS` alone at 0 it still appeared; with `DRPS` at 0 too and `POSG` running backs lowered by one, the Bears with their only fullback injured got past it, advanced to the regular season and simmed week 1. `POSG` wasn't tested separately. Fullback defaults: `PLPS` 1 and 1, `DRPS` 1 and 1, `POSG` running backs 4 and 2. All three are zeroed or lowered by `patches/optional_fullback.py`, whose output matches the xemu-tested `template.dat` byte for byte. `fe.qkl` and `game.qkl` don't change with it. The franchise Breakdown screen's REQ and ACT REQ columns are `DRPS`'s `PPIR` and `PPIA`: on hardware (2026-11-05) every position matches, FB shows 0 and 0, and the totals are 44 and 25. In a played game with a fullback formation and the team's fullback moved to running back, a tight end lined up at fullback. **A `PPIR` of 0 needs an XBE change:** when a team is over its roster limit, `0x396bd0` ranks position groups to cut from by players x 100 / `PPIR` (filled by `0x386d10`), so the table change alone divides by zero at `0x396d99` (`c0000094`) and hard locks the console, in preseason or later, whenever a team first trims. `optional_fullback.py` makes that `div` treat 0 as 1, the fullback's stock value. Among functions that call the four minimum getters, the only other division is the `fidiv` at `0x397320`, which guards its divisor. Values these functions pass on weren't traced further.

**Game rules aren't in tables.** Overtime and kickoff/touchback spots have no DB fields, only UI strings ("End of Overtime Quarter", "OVERTIME!!!", "Touchback"), so they live in gameplay code.

**Playbooks and kickoff alignment.** `GAMEDATA.dat` entries are LZH1-compressed TDBs. Kickoff plays (`PLYL` 5, 9, 10, 3372-3374) use `SETL` 5 (`FORM` 6) in 50 playbooks, with identical positions in all of them. Onside uses `SETL` 67, safety kickoff `SETL` 8, and the return teams `SETL` 6 and 70 in 49 playbooks. Each `SETP` row is a player (`poso` 0 = kicker, 1-10 = coverage) and `SETG` holds his spot as floats in `x___`/`y___` and mirrored `fx__`/`fy__`, apparently yards from the ball: kicker (-3.5, -3.8), coverage line `x` ±24.5 at `y` -6 to -7.5. In xemu, adding 10 to one player's `y` put him about 10 yards upfield, so `+y` points downfield toward the receiving team. Assignments are `PLYS` → `PSAL` steps: all coverage players share `PSAL` 22, so the same script runs for each. Step code 51 is a wait, and it ends on its timer (`val1`, 0-255) or when the receiving team touches the ball (seen in xemu, including on a muffed squib). At 64 it ran out as the kicker landed, and at 160 it outlasted a deep kick's flight. `patches/kickoff_setup.py` changes these and repacks the archive, since recompressing changes stream sizes; `fe.qkl`'s header copies then need `qkl_sync.py`. The return set uses the same `y` from the ball: returners at 65 and 55, front line at 15.

**Field coordinates and the kickoff spot.** Read from xemu memory at a kickoff lineup, through the gdb stub (`-gdb tcp:127.0.0.1:1234`, physical RAM at VA `0x80000000`; QMP `pmemsave` hung and crashed xemu). Live positions are yards from midfield, with the kicking team's half negative: the kicker at (-3.8, -24.0) against his playbook spot (-3.5, -3.8) from a ball at -20, its own 30. The game state at `[0x801c50]` holds the ball spot, `+0x34` across and `+0x38` downfield. Six paths (`0x45bef`, `0x45fbd`, `0x4660d`, `0x4715e`, `0x16a96d`, `0x293bc9`) set a kickoff to (0, -20.0) when `+0x3c` is 0 and call `0x294180`. `0x293e4d` turns a -20.0 spot into -30.0 (the 20) for a safety kick. `patches/kickoff_spot.py` moves all seven to -15.0. Play Now's kickoff is `0x30c730` instead: an adjustment `[[0x8034f0]+0x4c]` (normally 0) minus the shared 20.0 at `0x6fc624`, passed to the setter `0x294180` (called every frame from `0x30c75d` while a kickoff is set up). The safety free kick is `0x30c7e0` (-30.0). `0x1b83f7` picks -20.0 for situation 0.

**Play results (in progress).** After a play, `0x269c50` calls `0x2699b0`, which runs the result rules (`0x2672e0`, `0x2687d0`, `0x269020`), then `0x293ba0` with the dead-ball spot, stored at `[0x803504]+0x24/+0x28`. In `0x2687d0`, `0x268eab` is a touchback: the spot becomes +30.0 or -30.0 (the 20 on one side or the other, by direction flag `[ebp+0x14]&1`), unless `0x267140` finds an event of type 0x14 or 0x15 between -50 and 50 and uses its spot. It isn't yet known whether this path is kickoff-only or shared with punts and interceptions. Field constants: `0x709434` -50.0, `0x7093e0` 50.0 (goal lines), `0x7093e4` 30.0, `0x709914` -49.0. Debugger breakpoints and watches make xemu unplayable, so use them only when nobody is playing.

**The play event list** (2026-11-08, xemu, `tools/play_events.py`). `0x267140` and the other result rules read a per-play list: its id is `[0x7405cc]`, its header `[[0x764ba8] + id*4]` (u32 capacity 50, count, entry size 32, callbacks), and entries follow the callbacks. `0x3424a0` returns the next free entry, `0x3424e0` commits it, `0x342550` gives the count and `0x3424c0` an entry. An entry has the spot as floats at `+0x10`/`+0x14` (absolute field yards, as in the game state) and a u16 type at `+0x1c`. The list is cleared once the play's result is applied. Types seen in Play Now:
- **Every play:** `0x03` at the snap or kick spot, then `0x02` with no spot at the end.
- **Kickoff (a catch and return):** `0x0d` and `0x20`, then `0x1a` where the ball was kicked. `0x0e` was at (22.4, -48.8).
- **Run play:** `0x04` (handoff), then `0x2e` and `0x1e` at the tackle spot.
- **Scramble and sack:** `0x27`, `0x22`, `0x09`, and `0x1a`.
- **Pre-snap penalty:** `0x1b` (delay of game).
- **Readers:** `0xcc4b2` and `0x2b52f2` test the range `0x0b`-`0x0e`.

`0x0e` is gaining possession: `0x28b8bf` and `0x28b8ff` write it at the player's spot (`+0x1b8`/`+0x1bc`). The same routine writes `0x15`, the type `0x267140` lets a touchback keep. `0x286af5` passes `0x0b`, or `0x0c` when `[0x803504]+0x40` is 6, to the second event function `0x285db0`. **No event marks the ball landing.** The kick-short-of-the-20 rule needs the first ground contact from the ball's own state. Leads: the incomplete-pass check, since a pass that hits the ground needs the same test, and the ball object behind the `0x1b8` positions.

## 9. Team logos and uniforms (09)

All of this was tested on hardware on 2026-11-04 unless it says otherwise. The tools are `patches/team_logo.py` and `patches/team_helmet.py`.

**Menu logos.** Entry = `TLGL` + 1. "All Redskins" (TGID 208) shared the modern team's logo in `TLGL`/`TLGS` in `template.dat` (3 DBs) and `strmdata.db`. Those are the copies the menus read: changing `TLGS` in `DB_TEAMS.dat` alone did nothing.

**Uniform tables.** `TUNI` (`UFID`, `TGID`, `TUCO`) lists a team's uniforms, in `template.dat` (3 DBs) and `DB_TEAMS.dat`, and it isn't sorted. Washington's rows are `TUCO` 0 = 283 white, 1 = 284 burgundy, 2 = 281, 3 = 282, 4 = 286, 5 = 285. The Y screen calls them Default Home, Default Away and Alternate N. The modern team shared 283 and 284 with four classic Redskins teams (TGIDs 102, 117, 151, 208). Moving those to 287 and 288, which other classic Redskins teams already wear, is safe. Uniform clashes are settled by `UNIF.ULTF` (`0x39e2e0`): with the same lightness, the road team switches.

**The freeze.** The directory parser (`0x375a60`) keeps the offset of only every 20th entry, and `0x377030` adds rounded sizes from there. Saving smaller sizes for 283 and 284 put entries 284 to 299 2,816 or 6,400 bytes early, while entry 300 was correct again. So uniforms the build hadn't edited froze too, and it took a baseline build to show the helmet work was the cause.

Running the game's decoder at those wrong offsets gave status 3 for 284 and 286, and status 1 with no output for 285 and 288; the real offsets give status 1 and full output. Status 3 fits the freezes. No output may explain why the screen showed a stale uniform (Eagles whites; entry 131 is an Eagles white that `fe.qkl` preloads), but neither link was traced on hardware. The earlier lock on UFID 292 is in the same block of 20, though that build's contents weren't rechecked.

The fix keeps stock sizes and pads with zeros, which also leaves the header and `.qkl` copies stock. `lzh1emu.compress` reproduces stock entries 283, 284 and 292 byte for byte.

**Theories that were wrong.** A picker loop (`0xe30d0` ends on a fetch error), the Y screen itself, dark road uniforms in general (the Cowboys can pick all of theirs), and the moved `TUNI` rows. The dotted rings on the crown are on every team's helmet; the user reads them as the stadium lights, and they aren't from this mod.

**Writing the art.** Only the top mip follows the 0x80-byte header. Writing the smaller mips 0x80 late scrambled them and damaged the next texture's header. Reducing the palette caused rough edges and stray dots at a distance, so the logo now uses the stock palette's nearest colours and only touched pixels change.

**Placement.** Stock logos centre near (186, 65) on the right panel, the median of the 31 home helmets measured. The final W's gold spans x 172–197 and y 39–85, so its front edge is level with the Falcons' and Cowboys' logos. A logo must be mirrored between the panels to face forward on both sides, as the stock logos and the real helmet do.

**Training camp.** Commanders showed the old helmet there. Entries 626 and 627 have the same helmet as 283 and 284 but different jersey and pants textures, and the game loads them under flag `0x802abd`. Repainting them fixed training camp. What sets the flag isn't traced.

**Not traced.** `0x377305` reads a per-entry cache through the handle at `+0x90` and the table at `+0x94` when `0x7b68c4` is set, and `0x37a790` fills it. Whether it lasts between boots isn't known, and it caused no known trouble here.

## 10. Commentary team names (09)

`patches/commentary_team.py` is built on this. Read from the code and data. The surname recording works on the Xbox and sounds good to the user, and the '91 Redskins still get "Redskins" (2026-11-05). The city recording worked too but was quieter than "Cowboys". `tools/speech_clips.py` decodes clips to WAV and measures them, and the numbers agree: RMS over the active parts is about -12 to -13.5 dB for his "Cowboys" takes, against -15.8 and -18.1 for the two city takes the first build mostly uses. The surname takes are -16.3, -15.3 (the sentence-ending take) and -14.4.

**MicroTalk, as the game decodes it (`0x445db3`–`0x447080`).** A `SCDl` block is a `u32` sample count (big-endian in `GSTR` streams, little-endian in `PT` ones), `u32`, a byte, a marker byte, then frames of 432 samples. The stream's first block starts with a header: 1 bit reduced bandwidth, 4 bits for the multi-pulse threshold (32 - x), 4 bits for the first gain (8 × (x + 1)), 6 bits for the gain step (1.04 + x × 0.001). Reflection coefficients 0–3 are 6 bits, and 4–11 are 5 bits with 16 added to the index. The pitch memory holds the excitation, copied before the filter runs. Frames are byte-aligned: the last byte the reader has loaded after a frame is a marker, and 0xee means the next frame is followed by raw samples (big-endian offset, count, then the samples). The tables are at `0x727cd8` (rc), `0x727dd8` (codebooks) and `0x727fd8` (commands). The check that the decode stays in step is that each block's frames use all but 2 or 3 of its bytes, which held for all 21 clips tested.

**Other recordings of the name.** `0x000a`, sub-bank 1351 (descriptor `0x237e`, audio `0xaad`) is the player surname, the `--clip surname` option. Sentences use its takes 0 and 2 mid-sentence and take 1 only as the last slot. The surname bank's audio starts at `0x566`, and project 2 has its own recording in `0x412b`, sub-bank 958. `0x2026` (project 1, 13 sentences) sounds like the in-stadium announcer to the user (2026-11-05), so it doesn't suit Al's lines. `0x414f` also holds the name, in project 2, and whose voice that is isn't known.

**Name lookup.** `0x4ec3a`–`0x4ece1` read each team's `TDNA` and `TLNA`, upper-case them (`0x4e800`) and binary-search name tables in `SOUNDDAT.dat`, using the comparer at `0x2aa700`. A table is `u32 count`, then `(u32 string offset, s32 value)` rows sorted by name, then the strings. A missing name takes the fallback, which is why the renamed team became "the home team" or "the visiting team": the fallbacks are those tables' `HOME TEAM` and `VISITING TEAM` rows. The results go to `0x7cf5a0` (home) and `0x7cf5b0` (away), one byte per slot:

| Slot | Table (`SOUNDDAT.dat` entry) | Input | Fallback, home/away | Bank, descriptors, audio (`SPCHDATA.dat` entries) |
|---|---|---|---|---|
| +0 | 4 | `TDNA` | 63/64 | `0x419`, `0x33ca`, `0x1af9`; home team only (`0x2a5256`). Al's "Welcome to <sponsor> Stadium" with invented sponsors, by ear: 32 (Redskins) is Global Domination Bank, 63 (`HOME`) is New Road Fidelity. When it plays isn't known |
| +1 | 5 | `TLNA` | 33/34 | `0x2026`, `0x3433`, `0x1b62`; project 1 |
| +7 | 7 | `TDNA` | 56/57 | `0x08d`, `0x29cb`, `0x10fa`, and `0x7f1`, `0x2a24`, `0x1153` (first 50 only) |
| +8 | 8 | `TLNA` | 46/47 | `0x1f0`, `0x2a56`, `0x1185` |
| +9 | 18 (`0x12`) | `TDNA` | 62/63 | Not traced; event `0x4038` is project 2, not project 0 |
| +a | 19 (`0x13`) | `TLNA` | none seen | `0x414f`, `0x2ac8`, `0x11f7`; project 2 |

The rest hold coaches and stadiums. A value `v` loads descriptor `base + v - 1` and audio `base + v - 1` (`0x2b3660`, called from `0x2b3e10` and `0x2b4xxx`). Past value 59 in table 7, sub-bank numbers stop matching the values, so a borrowed slot has to be 50 or lower to be valid in both nickname banks.

**Speech files.** `SPCHDATA.dat`: entries 2–9 are the event files of projects 0–7 (`03 12 3c 07`; a project is event ID >> 13). Project 0 is the main file, with the play-by-play banks. After them come audio entries (`SCHl` streams, codec 4, 36 kHz, which should be EA MicroTalk), then sub-bank descriptors from `0x1e37`.

A descriptor is `u16 bank, u16 sub-bank, u8 type, u8 samples, u16, u32 total`, then each sample's big-endian `u16` offset (256-byte units) and `type` parameter bytes, then one `u32` mask per parameter listing the values present. The sample's stream is the audio between its offset and the next (or `total`), so zeros after a stream are harmless.

**Sentences.** A sentence is a header (`?? WW ?? ?? 00 00 00 00`, `WW` is usually 0x64) and a table of offsets in 4-byte units from the header. Each offset leads to a slot: `u16 bank, u8 event parameter, u8 flag, u32 rule count`, then 8-byte rules holding a mask and an argument. Slots play in order. The third rule selects `p2`, the take: mask 5 allows 0 or 2, and 6 allows 1 or 2.

**No sentence uses both a nickname and a city.** A scan found 114 sentences with a name bank and none mixes them, so "Washington Washington" shouldn't happen. Two hits, `0x1d6c` and `0x9ab0`, weren't resolved to a sentence.

**Real stadium names** come from table 17 (`SOUNDDAT.dat` entry 0x11, read at `0x4e640`, stored at `0x7cf598`), keyed on the stadium's name rather than the team's. `FEDEX FIELD` is 26. This patch doesn't touch it.

**The change.** In table 7, `COMMANDERS` takes `GALAXY`'s value, 34. No team uses Galaxy, an NFL Europe name. Sub-bank 34 of `0x08d` and `0x7f1` then holds Al's "Washington", keeping each slot's parameters. With `--clip surname` (take 2 mid-sentence, take 1 at the end), `0x08d`'s rows get takes 2, 2, 1 and `0x7f1` gets take 2. With `--clip city`, `0x08d`'s rows get (0,6,0), (0,6,1), (0,0,0) and `0x7f1` gets (0,6,1). In table 4, `COMMANDERS` joins the Redskins at 32, so it behaves as stock Washington does and bank `0x419` isn't changed. The first two test images put "Washington" in that bank, which was a mistake. Each table loses `GALAXY` and a spare row (`NFL-E ALUMNI`, `MILLENIUM`) because the new name is longer and an entry can't change size. `--check` rebuilds both tables unchanged and compares them with stock. Tables 6, 16 and 18 and John Madden's team references aren't changed.


## 11. Long franchises and full tables (09)

Tested 2026-11-06 in xemu, not on hardware: the `Season4Works` save, on the 17-game build without free agents, with `--save-unlock`. The user's team was set to CPU control in `OWNR` (the `CF*` flags) and every game was simmed. Offseasons were skipped with Start New Season. Years 5 to 10 each finished through the Pro Bowl with no stuck week, and every save passed its CRC check. `tools/table_growth.py` compares table counts across saves.

| Table | Capacity | Y5 | Y6 | Y7 | Y8 | Y9 | Y10 |
|---|---|---:|---:|---:|---:|---:|---:|
| `PLAY` | 2,754 | 2,635 | 2,635 | 2,635 | 2,635 | 2,635 | 2,635 |
| `PSDE` | 6,000 | 4,817 | 5,474 | **6,000** | **6,000** | **6,000** | **6,000** |
| `PSNG` | 9,000 | 6,632 | 7,460 | 8,253 | 8,791 | **9,000** | **9,000** |
| `PSOF` | 3,600 | 2,104 | 2,325 | 2,558 | 2,728 | 2,813 | 2,813 |
| `PSOL` | 3,000 | 1,331 | 1,564 | 1,749 | 1,888 | 1,946 | 1,974 |
| `PCDE` | 1,550 | **1,550** | **1,550** | **1,550** | **1,550** | **1,550** | **1,550** |
| `PCNG` | 2,100 | 2,013 | 2,013 | 2,023 | 2,055 | 2,055 | 2,064 |
| `PCOF` | 900 | 805 | 812 | 830 | 854 | 854 | 854 |
| `PCOL` | 430 | 415 | 420 | 424 | 424 | 424 | 424 |

- **`PLAY` doesn't fill.** It stays at 2,635, including the 104 Pro Bowl rows that exist until the offseason. Retired players (`TGID` 1014) and some free agents leave each offseason as rookies arrive. The code that decides this hasn't been traced, so the cause of the flat count is inferred.
- **Full season tables lose the oldest season first.** `PSDE` rows for the first season go 893, 786, 642, 155, 0, 0 across Y5 to Y10, and `PSNG` goes 1,233, 1,093, 964, 806, 517, 286. The latest season stays complete: about 1,030 `PSDE` rows and 32,000 tackles a year, before and after the table filled. So a long franchise keeps a rolling history, not its full history.
- **A full `PCDE` loses career rows.** Players with season rows and no career row go 26, 32, 52, 96, 83, 112 across Y5 to Y10. Their career defensive totals are presumably missing. Not checked on the screen.
- **Unexplained:** `PCOF`, `PCOL` and `PCKP` stop growing below capacity (854 of 900, 424 of 430, 183 of 325).
- **Player IDs are reused.** New players get the lowest free `PGID` (`0x39f910`), and 152 changed owner in one offseason. In one year 5 preseason save, 22 players with `PYRP` 0 had career game rows. The end-of-season saves show 0 or 1 such player above 17 career games, so inherited stats aren't confirmed.
- **The save file isn't the limit.** It's always 1,490,944 bytes. A table with flag `0x10` stores nothing while empty and its full capacity once it has rows, so the DB's size depends on which tables have rows, not on how full they are (1,335,932 bytes at years 3 and 4).
- **Stock does the same, sooner.** The stock template has the same capacities, and the roster's real career history is preloaded (`PSNG` rows from `SEYR` -10). The stock-roster saves `FranchisePreseasonYear2` and `Year3` have `PSNG` full at 9,000 of 9,000 by year 2. Between them, the rows for `SEYR` -10 to -7 (120, 1, 288 and 410) disappear while year 2 grows from 609 to 1,447, so stock also drops the oldest season first. `PCDE` is 1,379 of 1,550 there and growing by about 180 a year, so it should fill around year 3 or 4. The modern roster starts with no history, so it keeps every franchise season for longer.

Not tested: the free-agent build, which starts about 97 `PLAY` rows higher; a user-run team, including its draft and free agency; and years past 10.

Driving this in xemu:

- **Season sims:** Play/Simulate's fifth item is Simulate Preseason, Simulate Season or Simulate Playoffs. A trade deadline notice can come first, then a confirmation that defaults to No. The Super Bowl and Pro Bowl menus have three items.
- **Sign Player:** a CPU-controlled user team still gets this prompt. Answering CPU Sign Player carries on a sim that's running.
- **Saving:** leaving the franchise from its root menu autosaves. A save made at the Pro Bowl reloads into the season menus, and opening Weekly Schedule then shows the offseason prompt.
- **Offseason:** the task list's Start New Season, then Accept, skips every remaining task. Retirement notices can come first, in any number.
- **Don't idle on the main menu:** the attract demo starts, and leaving it is the known freeze.
- **The window can't be minimised:** `PrintWindow` then returns an empty image.

## 12. The radio show (2005 to 07)

Read from the code and data on 2026-11-10. Nothing is built or tested.

- **Where it is.** The Tony Bruno Show's audio is the front-end speech file: `SPCHFEDATA.DAT` in 2005 (4,125 entries, 245 MB) and `SPCHFEDT.dat` in 06 (4,526, 263 MB) and 07 (4,437, 228 MB). It's the commentary's format: entry 0 holds the sub-bank descriptors, entry 1 a small event file, entry 2 the show's event file, and entries from 3 are audio banks of "PT" streams (MicroTalk, 18 kHz, mono). `tools/radio_clips.py` decodes them to WAV in step. The 06 and 07 story text still names Tony Bruno.
- **07 is the last game that plays it.** Its loader (`0x29a9d0`) registers `0x1151` descriptors and loads event file 2. 08 ships 07's file byte for byte, but its loader (`0x2a7cd0`) registers only the first `0xa6` and never loads entry 2, and its story text says "Sports Radio". 09's loader (`0x2b4680`) is the same as 08's, apart from the first audio entry being 2 instead of 3 (`0x7f392c`), and its file is cut to 169 entries (2.3 MB): the 166 short clips, with no show event file.
- **What the clips are (the user, by ear, 2026-11-10).** 07's entry 195 is Tony on last week's action, 400 introduces a head coach by name ("Head coach Brian Billick on the Tony Bruno Show"), and 2000 is a fragment ("Here's..."). 2005's entry 170 is callers ("Hey Tony, thanks for taking my call"). 09's remaining clips are all the draft's "<team> is on the clock".
- **Where it plays in 07 (xemu, 2026-11-10).** Franchise → Storyline Central → EA SPORTS Radio: a screen with Play Next Segment, Replay Last Segment and Play Music. The show also runs in the franchise menus.
- **How 07 fires it.** Game code calls small stubs that build an event ID (`0x405f80(0, 0, event)`) and call `SPCH_AddEventV` through the pointer at `0x75b720`. The show has 11 stubs, at `0x4f000`–`0x4f140`, `0x50d24` and `0x50e36`, for events 0, 1, 2, 7, 9, 0xa, 0xb, 0xc, 0x10, 0x11 and 0x12, with 1 to 12 parameters. One event is one segment: Play Next Segment fired event 0x10 (parameters 8, 2, 4) and then event 7. The segment chooser is around `0x50f80`–`0x511f0` (jump table at `0x51158`), reached from `0x29b1a5`. `tools/spch_trace.py` logged this over the gdb stub.
- **08 and 09 have none of it.** A search for the stub pattern finds the 11 show stubs only in 07. The 32 other stubs, the in-game commentary's, are in all three. So 09 has the speech library and the bank loader, but no segment chooser, no event stubs and no radio screen. A port has to supply the data (07's file and a loader patch), new code that fires the events with sensible parameters, and somewhere to start it.
- **The show's event file (07's entry 2).** After an 8-byte entry header: `u32 project` (0), `u16`, `u16`, `u32 event count` (11), `u16 0x64`, `u16 0x1f4`, then one `u16` offset per event, in 4-byte units from the entry's start. `tools/speech_events.py` lists each event's sentences and banks. An event is `u16 ID`, `u16`, `u16`, `u16 sentence count`, `00 64 00`, `u8 parameter count`, then a `u16` offset per sentence (4-byte units from the event). The parameter counts match the stubs'. A sentence is as in §10, with its third byte being 4 × the slot count. Event 2 has 18 sentences and 8 parameters, and event 0xb has 30 and 12.
- **07's file is a superset of 09's.** Entry 1 (the draft's event file) is identical, 09's 167 audio entries are 07's entries 3 to 169, and the first 0xa6 descriptors match. `fe.qkl` preloads the stock file's header and entries 0 and 1, whose sizes differ in 07's file, so the test gives 07's file a new name instead (`spchfe07.dat`), which the game then reads from the disc.
- **Tony talks in 09 (xemu, heard by the user, 2026-11-10).** `patches/radio_show.py` restores 07's loader behaviour: `0x1151` descriptors, first audio entry 3, and event file 2 loaded through a cave at `0x10e40`. `tools/xemu_call.py` made the running game fire events 7 and 0x10 with 07's parameters. Two things had kept it silent:
  - **Volume.** The menus' sample player (`0x2b3c70`, the library's sample request callback at `[0x7bc420]`) queues each sample on the speech stream (`[0x7f2d84]`, through `0x37b9d0`), but sets the stream's volume (`0x37ba80`, level from `0x2a7d50` with `dl` 0x6e and mixer group 3) only when the event ID is `0xe000`, the draft's. The patch removes that `jne` (`0x2b3c9a`).
  - **Where speech is processed.** `SPCH_Play` (`0x448891`) is called for the menus by `0x2b4d20`, when the stream is idle. That function is the update entry of a module at `0x7581a0` (`0x2a2e00`, `0x2b4d20`, `0x2bb770`), which only some screens' module lists include (lists at `0x7581b8` and `0x7581d4`). The fantasy draft screen runs it; the main menu doesn't, and events fired there wait in the queue. The franchise menus haven't been checked.
- **The two events heard.** Event 0x10 with (8, 2, 4) took sentence 2 (banks 0x1f, 0x33, 0x40, 0x34) after sentence 0 failed on parameter 3, which is the normal fall-through. Event 7 is two banks (7 or 6, then 0x56).
- **Event 0x10 is the trivia segment** (the user, by ear: "who can guess how heavy a football is?", then a caller who gets it wrong). Its first parameter is the question (a row value + 1), the second is 2, and the third is 1, 2, 4 or 8 from a row value of 0 to 3.
- **The show is a list of rows in the franchise save, and 09 still writes them.** 07's player (`0x50e60`) reads row `stRK` = n of table `stRS` (fields `stRS`, `stET`, `stEI`, `TGID`, `stR1`, `stR2`, `srST`; 15 in `stRS` means not in the show) and switches on `stRS`, 0 to 12, through the jump table at `0x51124` to the event stubs. Play Next Segment and Replay Last Segment step n (`[[0x79f1e0]+0x18]`, at `0x51170`). 09's XBE still has the insert (`0x61a558`: rows move from the queue `stRL`, by priority `stPT`, into `stRS`), and 09 saves hold them: `7GameBrokenSave` (week 17) has 3 `stRS` rows and 1 in `stRL`, with `stET` (the story event type) 23, 13, 14 and 28, a team, and up to three references. But every 09 row has `stRK` and `stRS` at 15. 07 mentions `stRS` in 24 queries and 09 in 3, so the part that gives each row a slot and a segment type, and adds the filler such as trivia, is what 09 lost.
- **07's show code, mapped for a move into 09 (2026-11-10, read only).** It's one block, `0x4ef20`–`0x51600`, 37 functions and about 10 KB, with its 41 query strings at `0x649f28`–`0x64afb8`:
  - the event stubs (`0x4f000`–`0x4f160`), the builder (`0x4f160`–`0x508d0`, which gives rows their `stRK` and `stRS` and inserts filler), the player (`0x50e60`) with its two big cases (`0x508d0`, `0x50d50`), and the step function `0x51170(stream idle)`, which 07's menu speech update (`0x29b1a0`) calls so the show moves on by itself
  - setup and teardown: `0x51220` (called from `0x1b5600` and `0x1b5623`; it creates a table `stRP` at run time), `0x51410`, `0x514b0` and `0x4ef20`. These touch the screen and audio modules and have the most outside calls
  - the core calls only eight outside functions, and seven have exact matches in 09 (`tools/xmatch.py`): `0x405f80`→`0x447e80` (event ID), `0x3e5fb0`→`0x427eb0` (query), `0x3e3900`→`0x425800`, `0x335270`→`0x36efb0`, `0x4e670`→`0x4e800`, `0x41ba73`→`0x45d9e3`, `0x41ab0e`→`0x45ca7e`. The eighth, the name-table search `0x290960` (54 bytes, comparer `0x290910`), is inlined in 09 (comparer `0x2aa700`) and would be copied
  - every table the queries use is in a 09 franchise save (`AWPL`, `COCH`, `MOIN`, `PLAY`, `SCHD`, `SCOS`, `SEAI`, `TEAM`, `stIN`, `stRS`) except `stRP`, which the block makes itself. `stIN.stRP` exists in 09
  - still to map: about 20 globals (the show's state object at `[0x79f1e0]`, which holds name tables at +0x10 and the segment index at +0x18; `0x76e0xx`; `0x7902xx`), and where the name tables come from
  - room in 09's XBE: no section has 10 KB spare. The last section, `.XTLID` (file `0x767000`, 0x920 bytes, flags 0x38), can grow at the end of the file, which makes `default.xbe` larger for the first time. `tools/xqueries.py` lists the queries on a table with the code that uses them
- **07's show code runs in 09 (xemu, 2026-11-10; the speech log only, not yet heard).** `patches/radio_transplant.py` copies `0x4f000`-`0x51410` (stubs, builder, player, step, start, stop), the name search `0x290960` and the query strings to `0x81a000`, fixing calls, jump tables, strings and globals from the maps above. `radio_show.py --show` puts it in `.XTLID`, the last section, which grows and becomes preloaded and writable (flags 0x07), so `default.xbe` is 7,782,400 bytes. The enlarged XBE boots.
  - Globals, matched with `tools/xglobal.py`: `0x790250`→`0x7f2c80` (`SOUNDDAT.dat` handle), `0x790354`→`0x7f2d84` (speech stream), `0x790450`→`0x7f2e80` (music stream), `0x6cd3b8`→`0x72aae8` (stack cookie), `0x79ee40`→`0x80195c`, `0x7a2ca8`→`0x805ea4`, `0x7902d8`→`0x7f2d08`. The show's own (`0x79f1e0` state pointer, `0x76e240`, and the nickname and city tables `0x791998` and `0x7919a4`, which are `SOUNDDAT.dat` entries 7 and 8) get new slots. 09's `SOUNDDAT.dat` name tables are the same as 07's.
  - More function matches: `0x33e690`→`0x3783d0` (load an archive entry), `0x33cbc0`→`0x376900`, `0x3635c0`→`0x39e640` and `0x363650`→`0x39e6d0` (temporary table), `0x2896d0`→`0x2a3470`, `0x289900`→`0x2a3740`, `0x289960`→`0x2a37a0`, `0x341ec0`→`0x37bc00` (stream status), `0x341d10`→`0x37ba50`.
  - State object (0x40 bytes, fixed here): +0x10 and +0x14 name tables while building, +0x18 segment index, +0x19 playing, +0x1a just built, +0x1b first segment pending, +0x1c this show has been played. `start(0)` builds the show if no row has segment type 0 and plays it unless it has been played; `start(1)` replays.
  - 07 started it from a screen command (`0x1b55d0`, case in `0x1bbea4`: 0 start if the `OPTS.OSPR` option is on, 1 replay, 2 stop, 3 and 4 next and previous), and its menu speech update (`0x29b160`) called `step(stream idle)` every frame. 09 has neither the option nor the command, so a new hook at the end of 09's update (`0x2b4d47`) runs `start(0)` every 256th call while nothing is playing, then `step`. The franchise menu runs that update.
  - The menu speech update, and so the hook, runs every frame on every menu screen: `0x1e01da` walks the list at `[0x7f2c94]` (music update `0x2a2e00`, speech update `0x2b4d20`). Events fired at the main menu right after boot weren't processed, for a reason not found. `0xffe50` returns the game mode, 2 in a franchise and 0x1f at the main menu (xemu). `0x1e0210`, 07's `0x1cd930`, returns 1 in both, so it isn't a test for being in the franchise menus.
  - The mode comes from the franchise database: `0xffe50` reads `MOIN.MTYP`, and it's already 2 on the franchise setup screens. `MOIN.MCSA` is the stage: 0x1f while franchise mode loads (the "Loading..." box), 2 on the setup and team select screens, 3 in the fantasy draft (with 5 resource sets, so the show stays off there), 5 in a new franchise's menu at training camp, and 9 in the user's regular-season saves (`MPSA`, the previous stage, is 1, 2 and 8 there). The offseason's stages weren't read. `0x61d214` is the game's own `select MCSA from MOIN`.
  - Player names: the builder's check (`0x4f570`) lets a story through when the player's `PCMT` isn't 999 or his upper-cased `PLNA` is in `SOUNDDAT.dat`'s surname table (entry 9, 3,043 names). Events 2 (`0x50d50`) and 0xb (`0x508d0`) get `PCMT` as a parameter, and their sentences come in pairs using bank 8 or bank 0x2c, one keyed by `PCMT` and one by surname. `PCMT` IDs are stable across years (54 was a Brown in 2006 and still is), and the show's `PCMT` recordings are first and last names, by ear. `radio_transplant.py` patches the three places to behave as if `PCMT` were 999.
  - Loading a save (xemu): Franchise at the main menu gives a NEW / LOAD screen (mode not 2), then the file list (mode 2, `MCSA` 1, `MPSA` 0x1f). With a new franchise saved at training camp, `MCSA` stayed 1 at "Load successful" and changed only after OK. With the user's week 17 save, `MCSA` (9), `MPSA` (8), `MISB` and `MNAI` already read the save's values at "Load successful", the same as in the franchise menu afterwards, so the database can't tell the two apart.
  - What can: the byte at `0x774804`, a count of loaded menu resource sets (`0x35eb3c` loads an archive entry and adds one; `0x35f4ca` drops one). It was 5 at the main menu, NEW / LOAD, the file list, "Load successful" and the new-franchise setup screen, and 6 in the franchise menu (new or loaded) and on Rosters. The hook records the count while outside a started franchise and needs a higher one.
  - Simulations: `[0x802400]` is set at the start of every sim routine (`0x178ddc` and the others around `0x1788aa`-`0x1790c9`, and a second set at `0x18392a`-`0x184632`) and cleared at the end (`0x178f60`); it read `0x1e0300` through a season sim and 0 after cancelling with B. `[0x743b08]` counts games as they sim. The sim loops call the menu audio updates in `[0x7f2c94]` themselves, so the show's hook runs during a sim. Simulate Season asks twice (the trading deadline, then "Simulate entire Regular Season?"), each with the cursor on the cancelling answer.
  - Dead ends: the six flow objects of `0x34c30` read the same at the main menu, the setup screen and the franchise menu (1, 0, 0, 1, 0, 1), and asking for a seventh crashes; the menus' "start the music" isn't called on the way in from a load; `0x3783d0` (load an archive entry) is called constantly while a show plays; "Load successful." (`0x6feee8`) is only formatted at `0x31f578`, a text builder for every file message. `tools/xemu.py ram` sometimes returns a wrong picture of memory: check a known value in each dump, and take several per screen.
  - The state object's +0x1a has to start as 1. 07's radio screen set the object up; with 0, a show that was already built when its save was loaded played twice, because `start()` marks a show played only when +0x1a is set.
  - A franchise left for the main menu stays in memory: on choosing Franchise again its stage still reads 9 until the setup screen resets it to 2, which is why the hook waits for 12 good checks in a row. After a simmed week the old show's current segment plays out, then the player finds no row, and the new show is built.
  - Menu music: `[0x7f3010]` is its state (1 asked to start, 5 fading out) and `[0x75706c]` is set when it's stopped. `0x2a3470` (07's `0x2896d0`) fades it out over a second and does nothing when it's stopped or in state 1. `0x2a3740` and `0x2a37a0` (07's `0x289900` and `0x289960`) start it, and 21 places in the menus call them, which is how music came back during a show.
  - `SOUNDDAT.dat`'s handle changes now and then (seen after the user played and simmed). The hook reloads the two name tables when it does and leaves a show in progress alone. An earlier version cleared the playing flag there, which left the week's show marked as played and silent.
  - The week's show ends when the player finds no row for the next slot: `step` calls stop (`0x513b0`). After a simmed week the story engine has replaced the rows, so the next `start(0)` builds and plays a new show.
  - In a new franchise (preseason, no story rows) the show started by itself and played event 0 (intro), 0xc, four of 0x10 (trivia) about 20 to 30 s apart, then 0xa, a long piece: 10 clips, one of 221 KB.
- **The draft announcement isn't in the fantasy draft.** `0x145660` (event `0xe000`, project 7) is a screen-script command (case at `0x145f88`), and 20 CPU picks in a fantasy draft never called it. It's probably the offseason rookie draft's.
- **Tools.** `tools/spch_trace.py` logs speech events from a running game, `tools/xemu_call.py` makes it call one of its own functions, `tools/xrefs.py` lists every mention of an address, and `tools/xcallers.py` lists call and jump sites (the library's functions aren't aligned, so `xdis.py --callers` misses them).
