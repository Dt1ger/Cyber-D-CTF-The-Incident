import pytest

from game.systems.decode import DecodeError, decode, encode
from game.systems.query import QueryError, Table, execute, parse

ROWS = [
    {"id": "p1", "time": "2026-11-17T09:00:00Z", "host": "WS-FIN-0142", "name": "winword.exe",
     "parent": "explorer.exe", "cmdline": "winword.exe Invoice.docm", "bytes": 10},
    {"id": "p2", "time": "2026-11-17T09:01:00Z", "host": "WS-FIN-0142", "name": "powershell.exe",
     "parent": "winword.exe", "cmdline": "powershell.exe -NoP -enc AAAA", "bytes": 300},
    {"id": "p3", "time": "2026-11-17T09:02:00Z", "host": "WS-HR-0007", "name": "powershell.exe",
     "parent": "explorer.exe", "cmdline": "powershell.exe Get-Date", "bytes": 50},
    {"id": "p4", "time": "2026-11-17T09:03:00Z", "host": "DC-01", "name": "net.exe",
     "parent": "cmd.exe", "cmdline": "net group \"Domain Admins\" /domain", "bytes": 5},
]
TABLES = {"proc": Table("proc", ROWS, ["time", "host", "name", "parent", "cmdline"])}


def ids(q):
    return [r["id"] for r in execute(q, TABLES, {"process": "proc"}).rows]


def test_equals_is_case_insensitive():
    assert ids('search proc where name="POWERSHELL.EXE"') == ["p2", "p3"]


def test_and_or_not_and_parentheses():
    assert ids('search proc where name="powershell.exe" and parent="winword.exe"') == ["p2"]
    assert ids('search proc where parent="winword.exe" or host="DC-01"') == ["p2", "p4"]
    assert ids('search proc where not host="WS-FIN-0142"') == ["p3", "p4"]
    assert ids('search proc where (host="DC-01" or host="WS-HR-0007") and name!="net.exe"') == ["p3"]


def test_adjacent_conditions_join_with_and():
    assert ids('search proc where host="WS-FIN-0142" name="powershell.exe"') == ["p2"]


def test_contains_wildcard_numeric_and_in():
    assert ids('search proc where cmdline~"-enc"') == ["p2"]
    assert ids('search proc where name="power*"') == ["p2", "p3"]
    assert ids("search proc where bytes>=50") == ["p2", "p3"]
    assert ids('search proc where name in ("net.exe", "winword.exe")') == ["p1", "p4"]


def test_escaped_quotes_inside_strings():
    assert ids('search proc where cmdline~"\\"Domain Admins\\""') == ["p4"]


def test_pipes():
    res = execute('search proc | count by name', TABLES)
    assert res.aggregated and res.rows[0] == {"name": "powershell.exe", "count": 2}
    assert ids("search proc | sort bytes desc | head 2") == ["p2", "p3"]
    assert ids("search proc | dedup host") == ["p1", "p3", "p4"]
    res = execute("search proc | fields host, name", TABLES)
    assert res.columns == ["host", "name"]


def test_aliases_and_no_where():
    assert len(ids("search process")) == 4


def test_matched_ids_ignore_pipes():
    res = execute('search proc where name="powershell.exe" | head 1', TABLES)
    assert res.matched_ids == {"p2", "p3"} and len(res.rows) == 1


@pytest.mark.parametrize("bad, hint", [
    ('search prc', "Did you mean 'proc'"),
    ('search proc where nme="x"', "Did you mean 'name'"),
    ('search proc where name=', ""),
    ('search proc where name="unterminated', ""),
    ('search proc | head lots', ""),
    ('find proc', ""),
])
def test_errors_are_friendly(bad, hint):
    with pytest.raises(QueryError) as exc:
        execute(bad, TABLES)
    assert hint in str(exc.value)


def test_parse_returns_structure():
    q = parse('search proc where a="1" | head 3')
    assert q.table == "proc" and q.pipes == [("head", 3)]


@pytest.mark.parametrize("kind, key", [("base64", None), ("hex", None), ("rot13", None), ("xor", "0x2a"),
                                       ("base64u16", None)])
def test_decode_round_trips(kind, key):
    text = "FLAG{round_trip_ok}"
    blob = encode(kind, text, key)
    assert blob != text
    assert decode("base64" if kind == "base64u16" else kind, blob, key) == text


def test_decode_errors():
    with pytest.raises(DecodeError):
        decode("hex", "zz-not-hex")
    with pytest.raises(DecodeError):
        decode("xor", "41424344")
