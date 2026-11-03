"""Download headshots of the 2026 coaching staffs (coaches.STAFF) from the team sites.

Usage: python fetch_coach_photos.py OUT_DIR
Saves OUT_DIR/<TGID>_<COPS>.jpg (512x512, cropped to the face by the NFL's
image CDN); skips files already present and lists any coach it can't find.
Every team site has a /team/coaches-roster/ (or /team/coaches/) page of cards:
<img ... src= or data-src=".../image/{upload|private}/.../<team>/<id>.jpg">
followed by <h3 ...title">Name</h3>.
"""
import html, os, re, sys, time, unicodedata, urllib.request

from coaches import STAFF

SITES = {1: 'chicagobears.com', 2: 'bengals.com', 3: 'buffalobills.com', 4: 'denverbroncos.com',
         5: 'clevelandbrowns.com', 6: 'buccaneers.com', 7: 'azcardinals.com', 8: 'chargers.com',
         9: 'chiefs.com', 10: 'colts.com', 11: 'dallascowboys.com', 12: 'miamidolphins.com',
         13: 'philadelphiaeagles.com', 14: 'atlantafalcons.com', 15: '49ers.com', 16: 'giants.com',
         17: 'jaguars.com', 18: 'newyorkjets.com', 19: 'detroitlions.com', 20: 'packers.com',
         21: 'panthers.com', 22: 'patriots.com', 23: 'raiders.com', 24: 'therams.com',
         25: 'baltimoreravens.com', 26: 'commanders.com', 27: 'neworleanssaints.com',
         28: 'seahawks.com', 29: 'steelers.com', 30: 'tennesseetitans.com', 31: 'vikings.com',
         32: 'houstontexans.com'}
CDN = 'https://static.clubs.nfl.com/image/{}/c_fill,g_face,w_512,h_512/{}'
CARD = re.compile(r'<img [^>]*?(?:data-src|src)="https://static\.clubs\.nfl\.com/image/(upload|private)/'
                  r'(?:[^"/]*/)*?(?:v\d+/)?([a-z0-9_]+/[^"/]+?)(?:\.\w+)?"[^>]*>(?:(?!<img ).)*?'
                  r'<h3 class="d3-o-media-object__title">([^<]+)</h3>', re.S)


def get(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def key(name):
    s = unicodedata.normalize('NFKD', html.unescape(name)).encode('ascii', 'ignore').decode().lower()
    s = re.sub(r'\b(jr|sr|ii|iii)\b\.?', '', s)
    return re.sub(r'[^a-z ]', '', s).split()


def find(cards, full):
    """The card for `full`: the exact name, else the same first and last name, else the only
    card with that last name (Tampa has both Todd Bowles and Todd Bowles Jr.)."""
    exact_name = [c for c in cards if html.unescape(c[2]).strip() == full]
    if len(exact_name) == 1:
        return exact_name[0]
    want = key(full)
    same = [c for c in cards if key(c[2])[-1:] == want[-1:]]
    exact = [c for c in same if key(c[2])[:1] == want[:1]]
    return (exact or same)[0] if len(exact) == 1 or len(same) == 1 else None


def main(out):
    os.makedirs(out, exist_ok=True)
    missing = []
    for tid, staff in STAFF.items():
        todo = [(r, n) for r, n in enumerate(staff) if n and not os.path.exists(os.path.join(out, f'{tid}_{r}.jpg'))]
        if not todo:
            continue
        cards = []
        for path in ('team/coaches-roster/', 'team/coaches/'):
            try:
                cards = CARD.findall(get(f'https://www.{SITES[tid]}/{path}').decode('utf8', 'replace'))
            except urllib.error.HTTPError:
                continue
            if cards:
                break
        for role, full in todo:
            c = find(cards, full)
            if not c:
                missing.append(f'{tid} {SITES[tid]} {full}')
                continue
            open(os.path.join(out, f'{tid}_{role}.jpg'), 'wb').write(get(CDN.format(c[0], c[1])))
            print(f'{tid}_{role} {full} <- {html.unescape(c[2]).strip()}', flush=True)
            time.sleep(0.2)
    print('missing:' if missing else 'all found', *missing, sep='\n  ')


if __name__ == '__main__':
    main(sys.argv[1])
