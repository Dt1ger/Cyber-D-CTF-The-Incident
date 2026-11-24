"""Content rules: dialogue resolves, ATT&CK data is sane, and nothing points at real infrastructure."""

import ipaddress
import json
import re
from pathlib import Path

import pytest

from game.systems.attack import AttackDB
from game.systems.dialogue_db import DialogueDB
from game.world.zone_data import zone_count

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
CHARACTERS = ["demetri", "sasha"]
ALLOWED_NETS = [ipaddress.ip_network(n) for n in
                ("192.0.2.0/24", "198.51.100.0/24", "203.0.113.0/24", "10.0.0.0/8", "127.0.0.0/8")]
ALLOWED_TLDS = {"example", "test", "invalid"}
IP_RE = re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])")
DOMAIN_RE = re.compile(r"\b(?:[a-z0-9-]+\.)+(com|net|org|io|ru|cn|info|biz|co|xyz|uk|de|"
                       r"example|test|invalid|local|onion)\b", re.I)
SOURCE_CITATIONS = {"attack.mitre.org"}
FILENAME_EXTS = {"exe", "dll", "ps1", "bin", "dmp", "7z", "docm", "json", "py", "png", "zip", "log"}


def zones():
    return [json.loads((DATA / "zones" / f"zone_{i:02d}.json").read_text(encoding="utf-8"))
            for i in range(zone_count())]


def dialogue_keys(zone: dict) -> set[str]:
    keys = set()
    for seq in zone.get("dialogue", {}).values():
        keys.update(seq)
    for obj in zone.get("objectives", []):
        keys.update(obj.get("dialogue", []))
    return keys


@pytest.mark.parametrize("char", CHARACTERS)
def test_every_dialogue_key_resolves(char):
    db = DialogueDB(DATA / "dialogue")
    missing = []
    for zone in zones():
        for key in sorted(dialogue_keys(zone)):
            if db.line(key, char) is None:
                missing.append(f"zone {zone['index']}: {key}")
    for key in ("select", "zone_complete", "tipoff", "dataloss", "seer_tipoff", "seer_dataloss"):
        if db.line(key, char) is None:
            missing.append(key)
    assert not missing, missing
    assert len(db.sequence("cinematic")) >= 6 and db.sequence("oracle_idle")


@pytest.mark.parametrize("char", CHARACTERS)
def test_every_node_has_a_thought(char):
    db = DialogueDB(DATA / "dialogue")
    missing = [f"z{z['index']}_node_{n['id']}" for z in zones()[:9] for n in z.get("nodes", [])
               if db.line(f"z{z['index']}_node_{n['id']}", char) is None]
    assert not missing, missing


def test_attack_data_is_consistent():
    db = AttackDB.load(DATA / "attack_techniques.json")
    tactic_ids = {t.id for t in db.tactics}
    assert all(re.fullmatch(r"TA\d{4}", t) for t in tactic_ids)
    for tech in db.techniques.values():
        assert re.fullmatch(r"T\d{4}(\.\d{3})?", tech.id), tech.id
        assert tech.tactics and set(tech.tactics) <= tactic_ids, tech.id
        assert tech.description and tech.detection and tech.mitigation, tech.id
        if "." in tech.id:
            parent = db.technique(tech.id.split(".")[0])
            assert parent is None or tech.name.startswith(parent.name), tech.id
    for zone in zones():
        for tid in zone.get("attack", []):
            assert db.technique(tid), f"zone {zone['index']} lists unknown technique {tid}"


KNOWN_NAMES = {
    "T1566.001": "Phishing: Spearphishing Attachment", "T1204.002": "User Execution: Malicious File",
    "T1059.001": "Command and Scripting Interpreter: PowerShell", "T1053.005": "Scheduled Task/Job: Scheduled Task",
    "T1547.001": "Boot or Logon Autostart Execution: Registry Run Keys / Startup Folder",
    "T1003.001": "OS Credential Dumping: LSASS Memory", "T1087.002": "Account Discovery: Domain Account",
    "T1018": "Remote System Discovery", "T1021.002": "Remote Services: SMB/Windows Admin Shares",
    "T1021.001": "Remote Services: Remote Desktop Protocol", "T1071.001": "Application Layer Protocol: Web Protocols",
    "T1071.004": "Application Layer Protocol: DNS", "T1041": "Exfiltration Over C2 Channel",
    "T1486": "Data Encrypted for Impact", "T1490": "Inhibit System Recovery",
    "T1569.002": "System Services: Service Execution", "T1560.001": "Archive Collected Data: Archive via Utility",
}


def test_core_technique_names_match_attack():
    db = AttackDB.load(DATA / "attack_techniques.json")
    for tid, name in KNOWN_NAMES.items():
        assert db.technique(tid) is not None, tid
        assert db.technique(tid).name == name, tid


def scanned_files():
    for folder in ("data", "game", "tools", "challenges"):
        yield from (p for p in (ROOT / folder).rglob("*") if p.suffix in (".json", ".py"))
    for name in ("README.md", "SPEC.md", "main.py"):
        if (ROOT / name).exists():
            yield ROOT / name


def test_only_reserved_ip_addresses():
    bad = []
    for path in scanned_files():
        for m in IP_RE.finditer(path.read_text(encoding="utf-8")):
            try:
                ip = ipaddress.ip_address(m.group(0))
            except ValueError:
                continue
            if not any(ip in net for net in ALLOWED_NETS) and str(ip) != "0.0.0.0":
                bad.append(f"{path.relative_to(ROOT)}: {ip}")
    assert not bad, bad


def test_only_reserved_domains():
    bad = []
    for path in scanned_files():
        for m in DOMAIN_RE.finditer(path.read_text(encoding="utf-8")):
            tld = m.group(1).lower()
            if tld in ALLOWED_TLDS or tld in FILENAME_EXTS or m.group(0).lower() in SOURCE_CITATIONS:
                continue
            bad.append(f"{path.relative_to(ROOT)}: {m.group(0)}")
    assert not bad, bad


def test_no_network_code():
    banned = re.compile(r"^\s*(import|from)\s+(socket|urllib|requests|http|ftplib|smtplib|asyncio)\b", re.M)
    offenders = [str(p.relative_to(ROOT)) for p in scanned_files() if p.suffix == ".py"
                 and banned.search(p.read_text(encoding="utf-8"))]
    assert not offenders, offenders
