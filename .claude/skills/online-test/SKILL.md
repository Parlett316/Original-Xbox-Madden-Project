---
name: online-test
description: Test Madden 09 online play (patches/online.py + tools/aries_server.py) in xemu with one or two instances, using tools/online_test.py instead of driving menus by hand. Use for any lobby/room/game-invite test or server change.
---

# Online test in xemu

Background: docs/findings.md §14. The XBE patch is `patches/online.py`, the lobby server
`tools/aries_server.py`. Hardware is still the source of truth; xemu is for the protocol work.

## Commands (one call each; don't drive menus key by key)

Work folder: `patched/online_test` (durable, git-ignored; holds online.iso, w/, w2/, server.log).

```
python tools/online_test.py patched/online_test setup              # after any online.py change
python tools/online_test.py patched/online_test up --two --join    # ~5 min: server + 2 boxes in USR.Madden
python tools/online_test.py patched/online_test up --join --bot     # one box + a fake player 'Bot' (accepts invites)
python tools/online_test.py patched/online_test lobby [--inst N] [--join]   # from the main menu
python tools/online_test.py patched/online_test report [N] [--all] # both.png + filtered server log
python tools/online_test.py patched/online_test reboot --inst 1 --join   # one stuck box
python tools/online_test.py patched/online_test down
```

- After a server-only change: `up` again (the server restart drops both logins anyway).
- Run `up` in the background and work on something else; read `both.png` once at the end.
- Look at the server log first; take a screenshot only when the log doesn't answer the question.
- Extra keys: `XEMU_INSTANCE=1 python tools/xemu.py keys <work>/w2 <name> TOKENS...`
  (instance 0 = `w`, Player1 if it logs in first; screens in `report` are left = 0).

## Gotchas (all cost time before)

- **Known flaky (2026-11-21):** instance 0 reaches the room reliably; instance 1 keeps losing one
  key (the Up after entering Game Modes, so it lands in Franchise or Family Play) even with long
  waits; `up` reboots it once, then gives up. Finish it by hand with `XEMU_INSTANCE=1 xemu.py keys`
  and a screenshot per step, or let the user drive it with a real pad (`xemu.py setup ... --pad`).
- xemu reads only the focused window's keyboard; `xemu.py keys` moves the focus when two
  instances run (the user's foreground window changes), and sends F13 first because the first
  key after a switch is lost. If a key still goes missing, the user probably clicked something:
  check `report`, then resend.
- Menu route: title Start, wait ~30 s (profile and menu load; slower with two boxes), Game Modes (down, down, a), Xbox Live (up, a),
  login ~15 s (wait for `-> uatr` in the log), online Game Modes (down, down, a), Lobby (down, a).
  Lobby list needs ~3 s before A.
- A running xemu holds the ISO open: `setup` stops everything first.
- Player names come from the server's counter (Player1, Player2...), in login order.
- Two boxes that must reach each other need LAN mode: `setup --lan 192.168.1.199
  {0B97E908-ECB8-4512-B09C-96FB1C442321}` (this PC's IP and card, Npcap installed, checksum and
  large-send offload off on that card, or the PC's replies arrive with bad checksums and XNet drops
  them). `setup` without `--lan` goes back to NAT (both boxes 10.0.2.15, can't reach each other).
- A frozen box with EIP 0x800151ef is a bugcheck: read code/params at [esp+0x14..] over gdb
  (`XEMU_INSTANCE=1` for box 2) and the code addresses on the stack.
- The on-screen keyboard (Create Room name): A types the highlighted key, arrows move, Start = Done.

- Invite Bot from the room: `xemu.py keys patched/online_test/w inv a w3 a w4 a w12` (Bot is the
  highlighted first row). Change the bot's game record live by writing `5=89` (USERPARAMS byte)
  or `PRES=5` (record field) to `patched/online_test/server.log.bot`.
- **Don't attach gdb while the boxes set up their link** (invite to Start Game): a data watch or
  `online_state.py` reads made the link fail ("Failed to Connect!"). Execution breakpoints armed in
  the room were fine. Arm data watches (`xemu_watch.py ... w0x<addr>`) after Start Game. While a
  watcher runs, `online_state.py` can't attach (one gdb client); use `report` screenshots.
- The server starts the session only on the host's `gsta` (Start Game, once the link is up).
  Order: box 2 invites (`a w3 a w4 a w10` on the other player's row), box 1 accepts
  (`x w5 a w8`), guest Ready (`a`), host Ready + Start (`a w6 a`).
- gdb breakpoints (`xemu_watch.py`) slow the game so much that menu keys get dropped: open the
  dialog first, then arm the watcher, then send one key. Only one gdb client at a time.

## Where things stand (update this list)

Works: login, online menu, Lobby room list, join/leave, Create Room (online.py patch 9),
two players in one room seeing each other, invites (`mesg` in, `priv` out) up to Game Setup and
"Connecting ..." against the bot.
Two LAN boxes: invite, accept (box 2: `x w5 a w4`), Game Setup on both with the direct link up
(online.py 11/12), Ready on both (`a` each), host Start Game (`a`) -> gsta/+ses -> loading screen on
both -> kickoff screen (the 0x34265f bugcheck, an out-of-range slot store, is fixed by change 13).
Link state: `python tools/online_state.py conn` (XEMU_INSTANCE=1 for box 2) prints ConnApi
clients and status (3 active, 5 failed); `heaps`, `heap 4` (one heap's header and free tree) and `cpu` (bugcheck code) too. Packets: `python tools/npcap_capture.py <GUID> 90
out.pcap "udp and host 192.168.1.100"` (game link 3658, voice 6000).
Load (2026-11-21, online.py change 13): both boxes reach the kickoff screen. Change 14 fixed the
controller port (the Live sign-in screen sets it; syslink skipped it, so it was -1 -> controllers
15/3; now port 1). `setup` builds with `online.py --lag-tolerant` (xemu stalls tripped the in-game
lag monitor -> "connection to your opponent has been lost"). With it both boxes play the coin toss in
sync; the guest dropped ~5 min in (untraced: trace 0x6ab90 on the guest with
`xemu_watch.py ... --stack`, which now logs the first four stack args), and the guest's Down didn't
move the toss menu. "End game" on both (`a`) returns both to the room: invite again without `up`.
Coin toss: guest is away (Bills) and calls it; the menu shows on both.
Open: a user-created room is hidden in the *other* player's Lobby list (client has it, screen
drops it); a box sometimes sticks on an empty Lobby list after `up` (use `reboot --inst 1 --join`).
