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
