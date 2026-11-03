"""2026 coaching staffs for the modern roster (used by build_roster.py).

Every current team (TGID 1-32) has four rows in COCH, one per role COPS
(0 head coach, 1 offensive, 2 defensive, 3 special teams coordinator). Each
row is renamed to the 2026 coach for that team and role. Other teams' rows
(the coach pool 1023, Pro Bowl coaches 1010/1011) are left as they are.

Coaches who were already in 09 (SAME_PERSON) take their own stock row
(ratings and 3D head), keeping the slot's ids. The others keep the slot's
ratings and get the
generic head and the silhouette photo, so a 2008 coach's face doesn't
appear on a new name (the menu photo comes from CSXP, not CHID). Skin tone
(CSKI, for the 3D head) comes from DARK/MEDIUM, read off the team photos;
photo brightness was tried and misjudged a dozen coaches under studio lighting.

With photos (fetch_coach_photos.py), photo_plan() gives every renamed coach a
uis_coac.dat entry: a returning coach's own entry (his current photo replaces
the 2008 one), and for the others entries that no remaining row uses (the
2008 coaches they replaced).

Every renamed coach gets his real age at the 2026 opener (BORN) and his NFL
head-coaching record before 2026 (RECORDS, SUPER_BOWLS; zero if he has never
been a head coach). fetch_coach_facts.py gathers BORN and RECORDS.

Sources (2026-11-03): ESPN's coaches page for head coaches; Wikipedia's
"List of current NFL offensive / defensive / special teams coordinators".
"""

GENERIC_FACE = 14       # CHID (3D head) shared by 80 stock coaches
NO_PHOTO = 15           # CSXP: menu photo is uis_coac.dat entry CSXP+1; entry 16 is the silhouette
SEASON_START = (2026, 9, 10)   # ages are taken at the 2026 opener
SLOT_FIELDS = ('CCID', 'TGID', 'CPID', 'CDID', 'COPS')   # kept from the slot when copying a stock coach
# Career record (Reid 2008: 88-54, playoffs 8-6, a Super Bowl loss; Schottenheimer's 13 playoff
# seasons): W, L, T, playoff W, L, winning seasons, playoff seasons, then Super Bowls W, L.
RECORD_FIELDS = ('CCWI', 'CCLO', 'CCTI', 'CCPW', 'CCPL', 'CCWS', 'CCPM', 'CSBW', 'CSBL')

