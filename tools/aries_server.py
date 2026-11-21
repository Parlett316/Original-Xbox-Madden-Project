"""A private lobby server for Madden 09's online mode (EA's "Aries" protocol), work in progress.

    python tools/aries_server.py <log> [--host <IP the Xbox reaches this PC at>] [--name <persona prefix>]
                                       [--bot]   # a fake player in USR.Madden, to test invites alone

The game opens a TCP connection to its directory server (port 30010), sends `@tic` and `@dir`,
and expects to be sent on to a lobby server (`ADDR`/`PORT`), where the login commands follow.
Every packet is a 12-byte header (4-char command, 4-byte code, 4-byte big-endian total length)
and a body of KEY=VALUE lines ending in a NUL. The XBE must be patched to skip Xbox Live and to
let XNet talk to a plain PC (docs/findings.md §14).

It answers the directory (`@dir`), the login (`auth` with one persona, `pers`), `sele`, the room
categories (`rcat`) and rooms (`+rom`, one room `USR.Madden`; joining and leaving with `move`,
creating with `room`; `+who`, `+usr`, `+pop` in the formats of breakin-in, a server for The Sims:
Bustin' Out), games (`gcre`, `gjoi`, `glea`, `gdel`, `gset`, `gsta`, with `+mgm`/`+ses`; untested),
the config files (`news`: the messenger's address and a locker URL), the rankings queries `cate`
and `slst` that lobby setup waits for, and pings every 15 s, because the client hangs up after the
`IDLE` time without traffic. Port 10899 is EA Messenger (`AUTH`, `EPGT`, `RGET`, `PSET`). Everything
else gets an empty reply of the same command. Each lobby connection gets its own persona (Player1,
Player2...). tools/online_test.py runs it with one or two xemu instances.
With these, two xemu instances reach the Lobby and meet in one room (2026-11-21).
"""
import os
import socket
import struct
import sys
import threading
import time

DIR_PORT = 30010
LOBBY_PORT = 10901
HTTP_PORT = 8080                 # nothing listens yet; named by LOCKER_SERVER
BUDDY_PORT = 10899                # EA Messenger (BuddyApi), named by BUDDY_SERVER/BUDDY_PORT in the news reply


def pack(cmd, body, code=0):
    data = (''.join('%s=%s\n' % kv for kv in body.items()) or '\n').encode('latin1') + b'\0'
    return cmd.encode('latin1') + struct.pack('>II', code, 12 + len(data)) + data


def unpack(buf):
    """Split complete packets off the front of buf; return (packets, rest)."""
    out = []
    while len(buf) >= 12:
        n = struct.unpack_from('>I', buf, 8)[0]
        if n < 12 or len(buf) < n:
            break
        cmd, code = buf[:4].decode('latin1'), struct.unpack_from('>I', buf, 4)[0]
        body = {}
        for line in buf[12:n].rstrip(b'\0').decode('latin1').split('\n'):
            if '=' in line:
                k, v = line.split('=', 1)
                body[k] = v
        out.append((cmd, code, body))
        buf = buf[n:]
    return out, buf


