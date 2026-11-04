# File formats (Madden NFL 2005–09, Xbox)

All little-endian. Offsets are for Madden 09 unless stated otherwise.

## TDB databases (`*.db`, inside `template.dat`, `DB_TEAMS.dat`, saves)

EA's table database. Code: [`roster/tdb.py`](../roster/tdb.py).

```
DB header, 0x18 bytes: 'DB\0\x08', u32 0, u32 db size (incl. trailer), u32 0,
                       u32 table count, u32 CRC(header[0:0x14])
index:                 per table: 4-byte tag (reads normally, e.g. 'PLAY'), u32 offset from end of index
table header, 0x28:    u32 CRC of the previous region, u32 flags, u32 record length,
                       u32 record bits - 1, u32 0, u16 capacity, u16 count, u16 0, u16 0xffff,
                       u8 field count, ..., u32 CRC(table[4:0x24]) at +0x24
field defs, 16 each:   u32 type, u32 bit offset, 4-byte tag, u32 bit width
records:               capacity × record length (tables are packed back to back);
                       tables with flags 0x1a store only count × record length
trailer:               u32 CRC of the last table's field defs + records
```

- **Checksums** are all CRC-32/MPEG-2: poly `0x04C11DB7`, not reflected, init `0xFFFFFFFF`, no final xor. Table 0's leading CRC covers the index; table *k*'s covers table *k*−1's field defs and records. `tdb.DB.fix()` recomputes everything, and verifies on every DB in all five games.
- **Fields** are LSB-first bitfields over the little-endian record. Type 0 = string (full width, no terminator needed), 2 = signed, 3 = unsigned.
- `DB.resized({table: capacity})` grows tables, padding only full-storage ones (flags 2/6); a 0x1a table keeps its stored rows and just gets the new capacity. With no changes it reproduces every DB in `template.dat` and `strmdata.db` byte for byte. Most of the franchise DB (`template.dat` entry 4) is 0x1a.
- **In XBE code**, queries are SQL-like strings with byte-reversed tags: `select 'PXSP' into ? from 'YALP' where 'DIGP' = ?` reads `PSXP` from `PLAY` where `PGID` = ?. Marker bytes 0x80–0x8C stand for parameters.

### Where things live (09)

| Data | Location |
|---|---|
| Default league roster | `template.dat`, DB @ `0x180`: `PLAY` (1,986/2,048), `DCHT` depth chart, `INJY`, `TEAM` (33) |
| Career/season stats of the default roster | `template.dat`, DB @ `0x16ad00` (PCNG, PSOF, PSDE…, keyed by PGID) |
| Per-team rosters for current teams, then the FA pool, then classic teams | `DB_TEAMS.dat`: 32 team DBs (packed, capacity = count), FA DB (276 slots), 200+ classic-team DBs |
| Colleges | `strmdata.db` `COLL` (277; `PCOL` indexes it) |
| In-season progression | `strmdata.db` `PWRA` (deltas) and `PLLO` (grade thresholds); checkpoints in `template.dat` `SCWE` |
| Offseason progression | `strmdata.db` `PYRA` (yearly multipliers for physical ratings) |
| Roles | `strmdata.db` `RINF`, `RLPM` (self bonuses), `RLTM` (teammate bonuses); `PLAY.PROL/PRL2` |
| Music | `strmdata.db` `MUST` (soundtracks), `MUSO` (songs); `template.dat` `MUPL` (default EA Trax playlist, 40 slots) |
| 2005 | `DB_TEMPLATES.DAT` @ `0x100` (roster, 1,996/2,048), `STREAMEDDATA.DB` |

### PLAY fields worth knowing

| Field | Meaning |
|---|---|
| `PGID`/`POID` | player id (15 bits); unique; renumbered when a franchise is created |
| `TGID` | team; 1–32 match EA's ratings-site team ids, 1009 = free agent |
| `PPOS` | position: QB 0, HB 1, FB 2, WR 3, TE 4, LT 5, LG 6, C 7, RG 8, RT 9, LE 10, RE 11, DT 12, LOLB 13, MLB 14, ROLB 15, CB 16, FS 17, SS 18, K 19, P 20 |
| `POVR`, `PAWR`, `PSPD`, … | ratings (7 bits) |
| `PWGT` | weight − 160 lb |
| `PTSA`/`PVTS`, `PSBO`/`PVSB` | salary and bonus, in $1,000 |
| `PCON`/`PVCO` | contract years |
| `PDPI`/`PDRO` | draft pick/round; 63/15 = undrafted |
| `PROL`, `PRL2` | role slots; 45 (0x2D) = none in 08/09, 31 (0x1F) in 07 |
| `PCMT` | commentary name id; 999 = no spoken name |
| `PSXP` | menu headshot: `uis_plyr.dat` entry PSXP+1; 0 = blank |
| `PSKI` | skin tone, 0 light … 2 dark |
| `PFEx` | face model; values used by only one player are scanned star faces |
| `PICN` | superstar icon flag |
| `PCPH` | career phase (0 young, 1 prime, 2 veteran), used by progression |

DCHT depth slots: 0–20 = positions, 21 KR, 22 PR, 23 kickoff kicker, 24 long snapper, 25 third-down back.

## Saves (`E:\UDATA\<title id>\<save id>\`)

| File | Layout |
|---|---|
| `Rost-Rost1` (roster) | `'Rost1'` + padding, 20-byte signature at 0x10, TDB at `0x25` |
| `Fran-FranN` (franchise) | `'Fran1'` + padding, 20-byte signature, TDB at `0x29` (185 tables) |
| `Prof-<name>`, `Sett-Sett1` | profile (includes the EA Trax playlist) and settings |

