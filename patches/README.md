# Patches

Each script reads stock files and writes new ones; stock inputs are never modified. Background and measurements: [docs/findings.md](../docs/findings.md). How to install and test: [docs/workflow.md](../docs/workflow.md).

## `madden_awareness_fix.py`: awareness-inflation fix (07, 08, 09)

    python madden_awareness_fix.py "<game>/default.xbe" out/default.xbe

When a player is given a better role, the role it replaces is dropped without its rating bonuses being taken back. This patch hooks that spot so the game's own remove routines run first. It also fixes the unsigned clamp that turned negative ratings into 99. The game is identified by its `.text` SHA-1; any other build is refused, and so is 06 (no role system).

| Game | Stock SHA-1 | Patched SHA-1 |
|---|---|---|
| 09 | `eda937d7…` | `3814c23eb76a390936fbb5562291e70486ea2e0b` |
| 08 | `933c4297…` | (before rename) built, not hardware-tested |
| 07 | `cf062491…` | (before rename) built, not hardware-tested |

The code cave sits at VA `0x10F00` in the header page's padding: `SizeOfHeaders` goes to `0x1000` and the `.text` digest is recomputed. The RSA signature can't be regenerated, so this needs a modded console or an emulator.

## `set_xbe_title.py`: dashboard name

    python set_xbe_title.py in.xbe out.xbe "Madden NFL 09 Modded"

Changes only the certificate's title name (40 UTF-16 characters). The title id stays the same, so saves are shared with the stock game.

## `progression_2005.py`: in-season progression tables

    python progression_2005.py "<2005>/DATA/STREAMEDDATA.DB" "<09>/data/strmdata.db" out/strmdata.db [mode]

Rewrites `PWRA` (rating changes) and `PLLO` (grade thresholds) in 09's `strmdata.db`, leaving every other table as it is. The input can be stock or already carry the music tables.

| Mode | Effect |
|---|---|
| `1` (default) | Madden 2005's tables |
| `0`–`1` | blend: 0 = stock 09, 0.5 = halfway |
| `performance` | 2005 gains ×0.5 at 90+ and ×0.75 at 82–89; young ×1.25, veteran ×0.75; 09's declines ×1.5 / ×1.25 at the top (veterans ×1.25); neutral preseason; 09's thresholds with a real bad zone (`PLSP` = 0.5 × `PL1P`). Fractions are spread across checkpoints by error diffusion. |

