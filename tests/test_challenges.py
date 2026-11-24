"""Built-in case files stay text, and the mode does not start a campaign."""

import json
import re

from game.engine import config
from game.systems.challenges import CaseSession, identify, load_challenges, run_command
from game.systems.decode import decode


def _write(folder, name, data):
    (folder / name).write_text(json.dumps(data), encoding="utf-8")


ANSWERS = {
    "ransom_copy": "FLAG{double_extortion}",
    "fake_login": "FLAG{fake_login_portal}",
    "card_skimmer": "FLAG{web_skimmer}",
    "sim_swap": "FLAG{sim_swap}",
    "cryptojacking": "FLAG{cryptojacking}",
}


def test_builtin_cases_ship_with_the_game():
    found, notes = load_challenges(config.CHALLENGES_DIR)
    assert not notes
    by_id = {c.id: c for c in found}
    assert set(by_id) == set(ANSWERS)
    for case in by_id.values():
        note = case.plaintext()
        answer = ANSWERS[case.id]
        assert answer in note
        assert len(re.findall(r"FLAG\{", note)) >= 3, f"{case.id} needs decoys"
        assert answer.lower() not in (config.CHALLENGES_DIR / case.source).read_text(encoding="utf-8").lower()
        assert case.evidence and len(case.hints) >= 3
        assert run_command(case, "submit " + answer).solved
        assert not run_command(case, "submit FLAG{nope}").solved


def test_cases_need_every_layer_peeled_in_order():
    found, _ = load_challenges(config.CHALLENGES_DIR)
    for case in found:
        session = CaseSession.start(case)
        assert "Name the encoding" in run_command(case, "decode", session).lines[0][0]
        for kind, key in case.layers:
            result = run_command(case, f"decode {kind} {key or ''}", session)
            assert result.lines[-1][1] == "ok", (case.id, kind)
        assert session.buffer == case.plaintext()
        assert "plain English" in " ".join(t for t, _ in identify(session.buffer))
        run_command(case, "reset", session)
        assert session.buffer == case.ciphertext
    multi = [c for c in found if len(c.layers) > 1]
    assert len(multi) == len(found)
    keyed = [c for c in found if any(k == "xor" for k, _ in c.layers)]
    for case in keyed:
        assert "xor needs a key" in run_command(case, "decode xor").lines[0][0]
        key = next(k for kind, k in case.layers if kind == "xor")
        assert key not in case.clue and any(key in line for line in case.evidence)


def test_decoys_and_hints_are_counted():
    case = next(c for c in load_challenges(config.CHALLENGES_DIR)[0] if c.id == "cryptojacking")
    session = CaseSession.start(case)
    assert "doesn't answer" in run_command(case, "submit FLAG{default_creds}", session).lines[0][0]
    assert run_command(case, "hint", session).lines[0][0].startswith("Hint 1/")
    result = run_command(case, "submit flag{CRYPTOJACKING}", session)
    assert result.solved and "1 wrong answer(s) and 1 hint(s)" in result.lines[1][0]


def test_decoded_notes_use_reserved_addresses_only():
    import ipaddress
    from test_content import ALLOWED_NETS, ALLOWED_TLDS, DOMAIN_RE, FILENAME_EXTS, IP_RE
    for case in load_challenges(config.CHALLENGES_DIR)[0]:
        text = case.plaintext() + "\n".join(case.evidence)
        for m in IP_RE.finditer(text):
            assert any(ipaddress.ip_address(m.group(0)) in net for net in ALLOWED_NETS), (case.id, m.group(0))
        for m in DOMAIN_RE.finditer(text):
            assert m.group(1).lower() in ALLOWED_TLDS | FILENAME_EXTS, (case.id, m.group(0))


def test_aisha_unlocks_after_the_hunt_or_every_case(tmp_path):
    from game.art.loader import Assets
    from game.characters.unlock import is_unlocked
    from game.systems.save import SaveStore

    class App:
        saves = SaveStore(tmp_path)

    assets = Assets(config.ASSETS_DIR)
    sprites = assets.sprites("aisha_256")
    assert not sprites.placeholder
    assert len(sprites.get("walk_down").frames) == 4
    assert len(sprites.get("interact").frames) == 4
    assert assets.image(assets.character_entry("aisha_256").get("locked_image")) is not None
    assert not is_unlocked(App, "aisha_256")
    *most, last = ANSWERS
    for case_id in most:
        App.saves.mark_custom_solved(case_id)
    assert not is_unlocked(App, "aisha_256")
    App.saves.mark_custom_solved(last)
    assert is_unlocked(App, "aisha_256")

    fresh = SaveStore(tmp_path / "hunt")
    app2 = App
    app2.saves = fresh
    assert not is_unlocked(app2, "aisha_256")
    fresh.record_result("demetri", "Hunter", 600)
    assert is_unlocked(app2, "aisha_256")


