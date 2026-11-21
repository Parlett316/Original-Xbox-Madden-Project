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
- gdb breakpoints (`xemu_watch.py`) slow the game so much that menu keys get dropped: open the
  dialog first, then arm the watcher, then send one key. Only one gdb client at a time.

## Where things stand (update this list)

Works: login, online menu, Lobby room list, join/leave, Create Room (online.py patch 9),
two players in one room seeing each other, invites (`mesg` in, `priv` out) up to Game Setup and
"Connecting ..." against the bot.
Two LAN boxes: invite, accept (box 2: `x w5 a w12` opens the invite and picks Play), Game Setup on
both, Ready on both (`a` on each), then +ses and "Failed to Connect!" (findings §14).
Open: the session listener behind "Failed to Connect!"; a user-created room is hidden in the
*other* player's Lobby list (client has it, screen drops it).
