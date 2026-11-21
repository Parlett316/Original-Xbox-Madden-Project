"""Capture packets on a network card through Npcap (wpcap.dll, ctypes) and print a line per packet.

    python npcap_capture.py <adapter GUID> <seconds> <out.pcap> ["bpf filter"]

Example: python tools/npcap_capture.py {0B97E908-...} 60 cap.pcap "udp port 3658"
Each line: time, source > destination, protocol, length, first payload bytes. The file is a
normal pcap (Ethernet) for Wireshark. Used for the xemu boxes bridged onto the card
(online_test.py setup --lan); Npcap also shows what one xemu instance sends to the other.
"""
import ctypes
import struct
import sys
import time

WPCAP = r'C:\Windows\System32\Npcap\wpcap.dll'


class Hdr(ctypes.Structure):
    _fields_ = [('sec', ctypes.c_long), ('usec', ctypes.c_long), ('caplen', ctypes.c_uint32), ('len', ctypes.c_uint32)]


class Prog(ctypes.Structure):
    _fields_ = [('n', ctypes.c_uint), ('insns', ctypes.c_void_p)]


def ip(b):
    return '.'.join(str(x) for x in b)


def summary(pkt):
    if len(pkt) >= 42 and pkt[12:14] == b'\x08\x06':
        op, sha, spa, tpa = struct.unpack('>H', pkt[20:22])[0], pkt[22:28].hex(':'), ip(pkt[28:32]), ip(pkt[38:42])
        return ('ARP who-has %s tell %s (%s)' if op == 1 else 'ARP reply %s: %s is-at %s to %s') % (
            (tpa, spa, sha) if op == 1 else (op, spa, sha, tpa))
    if len(pkt) < 34 or pkt[12:14] != b'\x08\x00':
        return 'non-IP %d bytes' % len(pkt)
    ihl = (pkt[14] & 15) * 4
    proto, src, dst = pkt[23], ip(pkt[26:30]), ip(pkt[30:34])
    t = pkt[14 + ihl:]
    if proto in (6, 17) and len(t) >= 8:
        sp, dp = struct.unpack('>HH', t[:4])
        head = 20 if proto == 6 else 8
        if proto == 6:
            head = (t[12] >> 4) * 4
        data = t[head:]
        return '%s:%d > %s:%d %s %d  %s' % (src, sp, dst, dp, 'TCP' if proto == 6 else 'UDP', len(data), data[:24].hex())
    return '%s > %s proto %d' % (src, dst, proto)


def main(guid, secs, out, flt=''):
    lib = ctypes.CDLL(WPCAP)
    lib.pcap_open_live.restype = ctypes.c_void_p
    lib.pcap_open_live.argtypes = [ctypes.c_char_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_char_p]
    lib.pcap_next_ex.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.POINTER(Hdr)), ctypes.POINTER(ctypes.POINTER(ctypes.c_ubyte))]
    lib.pcap_compile.argtypes = [ctypes.c_void_p, ctypes.POINTER(Prog), ctypes.c_char_p, ctypes.c_int, ctypes.c_uint32]
    lib.pcap_setfilter.argtypes = [ctypes.c_void_p, ctypes.POINTER(Prog)]
    err = ctypes.create_string_buffer(256)
    h = lib.pcap_open_live(('\\Device\\NPF_' + guid).encode(), 65535, 1, 200, err)
    if not h:
        raise SystemExit(err.value.decode())
    if flt:
        p = Prog()
        if lib.pcap_compile(h, ctypes.byref(p), flt.encode(), 1, 0xffffffff) or lib.pcap_setfilter(h, ctypes.byref(p)):
            raise SystemExit('bad filter')
    f = open(out, 'wb')
    f.write(struct.pack('<IHHiIII', 0xa1b2c3d4, 2, 4, 0, 0, 65535, 1))
    hdr, data = ctypes.POINTER(Hdr)(), ctypes.POINTER(ctypes.c_ubyte)()
    end, n = time.time() + float(secs), 0
    while time.time() < end:
        r = lib.pcap_next_ex(h, ctypes.byref(hdr), ctypes.byref(data))
        if r != 1:
            continue
        pkt = ctypes.string_at(data, hdr.contents.caplen)
        f.write(struct.pack('<IIII', hdr.contents.sec, hdr.contents.usec, len(pkt), hdr.contents.len) + pkt)
        f.flush()
        n += 1
        print(time.strftime('%H:%M:%S', time.localtime(hdr.contents.sec)), summary(pkt), flush=True)
    print('done', n, 'packets', flush=True)


if __name__ == '__main__':
    if len(sys.argv) < 4:
        raise SystemExit(__doc__)
    main(*sys.argv[1:])
