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
- Both boxes sit behind separate xemu NATs (both 10.0.2.15): lobby works, box-to-box game
  traffic can't flow between them. That step needs another network setup or real Xboxes.
- The on-screen keyboard (Create Room name): A types the highlighted key, arrows move, Start = Done.

## Where things stand (update this list)

Works: login, online menu, Lobby room list, join/leave, Create Room (online.py patch 9),
two players in one room seeing each other, Invite to Game sends `gcre`.
Open: game replies (`gcre`/`gjoi`/`+mgm`/`gsta`/`+ses`, written in aries_server.py, untested);
a user-created room is hidden in the *other* player's Lobby list (client has it, screen drops it).
