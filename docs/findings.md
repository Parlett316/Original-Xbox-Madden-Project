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

**Game rules aren't in tables.** Overtime and kickoff/touchback spots have no DB fields, only UI strings ("End of Overtime Quarter", "OVERTIME!!!", "Touchback"), so they live in gameplay code.

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
