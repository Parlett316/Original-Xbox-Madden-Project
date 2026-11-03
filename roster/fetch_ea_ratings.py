"""Download Madden player ratings from EA's ratings site into one JSON file.

Usage: python fetch_ea_ratings.py OUT.json [ITERATION]

Uses the site's Next.js page-data route (100 players per page), which carries
team and position; the bare drop-api endpoint leaves those null.
"""
import json, re, sys, time, urllib.request

SITE = 'https://www.ea.com'
UA = {'User-Agent': 'Mozilla/5.0'}


def get(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode('utf8')


def build_id():
    html = get(SITE + '/games/madden-nfl/ratings')
    return re.search(r'"buildId":"([^"]+)"', html).group(1)


def main(out, iteration=None):
    bid = build_id()
    items, page, total = [], 1, None
    while total is None or len(items) < total:
        url = f'{SITE}/_next/data/{bid}/games/madden-nfl/ratings.json?franchiseSlug=madden-nfl&page={page}'
        if iteration:
            url += '&iteration=' + iteration
        r = json.loads(get(url))['pageProps']['ratingDetails']
        total = r['totalItems']
        if not r['items']:
            break
        items += r['items']
        print(f'page {page}: {len(items)}/{total}', flush=True)
        page += 1
        time.sleep(1.0)
    seen = {}
    for it in items:
        seen.setdefault(it['id'], it)
    json.dump({'iteration': items[0]['iteration'] if items else None,
               'totalItems': total, 'items': list(seen.values())},
              open(out, 'w', encoding='utf8'), ensure_ascii=False)
    print(f'saved {len(seen)} unique players to {out}')


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
