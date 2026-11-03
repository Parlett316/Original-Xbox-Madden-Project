# Modern rosters for Madden NFL 09 (Xbox)

Builds 09's default roster from EA's ratings site.

```
python fetch_ea_ratings.py madden27_week7.json            # current game on ratings site
python fetch_ea_archive.py madden26_superbowl.json 23-super-bowl madden27_week7.json
python fetch_headshots.py madden27_week7.json headshots_raw
python fetch_coach_photos.py coach_photos                  # 2026 staffs from the team sites
python build_roster.py madden27_week7.json "../Madden NFL 09 (USA)" out_m27 --photos headshots_raw        --coach-photos coach_photos
```

Output: `out_m27/data/template.dat`, `DB_TEAMS.dat`, `uis_plyr.dat` and
`uis_coac.dat` (drop-in replacements, same sizes) plus `out_m27/roster_report.csv`.
The files must be installed together, since photo numbers are assigned per build.

The JSON files and headshots are EA's data. They're downloaded by these scripts
and not part of the repository. `fetch_ea_archive.py` rebuilds an older season
(here the final Madden 26 ratings), whose API returns teams and positions as null,
by querying per team and per position.

## Files
- `tdb.py`: read/write EA TDB databases: bitfields, all checksums, and `DB.resized()` to grow tables.
- `headshots.py`: `uis_plyr.dat` photo slots: crop EA portraits, quantise, Xbox swizzle, skin brightness.
- `build_roster.py`: the builder (details below).
- `fetch_ea_ratings.py`, `fetch_ea_archive.py`, `fetch_headshots.py`: EA ratings-site downloaders.
- `coaches.py`: the 2026 coaching staffs and how they're written; `fetch_coach_photos.py` downloads their headshots.

## What it writes
- `template.dat` league roster DB: players, depth charts, team names; the
  career/season stats DB there is emptied, since the stats belonged to the 2008 players.
- `DB_TEAMS.dat`: the 32 current-team DBs and the free-agent DB, with the same
  players and depth charts. The classic teams are untouched.
- All TDB checksums are recomputed (see `tdb.py`).

## How values are produced
- Ratings: percentile within position in Madden 27, mapped onto 09's own
  distribution for that position. Throw accuracy = mean of short/mid/deep;
  agility = mean of agility and change of direction; defenders' awareness =
  mean of awareness and play recognition.
- Headshots: EA's current photos, written into `uis_plyr.dat` (see `headshots.py`);
  players EA has no photo for show the blank picture.
- Skin tone (PSKI): from the EA photo's face brightness, split in 09's own
  light/medium/dark proportions.
- Appearance/equipment: copied from a 2008 player at the same position and skin tone, with a
  generic face (shared by 5+ players, not a superstar), close in weight.
- Contracts: the 2008 contract at the same position and rank (rookie deals
  for rookies), so team payrolls stay in 2008's range.
- Commentary: a 2008 player's recorded name when the surname matches,
  otherwise none.
- Rosters: cut to each team's original 09 size (51–54) with 09 position
  minimums; teams EA lists too thin sign the best cut player. Everyone else is
  a free agent.
- Not available from EA, so set to defaults: draft round/pick (undrafted),
  Pro Bowl flag, years with team (= years pro).
- Team renames: LA Chargers, LV Raiders, LA Rams, Washington Commanders
  (text only; logos, uniforms and commentary audio are unchanged). Use
  `--keep-team-names` to skip.
- Coaches: all four staff per team (head coach and coordinators) from 2026
  lists, except the Bucs DC. Coaches already in 09 keep their own ratings and
  3D head; new ones take the replaced coach's ratings. Everyone gets his real
  age and NFL head-coaching record (`fetch_coach_facts.py` gathers them). With
  `--coach-photos`, every one gets his team-site photo in `uis_coac.dat`
  (otherwise new ones show the silhouette). Use `--keep-coaches` to skip.

## The memory card overrides this
Madden auto-loads a saved roster (`Rost-Rost1` under title `4541023b` on the
memory card) instead of the default roster. Move that save off the card to use
this one.

## 2008 roster saves and these photos
The new headshots reuse the 2008 players' photo slots in `uis_plyr.dat`. With
this photo file installed, a 2008 roster save shows other people's faces in
the menus. To play a 2008 roster, install the stock `template.dat`,
`DB_TEAMS.dat` and `uis_plyr.dat`. Giving the modern roster its own slots is on
the [roadmap](../docs/roadmap.md).
