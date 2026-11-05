"""Pick extra free agents for the modern roster from an older EA ratings file.

    python pick_free_agents.py <older ratings.json> <current ratings.json> <out.csv>

Also writes <out>.json next to the CSV, for build_roster.py --free-agents.

EA's ratings site lists only rostered players, so a new franchise starts with no
kickers, punters or fullbacks in free agency. A player in the older file but not the
current one (matched by EA id, then by name, then by birthdate and surname) is probably
unsigned or retired. TARGETS says how many to take per position, best overall first.
QUOTA_FROM fills a position from another one when it runs out, using the rating that
matters there. Review the CSV: the data doesn't say who has retired, so players aged
RETIRE_AGE or more are flagged.

The franchise's PLAY table grows every season and has a fixed size, so keep the list
short (docs/roadmap.md).
"""
import collections
import csv
import json
import sys

# EA position: how many to take.
TARGETS = {'K': 8, 'P': 5, 'FB': 2, 'SAM': 7, 'MIKE': 10, 'WILL': 8, 'LT': 6, 'LG': 5, 'C': 5,
           'RG': 6, 'RT': 7, 'LEDG': 4, 'REDG': 4, 'FS': 4, 'SS': 4, 'HB': 4, 'LS': 1}
# Plays at: (how many, EA position to take from, rating that fits the new position).
QUOTA_FROM = {'FB': (4, 'TE', 'runBlock'), 'SAM': (3, 'WILL', 'overallRating'), 'LG': (3, 'RG', 'overallRating')}
RETIRE_AGE = 34
OVERALL_CAP = 80        # free agency is depth, not instant stars
# Older players lose speed and strength but keep their awareness. Madden 09 has no man or
# zone coverage rating, so slower feet are what reduces coverage. Kickers and punters are left alone.
AGING_FROM = 32
AGING_RATINGS = {'speed': 1, 'agility': 1, 'changeOfDirection': 1, 'strength': 1, 'acceleration': 0.8}
AGING_EXEMPT = {'K', 'P', 'LS'}


def aged(p):
    """EA-scale ratings to replace: 4 points at age 32 and 2 more per year after that."""
    if p['age'] < AGING_FROM or pos(p) in AGING_EXEMPT:
        return {}
    drop = 4 + 2 * (p['age'] - AGING_FROM)
    return {k: stat(p, k) - round(drop * share) for k, share in AGING_RATINGS.items()}
RETIRED = {
    'Adam Thielen', 'Ahkello Witherspoon', 'Andrus Peat', 'Anthony Walker Jr', 'Bradley Bozeman',
    'Brandon Graham', 'Bryce Huff', 'C.J. Ham', 'D.J. Davidson', 'Dan Skipper',
    'Dane Jackson', 'Darious Williams', 'Drew Dalman', 'Hakeem Adeniji', "Ja'Lynn Polk",
    'Jaire Alexander', 'Joe Tryon-Shoyinka', 'Joel Bitonio', 'Kaleb McGary', 'Kendall Lamm',
    'LaBryan Ray', 'Lane Johnson', 'Lavonte David', 'Logan Wilson', 'Markees Watts',
    'Nick Bellore', 'Nick Chubb', 'Philip Rivers', 'Reuben Lowery III', 'Rob Havenstein',
    'Russell Wilson', 'Ryan Kelly', 'Sam Webb', 'Teddy Bridgewater', 'Travis Vokolek',
    'Trent Taylor', 'Trystan Colon', 'Will Clapp', 'Yosh Nijman',
}  # checked 2026-11-05: nflverse 2026 rosters, Wikipedia's 2026 season page, news; incomplete


def load(path):
    with open(path, encoding='utf8') as f:
        return json.load(f)['items']


def pos(p):
    return p['position']['id']


def name(p):
    return f"{p['firstName']} {p['lastName']}"


def gone(older, current):
    """Older players with no match in the current file."""
    ids = {p['id'] for p in current}
    names = {name(p).lower() for p in current}
    born = {(p.get('birthdate'), p['lastName'].split()[0].lower()) for p in current}
    return [p for p in older if p['id'] not in ids and name(p).lower() not in names
            and (p.get('birthdate'), p['lastName'].split()[0].lower()) not in born]


def stat(p, key):
    if key == 'overallRating':
        return p[key]
    v = p['stats'][key]
    return v['value'] if isinstance(v, dict) else v


def main(older_path, current_path, out):
    pool = [p for p in gone(load(older_path), load(current_path)) if name(p) not in RETIRED]
    by_pos = collections.defaultdict(list)
    for p in pool:
        by_pos[pos(p)].append(p)
    for v in by_pos.values():
        v.sort(key=lambda p: -p['overallRating'])
    rows, taken = [], set()

    def take(plays_at, players, n, note=''):
        for p in [q for q in players if q['id'] not in taken][:n]:
            taken.add(p['id'])
            rows.append(dict(plays_at=plays_at, ea_pos=pos(p), name=name(p), overall=min(p['overallRating'], OVERALL_CAP),
                             ea_overall=p['overallRating'], age=p['age'], check='age' if p['age'] >= RETIRE_AGE else '',
                             note=note, ea_id=p['id'], overrides=json.dumps(aged(p))))

    for ea_pos, n in TARGETS.items():
        take(ea_pos, by_pos[ea_pos], n)
    for plays_at, (n, source, key) in QUOTA_FROM.items():
        players = sorted((p for p in by_pos[source] if p['id'] not in taken), key=lambda p: -stat(p, key))
        take(plays_at, players, n, note=f'moved from {source}')
    with open(out, 'w', newline='', encoding='utf8') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    by_id = {p['id']: p for p in pool}
    items = []
    for r in rows:
        item = json.loads(json.dumps(by_id[r['ea_id']]))
        item['playsAt'] = r['plays_at']
        for k, v in json.loads(r['overrides']).items():
            item['stats'][k]['value'] = v
        items.append(item)
    with open(out.rsplit('.', 1)[0] + '.json', 'w', encoding='utf8') as f:
        json.dump({'items': items}, f)
    print(f'{len(pool)} candidates, {len(rows)} picked, {sum(r["check"] == "age" for r in rows)} to check for retirement')
    return rows


if __name__ == '__main__':
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    main(*sys.argv[1:])
