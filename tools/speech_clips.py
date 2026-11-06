"""Decode commentary clips from Madden 09's SPCHDATA.dat to WAV, and measure their loudness.

Usage: python speech_clips.py <game folder> <out folder>
       python speech_clips.py <game folder> <out folder> --entry <descriptor> <audio> <label>

Inputs are only read. The clips are EA MicroTalk 10:1 (codec 4, 432 samples a frame), decoded with
the rc and codebook tables from the stock XBE (found by content). Each block's frames should use up
its bytes, so "left over" shows whether the decode stayed in step. The format notes are in
docs/findings.md section 10.
"""
import os
import struct
import sys
import wave

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'roster'))
from headshots import terf_entries  # noqa: E402

N, L = 0, 1   # next model: normal, large pulse

# code size and pulse value for each code the codebooks return (0-1 big pulse, 2-3 run of zeros)
COMMANDS = [(L, 8, 0.), (L, 7, 0.), (N, 8, 0.), (N, 7, 0.), (N, 2, 0.), (N, 2, -1.), (N, 2, 1.), (N, 3, -1.), (N, 3, 1.),
            (L, 4, -2.), (L, 4, 2.), (L, 3, -2.), (L, 3, 2.), (L, 5, -3.), (L, 5, 3.), (L, 4, -3.), (L, 4, 3.),
            (L, 6, -4.), (L, 6, 4.), (L, 5, -4.), (L, 5, 4.), (L, 7, -5.), (L, 7, 5.), (L, 6, -5.), (L, 6, 5.),
            (L, 8, -6.), (L, 8, 6.), (L, 7, -6.), (L, 7, 6.)]
TAPS = (0.01803267933428287506103515625, -0.114591561257839202880859375, 0.597385942935943603515625)


def tables(xbe):
    rc_at = xbe.find(struct.pack('<f', -0.99677598476409912109375)) - 4
    books_at = xbe.find(bytes([4, 6, 5, 9, 4, 6, 5, 13]))
    assert rc_at >= 0 and books_at >= 0, 'MicroTalk tables not found'
    return struct.unpack_from('<64f', xbe, rc_at), xbe[books_at:books_at + 256], xbe[books_at + 256:books_at + 512]


class Bits:
    """Least significant bit first. As in the game (0x445db3), it refills after each read so that it
    always holds 8 to 15 bits, which leaves the byte after a frame already loaded."""

    def __init__(self, data):
        self.d, self.p = data, 0
        self.load()

    def byte(self, at):
        return self.d[at] if at < len(self.d) else 0

    def load(self):
        self.v, self.n = self.byte(self.p), 8
        self.p += 1

    def read(self, count):
        out = self.v & ((1 << count) - 1)
        self.v >>= count
        self.n -= count
        if self.n < 8:
            self.v |= self.byte(self.p) << self.n
            self.p += 1
            self.n += 8
        return out