# TGID: (head coach, offensive coordinator, defensive coordinator, special teams). None keeps the stock coach.
STAFF = {
    1: ('Ben Johnson', 'Press Taylor', 'Dennis Allen', 'Richard Hightower'),          # Bears
    2: ('Zac Taylor', 'Dan Pitcher', 'Al Golden', 'Darrin Simmons'),                  # Bengals
    3: ('Joe Brady', 'Pete Carmichael', 'Jim Leonhard', 'Jeff Rodgers'),              # Bills
    4: ('Sean Payton', 'Davis Webb', 'Vance Joseph', 'Darren Rizzi'),                 # Broncos
    5: ('Todd Monken', 'Travis Switzer', 'Mike Rutenberg', 'Byron Storer'),           # Browns
    6: ('Todd Bowles', 'Zac Robinson', None, 'Danny Smith'),                          # Buccaneers (Bowles is his own DC)
    7: ('Mike LaFleur', 'Nathaniel Hackett', 'Nick Rallis', 'Michael Ghobrial'),      # Cardinals
    8: ('Jim Harbaugh', 'Mike McDaniel', "Chris O'Leary", 'Ryan Ficken'),             # Chargers
    9: ('Andy Reid', 'Eric Bieniemy', 'Steve Spagnuolo', 'Dave Toub'),                # Chiefs
    10: ('Shane Steichen', 'Jim Bob Cooter', 'Lou Anarumo', 'Brian Mason'),           # Colts
    11: ('Brian Schottenheimer', 'Klayton Adams', 'Christian Parker', 'Nick Sorensen'),  # Cowboys
    12: ('Jeff Hafley', 'Bobby Slowik', 'Sean Duggan', 'Chris Tabor'),                # Dolphins
    13: ('Nick Sirianni', 'Sean Mannion', 'Vic Fangio', 'Michael Clay'),              # Eagles
    14: ('Kevin Stefanski', 'Tommy Rees', 'Jeff Ulbrich', 'Craig Aukerman'),          # Falcons
    15: ('Kyle Shanahan', 'Klay Kubiak', 'Raheem Morris', 'Brant Boyer'),             # 49ers
    16: ('John Harbaugh', 'Matt Nagy', 'Dennard Wilson', 'Chris Horton'),             # Giants
    17: ('Liam Coen', 'Grant Udinski', 'Anthony Campanile', 'Heath Farwell'),         # Jaguars
    18: ('Aaron Glenn', 'Frank Reich', 'Brian Duker', 'Chris Banjo'),                 # Jets
    19: ('Dan Campbell', 'Drew Petzing', 'Kelvin Sheppard', 'Dave Fipp'),             # Lions
    20: ('Matt LaFleur', 'Adam Stenavich', 'Jonathan Gannon', 'Cameron Achord'),      # Packers
    21: ('Dave Canales', 'Brad Idzik', 'Todd Wash', 'Tracy Smith'),                   # Panthers
    22: ('Mike Vrabel', 'Josh McDaniels', 'Zak Kuhr', 'Jeremy Springer'),             # Patriots
    23: ('Klint Kubiak', 'Andrew Janocko', 'Rob Leonard', 'Joe DeCamillis'),          # Raiders
    24: ('Sean McVay', 'Nathan Scheelhaase', 'Chris Shula', 'Ray Ventrone'),          # Rams
    25: ('Jesse Minter', 'Declan Doyle', 'Anthony Weaver', 'Anthony Levine'),         # Ravens
    26: ('Dan Quinn', 'David Blough', 'Daronte Jones', 'Larry Izzo'),                 # Commanders
    27: ('Kellen Moore', 'Doug Nussmeier', 'Brandon Staley', 'Phil Galiano'),         # Saints
    28: ('Mike Macdonald', 'Brian Fleury', 'Aden Durde', 'Jay Harbaugh'),             # Seahawks
    29: ('Mike McCarthy', 'Brian Angelichio', 'Patrick Graham', 'Danny Crossman'),    # Steelers
    30: ('Robert Saleh', 'Brian Daboll', 'Gus Bradley', 'John Fassel'),               # Titans
    31: ("Kevin O'Connell", 'Wes Phillips', 'Brian Flores', 'Matt Daniels'),          # Vikings
    32: ('DeMeco Ryans', 'Nick Caley', 'Matt Burke', 'Frank Ross'),                   # Texans
}

# 2026 coach -> (stock CLNA, stock TGID) of the same person. Name matches that
# are different people are deliberately absent: W.Phillips is Wade (Wes's
# father), J.Fassel is Jim (John's father), B.Slowik is Bob (Bobby's father).
SAME_PERSON = {
    'Andy Reid': ('A.Reid', 13), 'Sean Payton': ('S.Payton', 27),
    'Mike McCarthy': ('M.McCarthy', 20), 'John Harbaugh': ('J.Harbaugh', 25),
    'Josh McDaniels': ('J.McDaniels', 22), 'Steve Spagnuolo': ('S.Spagnuolo', 16),
    'Dave Toub': ('D.Toub', 1), 'Danny Crossman': ('D.Crossman', 21),
    'Danny Smith': ('D.Smith', 26), 'Darrin Simmons': ('D.Simmons', 2),
    'Joe DeCamillis': ('J.DeCamillis', 17),
}

