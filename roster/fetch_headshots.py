"""Download EA ratings-site headshots (512x512 PNG) for every player in a ratings JSON.

Usage: python fetch_headshots.py RATINGS.json OUT_DIR
Saves OUT_DIR/<ea player id>.png; skips files already present.
"""
import json, os, sys, time, urllib.request


def main(src, out):
    os.makedirs(out, exist_ok=True)
    items = json.load(open(src, encoding='utf8'))['items']
    done = have = none = failed = 0
    for it in items:
        url = it.get('avatarUrl')
        if not url:
            none += 1
            continue
        path = os.path.join(out, f"{it['id']}.png")
        if os.path.exists(path):
            have += 1
            continue
        req = urllib.request.Request(url.split('?')[0], headers={'User-Agent': 'Mozilla/5.0'})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read()
            open(path, 'wb').write(data)
            done += 1
            if done % 200 == 0:
                print(f'{done} photos downloaded', flush=True)
        except urllib.error.HTTPError as e:
            if e.code in (403, 404):    # EA's image host answers 403 for a portrait it doesn't have
                none += 1
            else:
                failed += 1
                print('fail', it['id'], e, flush=True)
        except Exception as e:
            failed += 1
            print('fail', it['id'], e, flush=True)
        time.sleep(0.2)
    print(f'downloaded {done} photos ({have} already here); {none} players have no photo on EA\'s site '
          'and get the game\'s generic face' + (f'; {failed} failed, run again to retry them' if failed else ''))


if __name__ == '__main__':
    main(*sys.argv[1:3])
