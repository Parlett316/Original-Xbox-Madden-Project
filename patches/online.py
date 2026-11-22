"""Let Madden 09's online mode reach a private lobby server instead of Xbox Live (default.xbe).

    python online.py <in default.xbe> <out default.xbe> <server IPv4 address> [--name NAME] [--lag-tolerant]

--name gives this copy's player name (1 to 15 letters, digits, '_' or '-'). The login sends it as
GTAG, which the lobby server (tools/aries_server.py) uses instead of Player<n>. The game passes the
login its Live gamertag (a virtual getter called at 0x501931), which syslink leaves empty; the patch
pushes the name instead, kept in 16 unused zero bytes of .rdata (0x636f20). The reconnect path reads
the gamertag at +0x104 of the lobby client (0x54638f) and is pointed at the name too. Without
--name it stays empty and the server hands out Player1, Player2...

--lag-tolerant (for two xemu boxes on one PC) turns off the in-game lag drop: the game ends a
match ("The connection to your opponent has been lost") after 5 waits of over 1 s for the other
box's frames once more than 2.5 s of lag has added up (monitor set up at 0x68d20, checked at
0x68dd0). Two emulated boxes stall like that. The switch makes the monitor skip waits of over 1 s
(the jbe at 0x68cab always jumps), so none is counted. Raising the 5 instead (the first try) let
the count pass the end of the 10-entry time array at +0x2c (stored by 0x68d00), which broke a heap
block, and the host crashed in the allocator (0x371345) at the coin toss.

Work in progress (docs/findings.md §14). Fourteen kinds of change, each checked against the stock bytes:

1. EA's network startup (0x4693a5, DirtySDK NetConn) reads "-syslink" and "-coop"/"-nosecure"
   from its argument, but all three callers pass "" (0x7063dc). They now pass 0x72b98c, whose
   string becomes "-syslink    -coop" (the four zero bytes before "-coop" turned into spaces; it
   still matches itself as the "-syslink" needle). Syslink skips XOnlineStartup and the
   gamertag screen; -coop asks XNet to bypass security, which this retail XNet ignores.
2. The directory server name "xblmadden09.ea.com" (0x6ed51c, 18 characters) becomes the
   server's address. A dotted address skips the DNS lookup (ProtoSSL parses it, 0x55c5d3).
3. XNet's IP routing (0x5e120f) drops a plain (unencrypted) packet to a host that isn't a
   key-exchanged Xbox unless the packet is flagged as allowed (DHCP, DNS). The je at 0x5e1287
   becomes two nops, so plain packets go out.
4. XNet's TCP input (0x5ed3d7) drops a plain segment unless the socket is flagged 0x2000000.
   The je at 0x5ed3f5 becomes nops (a segment for no socket is still dropped).
5. The EA online layer tears the session down unless NetConnStatus('conn') is '+onl' (signed
   into Live). In syslink mode it's '+isp' (link up), so its four comparisons now take '+isp'.
6. NetConnStatus('onln') reports the Live sign-in flag (+0x7e8); it now reports the syslink flag
   (+0x7e4), which is 1.
7. Voice chat's startup (0x53ef85) copies the signed-in user's XUID from XOnlineGetLogonUsers,
   which returns NULL without Live, so startup failed and the lobby crashed right after login
   (0x53f3ba writes through the NULL voice module: bugcheck 0x1E at 0x55441d). The call at
   0x53efe3 now loads the address of 16 unused zero bytes in .rdata (0x636ee0) instead.
8. After login the online menu compares the server's ROSTER_VER with a checksum of the loaded
   roster (0x23ce60, over the PLAY table) and offers EA's roster download when they differ; with
   no ROSTER_URL the download never starts, and its Cancel crashes (NULL handle, 0x5044ce). The
   sete at 0x23ce79 becomes "mov al, 1": the roster always counts as current, so our own roster
   is never replaced.
9. Before sending `room` (create a room) the client has Xbox Live check the room name for
   profanity (0x552632), unless the request says IGNPROFANE=1. Without Live the check fails and
   the name goes out as '***' ('USR.***'), while the client waits for a room under the name it
   typed, so Create Room never finished. The jne at 0x552658 becomes nops: the name is always
   sent as typed, as with IGNPROFANE=1.

10. Receiving a game invite crashed the guest (bugcheck 0x1E at 0x5f5710 reading address 4):
   EA's message code asks XOnline whether a player handle is a given one (0x5ee867, which loads
   the XOnline object 0x7cc408, NULL without XOnlineStartup, and compares). Callers 0x55af8e (via
   0x54f242, the message/voice checks) and 0x55a850. 0x5ee867 now returns 0 ("no") at once:
   xor eax, eax; ret 4 (stdcall, one argument).
11. The game link between the boxes (DirtySDK ConnApi) never started: copying the game's players
   into its client list (0x542cec) clears each client's address (`and dword ptr [edx], 0` at
   0x542d4b), and an empty address is then looked up through Xbox Live matchmaking (0x5562cc /
   0x556396: MADDR read as a Live session ID, XOnlineMatchSessionFindFromID, XNetRegisterKey,
   XNetXnAddrToInAddr). Without Live that fails, both status words go to 5 and the game says
   "Failed to Connect!". The `and` becomes nops, so each client keeps the lobby's ADDR and the
   lookup (skipped when the address is set, 0x543678) never runs.
12. XNet's UDP input (0x5edcca) drops a plain datagram addressed to one socket unless the socket
   is flagged 0x2000000, as TCP does (4); with change 11 the guest's connect then timed out after
   10 s. The je at 0x5eddc6 becomes nops. (The broadcast branch, 0x5edd56, keeps its check.)

13. Loading the online game crashed both boxes (bugcheck 0x1E at 0x34265f, a NULL pool from the
   STATE heap). The setter 0x24aea0 stores a byte in a per-slot table ([[0x803434]], count byte at
   +4, 11 entries in the online game) at the slot number from OCMT/MTTS ('UNLS'); it checks the
   slot against the count, but its jae goes to the store (0x24aeeb) instead of past it. Online
   the slot was 15, so the store landed 0x3c bytes in, on the low byte of the next free block's
   end pointer in STATE, and every later STATE allocation failed. The jae at 0x24aeac now skips
   to 0x24af00, the code after the store.
14. Each box's local controller port is the OSDK user object's +8 (method +0x24, set by +0x20 from
   the Live sign-in screen's script command 0x4d339c), which syslink skips, so it stayed -1. The
   game sends it to the other box as the player's "Controller" attribute (0x236102), and
   0xec3bf puts the local player on controller "Controller" and the remote one on "Controller"
   + 4: -1 became 15 (none) and 3 (port 4), so the guest was "removed ... excessive controller
   pulls" and the host's port 4 counted as disconnected. The attribute now comes from a stub in
   the dead XOnline compare body (0x5f570a, reached only through 0x5ee86d, which change 10 cut
   off) that reads +8 and gives 0 (controller port 1) when it is negative.
15. (--name only) The login's GTAG comes from the name at 0x636f20 instead of the empty gamertag:
   the game's call to the gamertag getter (0x50192f, `mov eax,[ecx]; call [eax+0x14]; push eax`)
   becomes `push 0x636f20; nop`, and the reconnect's read (0x54638f) becomes `mov eax, 0x636f20`.
   The first version patched only the reconnect read, and the login still sent GTAG ''.

The game traffic between the boxes is now plain UDP to the lobby's ADDR, not XNet's encrypted kind.
"""
import re
import struct
import sys

