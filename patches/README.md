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

## `loadscreen/`: custom loading and start screens
See [loadscreen/README.md](loadscreen/README.md).
