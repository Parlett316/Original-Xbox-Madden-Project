"""Put custom players (name, size, skin, photo) into existing roster slots.

    python custom_players.py <spec.json> <DB_TEAMS.dat> <uis_plyr.dat> <out dir>

spec.json (personal, never committed; roster/*.json is ignored):
    {"players": [{"team": "63 Bears", "pos": "RT", "number": 81,
                  "first": "Dylan", "last": "Feltz", "height": 78, "weight": 300,
                  "skin": 0, "photo": "C:/path/face.jpg", "psxp": 2692,
                  "crop": [10, 2, 194, 186]}]}

A player is found by team name (TEAM.TDNA), position and jersey number and
must be unique. height is inches, weight pounds (stored as PWGT + 160),
skin is PSKI (0 light .. 2 dark). The photo is cropped (optional box, else
the centre square) to 09's 66x66 headshot and written to uis_plyr.dat entry
psxp + 1. Use a psxp that no player references: 1856-2692 held 2008-roster
photos the current roster doesn't use (only a 2008 roster save would show
them); 2693+ are the game's generic faces and hair overlays, so keep out.
Writes <out dir>/DB_TEAMS.dat and uis_plyr.dat; re-sync fe.qkl and game.qkl
afterwards, since both preload part of uis_plyr.dat.
"""
import json
import os
import sys

from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'tools'))
from db_survey import find_dbs  # noqa: E402
import headshots  # noqa: E402

GAME_POS = ['QB', 'HB', 'FB', 'WR', 'TE', 'LT', 'LG', 'C', 'RG', 'RT', 'LE', 'RE', 'DT',
            'LOLB', 'MLB', 'ROLB', 'CB', 'FS', 'SS', 'K', 'P']
GENERIC_FACES = 2693                    # first psxp of the generic-face pool


def photo(path, crop=None):
    im = Image.open(path).convert('RGBA')
    if crop is None:
        side = min(im.size)
        x, y = (im.width - side) // 2, (im.height - side) // 2
        crop = (x, y, x + side, y + side)
    return im.crop(tuple(crop)).resize((headshots.PHOTO, headshots.PHOTO), Image.LANCZOS)


def main(spec_path, teams_path, plyr_path, out_dir):
    spec = json.load(open(spec_path, encoding='utf8'))['players']
    teams = bytearray(open(teams_path, 'rb').read())
    plyr = bytearray(open(plyr_path, 'rb').read())
    data_at, entries = headshots.terf_entries(plyr)
    dbs = list(find_dbs(teams))
    used = {db['PLAY'].get(i, 'PSXP') for db in dbs if 'PLAY' in db.tables for i in range(db['PLAY'].count)}
    for p in spec:
        hits = [(db, i) for db in dbs if 'TEAM' in db.tables and db['TEAM'].count
                and db['TEAM'].row(0)['TDNA'] == p['team'] and 'PLAY' in db.tables
                for i in range(db['PLAY'].count)
                if GAME_POS[db['PLAY'].get(i, 'PPOS')] == p['pos'] and db['PLAY'].get(i, 'PJEN') == p['number']]
        assert len(hits) == 1, f"{p['team']} {p['pos']} #{p['number']}: {len(hits)} matches"
        db, i = hits[0]
        t = db['PLAY']
        psxp = p['psxp']
        assert 0 < psxp < GENERIC_FACES and (psxp not in used or t.get(i, 'PSXP') == psxp), \
            f'psxp {psxp} is in use or in the generic-face pool'
        for field, value in (('PFNA', p['first']), ('PLNA', p['last']), ('PHGT', p['height']),
                             ('PWGT', p['weight'] - 160), ('PSKI', p['skin']), ('PSXP', psxp)):
            t.set(i, field, value)
        db.fix()
        assert db.verify()
        o, s = entries[psxp + 1]
        a = data_at + o
        plyr[a:a + s] = headshots.encode(plyr[a:a + s], photo(p['photo'], p.get('crop')))
        used.add(psxp)
        print(f"{p['team']} {p['pos']} #{p['number']}: {p['first']} {p['last']}, "
              f"{p['height'] // 12}'{p['height'] % 12}\" {p['weight']} lb, photo entry {psxp + 1}")
    os.makedirs(out_dir, exist_ok=True)
    open(os.path.join(out_dir, 'DB_TEAMS.dat'), 'wb').write(teams)
    open(os.path.join(out_dir, 'uis_plyr.dat'), 'wb').write(plyr)


if __name__ == '__main__':
    if len(sys.argv) != 5:
        sys.exit(__doc__)
    main(*sys.argv[1:])
