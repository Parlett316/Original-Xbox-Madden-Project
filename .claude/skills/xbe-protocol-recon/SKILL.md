---
name: xbe-protocol-recon
description: Work out what Madden 09's online code expects from the lobby server (reply keys, order, waits) by reading the XBE. Use when a lobby/messenger screen hangs, a reply is ignored, or a new command shows up in the server log.
---

# Reading the XBE for the lobby protocol

Background and addresses found so far: docs/findings.md §14 (search it before reading code).
XBE: `Madden NFL 09 (USA)/default.xbe`. Tools in `tools/` (all fast; never pipe stdin into them).

## Steps

1. **Find the command's code.** `python tools/xkeys.py <xbe> --tag room +rom` — tags are
   big-endian dwords, so `'room'` is stored as `moor`. Hits in 0x4dc000–0x4ec000 are the game's
   OSDK screens, 0x53d000–0x554000 DirtySDK LobbyApi, 0x54d000–0x551800 EA Messenger (BuddyApi).
2. **List the keys a parser reads.** `python tools/xkeys.py <xbe> <VA>` prints every string the
   function references in order (`IDENT`, `NAME`, `OPPO%d`...). `%s%d` keys are indexed
   (`VIEW0`, `VIEW1`).
3. **Read the logic only where needed:** `python tools/xdis.py <xbe> <start> <end>`, callers with
   `tools/xcallers.py`. Reply handlers are registered with `0x53d55d(proto, tag, params, handler,
   ctx)`; filters for pushes (`+rom`...) with `0x53d428`. The OSDK waiter for a request is
   `0x4fd6e5`; its object's vtable has the reply handler.
4. **Check at runtime when reading stalls.** Over the gdb stub (`tools/xemu.py boot --gdb`, then
   `from xemu import GDB`): the lobby object is `[[[[0x7c5f18]+0x18]+0x34]+0x34]`; room list at
   `+0xc` (count `+0x1c`, array `+0x44`, room name at entry `+0x24`), categories at `+0x18`/`+0x1c`
   (0x151 each), pending room request at `+0x5474` (callback) / `+0x5480` (name).
5. **Prefer one decisive test** (server change + `online-test` skill) over more reading.

## Patterns seen so far

- A reply with the right tag but missing keys usually makes the client wait silently, not fail.
- The client often waits for a *push* after the reply (room create: `room` reply, then it looks
  for a `+rom` with the same NAME) — send pushes before the reply when the client checks on reply.
- Comma fields end at a space unless quoted (`"User Rooms"`); parser `0x46b292`.
- Anything that needed Xbox Live (string verify, logon users, roster download) fails without it:
  patch the check in `patches/online.py`, with a numbered note and stock-byte assert.
- Bugcheck freeze: EIP at `0x800151ef` → read code/params off the stack over gdb.