class Decoder:
    def __init__(self, rc_table, book_normal, book_large):
        self.rc_table, self.books = rc_table, (book_normal, book_large)
        self.rc, self.history = [0.0] * 12, [0.0] * 12
        self.buf = [0.0] * 756     # 324 samples of pitch memory, then the 432-sample frame
        self.gains, self.reduced, self.thresh, self.raw_next = None, 0, 0, False

    def header(self, b):
        self.reduced = b.read(1)
        self.thresh = 32 - b.read(4)
        gain = 8.0 * (1 + b.read(4))
        step = 1.04 + b.read(6) * 0.001
        self.gains = [gain * step ** i for i in range(64)]

    def excitation(self, b, multipulse, out, at, stride):
        i = 0
        if not multipulse:
            while i < 108:
                out[at + i] = 0.0 if not b.read(1) else (-2.0 if not b.read(1) else 2.0)
                i += stride
            return
        model = N
        while i < 108:
            cmd = self.books[model][b.v & 0xff]
            model, size, pulse = COMMANDS[cmd]
            b.read(size)
            if cmd > 3:
                out[at + i] = pulse
                i += stride
            elif cmd > 1:
                count = 7 + b.read(6)
                if i + count * stride > 108:
                    count = (108 - i) // stride
                for _ in range(count):
                    out[at + i] = 0.0
                    i += stride
            else:
                x = 7
                while b.read(1):
                    x += 1
                out[at + i] = float(x if b.read(1) else -x)
                i += stride

    def synthesise(self, offset, blocks):
        lpc, tmp1, tmp2 = [0.0] * 12, [0.0] * 12, [0.0] * 12
        for i in range(10, -1, -1):
            tmp2[1 + i] = self.rc[i]
        tmp2[0] = 1.0
        for i in range(12):
            x = -(self.rc[11] * tmp2[11])
            for j in range(10, -1, -1):
                x -= self.rc[j] * tmp2[j]
                tmp2[j + 1] = x * self.rc[j] + tmp2[j]
            tmp1[i] = tmp2[0] = x
            for j in range(i):
                x -= tmp1[i - 1 - j] * lpc[j]
            lpc[i] = x
        at, h = 324 + offset, self.history
        for _ in range(blocks):
            for j in range(12):
                x = self.buf[at]
                for k in range(j):
                    x += lpc[k] * h[k - j + 12]
                for k in range(j, 12):
                    x += lpc[k] * h[k - j]
                h[11 - j] = x
                self.buf[at] = x
                at += 1

    def frame(self, b):
        multipulse = False
        delta = [0.0] * 12
        for i in range(12):
            if i < 4:
                idx = b.read(6)
                if i == 0 and idx < self.thresh:
                    multipulse = True
            else:
                idx = 16 + b.read(5)
            delta[i] = (self.rc_table[idx] - self.rc[i]) * 0.25
        for sub in range(4):
            lag = b.read(8)
            pitch = b.read(4) / 15.0
            fixed = self.gains[b.read(6)]
            ex = [0.0] * 118
            if not self.reduced:
                self.excitation(b, multipulse, ex, 5, 1)
            else:
                align = b.read(1)
                zero = b.read(1)
                self.excitation(b, multipulse, ex, 5 + align, 2)
                base = 5 + (1 - align)
                for j in range(0, 108, 2):
                    ex[base + j] = 0.0
                if not zero:
                    for j in range(0, 108, 2):
                        k = base + j
                        ex[k] = (TAPS[0] * (ex[k - 5] + ex[k + 5]) + TAPS[1] * (ex[k - 3] + ex[k + 3]) +
                                 TAPS[2] * (ex[k - 1] + ex[k + 1]))
                    fixed *= 0.5
            for j in range(108):
                back = 108 * sub + 216 - lag + j
                # A long lag early in a frame reads the state stored just before the pitch memory.
                old = self.buf[back] if back >= 0 else (self.gains + self.rc + self.history)[back]
                self.buf[324 + 108 * sub + j] = fixed * ex[5 + j] + pitch * old
        return delta

    def decode(self, b):
        """One frame, then what follows it (0x446f90): the last byte loaded is a marker, 0xee meaning
        that the next frame is followed by raw samples, and the next frame starts on the byte after."""
        delta = self.frame(b)
        self.buf[:324] = self.buf[432:756]     # pitch memory keeps the excitation, not the filtered output
        for i in range(3):
            for j in range(12):
                self.rc[j] += delta[j]
            self.synthesise(12 * i, 1)
        for j in range(12):
            self.rc[j] += delta[j]
        self.synthesise(36, 33)
        at = b.p - 1
        if self.raw_next:
            start, count = struct.unpack_from('>hh', b.d, at)
            for k in range(count):
                self.buf[324 + start + k] = float(struct.unpack_from('>h', b.d, at + 4 + 2 * k)[0])
            at += 4 + 2 * count
            b.p = at + 1
            self.raw_next = False
        self.raw_next = b.byte(at) == 0xee
        b.load()
        return self.buf[324:756]


