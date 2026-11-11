"""List the events, sentences and banks in a speech event file (an entry of SPCHFEDT.dat or SPCHDATA.dat).

Usage: python speech_events.py <speech .dat> <entry> [--slots]

Inputs are only read. Format (docs/findings.md sections 10 and 12): an 8-byte entry header, then
u32 project, u16, u16, u32 event count, u16, u16 and a u16 offset per event (4-byte units from the
entry's start). An event: u16 ID, u16, u16, u16 sentences, 00 64 00, u8 parameters, a u16 offset
per sentence (4-byte units from the event). A sentence: an 8-byte header whose third byte is
4 x the slot count, one byte per slot (its offset in 4-byte units from the sentence), then the
slots: u16 bank, u8 event parameter, u8 flag, u32 rule count and 8-byte rules.
The summary gives each sentence's banks in order; --slots adds the parameter, flag and rules.
"""
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'roster'))
from headshots import terf_entries  # noqa: E402


def events(blob):
    """Yield (event ID, parameter count, [sentence: [(bank, parameter, flag, [rule bytes])]])."""
    count = struct.unpack_from('<I', blob, 16)[0]
    for k in range(count):
        e = blob[struct.unpack_from('<H', blob, 24 + 2 * k)[0] * 4:]
        ident, _, _, n = struct.unpack_from('<4H', e)
        sentences = []
        for j in range(n):
            s = e[struct.unpack_from('<H', e, 12 + 2 * j)[0] * 4:]
            slots = []
            for i in range(s[2] // 4):
                at = s[8 + i] * 4
                bank, par, flag, rules = struct.unpack_from('<HBBI', s, at)
                assert rules < 64, 'not a slot'
                slots.append((bank, par, flag, [s[at + 8 + 8 * r:at + 16 + 8 * r] for r in range(rules)]))
            sentences.append(slots)
        yield ident, e[11], sentences


def main(path, entry, detail):
    f = open(path, 'rb').read()
    data_at, entries = terf_entries(f)
    o, s = entries[entry]
    for ident, pars, sentences in events(f[data_at + o:data_at + o + s]):
        print(f'event {ident:#x}: {pars} parameters, {len(sentences)} sentences')
        for j, slots in enumerate(sentences):
            if detail:
                print(f'  sentence {j}')
                for bank, par, flag, rules in slots:
                    print(f'    bank {bank:#06x} par {par} flag {flag}  ' + '  '.join(r.hex(' ', 4) for r in rules))
            else:
                print(f'  {j:2}: ' + ' '.join(f'{b:x}' for b, *_ in slots))


if __name__ == '__main__':
    a = [v for v in sys.argv[1:] if v != '--slots']
    if len(a) != 2:
        sys.exit(__doc__)
    main(a[0], int(a[1], 0), '--slots' in sys.argv)
