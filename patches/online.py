"""Let Madden 09's online mode reach a private lobby server instead of Xbox Live (default.xbe).

    python online.py <in default.xbe> <out default.xbe> <server IPv4 address>

Work in progress (docs/findings.md §14). Ten kinds of change, each checked against the stock bytes:

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

Encrypted traffic between two Xboxes (the game itself) is untouched.
"""
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
)
PLUS_ONL, PLUS_ISP = b'lno+', b'psi+'           # '+onl' and '+isp' as little-endian dwords
ONL_SITES = (0x4fa152, 0x4fa303, 0x4fa35d, 0x4fa393)
ONLN_DISP = 0x46992a                             # cmp byte ptr [edx+0x7e8], 1 -> [edx+0x7e4]
LOGON_CALL = 0x53efe3                            # call XOnlineGetLogonUsers (0x5ee83b), in voice startup
NO_USERS = 0x636ee0                              # 16 zero bytes in .rdata that nothing references
ROSTER_CURRENT = 0x23ce79                        # sete al -> mov al, 1; nop (roster version check)
PROFANITY_CHECK = 0x552658                       # jne -> nops: room names skip Live's string check
XONLINE_COMPARE = 0x5ee867                       # mov ecx, [0x7cc408] -> xor eax, eax; ret 4


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
    print(f'online: syslink without Xbox Live, plain TCP allowed, lobby server {server}')


def main(src, dst, server):
    with open(src, 'rb') as f:
        buf = bytearray(f.read())
    size = len(buf)
    patch(buf, server)
    assert len(buf) == size
    with open(dst, 'wb') as f:
        f.write(buf)


if __name__ == '__main__':
    if len(sys.argv) != 4:
        raise SystemExit(__doc__)
    main(*sys.argv[1:])