Every key combination is written once (09's loader indexes rows by key). This also fixes stock 09's one mis-keyed row.

## `music_import.py`: 2005–08 soundtracks

    python music_import.py "<09>/data/BGM.dat" "<09>/data/strmdata.db" out/data [games dir]

Adds 107 licensed songs (2005: 21, 06: 21, 07: 36, 08: 29) as four extra soundtracks. That makes `BGM.dat` 154 tracks and 756 MB, with `MUST`/`MUSO` grown in `strmdata.db`. 2005's stream headers are rewritten to the 06–09 form. The NFL Films instrumentals are skipped, since 09 already has them. The EA Trax limit of 40 active songs is unchanged; new songs start switched off. **Run `qkl_sync.py` afterwards,** or the new tracks stay silent.

## `qkl_sync.py`: quick-load bundles

    python qkl_sync.py "<09>/data/fe.qkl" "<09>/data" out/data out/data/fe.qkl

`fe.qkl` and `game.qkl` hold copies of some files' headers and archive entries, which the game uses instead of the files. This copies the preloaded parts of every changed file from the patched directory into the bundle; each copy must keep its size. With no changes it reproduces the stock bundle byte for byte. Current patches only touch `fe.qkl` (the BGM.dat directory and the start screen).

## `press_start_timer.py`: attract-mode demo delay

    python press_start_timer.py "<09>/data/uis_all.dat" out/uis_all.dat 86400000

Sets the idle time (ms) on the Press START screen before the CPU-vs-CPU demo starts (stock 75000). Leaving the demo hard-locks the console, even on the stock game, so the build uses 24 h. The script's entry is recompressed into its old slot; a rebuild with 75000 reproduces the stock file byte for byte. **Run `qkl_sync.py` afterwards:** `fe.qkl` preloads this part of `uis_all.dat`.

## `team_logo.py`: a team's menu logo

    python team_logo.py "<09>/data" my_logo.png out/data --teams template.dat DB_TEAMS.dat strmdata.db

Replaces entry 26 of `uis_tmlo.dat` (64×64) and `UIS_TMLL.dat` (128×128), the modern Washington team by default. `--teams` also moves any other team using that logo to `--classic-entry` (default 37, the classic Redskins' image). Solid art must have alpha 255: a logo with solid areas at 248–253 looked grainy on hardware.

## `team_helmet.py`: a team's helmet logo

    python team_helmet.py "<09>/data" my_logo.png out/data --teams template.dat DB_TEAMS.dat

Repaints the helmet in `UNIFORMS.dat` entries 283 and 284 (Washington's white and burgundy) and 626 and 627 (the copies training camp uses), and moves every other team's `TUNI` rows from 283 and 284 to 287 and 288. The art must be a gold outline on burgundy, because the helmet logo is drawn inverted: gold panels with burgundy seams. It's mirrored across the crown stripe so it faces forward on both sides.

Each entry keeps its stock directory size, with zeros after the shorter stream, so `fe.qkl` and `game.qkl` stay stock. Changing a size freezes the console: see [formats](../docs/formats.md#terf-archives-dat-asset-files). `build_all.py --commanders-logo` runs both scripts. Details: [findings §9](../docs/findings.md#9-team-logos-and-uniforms-09).

## `commentary_team.py`: Al Michaels says "Washington"

    python commentary_team.py "<09>/data" out/data
    python qkl_sync.py "<09>/data/game.qkl" "<09>/data" out/data out/data/game.qkl    # and fe.qkl

Gives `COMMANDERS` its own slot in the commentary name tables, taken from the unused NFL Europe Galaxy, and puts Al's existing "Washington" audio there. Classic Redskins teams keep "Redskins". Entries keep their directory sizes. It uses his player surname recording by default. `--clip city` uses his city recording, which is quieter than his nicknames. `--check` rebuilds the name tables with no changes, compares them with stock, and writes nothing. `build_all.py --commanders-commentary` runs it. Details: [findings §10](../docs/findings.md#10-commentary-team-names-09).

## `playoffs7.py`: seven playoff teams per conference

    python playoffs7.py <in default.xbe> <out default.xbe>
    python playoffs7.py <in template.dat> <out template.dat>

Gives each conference one bye and three wild-card games. Apply it to both files, after `season17.py`. Seven teams need a franchise created on this build. An older one keeps 6 for the season it's in (xemu only), and its next season isn't tested. `build_all.py` runs it unless given `--no-playoffs7`. Details are in the script.

## `optional_fullback.py`: a team with no fullback

    python optional_fullback.py <in default.xbe> <out default.xbe>
    python optional_fullback.py <in template.dat> <out template.dat>

Lowers the position minimums in `template.dat` so a team can carry no fullback. The XBE change guards a divide by zero those minimums would otherwise cause when a team trims its roster, so use both files. Saves don't carry these tables. `build_all.py --optional-fullback` runs it. Details: [findings §8](../docs/findings.md).

## `team_name_keys.py`: the XBE's team-name lookups

    python team_name_keys.py <in default.xbe> <out default.xbe>

The minicamp, one game scenario and a city table find Washington by the nickname "Redskins", stored in the XBE. After the roster's rename to Commanders, those lookups found no team, and the minicamp showed another team in Washington's place. This changes the four strings to "Commanders". `build_all.py` runs it whenever it builds the roster. Details are in the script.

## `kickoff_spot.py` and `kickoff_setup.py`: the modern kickoff

    python kickoff_spot.py <in default.xbe> <out default.xbe>
    python kickoff_setup.py <in GAMEDATA.dat> <out GAMEDATA.dat> --hold 255 --lineup --ball 35

`kickoff_spot.py` moves the kickoff to the kicking team's 35, sends kickoff touchbacks to the 35 (punts keep the 20), and spots a kickoff out of bounds at the receiving 40. `kickoff_setup.py` edits the playbooks: the NFL's hybrid lineup, and copied kickoff and return scripts that hold everyone, CPU kickers included, until the receiving team touches the ball. Use both, then re-sync `fe.qkl`. `build_all.py --modern-kickoff` runs them. Details: [findings §7](../docs/findings.md).

## `season17.py`: the 17-game, 18-week season

    python season17.py <in template.dat> <out template.dat> [<games.csv> [season]]
    python season17.py <in strmdata.db> <out strmdata.db>
    python season17.py <in default.xbe> <out default.xbe>

Adds a 17th game and an 18th week with a 3-week preseason, and with `games.csv` makes year 1 a real NFL season. Apply it to all three files. It must be the last change to `template.dat` apart from `playoffs7.py` and `optional_fullback.py`, and `fe.qkl` needs re-syncing afterwards. A franchise needs the matching build from its creation. `build_all.py` runs it unless given `--no-season17`.

## `save_unlock.py`: load edited saves

    python save_unlock.py <in default.xbe> <out default.xbe>

Skips the signature check on a save's contents, so a franchise edited on a PC loads. The save has to keep its name and file size and have correct database checksums (`tdb.DB.fix`). `build_all.py --save-unlock` runs it.

## `any_number.py`: any jersey number at any position

    python any_number.py <in default.xbe> <out default.xbe>

Sets the edit screen's number ranges to 0-99 for every position. Rookies and signings still get traditional numbers. `build_all.py --any-number` runs it.

## `loadscreen/`: custom loading and start screens
See [loadscreen/README.md](loadscreen/README.md).

## `radio_show.py` and `radio_transplant.py`: 07's radio show in 09 (a test, not in `build_all.py`)

    python radio_show.py <in default.xbe> <out default.xbe> [--show <Madden 07 default.xbe>] [--test-draft]

Makes 09 load Madden 07's `SPCHFEDT.dat`, copied to the data folder as `spchfe07.dat`, with the Tony Bruno Show's sub-banks and event file, and lets menu speech other than the draft's be heard. With `--show`, `radio_transplant.py` copies 07's show code into the XBE, which grows by 16 KB, and the franchise menu starts the week's show by itself. `--test-draft` replaces the rookie draft's announcement with two of the show's events, for testing. Run it after `madden_awareness_fix.py`. Details are in [docs/findings.md §12](../docs/findings.md#12-the-radio-show-2005-to-07).
