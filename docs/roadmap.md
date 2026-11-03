# Roadmap and open work

Last updated 2026-11-03.

## In progress

### Progression: performance v2 shipped
Test 2 (2026-11-03) met two of three criteria clearly: production drives progression, and half the bottom-third starters declined. 99s went 5 → 6 → 11, against stock's 31 and v1's 8; all 11 are established stars who were already 96–99. Results: [findings §3](findings.md#3-progression-experiments).

- **Shipped 2026-11-03:** `performance` is `build_all.py`'s default and is in the overlay's `data/strmdata.db`. The stock-progression file (with the music) is kept in `patched/…/progression_stock/` for rollback.
- **If fewer 99s are wanted:** lower `GAIN_BY_GROUP[0]` (90+, now 0.5) or add a 95+ group. Test with the same procedure.
- **Watch over more seasons:** the league OVR mean is drifting down slowly (−0.1/season), and generated rookies have to replace the real players.

## Ready but not hardware-tested
- **Awareness fix for 07 and 08:** `patched/Madden NFL 07 (USA)/default.xbe`, `…08…` ("Madden NFL 0x Modded"). Checked by disassembly only. The first test is simply that franchise seasons sim without crashing.

## Ideas, roughly by value
1. **Throwback rosters from 07 and 08** (2006 and 2007 seasons). Their PLAY layout is identical to 09's, so the roster is nearly a direct copy; their headshot files may come along too.
2. **2005 and 06 rosters in 09** (2004 and 2005 seasons). These need field conversion (115 and 111 fields vs 110).
3. **Raise the 40-song EA Trax limit.** It's in three places: `MUPL` capacity (template.dat and the fe.qkl copy), the constant at `0x18cebb`, and the playback array (`0x370` bytes = 55 entries, allocated at `0x2a9e65`). The profile save also stores the playlist.
4. **Separate photo slots for the modern roster**, so 2008 roster saves keep their own photos. `uis_plyr.dat`'s directory is full, and its header is preloaded in both qkl bundles (fixed size), so this needs the qkl regions rebuilt.
5. **Attract-mode demo delay:** on hold; the 24 h build didn't stop the demo (see Done).
6. **Write roster saves to the memory card.** This needs the 20-byte save signature (at 0x10 in `Rost-Rost1`).
7. **Look at Madden 06** for another cause of awareness creep, since it has no roles.
8. **Port 2005-style offseason progression** (`PYRA`), if in-season tuning isn't enough.

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
