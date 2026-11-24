"""Content checks: every zone loads, every solution works, every ATT&CK reference is real,
and both characters can finish the whole campaign headless."""

import pytest

from game.characters.character import load_characters
from game.engine.config import DATA_DIR
from game.systems.attack import AttackDB
from game.systems.autoplay import response_order, solve_zone
from game.systems.campaign import RunState
from game.systems.query import execute
from game.systems.scoring import score_run
from game.systems.zone_state import TABLE_ALIASES, ZoneState
from game.world.zone_data import load_zone, zone_count

ZONES = list(range(zone_count()))
PLAYABLE = [i for i in ZONES if load_zone(i).objectives]


@pytest.fixture(scope="module")
def attack():
    return AttackDB.load(DATA_DIR / "attack_techniques.json")


@pytest.fixture(scope="module")
def characters():
    return {c.id: c for c in load_characters(DATA_DIR / "characters.json")}


def test_ten_zones():
    assert ZONES == list(range(10))
    assert PLAYABLE == list(range(9))


@pytest.mark.parametrize("index", ZONES)
def test_zone_references(index, attack):
    zone = load_zone(index)
    assert zone.index == index
    for node in zone.nodes:
        for eid in node.get("evidence", []):
            assert eid in zone.evidence, f"node {node['id']} -> missing evidence {eid}"
    obj_ids = [o["id"] for o in zone.objectives]
    assert len(obj_ids) == len(set(obj_ids))
    for obj in zone.objectives:
        for eid in obj.get("evidence", []) + obj.get("pins", []) + obj.get("reward_evidence", []):
            assert eid in zone.evidence, f"{obj['id']} -> missing evidence {eid}"
        if obj["type"] == "choice":
            assert sum(1 for o in obj["options"] if o.get("correct")) == 1
        if obj["type"] == "map":
            for fid in obj["findings"]:
                assert fid in zone.findings
        if obj["type"] != "respond":
            assert len(obj.get("hints", [])) == 3, f"{obj['id']} needs three hint tiers"
    for tid in zone.attack:
        assert attack.technique(tid), f"unknown technique {tid}"
    for fid, f in zone.findings.items():
        tech = attack.technique(f["technique"])
        assert tech, f"{fid}: unknown technique {f['technique']}"
        for tac in f["tactics"]:
            assert attack.tactic(tac), f"{fid}: unknown tactic {tac}"
            assert tac in tech.tactics, f"{fid}: {tech.id} is not under {tac}"
        for alt in f.get("accept", []):
            assert attack.technique(alt), f"{fid}: unknown alternate {alt}"
    ids = [a["id"] for a in zone.responses]
    assert len(ids) == len(set(ids))
    for a in zone.responses:
        for r in a.get("requires", []):
            assert r in ids
        for n in a.get("clears", []):
            assert zone.node(n), f"{a['id']} clears unknown node {n}"
    if any(o["type"] == "respond" for o in zone.objectives):
        assert any(a["outcome"] == "bad" for a in zone.responses)


@pytest.mark.parametrize("index", PLAYABLE)
def test_query_solutions_fit(index):
    zone = load_zone(index)
    for obj in zone.objectives:
        if obj["type"] != "query":
            continue
        result = execute(obj["solution"], zone.tables, TABLE_ALIASES)
        assert result.table == obj["table"]
        assert set(obj["required"]) <= result.matched_ids, f"{obj['id']}: solution misses rows"
        assert len(result.matched) <= obj["max_rows"], (
            f"{obj['id']}: solution returns {len(result.matched)} rows, max is {obj['max_rows']}")


@pytest.mark.parametrize("index", PLAYABLE)
def test_responses_have_a_valid_order(index, attack, characters):
    zone = load_zone(index)
    state = ZoneState(zone, RunState("demetri"), characters["demetri"], attack)
    if zone.responses:
        assert response_order(state)


@pytest.mark.parametrize("char_id", ["demetri", "sasha"])
def test_full_campaign_headless(char_id, attack, characters):
    run = RunState(char_id)
    for index in PLAYABLE:
        run.zone = index
        state = ZoneState(load_zone(index), run, characters[char_id], attack)
        solve_zone(state)
        state.update(1.0)
        assert state.complete
        kinds = [e.kind for e in state.drain()]
        assert "zone_complete" in kinds
    assert run.flag_captured
    score = score_run(run)
    assert score.rank == "Threat Hunt Lead"
    if char_id == "sasha":
        assert len(run.puzzles) == len(PLAYABLE) - 1
    else:
        assert run.puzzles == []
    techniques = set(run.mapped)
    assert {"T1566.001", "T1059.001", "T1003.001", "T1021.002", "T1071.004", "T1041"} <= techniques


def test_terminal_decode_by_row_and_cache(attack, characters):
    run = RunState("sasha")
    state = ZoneState(load_zone(2), run, characters["sasha"], attack)
    from game.systems.terminal import TerminalSession
    term = TerminalSession(state)
    out = term.execute("decode base64 p-202")
    assert any("cdn.halcyon-support.test" in t for t, _ in out)
    out = term.execute("decode hex cache")
    assert any("FLAG{" in t for t, _ in out)
    demetri = ZoneState(load_zone(2), RunState("demetri"), characters["demetri"], attack)
    out = TerminalSession(demetri).execute("decode hex cache")
    assert not any("FLAG{" in t for t, _ in out)


def test_premature_action_and_breach_reset(attack, characters):
    run = RunState("sasha")
    zone = load_zone(1)
    state = ZoneState(zone, run, characters["sasha"], attack, seed=1)
    outcome, _ = state.respond("r4")
    assert outcome == "premature"
    assert state.stats.tipoffs == 1
    run.breach = 99.5
    state.respond("r5")
    assert state.stats.data_loss == 1
    assert run.breach == zone.clock.get("reset", 80)
