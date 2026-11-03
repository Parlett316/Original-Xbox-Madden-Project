"""Download EA ratings-site headshots (512x512 PNG) for every player in a ratings JSON.

Usage: python fetch_headshots.py RATINGS.json OUT_DIR
Saves OUT_DIR/<ea player id>.png; skips files already present.
"""
import json, os, sys, time, urllib.request


def main(src, out):
    os.makedirs(out, exist_ok=True)
    items = json.load(open(src, encoding='utf8'))['items']
    done = 0
    for it in items:
        url = it.get('avatarUrl')
        if not url:
            continue
        path = os.path.join(out, f"{it['id']}.png")
        if os.path.exists(path):
            continue
        req = urllib.request.Request(url.split('?')[0], headers={'User-Agent': 'Mozilla/5.0'})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read()
            open(path, 'wb').write(data)
            done += 1
        except Exception as e:
            print('fail', it['id'], e, flush=True)
        if done % 200 == 0:
            print(done, flush=True)
        time.sleep(0.2)
    print('downloaded', done)


if __name__ == '__main__':
    main(*sys.argv[1:3])
