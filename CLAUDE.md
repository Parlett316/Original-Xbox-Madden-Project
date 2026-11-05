# CLAUDE.md: guide for AI agents working on this project

## What this is
Reverse-engineered fixes and mods for original-Xbox **Madden NFL 2005–09**, mainly **09**. The user plays on a real softmodded Xbox (UnleashX dashboard) and copies files over FTP. Every change is proven on the console by the user, so treat a hardware test as the source of truth and make each test cheap and decisive.

Start with [docs/outstanding.md](docs/outstanding.md) (what's open right now) and keep it current. Open the rest only when the task needs them, and search them for the relevant part rather than reading them whole: [README.md](README.md), [docs/workflow.md](docs/workflow.md) (rules that bite, and the prompt for starting a new chat), [docs/formats.md](docs/formats.md) (file formats and table fields), [docs/findings.md](docs/findings.md) (what was learned, with addresses) and [docs/roadmap.md](docs/roadmap.md) (full list of work).

## Ground rules
- **Never modify the stock game folders** (`Madden NFL 0x (USA)/`). Scripts take stock inputs and write to new paths (`patched/…`, scratch dirs).
- **Never commit game data, saves, build output, EA downloads or personal images.** `.gitignore` is an allow-list; CI fails if `.xbe/.dat/.db/.qkl/.json/.png/.jpg` files are tracked; the one exception is `docs/screenshots/` (photos of the game running, metadata stripped).
- **Prove writers byte for byte.** Rebuilding with no changes must reproduce the stock file exactly: `tdb.DB.resized({})`, `qkl_sync.py` with stock inputs, and the awareness patcher's 09 output SHA-1 `3814c23eb76a390936fbb5562291e70486ea2e0b`. After a refactor, rebuild existing outputs and `cmp` them.
- **Recompute every checksum.** Every TDB edit ends with `db.fix()`; verify with `db.verify()`.
- **Keep file sets consistent:**
  - roster: `template.dat` + `DB_TEAMS.dat` + `uis_plyr.dat` + `uis_coac.dat`
  - music: `BGM.dat` + `strmdata.db`
  - and `fe.qkl` re-synced whenever a file it preloads changes. `tools/build_all.py` handles all of this.
- **When a hardware result contradicts the code reading,** don't guess repeatedly. Build a small diagnostic variant that splits the hypotheses: one file, one or two marked test entries, a table of outcomes for the user.
- **Give the user exact file lists and byte sizes** for every install. They upload with FTP and have hit partial uploads and overwrite problems.
- **Never delete the Xbox `data` folder.** Overlays contain only changed files.

## Map
| Task | Where |
|---|---|
| Read or edit any EA database | `roster/tdb.py` (`DB`, `Table.get/set/rows/raw/set_raw`, `fix`, `verify`, `resized`) |
| TERF archives / MMAP textures / LZH1 | `roster/headshots.py:terf_entries`, `patches/loadscreen/{terf,eammap,lzh1emu}.py` |
| Disassemble the XBE, find strings and callers | `tools/xdis.py` (DB query tags are byte-reversed: `'YALP'` = PLAY) |
| Compare franchise saves | `tools/franchise_report.py` (ratings across seasons), `tools/save_diff.py` (what changed, table by table) |
| Jump a franchise to a later week | `tools/save_jump.py` (needs `--save-unlock`; docs/workflow.md) |
| Move saves on an xemu drive | `tools/xbox_hdd.py` (qcow2 + FATX) |
| List every table and field in a data file | `tools/db_survey.py` (results: docs/findings.md §7) |
| Build everything | `tools/build_all.py` |
| Fix quick-load bundles | `patches/qkl_sync.py` |
| Coaching staffs and coach photos | `roster/coaches.py`, `roster/fetch_coach_photos.py` (photo = `uis_coac.dat` entry `CSXP`+1) |
| Classic teams' real names | `roster/classic_names.py` (nflverse rosters in `nflverse_rosters/`; review CSV, then `--apply`) |
| One-off custom players (name, size, photo) | `roster/custom_players.py` with a personal spec in `custom/` (never committed) |
| Test a build in xemu | `tools/make_xiso.py` and docs/workflow.md ("Testing in xemu") |
| A team's menu logo and helmet | `patches/team_logo.py`, `patches/team_helmet.py` (`build_all.py --commanders-logo`, art in `custom/`) |

## Environment notes
- Windows. Bash (Git Bash) and PowerShell are both available, and paths contain spaces: quote them.
- Python 3.14 from the user's install. `pip install -r requirements.txt` (Pillow, capstone, unicorn).
- Don't run the repo's scripts with `python -I`: they import sibling modules (`tdb`, `headshots`, `xbe`).
- Set `PYTHONIOENCODING=utf8` when printing non-ASCII (the console is cp1252).
- `lzh1emu.py` runs the game's codec from the stock 09 XBE. Set `MADDEN09_XBE` if the game isn't at `../../Madden NFL 09 (USA)/default.xbe`.
- Large files: `BGM.dat` is 756 MB when built, `uis_plyr.dat` 59 MB. Long builds should run in the background.

## Current state (2026-11-04)
- **Working on hardware:**
  - the 09 awareness fix, verified over two franchise seasons
  - the Madden 27 roster with headshots and matched skin tones, modern team names (classic teams keep theirs), and the 2026 coaching staffs with photos
  - all 154 music tracks
  - "performance" progression v2 (two seasons: production drives progression, 99s 5 → 11 vs stock 31); the default build
  - custom screens and the dashboard rename
  - the Commanders' W in menus and on the white and burgundy helmets, with classic Redskins teams keeping their logo (`--commanders-logo`, including the training camp uniforms; alternates still have the old helmet)
  - the 17-game, 18-week season with a 3-week preseason, through year 4, with no preseason picker (the default build; `--no-season17` opts out); `--schedule` makes year 1 a real NFL season (2026)
  - loading and re-saving an edited franchise save (`--save-unlock`, off by default; tested with a jersey-only edit)
  - jumping a franchise to a later week (`tools/save_jump.py`; year 2, week 1 to 18, through the postseason into the offseason)
- **Checked 2026-11-04:** the full `build_all.py` command in docs/workflow.md reproduces the hardware-tested files byte for byte, and its output boots in xemu.
- **Working on hardware, off by default:** 7-team playoffs (`--playoffs7`), simmed through years 1 and 2 to the year 2 offseason prompt. Not tried: playing a playoff game by hand. Needs a franchise created on that build; an older franchise sticks at the end of its last regular-season week.
- **Built, not tested:** the 07/08 awareness XBEs.

## Things that cost time before (avoid repeating)
- **New data ignored on the console?** Check `fe.qkl`/`game.qkl` first (`qkl_sync.py`). That's what silenced the new music and hid the start screen.
- **Wrong roster or photos?** Check for a roster save on the hard drive or memory card (`Rost-` folders override `template.dat`; xemu's test drive has none, so xemu won't show this) and for mismatched roster files from different builds.
- **Comparing players across a franchise's creation:** PGIDs are renumbered at creation. Match by name and position, or compare totals.
- **The demo-exit freeze** happens on the stock game too. It isn't a mod bug. The build now delays the demo by 24 h (`patches/press_start_timer.py`, which needs `fe.qkl` re-synced).
- **Never change a TERF entry's directory size in place.** The game adds up rounded sizes from the last multiple of 20 to find an entry (docs/formats.md), so a shorter entry breaks later, untouched ones. Keep the size and pad with zeros.
- **Base test overlays on the current build.** Helmet tests used a pre-17-game `template.dat`, which replaced the 17-game one on the Xbox. Compare sizes against a full `build_all.py` output.
- **Reading thresholds by stack offset is error-prone.** The PLLO slot order was settled by the logic of the grading comparisons (`0x413666`), not by the fetch call's stack layout.
- **Analysis scripts:** write them as `tools/` files rather than long one-off heredocs once they're reused.
