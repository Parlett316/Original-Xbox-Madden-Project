"""Look up birth dates and NFL head-coaching records for the 2026 staffs (coaches.STAFF).

Usage: python fetch_coach_facts.py OUT.json [SEASON]
SEASON (default 2026) is the season the roster starts in; records count the
seasons before it. Writes {name: {"born": "YYYY-MM-DD" | null, "record": {...} | null}}
for review before it's copied into coaches.py.

  - Records of the current head coaches: ESPN's core API (the season's team
    coach lists give their ids; ESPN returns today's coach for past seasons,
    so former head coaches can't be found this way). Per season, the regular-
    season and postseason records give W-L-T, playoff W-L, winning seasons
    and playoff appearances (a season's playoffs are filed under the next year).
  - Records of former head coaches (FORMER_HC, now coordinators): the
    season rows of the "Head coaching record" table in their Wikipedia
    article, cross-checked against the infobox totals.
  - Super Bowls aren't derivable from a W-L line, so coaches.py lists them.
  - Birth dates: Wikidata (P569), via the English Wikipedia article
    "<name> (American football)" or "<name>", accepted only if its Wikidata
    description mentions football.
"""
import concurrent.futures as cf, json, re, sys, time, urllib.parse, urllib.request

from coaches import STAFF

ESPN = 'http://sports.core.api.espn.com/v2/sports/football/leagues/nfl'
TEAMS = list(range(1, 31)) + [33, 34]
FIRST = 1990
# Coordinators with an NFL head-coaching record (interim stints included)
FORMER_HC = ['Vic Fangio', 'Matt Nagy', 'Frank Reich', 'Brian Daboll', 'Brian Flores', 'Jonathan Gannon',
             'Raheem Morris', 'Brandon Staley', 'Steve Spagnuolo', 'Mike McDaniel', 'Nathaniel Hackett',
             'Gus Bradley', 'Vance Joseph', 'Dennis Allen', 'Josh McDaniels', 'Jeff Ulbrich', 'Darren Rizzi',
             'John Fassel']
TITLES = {'Pete Carmichael': 'Pete Carmichael Jr.'}   # the plain title is his father


