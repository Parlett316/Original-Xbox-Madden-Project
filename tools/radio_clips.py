"""Decode the first clips of front-end speech banks (the radio show in 2005-07's SPCHFEDT.dat) to WAV.

Usage: python radio_clips.py <SPCHFEDT.dat> <out folder> <entry> [<entry> ...] [--clips N]

Inputs are only read. A bank entry is a run of "PT" streams (header, SCCl, SCDl blocks, SCEl), found by
their "PT" marker. The codec is the commentary's MicroTalk, so the tables come from
the stock 09 XBE (MADDEN09_XBE, or ../Madden NFL 09 (USA)/default.xbe).
"""
import os
import struct
import sys
import wave

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import speech_clips  # noqa: E402
from headshots import terf_entries  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
XBE = os.environ.get('MADDEN09_XBE', os.path.join(HERE, '..', 'Madden NFL 09 (USA)', 'default.xbe'))


def pt_header(blob):
    """Return (sample rate, samples, offset of the first chunk) of a PT stream."""
    end = blob.find(b'SCCl')
    h = blob[:end]
    rate, count = 22050, None
    at = h.find(bytes([0x84]), 4)
    if at >= 0:
        rate = int.from_bytes(h[at + 2:at + 2 + h[at + 1]], 'big')
    at = h.find(bytes([0xfd, 0x80, 0x01, 0x03, 0x85]))
    if at >= 0:
        count = int.from_bytes(h[at + 6:at + 6 + h[at + 5]], 'big')
    return rate, count, end


def streams(bank):
    """Each stream: a "PT" header, SCCl, SCDl blocks and SCEl. The first follows 8 bytes of entry header."""
    p = bank.find(b'PT')
    while 0 <= p < len(bank):
        end = bank.find(b'SCEl', p)
        end = len(bank) if end < 0 else end + 8
        yield bank[p:end]
        p = bank.find(bytes([0x50, 0x54, 7, 0]), end)


def main(path, out, wanted, limit):
    tabs = speech_clips.tables(open(XBE, 'rb').read())
    f = open(path, 'rb').read()
    data_at, entries = terf_entries(f)
    os.makedirs(out, exist_ok=True)
    for e in wanted:
        o, s = entries[e]
        bank = f[data_at + o:data_at + o + s]
        n = 0
        for k, st in enumerate(streams(bank)):
            n += 1
            if k >= limit:
                continue
            rate, count, at = pt_header(st)
            pcm, _, worst = speech_clips.decode_stream(st[at:], *tabs)
            pcm = pcm[:count] if count else pcm
            name = os.path.join(out, f'e{e}_{k}.wav')
            with wave.open(name, 'wb') as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(rate)
                w.writeframes(b''.join(struct.pack('<h', max(-32768, min(32767, round(x)))) for x in pcm))
            print(f'{name}  {len(pcm) / rate:6.2f} s  {rate} Hz  left over {worst}')
        print(f'entry {e}: {n} streams, {s} bytes')


if __name__ == '__main__':
    a = sys.argv[1:]
    limit = 2
    if '--clips' in a:
        i = a.index('--clips')
        limit = int(a[i + 1])
        del a[i:i + 2]
    if len(a) < 3:
        sys.exit(__doc__)
    main(a[0], a[1], [int(v, 0) for v in a[2:]], limit)