# Birth dates: Wikidata, else profootballarchives.com / news reports (2026-11-03)
BORN = {
    'Ben Johnson': '1986-05-11',
    'Press Taylor': '1988-01-13',
    'Dennis Allen': '1972-09-22',
    'Richard Hightower': '1980-09-15',
    'Zac Taylor': '1983-05-10',
    'Dan Pitcher': '1987-01-13',
    'Al Golden': '1969-07-04',
    'Darrin Simmons': '1973-04-09',
    'Joe Brady': '1989-09-23',
    'Pete Carmichael': '1971-10-06',
    'Jim Leonhard': '1982-10-27',
    'Jeff Rodgers': '1978-01-12',
    'Sean Payton': '1963-12-29',
    'Davis Webb': '1995-01-22',
    'Vance Joseph': '1972-09-20',
    'Darren Rizzi': '1970-07-21',
    'Todd Monken': '1966-02-05',
    'Travis Switzer': '1992-11-11',
    'Mike Rutenberg': '1981-10-29',
    'Byron Storer': '1984-05-01',
    'Todd Bowles': '1963-11-18',
    'Zac Robinson': '1986-09-29',
    'Danny Smith': '1953-09-07',
    'Mike LaFleur': '1987-07-01',  # year only
    'Nathaniel Hackett': '1979-12-19',
    'Nick Rallis': '1993-07-13',
    'Michael Ghobrial': '1988-02-09',
    'Jim Harbaugh': '1963-12-23',
    'Mike McDaniel': '1983-03-06',
    "Chris O'Leary": '1991-11-07',
    'Ryan Ficken': '1980-02-20',
    'Andy Reid': '1958-03-19',
    'Eric Bieniemy': '1969-08-15',
    'Steve Spagnuolo': '1959-12-21',
    'Dave Toub': '1962-06-01',
    'Shane Steichen': '1985-05-11',
    'Jim Bob Cooter': '1984-07-03',
    'Lou Anarumo': '1966-08-18',
    'Brian Mason': '1986-10-29',
    'Brian Schottenheimer': '1973-10-16',
    'Klayton Adams': '1983-02-13',
    'Christian Parker': '1991-12-23',
    'Nick Sorensen': '1978-07-31',
    'Jeff Hafley': '1979-04-04',
    'Bobby Slowik': '1987-06-09',
    'Sean Duggan': '1993-04-04',
    'Chris Tabor': '1971-03-04',
    'Nick Sirianni': '1981-06-15',
    'Sean Mannion': '1992-04-25',
    'Vic Fangio': '1958-08-22',
    'Michael Clay': '1991-08-30',
    'Kevin Stefanski': '1982-05-08',
    'Tommy Rees': '1992-05-22',
    'Jeff Ulbrich': '1977-02-17',
    'Craig Aukerman': '1976-11-22',
    'Kyle Shanahan': '1979-12-14',
    'Klay Kubiak': '1988-10-10',
    'Raheem Morris': '1976-09-03',
    'Brant Boyer': '1971-06-27',
    'John Harbaugh': '1962-09-23',
    'Matt Nagy': '1978-04-24',
    'Dennard Wilson': '1982-03-31',
    'Chris Horton': '1984-12-29',
    'Liam Coen': '1985-11-08',
    'Grant Udinski': '1996-01-12',
    'Anthony Campanile': '1982-08-18',
    'Heath Farwell': '1981-12-31',
    'Aaron Glenn': '1972-07-16',
    'Frank Reich': '1961-12-04',
    'Brian Duker': '1989-07-15',
    'Chris Banjo': '1990-02-26',
    'Dan Campbell': '1976-04-13',
    'Drew Petzing': '1987-03-12',
    'Kelvin Sheppard': '1988-01-02',
    'Dave Fipp': '1974-08-08',
    'Matt LaFleur': '1979-11-03',
    'Adam Stenavich': '1983-03-11',
    'Jonathan Gannon': '1983-04-04',
    'Cameron Achord': '1987-02-04',
    'Dave Canales': '1981-05-07',
    'Brad Idzik': '1991-10-20',
    'Todd Wash': '1968-07-19',
    'Tracy Smith': '1982-02-23',
    'Mike Vrabel': '1975-08-14',
    'Josh McDaniels': '1976-04-21',
    'Zak Kuhr': '1988-04-19',
    'Jeremy Springer': '1989-02-22',
    'Klint Kubiak': '1987-02-17',
    'Andrew Janocko': '1988-04-06',
    'Rob Leonard': '1987-01-01',
    'Joe DeCamillis': '1965-06-29',
    'Sean McVay': '1986-01-24',
    'Nathan Scheelhaase': '1990-11-08',
    'Chris Shula': '1986-02-05',
    'Ray Ventrone': '1982-10-21',
    'Jesse Minter': '1983-05-09',
    'Declan Doyle': '1996-07-01',  # year only
    'Anthony Weaver': '1980-07-28',
    'Anthony Levine': '1987-03-27',
    'Dan Quinn': '1970-09-11',
    'David Blough': '1995-07-31',
    'Daronte Jones': '1978-11-11',
    'Larry Izzo': '1974-09-26',
    'Kellen Moore': '1988-07-05',
    'Doug Nussmeier': '1970-12-11',
    'Brandon Staley': '1982-12-10',
    'Phil Galiano': '1977-09-08',
    'Mike Macdonald': '1987-06-26',
    'Brian Fleury': '1978-10-01',  # reported as 47 in Feb 2026; month unknown
    'Aden Durde': '1980-07-10',
    'Jay Harbaugh': '1989-06-14',
    'Mike McCarthy': '1963-11-10',
    'Brian Angelichio': '1972-12-27',
    'Patrick Graham': '1979-01-24',
    'Danny Crossman': '1967-01-17',
    'Robert Saleh': '1979-01-31',
    'Brian Daboll': '1975-04-14',
    'Gus Bradley': '1966-07-05',
    'John Fassel': '1974-01-10',
    "Kevin O'Connell": '1985-05-25',
    'Wes Phillips': '1979-02-17',
    'Brian Flores': '1981-02-24',
    'Matt Daniels': '1989-09-27',
    'DeMeco Ryans': '1984-07-28',
    'Nick Caley': '1983-01-22',
    'Matt Burke': '1976-03-25',
    'Frank Ross': '1987-07-24',
}