def get(url, tries=3):
    for k in range(tries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (madden09 roster tool)'})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            time.sleep(1 + k)
        except Exception:
            time.sleep(1 + k)
    return None


def key(name):
    return re.sub(r'[^a-z ]', '', name.lower().replace('jr.', '').replace(' sr.', '')).split()


def coach_ids(last):
    """{(first, last) lowercase: ESPN coach id} for the coaches the team lists return."""
    def season_team(st):
        d = get(f'{ESPN}/seasons/{st[0]}/teams/{st[1]}/coaches')
        return [i['$ref'] for i in (d or {}).get('items', [])]
    refs = set()
    with cf.ThreadPoolExecutor(12) as ex:
        for r in ex.map(season_team, [(s, t) for s in range(FIRST, last + 1) for t in TEAMS]):
            refs.update(re.search(r'coaches/(\d+)', x).group(1) for x in r)
    ids = {}
    with cf.ThreadPoolExecutor(12) as ex:
        for cid, d in zip(refs, ex.map(lambda c: get(f'{ESPN}/coaches/{c}'), refs)):
            if d:
                ids[tuple(key(f"{d['firstName']} {d['lastName']}"))] = cid
    return ids


def record(cid, season):
    d = get(f'{ESPN}/coaches/{cid}')
    years = sorted({int(re.search(r'seasons/(\d+)', s['$ref']).group(1)) for s in d.get('coachSeasons', [])})
    rec = dict(w=0, l=0, t=0, pw=0, pl=0, winning=0, playoffs=0, seasons=0)
    for y in years:
        if y >= season:
            continue
        reg = get(f'{ESPN}/seasons/{y}/types/2/coaches/{cid}/record')
        # ESPN files a season's playoffs under the next year (the calendar year they're played):
        # its "2024" postseason for Reid is 4-0, the 2023 season's Super Bowl run
        post = get(f'{ESPN}/seasons/{y + 1}/types/3/coaches/{cid}/record')
        st = lambda d: {s['name']: int(s['value']) for s in (d or {}).get('stats', [])}
        r, p = st(reg), st(post)
        if r:
            rec['seasons'] += 1
            rec['w'] += r['wins']; rec['l'] += r['losses']; rec['t'] += r['ties']
            rec['winning'] += r['wins'] > r['losses']
        if p and p['wins'] + p['losses']:
            rec['pw'] += p['wins']; rec['pl'] += p['losses']; rec['playoffs'] += 1
    return rec


def wiki(title, what):
    q = urllib.parse.urlencode(dict(action='query', prop=what, titles=title, redirects=1, format='json',
                                    formatversion=2, rvprop='content', rvslots='main'))
    for k in range(4):
        d = get(f'https://en.wikipedia.org/w/api.php?{q}')
        if d and 'query' in d:
            return d['query']['pages'][0]
        time.sleep(5 + 10 * k)
    raise RuntimeError(f'Wikipedia lookup failed: {title}')


def titles(name):
    return [TITLES[name]] if name in TITLES else         [f'{name} (American football)', f'{name} (American football coach)', name]


def born(name):
    for title in titles(name):
        qid = wiki(title, 'pageprops').get('pageprops', {}).get('wikibase_item')
        if not qid:
            continue
        e = get(f'https://www.wikidata.org/wiki/Special:EntityData/{qid}.json')['entities'][qid]
        desc = e.get('descriptions', {}).get('en', {}).get('value', '')
        claims = e.get('claims', {}).get('P569')
        if 'football' in desc.lower() and claims:
            return claims[0]['mainsnak']['datavalue']['value']['time'][1:11], desc
        time.sleep(0.5)
    return None, None


def wiki_record(name, season):
    """NFL head-coaching record before `season` from the article's "Head coaching record" table:
    a row header '![[2019 Denver Broncos season|DEN]] || [[2019 NFL season|2019]]' followed by
    '| W || L || T || {{winpct}} || finish || PW || PL || ...' (dashes when no playoffs)."""
    for title in titles(name):
        page = wiki(title, 'revisions')
        text = page['revisions'][0]['slots']['main']['content'] if 'revisions' in page else ''
        if 'oaching record' in text:
            break
    box = re.search(r'(?:regular_record|coachregrecord)\s*=\s*\{\{[Ww]inning percentage\|(\d+)\|(\d+)', text)
    at = text.find('oaching record')          # only that section: player stat tables also link seasons
    text = text[at:text.find('\n|}', at)] if at >= 0 else ''
    rec = dict(w=0, l=0, t=0, pw=0, pl=0, winning=0, playoffs=0, seasons=0)
    year = None
    for line in text.splitlines():
        m = re.match(r'!.*\[\[(\d{4}) NFL season', line)
        if m:
            year = int(m.group(1))
            continue
        if year is None or not line.startswith('|') or line.startswith('|-') or line.startswith('|}'):
            year = None if line.startswith('|}') else year
            continue
        # some tables give the record as one {{WinLossPct|W|L|T}} cell
        line = re.sub(r'\{\{WinLossPct\|(\d+)\|(\d+)(?:\|(\d+))?\}\}',
                      lambda m: f'{m[1]} || {m[2]} || {m[3] or 0} || pct', line)
        cells = [c.strip() for c in line.lstrip('|').split('||')]
        if year < season and len(cells) >= 7 and all(re.fullmatch(r'\d+', c) for c in cells[:3]):
            w, l, t = map(int, cells[:3])
            rec['seasons'] += 1
            rec['w'] += w; rec['l'] += l; rec['t'] += t
            rec['winning'] += w > l
            if all(re.fullmatch(r'\d+', c) for c in cells[5:7]) and int(cells[5]) + int(cells[6]):
                rec['pw'] += int(cells[5]); rec['pl'] += int(cells[6]); rec['playoffs'] += 1
        year = None
    rec['infobox'] = f'{box.group(1)}-{box.group(2)}' if box else None
    return rec


def main(out, season=2026):
    names = [n for staff in STAFF.values() for n in staff if n]
    ids = coach_ids(season - 1)
    facts = {}
    for n in names:
        b, desc = born(n)
        cid = ids.get(tuple(key(n)))
        rec = record(cid, season) if cid else wiki_record(n, season) if n in FORMER_HC else None
        facts[n] = dict(born=b, wikidata=desc, espn=cid, record=rec)
        print(n, b, cid, rec, flush=True)
        time.sleep(0.5)
    json.dump(facts, open(out, 'w', encoding='utf8'), indent=1)


if __name__ == '__main__':
    main(sys.argv[1], *map(int, sys.argv[2:]))
