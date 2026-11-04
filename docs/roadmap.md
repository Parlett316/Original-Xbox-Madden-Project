# Roadmap and open work

Last updated 2026-11-03.

## In progress

### Progression: performance v2 shipped
Test 2 (2026-11-03) met two of three criteria clearly: production drives progression, and half the bottom-third starters declined. 99s went 5 → 6 → 11, against stock's 31 and v1's 8; all 11 are established stars who were already 96–99. Results: [findings §3](findings.md#3-progression-experiments).

- **Shipped 2026-11-03:** `performance` is `build_all.py`'s default and is in the overlay's `data/strmdata.db`. The stock-progression file (with the music) is kept in `patched/…/progression_stock/` for rollback.
- **If fewer 99s are wanted:** lower `GAIN_BY_GROUP[0]` (90+, now 0.5) or add a 95+ group. Test with the same procedure.
- **Watch over more seasons:** the league OVR mean is drifting down slowly (−0.1/season), and generated rookies have to replace the real players.

## Ready but not hardware-tested
- **17-game season: works on hardware** (2026-11-03, years 1 to 3). `patches/season17.py`, the default in `build_all.py` since then (`--no-season17` opts out). Franchises need the build they were started with: the franchise tables are sized at creation. Test files: `patched/Madden NFL 09 (USA)/season17_test/`.
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
  - From year 2 the preseason picker schedules 4 games (harmless; a 4th checkpoint row is kept).
  - Next: 7-team playoffs (findings §8).
- **Awareness fix for 07 and 08:** `patched/Madden NFL 07 (USA)/default.xbe`, `…08…` ("Madden NFL 0x Modded"). Checked by disassembly only. The first test is simply that franchise seasons sim without crashing.

## Future work
Effort is a rough estimate. "Unknown" means nobody has looked yet, so the first step is research. Suggested order: finish the season format (year 3 check, 3-game preseason, then default), then 7-team playoffs, then classic-team photos.

### Modern NFL rules ([findings §8](findings.md#8-season-structure-and-playoffs-09))
- **3-game preseason from year 2.** Small. The picker schedules 4 games from its own code, not the schedule data.
- **7-team playoffs.** Large, XBE: seed limit 6 → 7, move the seed array, rewrite the divisional pairing for one bye.
- **Overtime and kickoff rules.** Unknown. They have no table fields, so they're in gameplay code.
- **Varied kickoff times in generated week 18s.** Small to medium. The cave uses Sunday 1:00 for all 16 games and has 11 bytes free, so a Saturday and Sunday-night mix may need more cave space.
- **2027 schedule in year 1.** Very small: re-download `games.csv` after the NFL releases it (about May 2027) and rebuild.

### Classic teams
- **Real names: built, not hardware-tested as a whole** (2026-11-03). `roster/classic_names.py` matches the 145 single-season classic teams to nflverse's open roster data (downloaded to `nflverse_rosters/`; Pro-Football-Reference blocks automated downloads).
  - EA changed every jersey number on these teams, so the match is a per-team assignment on position group, years pro, height, weight and age. A team's ages are used only when they agree with its age-free matches, since some teams have placeholder ages.
  - Results: 6,006 high, 550 medium, 381 low and 649 unmatched, out of 7,586 players. High and medium go into the game (`--apply`, `build_all.py --classic-names <csv>`); low and unmatched keep "position #number". A spot check of each team's top-rated players gives that season's stars.
  - Test file: `patched/Madden NFL 09 (USA)/classic_names_test/DB_TEAMS.dat` (2,585,792 bytes, the same size as the current one).
  - Custom players: `roster/custom_players.py` puts a name, size, skin and photo into an existing slot, using psxp 1856-2692 for the photo (2693+ is the game's generic-face pool). First use: the '63 Bears' RT #81, confirmed on hardware.
- **Photos.** Large: needs the photo-slot expansion below. nflverse has `headshot_url` for many players, mostly recent seasons.
- **Names for the 31 all-time teams** ("All 49ers"). Medium: they span many seasons, so matching is harder.
- **The remaining 1,030 players** (low or unmatched). Medium: accept lower match quality or find another source.

### Rosters and franchise
- **Separate photo slots for the modern roster**, so 2008 roster saves keep their own photos. Medium to large. `uis_plyr.dat`'s directory is full, and its header is preloaded in both qkl bundles (fixed size), so this needs the qkl regions rebuilt.
- **Write saves to the memory card.** Medium to large, uncertain. This needs the 20-byte save signature (at 0x10 in `Rost-Rost1`). Besides roster saves, it would let us edit franchise saves for quick tests (jump to a given week or year), which would cut many rounds of hardware testing.
- **Gameplay sliders and CPU tendencies.** Unknown, new idea: tune them from franchise reports, the way progression was tuned.
- **Long-run progression check.** Mostly sim time: 5+ seasons, to see whether the slow OVR drift above matters.
- **Coach contract lengths.** Small. They still come from the 2008 slot (Blough's ran one year).
- **Port 2005-style offseason progression** (`PYRA`), if in-season tuning isn't enough.
- **Throwback rosters from 07 and 08** (2006 and 2007 seasons). Lower priority (the user prefers the classic teams). Their PLAY layout is identical to 09's, so the roster is nearly a direct copy; their headshot files may come along too.
- **2005 and 06 rosters in 09** (2004 and 2005 seasons). Lower priority. These need field conversion (115 and 111 fields vs 110).

### Graphics and presentation
- **Real 3D faces from older games.** Unknown. 2005 has `PLYRFACE.DAT` and 09 has `plyrface.dat`; the formats haven't been compared.
- **Uniforms and logos for renamed or relocated teams** (the Commanders are the obvious case). Medium, using the texture tools we already have (TERF, MMAP). Team names are already modern; first survey which logos, uniforms and team text still look like 2008.
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