EMPTY_ARG, SYSLINK_ARG = 0x7063dc, 0x72b98c
ARG_SITES = (0x4f9fb2, 0x500a86, 0x50198a)     # imm32 operands passing the startup argument
GAP = 0x72b994                                   # the 4 zero bytes between "-syslink" and "-coop"
SERVER_NAME = 0x6ed51c
STOCK_NAME = b'xblmadden09.ea.com\0'
NOPS = (
    (0x5e1287, '7405'),            # IP routing: plain packet to an unknown host -> dropped
    (0x5ed3f5, '0f8485020000'),    # TCP input: plain segment for a secure socket -> dropped
    (0x542d4b, '832200'),          # ConnApi: client address cleared -> looked up through Live
    (0x5eddc6, '7434'),            # UDP input: plain datagram for a secure socket -> dropped
)
PLUS_ONL, PLUS_ISP = b'lno+', b'psi+'           # '+onl' and '+isp' as little-endian dwords
ONL_SITES = (0x4fa152, 0x4fa303, 0x4fa35d, 0x4fa393)
ONLN_DISP = 0x46992a                             # cmp byte ptr [edx+0x7e8], 1 -> [edx+0x7e4]
LOGON_CALL = 0x53efe3                            # call XOnlineGetLogonUsers (0x5ee83b), in voice startup
NO_USERS = 0x636ee0                              # 16 zero bytes in .rdata that nothing references
ROSTER_CURRENT = 0x23ce79                        # sete al -> mov al, 1; nop (roster version check)
PROFANITY_CHECK = 0x552658                       # jne -> nops: room names skip Live's string check
XONLINE_COMPARE = 0x5ee867                       # mov ecx, [0x7cc408] -> xor eax, eax; ret 4
SLOT_BOUNDS = 0x24aeac                           # jae 0x24aeeb (the store) -> jae 0x24af00 (past it)
USER_OBJECT = 0x4fa6d5                           # returns the OSDK user object (controller port at +8)
PORT_STUB = 0x5f570a                             # 15 dead bytes after change 10
NAME_SLOT = 0x636f20                             # 16 zero bytes after NO_USERS's run start; unused
GTAG_SOURCE = 0x54638f                           # lea eax, [esi+0x104] (reconnect's GTAG, the gamertag)
GTAG_GETTER = 0x50192f                           # mov eax,[ecx]; call [eax+0x14]; push eax (login's GTAG)
NAME_CHARS = re.compile(r'[A-Za-z0-9_-]{1,15}')
LAG_SPIKE_CHECK = 0x68cab                        # jbe: lag not over 1 s -> nothing recorded
CONTROLLER_ATTR = 0x236102                       # call USER_OBJECT ... call [edx+0x24] (16 bytes)


