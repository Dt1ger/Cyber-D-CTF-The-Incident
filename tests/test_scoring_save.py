from game.engine.settings import Settings
from game.systems.campaign import RunState, ZoneStats
from game.systems.save import SaveStore
from game.systems.scoring import compute, hint_cost, rank_for, score_run, time_points


def test_perfect_run_is_threat_hunt_lead():
    s = compute([ZoneStats(correct=40)], total_time=100 * 60, flag_captured=True)
    assert (s.accuracy_pts, s.containment_pts, s.time_pts, s.completion_pts) == (400, 300, 150, 150)
    assert s.total == 1000 and s.rank == "Threat Hunt Lead"


def test_penalties_and_bonus():
    stats = [ZoneStats(correct=30, wrong=10, tipoffs=1, data_loss=1, bad_actions=1, hint_points=35, puzzles=2)]
    s = compute(stats, total_time=150 * 60, flag_captured=True)
    assert s.accuracy_pts == 300
    assert s.containment == 100 - 12 - 20 - 8
    assert s.time_pts == time_points(150) == 112
    assert s.hint_penalty == 35 and s.bonus == 50
    assert s.total == 300 + 180 + 112 + 150 + 50 - 35


def test_no_flag_means_no_time_or_completion_points():
    s = compute([ZoneStats(correct=10)], 60 * 60, flag_captured=False)
    assert s.time_pts == 0 and s.completion_pts == 0


def test_rank_thresholds_and_hint_costs():
    assert [rank_for(x) for x in (0, 499, 500, 700, 850)] == [
        "Junior Analyst", "Junior Analyst", "Hunter", "Senior Hunter", "Threat Hunt Lead"]
    assert [hint_cost(i) for i in range(4)] == [10, 15, 25, 25]
    assert time_points(400) == 25


def test_run_round_trips_through_save(tmp_path):
    store = SaveStore(tmp_path)
    assert not store.has_run()
    run = RunState(character="sasha", zone=4, breach=33.5, puzzles=["puzzle_01"], flag_captured=False)
    run.add_evidence("e101", 1)
    run.mapped["T1566.001"] = {"tactic": "TA0001", "zone": 1, "finding": "phish"}
    run.zone_stats(1).correct = 5
    assert store.save_run(run.to_dict())
    loaded = RunState.from_dict(store.load_run())
    assert loaded == run
    assert score_run(loaded) == score_run(run)
    store.clear_run()
    assert store.load_run() is None


def test_corrupt_or_old_saves_are_ignored(tmp_path):
    store = SaveStore(tmp_path)
    store.autosave.write_text("{not json", encoding="utf-8")
    assert store.load_run() is None
    store.autosave.write_text('{"version": 999, "run": {"character": "x"}}', encoding="utf-8")
    assert store.load_run() is None


def test_best_rank_only_improves(tmp_path):
    store = SaveStore(tmp_path)
    assert store.record_result("demetri", "Hunter", 560)
    assert not store.record_result("demetri", "Junior Analyst", 480)
    assert store.record_result("demetri", "Senior Hunter", 710)
    assert store.load_profile()["best"]["demetri"] == {"rank": "Senior Hunter", "score": 710}


def test_reset_zone_forgets_progress_inside_that_zone():
    run = RunState(character="demetri")
    run.add_evidence("e101", 1)
    run.add_evidence("e201", 2)
    run.zone_stats(2).wrong = 3
    run.reset_zone(2)
    assert [e["id"] for e in run.journal] == ["e101"] and "2" not in run.stats


def test_settings_round_trip_and_bad_values(tmp_path):
    path = tmp_path / "settings.json"
    s = Settings(text_size=2, colorblind=True, music=0.3)
    s.save(path)
    assert Settings.load(path) == s
    path.write_text('{"text_size": "huge", "music": 0.9, "unknown": 1}', encoding="utf-8")
    loaded = Settings.load(path)
    assert loaded.text_size == 0 and loaded.music == 0.9
