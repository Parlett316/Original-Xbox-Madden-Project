# Custom loading and start screens (Madden NFL 09)

Replace the game's loading-screen cover art and the "Press START" background with your own images. The author's build uses a personal photo, which isn't in this repository. Bring your own image.

## Loading screen (`data/LOADDATA.dat`)

    python pack_loadscreen.py "<game>/data/LOADDATA.dat" "<out>/data/LOADDATA.dat" my_screen.png

- Entries 0 and 2 (the cover image) are 1024×512 P8 textures (Xbox format 0x0B, Morton-swizzled, 256-colour BGRA palette). The visible screen is the top-left 640×480, so make your image 640×480.
- The entries are compressed with EA "LZH1" (codec 5). `lzh1emu.py` runs the game's own compressor and decompressor from `default.xbe` under unicorn (`pip install unicorn`), so the output is exactly what the game expects. Each new entry is checked by decompressing it again.
  - decode: init `0x5354b0`, run `0x533ca0`; encode: init `0x535a50`, run `0x533ca0`, close `0x533150`; one-time startup `0x5330a0`.
- The image is quantised to 256 colours (median cut, Floyd–Steinberg).

To start from the original art (for example to keep the background and only change the player), render the original entry first. Use `eammap.render()` on the decompressed entry; see `pack_loadscreen.py` for how entries are read. The author's own composite was built that way, with a hand-tuned script that isn't included.

## Start screen (`data/uis_fe.dat` entry 7)

    python packstart.py "<game>/data/uis_fe.dat" "<out>/data/uis_fe.dat" my_start.png

- A 512×256 P8 texture, uncompressed, stretched to full screen by the game. Any image size works; it's resized.
- "Press START", the NFL Players logo and the sparkles are separate overlays and stay as they are.
- `start_preview.png` is written next to you for a quick check.

**You must also update `data/fe.qkl`.** The game loads the front end from that quick-load bundle, which holds a copy of the uis_fe.dat entries, so patching uis_fe.dat alone changes nothing on screen:

    python ../qkl_sync.py "<game>/data/fe.qkl" "<game>/data" "<out>/data" "<out>/data/fe.qkl"

## Files
- `terf.py`: EA TERF archive reader (DIR1 offsets relative to DATA, COMP codec table).
- `eammap.py`: MMAP texture-pack parsing, Xbox Morton swizzle, rendering to RGBA.
- `lzh1emu.py`: LZH1 via the game's own code under unicorn.
- `xbe.py`: minimal XBE section mapper (VA ↔ file offset).
- `pack_loadscreen.py`, `packstart.py`: the two packers above.