def file_offset(buf, va):
    base = struct.unpack_from('<I', buf, 0x104)[0]
    headers = struct.unpack_from('<I', buf, 0x120)[0] - base
    for k in range(struct.unpack_from('<I', buf, 0x11c)[0]):
        _, sva, vsize, raw, rsize = struct.unpack_from('<5I', buf, headers + k * 56)
        if sva <= va < sva + min(vsize, rsize):
            return va - sva + raw
    raise SystemExit(f'no section holds {va:#x}')


def put(buf, va, old, new):
    o = file_offset(buf, va)
    assert bytes(buf[o:o + len(old)]) == old, f'unexpected bytes at {va:#x}'
    assert len(new) == len(old)
    buf[o:o + len(new)] = new


def patch(buf, server):
    parts = server.split('.')
    assert len(parts) == 4 and all(p.isdigit() and int(p) < 256 for p in parts), 'give an IPv4 address'
    for va in ARG_SITES:
        put(buf, va, struct.pack('<I', EMPTY_ARG), struct.pack('<I', SYSLINK_ARG))
    put(buf, GAP - 8, b'-syslink\0\0\0\0-coop\0', b'-syslink    -coop\0')
    put(buf, SERVER_NAME, STOCK_NAME, server.encode().ljust(len(STOCK_NAME), b'\0'))
    for va, old in NOPS:
        old = bytes.fromhex(old)
        put(buf, va, old, b'\x90' * len(old))
    for va in ONL_SITES:
        put(buf, va, PLUS_ONL, PLUS_ISP)
    put(buf, ONLN_DISP, struct.pack('<I', 0x7e8), struct.pack('<I', 0x7e4))
    put(buf, NO_USERS, bytes(16), bytes(16))
    put(buf, LOGON_CALL, bytes([0xe8]) + struct.pack('<i', 0x5ee83b - (LOGON_CALL + 5)),
        bytes([0xb8]) + struct.pack('<I', NO_USERS))     # call -> mov eax, NO_USERS
    put(buf, ROSTER_CURRENT, bytes.fromhex('0f94c0'), bytes.fromhex('b00190'))
    put(buf, PROFANITY_CHECK, bytes.fromhex('7507'), bytes.fromhex('9090'))
    put(buf, XONLINE_COMPARE, bytes.fromhex('8b0d08c47c00'), bytes.fromhex('31c0c2040090'))
    put(buf, SLOT_BOUNDS, bytes.fromhex('733d'), bytes.fromhex('7352'))
    stub = (b'\xe8' + struct.pack('<i', USER_OBJECT - (PORT_STUB + 5))   # call: eax = user object
            + bytes.fromhex('8b4008'      # mov eax, [eax+8]   (the port, -1 without sign-in)
                            '85c0 7d02'   # test eax, eax; jge done
                            '31c0'        # xor eax, eax       (port 1)
                            'c3'))        # done: ret
    put(buf, PORT_STUB, bytes.fromhex('8b54240433c03b51040f94c0c20400'), stub)
    put(buf, CONTROLLER_ATTR, bytes.fromhex('e8ce452c008b108b3e6a048bc8ff5224'),
        b'\xe8' + struct.pack('<i', PORT_STUB - (CONTROLLER_ATTR + 5))
        + bytes.fromhex('8b3e 6a04') + b'\x90' * 7)      # mov edi, [esi]; push 4 (the setter's type)
    print(f'online: syslink without Xbox Live, plain TCP allowed, lobby server {server}')


