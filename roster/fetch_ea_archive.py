"""Download an archived Madden season (e.g. Madden 26) from EA's ratings API.

Usage: python fetch_ea_archive.py OUT.json ITERATION [TEAM_NAMES.json]

The archive API returns team and position as null, but it still filters on
them, so each player's team and position are rebuilt from one filtered
query per team and per position. TEAM_NAMES.json is any file written by
fetch_ea_ratings.py, used only to label the team ids.
"""
import json, sys, time, urllib.parse, urllib.request

API = 'https://drop-api.ea.com/rating/madden-nfl'
UA = {'User-Agent': 'Mozilla/5.0'}
POSITIONS = ['QB', 'HB', 'FB', 'WR', 'TE', 'LT', 'LG', 'C', 'RG', 'RT',
             'LEDG', 'REDG', 'DT', 'SAM', 'MIKE', 'WILL', 'CB', 'FS', 'SS',
             'K', 'P', 'LS']


def fetch_all(iteration, **filt):
    items, offset, total = [], 0, None
    while total is None or offset < total:
        q = dict(locale='en', limit=100, offset=offset, iteration=iteration, **filt)
        req = urllib.request.Request(API + '?' + urllib.parse.urlencode(q), headers=UA)
        with urllib.request.urlopen(req, timeout=60) as r:
            d = json.load(r)
        total = d['totalItems']
        if not d['items']:
            break
        items += d['items']
        offset += len(d['items'])
        time.sleep(0.5)
    return items


def main(out, iteration, names_file=None):
    names = {}
    if names_file:
        for it in json.load(open(names_file, encoding='utf8'))['items']:
            if it['team']:
                names[it['team']['id']] = it['team']['label']
    players = {it['id']: it for it in fetch_all(iteration)}
    print(f'{len(players)} players', flush=True)
    for tid in range(1, 33):
        ids = [it['id'] for it in fetch_all(iteration, team=tid)]
        for pid in ids:
            players[pid]['team'] = {'id': tid, 'label': names.get(tid)}
        print(f'team {tid} {names.get(tid)}: {len(ids)}', flush=True)
    for pos in POSITIONS:
        ids = [it['id'] for it in fetch_all(iteration, position=pos)]
        for pid in ids:
            players[pid]['position'] = {'id': pos}
        print(f'{pos}: {len(ids)}', flush=True)
    json.dump({'iteration': {'id': iteration}, 'totalItems': len(players),
               'items': list(players.values())},
              open(out, 'w', encoding='utf8'), ensure_ascii=False)
    print(f'saved {len(players)} players to {out}')


if __name__ == '__main__':
    main(*sys.argv[1:4])