class Server:
    def __init__(self, log, host, name='Player'):
        self.log, self.host, self.name = open(log, 'a', buffering=1, encoding='latin1'), host, name
        self.users = {}                 # lobby connection -> user
        self.next_id = 1                # user ids (and Player<n> names) are never reused
        self.games = {}                 # game id -> game (gcre); a private game is an invite between two
        self.next_game = 1
        # Room names are '<category>.<name>' (0x4e1e3a, '%s.%s'); Create Room uses USR. The Lobby
        # screen's filter (0x4e0b1e) checks the other categories against skill level (LVL.), a
        # flag (HED.), clubs (CLB.) and contests (CNT.), so only user rooms are offered.
        self.rooms = [{'id': 1, 'name': 'USR.Madden', 'pass': ''}]

    def say(self, *a):
        line = time.strftime('%H:%M:%S ') + ' '.join(str(x) for x in a)
        self.log.write(line + '\n')
        print(line, flush=True)

    def reply(self, c, who, cmd, body, code=0):
        self.say(who, '<-', cmd, body)
        c.sendall(pack(cmd, body, code))

    def handle(self, c, addr, port):
        who = '%s:%d>%d' % (addr[0], addr[1], port)
        self.say(who, 'connect')
        buf = b''
        if port == LOBBY_PORT:          # the client drops the link after IDLE ms (pers reply) of silence
            threading.Thread(target=self.pinger, args=(c, who), daemon=True).start()
        try:
            while True:
                b = c.recv(65536)
                if not b:
                    break
                if (port == BUDDY_PORT and not buf) or b[:4] in (b'room', b'move'):
                    self.say(who, 'raw', b[:96].hex())
                buf += b
                pkts, buf = unpack(buf)
                for cmd, code, body in pkts:
                    if cmd != '~png':
                        self.say(who, '->', cmd, hex(code), body)
                    self.answer(c, who, cmd, body, port)
        except OSError as e:
            self.say(who, 'error', e)
        self.say(who, 'closed')
        u = self.users.pop(c, None)
        if u and u['room']:
            n = sum(1 for v in self.users.values() if v['room'] == u['room'])
            for v in self.users.values():
                self.push(v, '+pop', {'Z': '%d/%d' % (u['room'], n)})
        c.close()

    def answer(self, c, who, cmd, body, port=None):
        if cmd == '~png':               # the client's answer to our keepalive
            return
        if port == BUDDY_PORT:
            self.buddy(c, who, cmd, body)
            return
        if cmd == '@tic':
            return                      # no reply seen in other EA titles; the client goes on to @dir
        if cmd == '@dir':
            self.reply(c, who, '@dir', {'ADDR': self.host, 'PORT': LOBBY_PORT,
                                        'SESS': '1234567890', 'MASK': '0123456789abcdef0123456789abcdef'})
            return
        if c not in self.users:
            self.users[c] = {'id': self.next_id, 'conn': c, 'room': None, 'addr': c.getpeername()[0]}
            self.next_id += 1
        u = self.users[c]
        u.setdefault('name', '%s%d' % (self.name, u['id']))
        name = u['name']
        if cmd == 'addr':               # the box's own address as it sees it (behind NAT: 10.0.2.15)
            u['addr'] = body.get('ADDR', u['addr'])
            self.reply(c, who, cmd, {})
            return
        if cmd == 'mesg':               # chat and invites: forwarded as +msg (parser 0x4df53b)
            self.message(c, who, u, body)
            return
        if cmd in ('gcre', 'gjoi', 'glea', 'gdel', 'gset', 'gsta', 'gget'):
            self.game(c, who, u, cmd, body)
            return
        if cmd == 'auth':               # 0x545ec7: NAME, PERSONAS (one persona -> it sends pers)
            u['mac'] = body.get('MAC', '')
            self.reply(c, who, cmd, {'NAME': name, 'PERSONAS': name, 'TOSVER': '1', 'NUCLEUSMSG': '0',
                                     'MAIL': 'player@localhost', 'BORN': '19800101', 'GEND': 'M',
                                     'FROM': 'US', 'LANG': 'en', 'SPAM': 'NN', 'SINCE': '2008.1.1-00:00:00',
                                     'LAST': '2008.1.1-00:00:00', 'ADDR': u['addr'], 'TOS': '1'})
            for r in self.rooms:        # breakin-in sends the room list right after auth
                self.reply(c, who, '+rom', self.room_info(r))
            return
        if cmd == 'pers':
            self.reply(c, who, cmd, {'NAME': name, 'PERS': name, 'LKEY': '0' * 32,
                                     'LOC': 'enUS', 'A': u['addr'], 'LA': u['addr'],
                                     'IDLE': '50000', 'LAST': '2008.1.1-00:00:00',
                                     'PLAST': '2008.1.1-00:00:00', 'SINCE': '2008.1.1-00:00:00',
                                     'PSINCE': '2008.1.1-00:00:00'})
            self.reply(c, who, '+who', self.who_info(u))
            return
        if cmd == 'sele':
            self.reply(c, who, cmd, {'GAMES': '1', 'ROOMS': '1', 'USERS': '1', 'MESGS': '1', 'RANKS': '0',
                                     'MORE': '1', 'SLOTS': '36'})
            if body.get('ROOMS') == '1':
                for r in self.rooms:
                    self.reply(c, who, '+rom', self.room_info(r))
            return
        if cmd == 'room':               # create a room (NAME, PASS, DESC, LVLRNG) and move into it
            # The client (0x5427a4) reads IDENT from the reply and looks for the room by NAME in its
            # list (0x5426db), so the +rom has to come first (join() sends it before the reply).
            r = next((r for r in self.rooms if r['name'] == body.get('NAME')), None)
            if r is None:
                r = {'id': max([0] + [r['id'] for r in self.rooms]) + 1, 'name': body.get('NAME', ''),
                     'pass': body.get('PASS', ''), 'desc': body.get('DESC', ''), 'host': name}
                self.rooms.append(r)
            self.join(c, who, u, r, cmd)
            return
        if cmd == 'move':               # join a room by name; IDENT=0 and no NAME leaves the room
            r = next((r for r in self.rooms if r['name'] == body.get('NAME')), None)
            if r is None:
                old = next((r for r in self.rooms if r['id'] == u['room']), None)
                u['room'] = None
                self.reply(c, who, cmd, {'IDENT': '0', 'NAME': ''})
                if old:
                    for v in self.users.values():
                        self.push(v, '+rom', self.room_info(old))
                return
            self.join(c, who, u, r, cmd)
            return
        if cmd == 'news':               # config files (client.cfg, then webconfig, which these come from)
            # BUDDY_*: the messenger (0x4dcf14). LOCKER_SERVER: an HTTP base for the file locker; empty,
            # its create (0x54b22e) returns NULL and the game crashes after lobby setup (0x54b347).
            self.reply(c, who, cmd, {'BUDDY_SERVER': self.host, 'BUDDY_PORT': BUDDY_PORT,
                                     'LOCKER_SERVER': 'http://%s:%d/locker' % (self.host, HTTP_PORT)})
            return
        if cmd == 'rcat':               # room categories (0x541e99): CAT0, CAT1... = name,description,
            # prefix,four more fields,flag ('1' sets a bit); a field ends at a space unless quoted.
            # Rooms are listed per category, by the prefix of their names ('<prefix>.<name>',
            # 0x54227f); without categories none show.
            cats = {'USR': 'User Rooms', 'CLB': 'Club Rooms', 'HED': 'Head to Head', 'LVL': 'Skill Level',
                    'CNT': 'Contests'}
            self.reply(c, who, cmd, {'CAT%d' % i: '"%s","%s",%s,,,,,0' % (n, n, k)
                                     for i, (k, n) in enumerate(cats.items())})
            return
        if cmd == 'slst':               # rankings views (0x592040): COUNT, then VIEW0, VIEW1... = id,name,desc
            # (indexed keys are '%s%d'); lobby setup waits until at least one view is read
            self.reply(c, who, cmd, {'COUNT': '1', 'VIEW0': 'PS2,Madden,Overall'})
            return
        if cmd == 'cate':               # rankings categories (0x5926e1); its caller waits for this
            syms = ['PS2', 'Overall', 'Ranked']
            # SYMS: names, SS: their size with NULs. R: numbers walked by a state machine: per channel
            # its name (a SYMS index) and index count; per index its name and view count; per view its
            # name, a number and a column count with that many columns. The reply is only accepted
            # (and lobby setup goes on) once a whole channel has been read; CC=0 hangs "Connecting".
            self.reply(c, who, cmd, {'SS': sum(len(n) + 1 for n in syms), 'SYMS': ','.join(syms),
                                     'CC': '1', 'IC': '1', 'VC': '1', 'R': '0,1,1,1,2,0,0'})
            return
        self.reply(c, who, cmd, {})

    def bot_control(self, path):
        """Test aid: write 'index=value ...' (hex values) to <log>.bot to change bytes of the bot's
        USERPARAMS (its copy of its opponent's), or 'KEY=value' to set its PRES%d/OPFLAG%d/...
        fields; the game record is pushed again on each change."""
        last = None
        while True:
            time.sleep(1)
            try:
                st = os.stat(path).st_mtime
            except OSError:
                continue
            if st == last:
                continue
            last = st
            for bot in [v for v in self.users.values() if v['conn'] is None]:
                g = self.games.get(bot.get('game') or 0)
                if not g:
                    continue
                host = g['players'][0]
                b = bytearray(host.get('userparams', '').encode('latin1'))
                bot['over'] = {}
                for kv in open(path).read().split():
                    i, v = kv.split('=')
                    if i.isdigit():
                        b[int(i)] = int(v, 16)
                    else:                   # a record field for the bot, e.g. PRES=5 or OPFLAG=1
                        bot['over'][i] = v
                bot['userparams'] = b.decode('latin1')
                bot['fixed'] = True
                self.say('bot params', b.hex(' '))
                for p in g['players']:
                    self.push(p, '+mgm', self.game_info(g))

    def message(self, c, who, u, body):
        """mesg ATTR=ENX PRIV=<name> TEXT=... -> a private message: tag 'priv', F=<ATTR> N=<sender>
        T=<TEXT>, to that user (the game's invite listener is subscribed to 'priv', 0x4df53b; without
        PRIV it goes to the sender's room as +msg). An invite's TEXT is TYPE=<'game'> MESG=[SEND]
        PARM=<settings>, URL-encoded; the receiver needs flag X (bit 24) in F and acts on MESG:
        [SEND], [REVK], [DECL], [BLCK], [ACPT], [BUSY] (table 0x72e71c)."""
        self.reply(c, who, 'mesg', {})
        msg = {'F': body.get('ATTR', 'ENX'), 'N': u['name'], 'T': body.get('TEXT', '')}
        to = body.get('PRIV')
        targets = [v for v in self.users.values() if v['name'] == to] if to else             [v for v in self.users.values() if v['room'] == u['room'] and v is not u]
        tag = 'priv' if to else '+msg'
        for v in targets:
            self.push(v, tag, msg)
            if v['conn'] is None and '[SEND]' in msg['T']:      # the bot accepts and joins, a bit
                threading.Timer(3, self.bot_accept, (u, v, msg)).start()   # later, as a person would

    def bot_accept(self, u, bot, msg):
        self.push(u, 'priv', dict(msg, N=bot['name'], T=msg['T'].replace('[SEND]', '[ACPT]')))
        g = self.games.get(u.get('game') or 0)
        if g and bot not in g['players']:
            g['players'].append(bot)
            bot['game'] = g['id']
            bot['userparams'] = u.get('userparams', '')
            for p in g['players']:
                self.push(p, '+mgm', self.game_info(g))

    def game(self, c, who, u, cmd, body):
        """Games (Invite to Game creates one: gcre with MINSIZE=MAXSIZE=2, PASS = the host's name).
        The reply and the +mgm/+ses pushes carry the game record the client parses at 0x5405f4."""
        if 'USERPARAMS' in body:        # each player's own state (team, ready...), echoed as OPPARAM%d
            u['userparams'] = body['USERPARAMS']
            for v in self.users.values():   # the bot mirrors its opponent: ready when they are
                if v['conn'] is None and v.get('game') and v['game'] == u.get('game') and not v.get('fixed'):
                    v['userparams'] = body['USERPARAMS']
        if cmd == 'gcre':
            g = {'id': self.next_game, 'name': body.get('NAME', u['name']), 'host': u,
                 'params': body.get('PARAMS', ''), 'sysflags': body.get('SYSFLAGS', '0'),
                 'pass': body.get('PASS', ''), 'min': body.get('MINSIZE', '2'),
                 'max': body.get('MAXSIZE', '2'), 'players': [u], 'room': u['room'] or 0,
                 'seed': int(time.time()) & 0x7fffffff, 'started': False}
            self.next_game += 1
            self.games[g['id']] = g
            u['game'] = g['id']
            self.reply(c, who, cmd, self.game_info(g))
            self.push(u, '+mgm', self.game_info(g))
            return
        ident = int(body.get('IDENT') or 0)
        if cmd == 'gjoi' and ident < 0:     # accepting an invite: gget IDENT=<n>, then gjoi IDENT=-1
            ident = u.get('fetched') or 0
        g = self.games.get(ident or u.get('game') or 0)
        if g is None and cmd == 'gjoi':     # joined by name
            g = next((g for g in self.games.values() if g['name'] == body.get('NAME')), None)
        if cmd == 'gget':                   # the game's record (the guest looks up the invite's game)
            if g:
                u['fetched'] = g['id']
                self.reply(c, who, cmd, self.game_info(g))
            else:
                self.reply(c, who, cmd, {}, code=0x6e6f6761)    # 'noga'
            return
        if g is None:
            self.reply(c, who, cmd, {}, code=0x6e6f6761)        # 'noga'
            return
        if cmd == 'gjoi':
            if u not in g['players']:
                g['players'].append(u)
            u['game'] = g['id']
        elif cmd == 'glea':
            if u in g['players']:
                g['players'].remove(u)
            u['game'] = None
        elif cmd == 'gdel':
            for v in g['players']:
                v['game'] = None
            g['players'] = []
        elif cmd == 'gset':
            g['params'] = body.get('PARAMS', g['params'])
        elif cmd == 'gsta':
            g['started'] = True
        self.reply(c, who, cmd, self.game_info(g))
        for v in g['players'] + ([u] if u not in g['players'] else []):
            self.push(v, '+ses' if cmd == 'gsta' else '+mgm', self.game_info(g))
        # Nobody sends gsta: the session starts (+ses, handled apart from +mgm at 0x4e86ad) once
        # the game is full and every player's USERPARAMS byte 5 has its ready bit (bit 0) set.
        ready = lambda v: len(v.get('userparams', '')) > 5 and ord(v['userparams'][5]) & 1
        if (cmd == 'gset' and not g['started'] and len(g['players']) >= int(g['max'])
                and all(ready(v) for v in g['players'])):
            g['started'] = True
            self.say('session start', g['id'])
            for v in g['players']:
                self.push(v, '+ses', self.game_info(g))
        if not g['players']:
            del self.games[g['id']]

    def game_info(self, g):
        info = {'IDENT': g['id'], 'NAME': g['name'], 'HOST': g['host']['name'], 'GPSHOST': g['host']['name'],
                'PARAMS': g['params'], 'PLATPARAMS': '', 'ROOM': g['room'], 'CUSTFLAGS': '0',
                'SYSFLAGS': g['sysflags'], 'COUNT': len(g['players']), 'PRIV': '1' if g['pass'] else '0',
                'MINSIZE': g['min'], 'MAXSIZE': g['max'], 'NUMPART': '1', 'SEED': g['seed'],
                'WHEN': time.strftime('%Y.%m.%d-%H:%M:%S'), 'GAMEPORT': '9657', 'VOIPPORT': '9667',
                'GAMEMODE': '0', 'AUTH': '', 'SESS': 'None'}
        for i, v in enumerate(g['players']):
            info.update({'OPID%d' % i: v['id'], 'OPPO%d' % i: v['name'], 'ADDR%d' % i: v['addr'],
                         'LADDR%d' % i: v['addr'], 'MADDR%d' % i: v.get('mac', ''), 'OPPART%d' % i: '0',
                         'OPPARAM%d' % i: v.get('userparams', ''), 'OPFLAG%d' % i: '0', 'PRES%d' % i: '0'})
            info.update({k + str(i): x for k, x in v.get('over', {}).items()})
        info.update({'PARTSIZE0': g['max'], 'PARTPARAMS0': ''})
        return info

    def join(self, c, who, u, r, cmd):
        u['room'] = r['id']
        members = [v for v in self.users.values() if v['room'] == r['id']]
        for v in self.users.values():   # the room record (new count) for everyone, then the reply
            self.push(v, '+rom', self.room_info(r))
        self.reply(c, who, cmd, {'IDENT': r['id'], 'NAME': r['name'], 'COUNT': len(members), 'FLAGS': 'C'})
        self.reply(c, who, '+who', self.who_info(u, r))
        for v in members:               # everyone in the room learns about everyone
            for t in members:
                if v is u or t is u:
                    self.push(v, '+usr', self.user_info(t))
        for v in self.users.values():
            self.push(v, '+pop', {'Z': '%d/%d' % (r['id'], len(members))})

    def buddy(self, c, who, cmd, body):
        """EA Messenger: AUTH (PROD, VERS, PRES, USER, LKEY) -> AUTH with TIID (0x55072e); RGET (buddy
        list: ID, LRSC, LIST) -> RGET with ID and SIZE=0, an empty list (0x550815); EPGT -> ID=4."""
        ident = {'ID': body['ID']} if 'ID' in body else {}     # replies are matched to requests by ID
        if cmd == 'AUTH':
            self.reply(c, who, cmd, {'TIID': '1'})
        elif cmd == 'RGET':
            self.reply(c, who, cmd, dict(ident, SIZE='0'))
        elif cmd == 'EPGT':             # 0x550cee: ADDR, and ENAB=T sets a flag
            self.reply(c, who, cmd, dict(ident, ADDR='', ENAB='F'))
        else:
            self.reply(c, who, cmd, ident)

    def pinger(self, c, who):
        n = 0
        while True:
            time.sleep(15)
            n += 1
            try:
                c.sendall(pack('~png', {'REF': time.strftime('%Y.%m.%d-%H:%M:%S'), 'TIME': n}))
            except OSError:
                return

    def room_info(self, r):
        count = sum(1 for v in self.users.values() if v['room'] == r['id'])
        # 0x540bde: I, N, DN (display name), H (host), D (description), F (flags), T (users), GT, G,
        # L (limit), LO, C
        return {'I': r['id'], 'N': r['name'], 'H': r.get('host', 'Madden'), 'D': r.get('desc', ''),
                'F': 'CK', 'T': count, 'L': '50', 'P': '0'}

    def who_info(self, u, r=None):     # the client's own record
        return {'I': u['id'], 'N': u['name'], 'M': u['name'], 'F': '', 'A': u['addr'], 'S': '', 'X': '',
                'R': r['name'] if r else '', 'RI': r['id'] if r else '0', 'RF': 'C', 'RT': '1'}

    def user_info(self, u):
        return {'I': u['id'], 'N': u['name'], 'M': u['name'], 'F': 'H', 'A': u['addr'], 'P': '0',
                'S': '', 'X': '', 'G': '0', 'T': '2'}

    def push(self, u, cmd, body):
        if u['conn'] is None:           # the --bot player: log what it would get
            self.say('bot <-', cmd, body)
            return
        try:
            self.reply(u['conn'], 'user%d' % u['id'], cmd, body)
        except OSError:
            pass

    def listen(self, port):
        s = socket.socket()
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(('0.0.0.0', port))
        s.listen(8)
        self.say('listening on', port)
        while True:
            c, a = s.accept()
            threading.Thread(target=self.handle, args=(c, a, port), daemon=True).start()


def main(argv):
    host = argv[argv.index('--host') + 1] if '--host' in argv else '10.0.2.2'
    name = argv[argv.index('--name') + 1] if '--name' in argv else 'Player'
    srv = Server(argv[0], host, name)
    if '--bot' in argv:                 # a fake player sitting in USR.Madden, to test invites with one box
        srv.users['bot'] = {'id': srv.next_id, 'conn': None, 'room': 1, 'addr': '10.0.2.16',
                            'name': 'Bot', 'mac': '$0050f2000001', 'game': None}
        srv.next_id += 1
        threading.Thread(target=srv.bot_control, args=(argv[0] + '.bot',), daemon=True).start()
    for p in (DIR_PORT, LOBBY_PORT, BUDDY_PORT):
        threading.Thread(target=srv.listen, args=(p,), daemon=True).start()
    while True:
        time.sleep(3600)


if __name__ == '__main__':
    main(sys.argv[1:])