def lag_tolerant(buf):
    put(buf, LAG_SPIKE_CHECK, bytes.fromhex('7647'), bytes.fromhex('eb47'))
    print('online: in-game lag drop off (xemu)')


def player_name(buf, name):
    if not NAME_CHARS.fullmatch(name):
        raise SystemExit(f'online: name {name!r}: use 1 to 15 letters, digits, _ or -')
    put(buf, NAME_SLOT, bytes(16), name.encode().ljust(16, bytes(1)))
    put(buf, GTAG_GETTER, bytes.fromhex('8b01ff501450'), bytes.fromhex('68') + struct.pack('<I', NAME_SLOT) + bytes.fromhex('90'))  # push name
    put(buf, GTAG_SOURCE, bytes.fromhex('8d8604010000'), bytes.fromhex('b8') + struct.pack('<I', NAME_SLOT) + bytes.fromhex('90'))  # mov eax, name
    print(f'online: player name {name}')


def main(src, dst, server, *flags):
    with open(src, 'rb') as f:
        buf = bytearray(f.read())
    size = len(buf)
    if '--name' in flags and not NAME_CHARS.fullmatch(flags[flags.index('--name') + 1]):
        raise SystemExit(f'online: name {flags[flags.index("--name") + 1]!r}: use 1 to 15 letters, digits, _ or -')
    patch(buf, server)
    if '--name' in flags:
        player_name(buf, flags[flags.index('--name') + 1])
    if '--lag-tolerant' in flags:
        lag_tolerant(buf)
    assert len(buf) == size
    with open(dst, 'wb') as f:
        f.write(buf)


if __name__ == '__main__':
    rest = sys.argv[4:]
    if '--name' in rest and rest.index('--name') + 1 < len(rest):
        del rest[rest.index('--name'):rest.index('--name') + 2]
    if len(sys.argv) < 4 or any(a != '--lag-tolerant' for a in rest):
        raise SystemExit(__doc__)
    args = sys.argv[1:]
    if '--name' not in args and sys.stdin.isatty():     # run by hand: ask (scripts pass no stdin)
        try:                                            # (Windows' NUL counts as a terminal)
            typed = input('Your player name online (1-15 letters, digits, _ or -; Enter for '
                          'Player1, Player2...): ').strip()
        except EOFError:
            typed = ''
        if typed:
            args += ['--name', typed]
    main(*args)