def test_loader_reads_text_and_skips_unsafe_files(tmp_path):
    _write(tmp_path, "note.json", {
        "title": "Note", "clue": "Decode the line.", "encoding": "hex", "answer": "FLAG{note}",
    })
    _write(tmp_path, "bad.json", {
        "title": "Bad", "clue": "No.", "encoding": "exec", "answer": "FLAG{no}",
    })
    _write(tmp_path, "escape.json", {
        "title": "Escape", "clue": "No.", "encoding": "base64", "answer": "FLAG{no}",
        "artifact": "../secret.txt",
    })
    (tmp_path / "ignore.py").write_text("print('no')\n", encoding="utf-8")
    found, notes = load_challenges(tmp_path)
    assert [c.id for c in found] == ["note"]
    assert decode("hex", found[0].ciphertext) == "FLAG{note}"
    assert len(notes) == 2
    assert not (tmp_path / "ignore.py").read_text(encoding="utf-8").startswith("{")


def test_custom_mode_does_not_write_a_campaign_save(tmp_path):
    import os
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    import pygame
    from game.engine.app import App
    from game.scenes.challenges import ChallengesScene

    app = App(start_scene="title", saves_dir=tmp_path)
    try:
        app.scenes.switch("character_select", fade=False, mode="custom")
        scene = app.scenes.current
        scene.confirm()
        scene.dialogue.skip_all()
        for _ in range(20):
            app.scenes.update(0.05)
        assert isinstance(app.scenes.current, ChallengesScene)
        assert app.run is None
        assert not (tmp_path / "autosave.json").exists()
        app.screen.fill((0, 0, 0))
        app.scenes.draw(app.screen)
    finally:
        app.running = False


def test_case_prompt_recalls_commands_instead_of_switching_cases(tmp_path):
    import os
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    import pygame
    from game.engine.app import App

    def key(k):
        return pygame.event.Event(pygame.KEYDOWN, key=k, mod=0, unicode="", scancode=0)

    def run(scene, text):
        scene.handle_event(pygame.event.Event(pygame.TEXTINPUT, text=text))
        scene.handle_event(key(pygame.K_RETURN))

    app = App(start_scene="title", saves_dir=tmp_path)
    try:
        app.scenes.switch("challenges", fade=False)
        scene = app.scenes.current
        assert scene.focus == "list"
        scene.handle_event(key(pygame.K_DOWN))
        second = scene.current.id
        assert scene.list.index == 1

        scene.handle_event(key(pygame.K_RETURN))
        assert scene.focus == "case"
        run(scene, "identify")
        run(scene, "evidence")
        scene.handle_event(key(pygame.K_UP))
        assert scene.prompt.text == "evidence" and scene.current.id == second
        scene.handle_event(key(pygame.K_UP))
        assert scene.prompt.text == "identify" and scene.list.index == 1
        scene.handle_event(key(pygame.K_DOWN))
        scene.handle_event(key(pygame.K_DOWN))
        assert scene.prompt.text == "" and scene.list.index == 1

        scene.handle_event(key(pygame.K_ESCAPE))
        assert scene.focus == "list"
        scene.handle_event(key(pygame.K_UP))
        assert scene.list.index == 0
        scene.handle_event(pygame.event.Event(pygame.TEXTINPUT, text="h"))
        assert scene.focus == "case" and scene.prompt.text == "h"
        scene.handle_event(key(pygame.K_UP))
        assert scene.prompt.text == "h", "each case keeps its own history"

        scene.handle_event(key(pygame.K_ESCAPE))
        scene.handle_event(key(pygame.K_DOWN))
        scene.handle_event(key(pygame.K_RETURN))
        scene.handle_event(key(pygame.K_UP))
        assert scene.prompt.text == "evidence"
        app.screen.fill((0, 0, 0))
        app.scenes.draw(app.screen)
    finally:
        app.running = False