def decode_stream(blob, rc_table, normal, large):
    """Return (samples, stated length, most bytes left over in a block).

    A block: u32 sample count (big-endian in GSTR streams, little-endian in PT ones), u32, a byte,
    a marker byte as above, then frames. The stream's first block starts with the header."""
    d = Decoder(rc_table, normal, large)
    p, pcm, stated, worst = 0, [], None, 0
    while p + 8 <= len(blob):
        tag, size = blob[p:p + 4], struct.unpack_from('<I', blob, p + 4)[0]
        if tag == b'SCHl':
            h = blob[p + 8:p + size]
            at = h.find(bytes([0xfd, 0x80, 0x01, 0x03, 0x85]))
            if at >= 0:
                n = h[at + 5]
                stated = int.from_bytes(h[at + 6:at + 6 + n], 'big')
        elif tag == b'SCDl':
            count = min(struct.unpack_from('>I', blob, p + 8)[0], struct.unpack_from('<I', blob, p + 8)[0])
            d.raw_next = blob[p + 17] == 0xee
            b = Bits(blob[p + 18:p + size])
            if d.gains is None:
                d.header(b)
            for _ in range((count + 431) // 432):
                pcm.extend(d.decode(b))
            worst = max(worst, abs(len(b.d) - (b.p - 1)))
        elif tag == b'SCEl':
            break
        p += size
    return (pcm[:stated] if stated else pcm), stated, worst


def loudness(samples):
    """Peak, and RMS of the 10 ms windows within 30 dB of the loudest, so pauses don't count."""
    import math
    win = 360
    levels = [sum(x * x for x in samples[i:i + win]) / win for i in range(0, len(samples) - win, win)] or [0.0]
    top = max(levels) or 1.0
    active = [v for v in levels if v > top / 1000]
    rms = math.sqrt(sum(active) / len(active)) if active else 0.0
    return max((abs(x) for x in samples), default=0.0), rms, len(active) * win / 36000


def main(game, out, extra=None):
    xbe = open(os.path.join(game, 'default.xbe'), 'rb').read()
    rc_table, normal, large = tables(xbe)
    spch = open(os.path.join(game, 'data', 'SPCHDATA.dat'), 'rb').read()
    data_at, entries = terf_entries(spch)

    clips = extra or [
        (0x2a56 + 30, 0x1185 + 30, 'washington_city'),     # bank 0x1f0, Al's city names (first image)
        (0x1e37 + 1351, 0x566 + 1351, 'washington_surname'),   # bank 0x00a, player surnames (second image)
        (0x2ac8 + 31, 0x11f7 + 31, 'washington_project2_city'),
        (0x2af6 + 858, 0x1225 + 858, 'washington_project2_surname'),
        (0x3433 + 31, 0x1b62 + 31, 'washington_project1_city'),
        (0x29cb + 8, 0x10fa + 8, 'compare_cowboys'),
        (0x29cb + 31, 0x10fa + 31, 'compare_redskins'),
        (0x2a56 + 8, 0x1185 + 8, 'compare_dallas_city'),
    ]
    os.makedirs(out, exist_ok=True)
    print(f'{"file":44} {"sec":>5} {"peak":>6} {"rms":>6} {"dB":>6} {"left":>4}')
    for desc_i, audio_i, label in clips:
        o, s = entries[desc_i]
        desc = spch[data_at + o:data_at + o + s]
        bank, sub, kind, count = struct.unpack_from('<HHBB', desc)
        total = struct.unpack_from('<I', desc, 8)[0]
        rows = [(struct.unpack_from('>H', desc, 12 + (2 + kind) * k)[0], tuple(desc[14 + (2 + kind) * k:12 + (2 + kind) * (k + 1)]))
                for k in range(count)]
        ao = data_at + entries[audio_i][0]
        for k, (offset, pars) in enumerate(rows):
            end = rows[k + 1][0] if k + 1 < count else total
            pcm, stated, worst = decode_stream(spch[ao + offset * 256:ao + end * 256], rc_table, normal, large)
            name = f'{label}_{k}_{"-".join(map(str, pars))}.wav'
            with wave.open(os.path.join(out, name), 'wb') as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(36000)
                w.writeframes(b''.join(struct.pack('<h', max(-32768, min(32767, round(x)))) for x in pcm))
            peak, rms, active = loudness(pcm)
            import math
            db = 20 * math.log10(rms / 32768) if rms else -99.0
            print(f'{name:44} {len(pcm) / 36000:5.2f} {peak:6.0f} {rms:6.0f} {db:6.1f} {worst:4d}  samples {len(pcm)} stated {stated}')


if __name__ == '__main__':
    args = sys.argv[1:]
    extra = None
    if '--entry' in args:
        i = args.index('--entry')
        extra = [(int(args[i + 1], 0), int(args[i + 2], 0), args[i + 3])]
        del args[i:i + 4]
    if len(args) != 2:
        sys.exit(__doc__)
    main(args[0], args[1], extra)