# NFL head-coaching record before 2026: (W, L, T, playoff W, L, winning seasons, playoff seasons).
# Wikipedia season tables (checked against ESPN regular-season totals); ESPN where the article
# has no table (Johnson, Vrabel, Macdonald). Coaches not listed have never been a head coach.
RECORDS = {
    'Ben Johnson': (11, 6, 0, 1, 1, 1, 1),
    'Dennis Allen': (26, 53, 0, 0, 0, 1, 0),
    'Zac Taylor': (52, 63, 1, 5, 2, 4, 2),
    'Sean Payton': (184, 108, 0, 10, 10, 12, 11),
    'Vance Joseph': (11, 21, 0, 0, 0, 0, 0),
    'Darren Rizzi': (3, 5, 0, 0, 0, 0, 0),
    'Todd Bowles': (61, 74, 0, 1, 3, 4, 3),
    'Nathaniel Hackett': (4, 11, 0, 0, 0, 0, 0),
    'Jim Harbaugh': (66, 31, 1, 5, 5, 5, 5),
    'Mike McDaniel': (35, 33, 0, 0, 2, 2, 2),
    'Andy Reid': (279, 157, 1, 28, 17, 21, 20),
    'Steve Spagnuolo': (11, 41, 0, 0, 0, 0, 0),
    'Shane Steichen': (25, 26, 0, 0, 0, 1, 0),
    'Brian Schottenheimer': (7, 9, 1, 0, 0, 0, 0),
    'Nick Sirianni': (59, 26, 0, 6, 4, 5, 5),
    'Vic Fangio': (19, 30, 0, 0, 0, 0, 0),
    'Kevin Stefanski': (45, 56, 0, 1, 2, 2, 2),
    'Jeff Ulbrich': (3, 9, 0, 0, 0, 0, 0),
    'Kyle Shanahan': (82, 67, 0, 9, 5, 5, 5),
    'Raheem Morris': (37, 56, 0, 0, 0, 1, 0),
    'John Harbaugh': (180, 113, 0, 13, 11, 13, 12),
    'Matt Nagy': (34, 31, 0, 0, 2, 1, 2),
    'Liam Coen': (13, 4, 0, 0, 1, 1, 1),
    'Aaron Glenn': (3, 14, 0, 0, 0, 0, 0),
    'Frank Reich': (41, 43, 1, 1, 2, 3, 2),
    'Dan Campbell': (53, 43, 1, 2, 2, 4, 2),
    'Matt LaFleur': (76, 40, 1, 3, 6, 6, 6),
    'Jonathan Gannon': (15, 36, 0, 0, 0, 0, 0),
    'Dave Canales': (13, 21, 0, 0, 1, 0, 1),
    'Mike Vrabel': (68, 48, 0, 5, 4, 5, 4),
    'Josh McDaniels': (20, 33, 0, 0, 0, 0, 0),
    'Sean McVay': (92, 57, 0, 10, 6, 8, 7),
    'Dan Quinn': (60, 59, 0, 5, 3, 3, 3),
    'Kellen Moore': (6, 11, 0, 0, 0, 0, 0),
    'Brandon Staley': (24, 24, 0, 0, 1, 2, 1),
    'Mike Macdonald': (24, 10, 0, 3, 0, 2, 1),
    'Mike McCarthy': (174, 112, 2, 11, 11, 12, 12),
    'Robert Saleh': (20, 36, 0, 0, 0, 0, 0),
    'Brian Daboll': (20, 40, 1, 1, 1, 1, 1),
    'Gus Bradley': (14, 48, 0, 0, 0, 0, 0),
    'John Fassel': (0, 3, 0, 0, 0, 0, 0),
    "Kevin O'Connell": (43, 25, 0, 0, 2, 3, 2),
    'Brian Flores': (24, 25, 0, 0, 0, 2, 0),
    'DeMeco Ryans': (32, 19, 0, 3, 3, 3, 3),
}

