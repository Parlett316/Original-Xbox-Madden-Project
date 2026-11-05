# Roadmap and open work

Last updated 2026-11-03.

## In progress

### Progression: performance v2 shipped
Test 2 (2026-11-03) met two of three criteria clearly: production drives progression, and half the bottom-third starters declined. 99s went 5 → 6 → 11, against stock's 31 and v1's 8; all 11 are established stars who were already 96–99. Results: [findings §3](findings.md#3-progression-experiments).

- **Shipped 2026-11-03:** `performance` is `build_all.py`'s default and is in the overlay's `data/strmdata.db`. The stock-progression file (with the music) is kept in `patched/…/progression_stock/` for rollback.
- **If fewer 99s are wanted:** lower `GAIN_BY_GROUP[0]` (90+, now 0.5) or add a 95+ group. Test with the same procedure.
- **Watch over more seasons:** the league OVR mean is drifting down slowly (−0.1/season), and generated rookies have to replace the real players.

## Ready but not hardware-tested
- **17-game season: works on hardware** (2026-11-03, years 1 to 4, the full interconference rotation). `patches/season17.py`, the default in `build_all.py` since then (`--no-season17` opts out). Franchises need the build they were started with: the franchise tables are sized at creation. Test files: `patched/Madden NFL 09 (USA)/season17_test/`.
  - What it does: a 3-week preseason; 17 games over 18 weeks with a bye; playoffs in weeks 19–22 and the Pro Bowl in week 23. The Super Bowl box score can be viewed during Pro Bowl week, and then the season advances to the offseason.
  - Year 1 can be a real NFL season (`--schedule nflverse_schedule/games.csv`, from nflverse's nfldata; the 2026 schedule was checked on hardware). Years 2+ are the game's own generated schedule plus week 18: each AFC division against the NFC division it played two years earlier (the modern rule), computed by the XBE every year.
  - Changes needed: `template.dat` (schedules plus franchise tables sized for 22 weeks), `strmdata.db` (`OWFW` week 21 and `OACI`/`OFAC` week 17) and the XBE (offseason-start week 22 → 23; a cave that adds week 18 after the year-2+ generator).
  - The hardware tests, in order:
    1. week 18 rematched week 1;
    2. the Super Bowl locked with the Pro Bowl at week 22;
    3. it still locked with no Pro Bowl;
    4. the missing `OWFW` row was fixed and the season reached the offseason, but the Super Bowl stats couldn't be viewed;
    5. the Pro Bowl came back with the XBE week patch and everything worked;
    6. year 2 had 17 weeks: the generator deletes week 18;
    7. keeping week 18 through the generator hung "Advancing To Regular Season";
    8. inserting week 18 after the generator worked: 18 weeks, 17 games each, no repeats (save checked).
    9. years 2 and 3 were played through the Pro Bowl and a second offseason: year 3's save (`SEYR` 2) has 18 weeks, 272 scored games, no repeats, and week 18 against a different NFC division from that year's rotation.
    10. the preseason picker was removed: every year plays the data's 3 preseason weeks. Year 4's save (`SEYR` 3) has 18 weeks, 272 scored games and no repeats.
  - Next: 7-team playoffs (findings §8).
- **Awareness fix for 07 and 08:** `patched/Madden NFL 07 (USA)/default.xbe`, `…08…` ("Madden NFL 0x Modded"). Checked by disassembly only. The first test is simply that franchise seasons sim without crashing.

## Future work
Effort is a rough estimate. "Unknown" means nobody has looked yet, so the first step is research. Suggested order: the save-jump tool (it makes playoff testing cheap), then 7-team playoffs, then classic-team photos.

### Modern NFL rules ([findings §8](findings.md#8-season-structure-and-playoffs-09))
- **Varied or selectable preseason.** Small to large. Every year now plays the same 3 preseason weeks from the data; restoring a 3-game picker would mean reworking its builder (`0x40a000`) and pick limits (`0x40456c`, `0x40459d`).
- **7-team playoffs.** Large, XBE: seed limit 6 → 7, move the seed array, rewrite the divisional pairing for one bye.
- **Overtime and kickoff rules.** Unknown. They have no table fields, so they're in gameplay code.
- **Varied kickoff times in generated week 18s.** Small to medium. The cave uses Sunday 1:00 for all 16 games and has 11 bytes free, so a Saturday and Sunday-night mix may need more cave space.
- **2027 schedule in year 1.** Very small: re-download `games.csv` after the NFL releases it (about May 2027) and rebuild.

### Classic teams
- **Real names: looked fine on hardware** (2026-11-04, test file below). `roster/classic_names.py` matches the 145 single-season classic teams to nflverse's open roster data (downloaded to `nflverse_rosters/`; Pro-Football-Reference blocks automated downloads).
  - EA changed every jersey number on these teams, so the match is a per-team assignment on position group, years pro, height, weight and age. A team's ages are used only when they agree with its age-free matches, since some teams have placeholder ages.
  - Results: 6,006 high, 550 medium, 381 low and 649 unmatched, out of 7,586 players. High and medium go into the game (`--apply`, `build_all.py --classic-names <csv>`); low and unmatched keep "position #number". A spot check of each team's top-rated players gives that season's stars.
  - Test file: `patched/Madden NFL 09 (USA)/classic_names_test/DB_TEAMS.dat` (2,585,792 bytes, the same size as the current one).
  - Custom players: `roster/custom_players.py` puts a name, size, skin and photo into an existing slot, using psxp 1856-2692 for the photo (2693+ is the game's generic-face pool). First use: the '63 Bears' RT #81, confirmed on hardware.
- **Photos.** Large: needs the photo-slot expansion below. nflverse has `headshot_url` for many players, mostly recent seasons.
- **Names for the 31 all-time teams** ("All 49ers"). Medium: they span many seasons, so matching is harder.
- **The remaining 1,030 players** (low or unmatched). Medium: accept lower match quality or find another source.

### Rosters and franchise
- **Separate photo slots for the modern roster**, so 2008 roster saves keep their own photos. Medium to large. `uis_plyr.dat`'s directory is full, and its header is preloaded in both qkl bundles (fixed size), so this needs the qkl regions rebuilt.
- **Edit franchise saves.** Loading works (2026-11-04): `--save-unlock` skips the signature check, see [formats](formats.md). Saving an edited franchise from the game and reloading it works too: the game writes new data and padding signatures and valid CRCs, and the edit survives offseason stages. Still to do: write the tool that jumps a franchise to a given week or year, which would cut many rounds of hardware testing. Roster saves appear to use the same stream driver, but haven't been tried.
- **Gameplay sliders and CPU tendencies.** Unknown, new idea: tune them from franchise reports, the way progression was tuned.
- **Long-run progression check.** Mostly sim time: 5+ seasons, to see whether the slow OVR drift above matters.
- **Coach contract lengths.** Small. They still come from the 2008 slot (Blough's ran one year).
- **Port 2005-style offseason progression** (`PYRA`), if in-season tuning isn't enough.
- **Throwback rosters from 07 and 08** (2006 and 2007 seasons). Lower priority (the user prefers the classic teams). Their PLAY layout is identical to 09's, so the roster is nearly a direct copy; their headshot files may come along too.
- **2005 and 06 rosters in 09** (2004 and 2005 seasons). Lower priority. These need field conversion (115 and 111 fields vs 110).

### Graphics and presentation
- **Real 3D faces from older games.** Unknown. 2005 has `PLYRFACE.DAT` and 09 has `plyrface.dat`; the formats haven't been compared.
- **Uniforms and logos for renamed or relocated teams** (the Commanders are the obvious case). Medium, using the texture tools we already have (TERF, MMAP). Team names are already modern; first survey which logos, uniforms and team text still look like 2008.
  - The W works on hardware in menus, the team intro and the scoreboard (2026-11-04), with the '91 Redskins keeping their logo. `patches/team_logo.py`, in `build_all.py` as `--commanders-logo`.
  - Team logos: entry = id + 1 in `uis_tmlo.dat` (64×64) and `UIS_TMLL.dat` (128×128). The modern team is 25 (entry 26) and the classic Redskins are 36 (entry 37, a separate image); entry 251 is a third copy, use unknown. "All Redskins" (TGID 208) is 25/25 in `TLGL`/`TLGS` in `template.dat` (3 DBs) and `strmdata.db`, so it showed the W; changing its `TLGS` in `DB_TEAMS.dat` alone did nothing on hardware. Fixed in those tables (hardware, 2026-11-04). `fe.qkl` and `game.qkl` don't preload logo entry 26.
  - Palette alpha matters: a first W with solid areas at alpha 248–253 looked grainy on hardware; rebuilt from a transparent PNG with alpha 255, it's clean (hardware, 2026-11-04).
  - Shared with the classic teams: the "REDSKINS" wordmark (`TFTL` 25, `uis_tmfn.dat` entry 26, and that archive is full) and the nickname image (`UIS_TIRN.dat`/`UIS_TIRL.dat` entry 26, the only one; how classic teams select it isn't traced).
  - Still 2008 on hardware: the stadium wall text ("WASHINGTON REDSKINS"), the small wall logo and the stadium scoreboard logo. Not traced yet. All the Redskins teams share `TMFL` 25 and `TSID` 26, so stadium art may be shared with them; `TMFL` may be the midfield logo (a guess from its name).
  - Commentary: Al Michaels says "the home team" or "the visiting team" for the renamed Washington team (hardware, 2026-11-04), and there's no "Commanders" recording. He still names the Chargers and Raiders. The Chargers' `TLNA`, `TMNC` and `TSNA` all changed, which leaves `TDNA` as the likely key. The lookup itself isn't traced. He still calls the Chargers' stadium Qualcomm in San Diego, so the stadium line doesn't come from `TLNA`.
  - Helmets: `UNIFORMS.dat` entries are indexed by UFID and each is an LZH1-compressed MMAP with named parts (`Hip`, `Thigh`, `Torso`, `Helmet`, ...), each part with mips and a palette. The `Helmet` part is 256×128: two side panels, the art rotated a quarter turn. `TUNI` (`UFID`, `TGID`, `TUCO`) lists a team's uniforms. Moving Commanders to an unused UFID failed: 292 (stock art, with a `UNIF` row) locked on the loading screen, though that run also opened the Y uniform screen first. Controls without Y both loaded (hardware, 2026-11-04): `UNIF` grown by a row with Commanders on 283/284, and Commanders home on existing UFID 287. The cause isn't traced. `patches/team_helmet.py` now adds no UFID: it repaints 283 and 284 in place and moves the classic Redskins teams on them (TGIDs 102, 117, 151, 208) to the near-identical 287 and 288, in `template.dat` and `DB_TEAMS.dat`. First swap build on hardware (2026-11-04): the W shows and Commanders at home load, but the helmet was blotchy and Commanders away locked. That build wrote the three smaller mips 0x80 bytes too late: only the top mip follows the 0x80-byte header, so a mip's pixels start at its table offset. It also spilled 128 bytes into the next texture's all-zero header and reduced the palette to 25 colours. With that fixed (hardware, 2026-11-04) the W reads well and Commanders @ Eagles loads, with Commanders in white, but setting the Eagles to white at home through the Y screen locked. Uniform clashes are resolved by `ULTF` (`0x39e2e0`): Commanders are 283 light and 284 dark, so 284 hadn't loaded in any game known to work. Every known lock since the mip fix followed the Y screen or needed 284; which one matters isn't known. That build also left dotted stray colours at a distance, because it freed palette entries by checking only the top mip; entries are now freed only if no kept pixel uses them at any level. On hardware that build (W length 58, centred 4 pixels lower in the texture) still showed dotted rings on the crown, and Commanders @ Cowboys, which needs 284, locked; Y-screen games with other teams loaded, so the Y screen isn't the cause. Whether stock 284 also locks isn't known yet (control: `helmet_diag_e`). The dotted rings on the crown are on every team's helmet (hardware, 2026-11-04), so they aren't from this mod; the user reads them as the stadium lights. `helmet_swap4` leaves every palette stock and draws the W as solid gold in the stripe's colour with burgundy seams; it looks right on hardware at home and in white on the road. Commanders @ Cowboys still locks on it, and the Y screen locks the moment it shows 284 (hardware, 2026-11-04), so no game is needed to reproduce it. The Cowboys can pick all their dark uniforms, so it isn't dark road uniforms in general. The rebuilt entry looks valid: `lzh1emu.compress` reproduces stock entries 283, 284 and 292 byte for byte, and the new 284 decompresses to full size. Whether stock 284 also locks isn't tested. Alternates 281, 282, 285 and 286 keep the old helmet. When `0x802abd` is set the game loads entry UFID + 343 instead (`0x222223`); entries 626 and 627 are a second copy of 283 and 284 with the old helmet, and that mode isn't identified. The Y screen also freezes on 286, which is byte-identical to stock in that build, and All Redskins (moved to 288) opened on Eagles whites and froze going right. A baseline with stock `UNIFORMS.dat` and `game.qkl`, unmoved rows and the same XBE (`helmet_baseline`) has none of this (hardware, 2026-11-04): Commanders' 284, 285 and 286 all show, Commanders @ Cowboys loads, and All Redskins show burgundy 284 and white 283. So the helmet build causes the freeze, and it reaches an entry it didn't edit. With only the moved rows added to that baseline (`helmet_split_rows`) everything still works (hardware, 2026-11-04), so the moves are safe. Cause found: the game keeps every 20th entry's offset and adds up rounded sizes for the rest (`0x377030`; docs/formats.md), so the shorter 283 and 284 put entries 284 to 299 2,816 or 6,400 bytes early. Running the game's decoder at those offsets on the swap4 file: 284 and 286 return status 3, while 285 and 288 return status 1 with no output, against status 1 and full output at the real offsets. Status 3 fits the freezes; no output may explain the stale Eagles whites, but neither link is traced on hardware. It may also explain the 292 lock, though that build's contents weren't rechecked. `team_helmet.py` now keeps stock directory sizes and pads with zeros, so the header and `.qkl` copies stay stock; `helmet_swap5` has the same pixels as swap4, passes the offset rule for every entry on the PC, and isn't tested on hardware yet. The two helmet panels are mirror images in stock, with small y at the helmet's front, so a logo must be mirrored to face forward on both sides. `helmet_swap6` does that, centres the W at the stock logo's height (x 185 on the right panel) and shortens it from 58 to 48. On hardware (2026-11-04) it passed every freeze test: Commanders' 284 and 286 on the Y screen, All Redskins' uniforms, Commanders @ Cowboys, and Commanders @ Eagles with the Eagles in white. The W looked too far back next to the Cowboys' star, which is centred at (184.5, 66) against the W's (185, 73), so `helmet_swap7` moves it 7 pixels forward; not tested on hardware yet. Measuring every team's home helmet showed the W's centre already sits at the league's median, (186, 65) on the right panel; the difference is size, because the W's gold spanned y 46 to 86 where the Falcons' logo spans 39 to 88 and the Cowboys' 39 to 93. `helmet_swap8` lengthens the art to 54 and sets `CENTRE` to (185, 63), so the gold spans x 172 to 197 and y 39 to 85. The user approved it on hardware (2026-11-04), from photos of both sides in white and burgundy. `build_all.py --commanders-logo` runs it and reproduces that `UNIFORMS.dat` byte for byte. On hold at the user's request (2026-11-04): alternates 281, 282, 285 and 286, which keep the old helmet, and entries 626 and 627.
- **Improved textures generally** (sharper uniforms, fields, menus). Unknown: the tools can replace textures, but larger ones may not fit the Xbox's memory or the file's slots. A single replaced texture would be a cheap first test.
- **Older stadiums and uniforms in 09.** Judged not realistic, not tested: art formats changed between years.
- **Commentary.** Judged not realistic, not tested: the announcers only have recorded audio for 2008-era names.
- **2005's radio show (the Tony Bruno Show) and newspaper storylines.** Judged not realistic, not tested: they're game code plus audio and art formats, not data tables. The first step would be finding where 2005 stores the show's audio and what triggers each segment. Even if the audio can be read, 09 has no code to play it, so a real port is unlikely.

### Music
- **Raise the 40-song EA Trax limit.** Medium. It's in three places: `MUPL` capacity (template.dat and the fe.qkl copy), the constant at `0x18cebb`, and the playback array (`0x370` bytes = 55 entries, allocated at `0x2a9e65`). The profile save also stores the playlist.

### Other games
- **Test the 07 and 08 awareness fixes** (see above). Small: mostly sim time.
- **Look at Madden 06** for another cause of awareness creep, since it has no roles. Medium, research.

### On hold
- **Attract-mode demo delay:** the 24 h build didn't stop the demo (see Done).

## Done (for context)
- Real coach ages and NFL head-coaching records (`coaches.BORN/RECORDS/SUPER_BOWLS`, `fetch_coach_facts.py`); confirmed on hardware over a season 2026-11-03 (only Danny Smith, 73, retired). Coaches' contract lengths still come from the 2008 slot (Blough's ran one year).
- 2026 coaching staffs with team-site photos (`roster/coaches.py`, `fetch_coach_photos.py`); confirmed on hardware 2026-11-03 and in the overlay (`template.dat`, `DB_TEAMS.dat`, `uis_coac.dat`). The 2008-coach roster files are kept in `patched/…/roster_2008_coaches/` for rollback. The first test showed the photo is `CSXP`, not `CHID`. Open: a 2008 roster save shows 2026 photos for the replaced coaches.
- Attract-mode demo delay (`press_start_timer.py`, in `build_all.py`); the timer was confirmed on hardware with 15 s. **On hold (2026-11-03):** with the 24 h build the demo still started. The PC build checks out (`uis_all.dat` = 86400000 and the matching entry is in `fe.qkl`), so either the Xbox wasn't running those files or 24 h overflows the game's timer. The demo hasn't frozen recently, so this is low priority. If it's resumed, test a 10 min build (600000) to split the two.
- Performance progression v2, tested over two seasons (2026-11-03).
- Draft-class generator located (`SPAD`); stock classes match real rookies, so no change needed.
- Awareness fix for 09, verified over two franchise seasons.
- Madden 27 roster with headshots and matched skin tones.
- 2005–08 soundtracks (154 tracks), after the `fe.qkl` sync fix.
- Custom loading and start screens, and the dashboard rename.
- `qkl_sync.py`, `tdb.DB.resized`, and `tools/build_all.py` (the one-command build; verified against the hardware-tested files byte for byte).