Title ids: 2005 `4541004D`, 06 `45410075`, 07 `4541009F`, 08 `454100AC`, 09 `4541023B`. An edited save loads only on an XBE built with `--save-unlock` (see below).

**Save signatures** (09, 2026-11-04). The file is: name (17 bytes), signature of the name at `0x11`, the data, a signature of the data, padding, and a signature of the padding in the last 20 bytes. So the value at `0x11` stays the same for a given save name, whatever the contents. All three are `XCalculateSignature` values keyed from the kernel, so they can't be recomputed on a PC. Franchises (types 1-4 and 12 share this path; `0x1ecf20` opens, `0x1ed020` finishes) load through the stream driver at `0x73b5f0`, starting at offset 4 of the data. Its close (`0x5d0c0`) checks the data signature, then hashes the padding and checks that signature too, both in `0x5ce00`. `patches/save_unlock.py` makes that compare always pass (`0x5cf05`, je to jmp); the name check stays, so an edited save must keep its name, its file size and correct database CRCs (`tdb.DB.fix`). Proven on hardware: a jersey-only edit loads, shows in game and survives a save and reload. The file size is fixed, but the database inside can shrink or grow when the game saves (so the data signature moves and the padding takes up the difference); read the size at `0x31`. The verifiers at `0xeb020` and `0xeb2b0` are a trap: `0x23c770` only reaches them for the saves listed in the table at `0x763fc0` (spawn games, online rosters and similar), not franchises.

Franchise season stats: `PSNG` (`sgmp` games played, `sgms` games started), `PSOF` (`saya` pass yards, `satd` pass TDs, `sain` INTs, `suya` rush yards, `sutd` rush TDs, `scya` receiving yards, `sctd` receiving TDs, …), `PSDE` (`sdta` tackles, `slsk` sacks, `ssin` INTs, `sdpd` passes defended, …). All are keyed by `PGID` + `SEYR` (0 = first franchise season). `SEAI` holds the current year and week.

## TERF archives (`*.dat` asset files)

```
'TERF', u32 header size (0x800 for BGM), u16 ?, u16 ?, u16 alignment, u16 entry count @ 14
chunks after the header: (tag, u32 size): DIR1 (u32 offset from DATA start, u32 size per entry),
                         optional COMP (u32 codec, u32 unpacked size per entry), DATA
```

`template.dat`'s entries are 0x40-aligned from the DATA chunk (an empty entry still takes one slot), and the DATA chunk's size field covers everything after it; `patches/season17.py:repack` rebuilds the archive by that rule, and with no changes reproduces the stock file byte for byte. `fe.qkl` preloads `template.dat`'s header and directory (and entry 11), so re-sync it whenever an entry's size changes.

Codec 5 is EA "LZH1"; `patches/loadscreen/lzh1emu.py` runs the game's own codec under unicorn. Readers: `patches/loadscreen/terf.py`, `roster/headshots.py:terf_entries`.

### MMAP texture packs (inside TERF entries)

Texture table at 0x28 (w, h, format, size, offset); offsets are relative to +0x80. Format 0x0B = P8, Morton-swizzled (x bits on even positions, y on odd), 256-entry BGRA palette. Code: `patches/loadscreen/eammap.py`.

| File | Entries |
|---|---|
| `LOADDATA.dat` | loading screens; entries 0 and 2 = cover art, 1024×512 P8, LZH1-compressed, visible area 640×480 |
| `uis_fe.dat` | front end; entry 7 = "Press START" background, 512×256 P8, uncompressed |
| `uis_plyr.dat` | 3,286 menu headshots, fixed 17,948-byte entries: 128×128 P8 at +0x100, palette at +0x4200, photo is a 66×66 crop at (15,15) with a light outline; entry 1 = blank |
| `uis_load.dat` | rookie-spotlight loading screens (unmodified) |
| `plyrface.dat` | 532 in-game face textures, 256×256 (unmodified) |

### BGM.dat (music)

A TERF archive with one EA SCHl audio stream per song, entries 0x800-aligned. All five games use 22,050 Hz stereo, codec 0x0A, version 3, with identical SCDl block layout. 2005's SCHl header lacks the `0b 01 02` platform tag and has tag 0x8C = 0x04 (06–09: 0x24). `MUSO.MSOR` is the entry index; `MSOI` is the song's position in its soundtrack (alphabetical by artist).

## QL01 quick-load bundles (`fe.qkl`, `game.qkl`)

```
'QL01', u32 header size; chunks (tag, u32 size):
FILS  u32 count, 48-byte entries: file name
DTLS  u32 count, 12-byte entries: u16 kind, u16 file index (into FILS), u32 n, u32 offset (from end of DTLS)
      kind 0 = the file's header region (TERF header + DIR1 + DATA chunk head), kind 1 = TERF entry n
DATA  the copies
```

Header copies have no stored length; `patches/qkl_sync.py` measures each one against the stock file. `fe.qkl` holds `BGM.dat`'s header and directory, `uis_fe.dat`'s entries, parts of `template.dat` and `uis_plyr.dat`, and more.

## XBE

Standard Xbox executable. Certificate at the header field `0x118`: title id at +8, title name (40 UTF-16 chars) at +0x0C. Code is in `.text` at VA `0x11000`; `tools/xdis.py` maps VAs. Patches go in the header page's zero padding at VA `0x10F00`, with `SizeOfHeaders` (`0x108`) raised to `0x1000` and the `.text` SHA-1 digest recomputed. The RSA header signature can't be regenerated.

The game copies 36 data files to the Z: cache partition (list at XBE `0x739fc8`) and refreshes them when they change. `bgm.dat` isn't one of them.