SUPER_BOWLS = {'Andy Reid': (3, 3), 'Sean Payton': (1, 0), 'Mike McCarthy': (1, 0), 'John Harbaugh': (1, 0),
               'Sean McVay': (1, 1), 'Nick Sirianni': (1, 1), 'Mike Macdonald': (1, 0), 'Kyle Shanahan': (0, 2),
               'Jim Harbaugh': (0, 1), 'Zac Taylor': (0, 1), 'Dan Quinn': (0, 1), 'Mike Vrabel': (0, 1)}

# CSKI 2 and 1; everyone else 0
DARK = {'Richard Hightower', 'Vance Joseph', 'Todd Bowles', 'Eric Bieniemy', 'Christian Parker', 'Michael Clay',
        'Raheem Morris', 'Dennard Wilson', 'Chris Horton', 'Aaron Glenn', 'Chris Banjo', 'Kelvin Sheppard',
        'Anthony Weaver', 'Anthony Levine', 'Daronte Jones', 'Patrick Graham', 'Brian Flores', 'Matt Daniels',
        'DeMeco Ryans'}
MEDIUM = {'Mike McDaniel', 'Aden Durde', 'Robert Saleh'}
PHOTO_ENTRY = 17948     # size of a uis_coac.dat photo entry (entry 0 is something else)


def short(name):
    """'Ben Johnson' -> 'B.Johnson', the stock CLNA style (16 characters at most, as stock B.Schottenheimer)."""
    first, last = name.split(' ')[0], name.split(' ')[-1]   # 'Jim Bob Cooter' -> 'J.Cooter'
    s = f'{first[0]}.{last}'
    assert len(s) <= 16, s
    return s


def age(born):
    y, m, d = map(int, born.split('-'))
    return SEASON_START[0] - y - ((m, d) > SEASON_START[1:])


def stock_rows(table):
    """Rows of the same-person coaches, read from a stock COCH table before any edit."""
    found = {}
    for i in range(table.count):
        key = (table.get(i, 'CLNA'), table.get(i, 'TGID'))
        for full, k in SAME_PERSON.items():
            if k == key:
                found[full] = table.row(i)
    assert len(found) == len(SAME_PERSON), set(SAME_PERSON) - set(found)
    return found


def renamed(tid, role):
    return 1 <= tid <= 32 and STAFF[tid][role] is not None


def photo_plan(table, entry_sizes):
    """{(TGID, COPS): CSXP} for every renamed coach, from a stock COCH table."""
    rows = table.rows()
    own = {(r['TGID'], r['COPS']): r['CSXP'] for r in rows if renamed(r['TGID'], r['COPS'])}
    back = {(r['CLNA'], r['TGID']): r['CSXP'] for r in rows}
    plan = {(t, c): back[SAME_PERSON[n]] for t, staff in STAFF.items() for c, n in enumerate(staff) if n in SAME_PERSON}
    taken = {r['CSXP'] for r in rows if not renamed(r['TGID'], r['COPS'])} | set(plan.values()) | {NO_PHOTO}
    free = sorted({c for c in own.values() if c not in taken}) +         [c for c in range(len(entry_sizes) - 1) if entry_sizes[c + 1] == PHOTO_ENTRY and c not in taken and c not in own.values()]
    new = [k for k in sorted(own) if k not in plan]
    assert len(free) >= len(new), (len(free), len(new))
    plan.update(zip(new, free))
    return plan


def apply(table, stock, photos=None):
    """Rename the 1-32 team staffs in a COCH table. `stock` is stock_rows() of a stock table;
    `photos` is {(TGID, COPS): CSXP} for coaches with a photo."""
    n = 0
    for i in range(table.count):
        tid, role = table.get(i, 'TGID'), table.get(i, 'COPS')
        if not renamed(tid, role):
            continue
        full = STAFF[tid][role]
        if full in SAME_PERSON:
            for k, v in stock[full].items():
                if k in table.fields and k not in SLOT_FIELDS:
                    table.set(i, k, v)
        else:
            table.set(i, 'CLNA', short(full))
            table.set(i, 'CHID', GENERIC_FACE)
            table.set(i, 'CSXP', NO_PHOTO)
            table.set(i, 'CSKI', 2 if full in DARK else 1 if full in MEDIUM else 0)
        table.set(i, 'CAGE', age(BORN[full]))
        for k, v in zip(RECORD_FIELDS, RECORDS.get(full, (0,) * 7) + SUPER_BOWLS.get(full, (0, 0))):
            table.set(i, k, v)
        if photos and (tid, role) in photos:
            table.set(i, 'CSXP', photos[tid, role])
        n += 1
    return n
