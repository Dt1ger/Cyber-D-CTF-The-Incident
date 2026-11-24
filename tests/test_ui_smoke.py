"""Drive the real App headlessly: every scene and panel draws, input works, zones chain."""

import os

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pygame  # noqa: E402
import pytest  # noqa: E402

from game.engine.app import App  # noqa: E402
from game.ui.widgets import BACKSPACE_DELAY, TextInput  # noqa: E402
from game.systems.autoplay import solve_zone  # noqa: E402
from game.systems.campaign import RunState  # noqa: E402
from game.ui.hud import TOOLS  # noqa: E402
from game.world.tilemap import TILE  # noqa: E402


@pytest.fixture
def app(tmp_path):
    a = App(start_scene="title", saves_dir=tmp_path)
    yield a
    pygame.quit()


def step(app, events=(), n=1, dt=1 / 60):
    for _ in range(n):
        for e in events:
            app.scenes.handle_event(e)
        events = ()
        app.scenes.update(dt)
        app.screen.fill((0, 0, 0))
        app.scenes.draw(app.screen)


def key(k, mod=0):
    return pygame.event.Event(pygame.KEYDOWN, key=k, mod=mod, unicode="", scancode=0)


def typed(s):
    return pygame.event.Event(pygame.TEXTINPUT, text=s)


def click(pos, button=1):
    return pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=button)


def enter_zone(app, char, zone):
    app.run = RunState(character=char, zone=zone)
    app.scenes.switch("zone", fade=False, zone=zone)
    scene = app.scenes.current
    step(app, n=200)
    while scene.dialogue.active:
        step(app, [key(pygame.K_ESCAPE)])
    return scene


def test_holding_backspace_keeps_erasing(monkeypatch):
    pygame.init()
    box = TextInput()
    box.set("hunt query")
    pressed = [0] * (pygame.K_BACKSPACE + 1)
    monkeypatch.setattr(pygame.key, "get_pressed", lambda: pressed)

    box.handle_event(key(pygame.K_BACKSPACE))
    assert box.text == "hunt quer"

    pressed[pygame.K_BACKSPACE] = 1
    box.update(BACKSPACE_DELAY - 0.05)
    assert box.text == "hunt quer"
    box.update(0.05)
    assert box.text == "hunt que"
    box.update(0.03)
    assert box.text == "hunt qu"

    pressed[pygame.K_BACKSPACE] = 0
    box.update(0.5)
    assert box.text == "hunt qu"


def test_front_end_scenes_draw(app):
    for name in ("splash", "title", "cinematic", "character_select"):
        app.scenes.switch(name, fade=False)
        step(app, n=5)
    app.scenes.switch("title", fade=False)
    step(app, [key(pygame.K_RETURN)], n=3)
    assert app.scenes.current.menu_open
    for overlay in ("settings", "how_to_play"):
        app.scenes.push(overlay)
        step(app, [key(pygame.K_DOWN), key(pygame.K_RIGHT)], n=3)
        step(app, [key(pygame.K_ESCAPE)], n=2)
    assert type(app.scenes.current).__name__ == "TitleScene"


def test_character_select_starts_zone_zero(app):
    app.scenes.switch("character_select", fade=False)
    step(app, [key(pygame.K_RIGHT)], n=2)
    step(app, [key(pygame.K_RETURN)], n=2)
    assert app.run is not None and app.run.character == app.characters[1].id
    step(app, [key(pygame.K_ESCAPE)], n=40)
    assert type(app.scenes.current).__name__ == "ZoneScene"
    assert app.scenes.current.zone.index == 0


def test_character_select_carousel_turns_and_wraps(app):
    app.scenes.switch("character_select", fade=False)
    scene = app.scenes.current
    ids = [c.id for c in app.characters]
    step(app, [key(pygame.K_LEFT)], n=1)
    assert scene.char.id == ids[-1] and scene.turn_t < 1
    step(app, n=40)
    assert scene.turn_t == 1 and scene.pos == scene.target == -1
    front = max(scene._placements())
    assert front[1] == len(ids) - 1 and front[0] > 0.99

    side = next(i for i, _ in scene.hits if i != scene.index)
    rect = dict(scene.hits)[side]
    click = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=rect.center)
    step(app, [click], n=40)
    assert scene.index == side and not scene.confirmed

    hidden = ids.index("aisha_256")
    scene.select(hidden)
    step(app, n=40)
    step(app, [key(pygame.K_RETURN)], n=2)
    assert not scene.confirmed and app.run is None


def test_every_panel_opens_takes_input_and_closes(app):
    scene = enter_zone(app, "sasha", 2)
    keys = [pygame.K_DOWN, pygame.K_UP, pygame.K_TAB, pygame.K_SPACE, pygame.K_RETURN, pygame.K_RETURN,
            pygame.K_RIGHT, pygame.K_c]
    for name, hotkey, _ in TOOLS:
        step(app, [key(getattr(pygame, f"K_{hotkey.lower()}"))], n=2)
        assert scene.panel is not None and scene.panel.name == name
        if name in ("terminal", "journal"):
            step(app, [typed(c) for c in "help"] + [key(pygame.K_RETURN)], n=2)
        else:
            step(app, [key(k) for k in keys], n=2)
        step(app, [key(pygame.K_ESCAPE)], n=2)
        assert scene.panel is None
    assert "journal" in scene.state.opened


def test_terminal_query_completes_objective(app):
    scene = enter_zone(app, "demetri", 2)
    st = scene.state
    st.collect("e201")
    step(app, [key(pygame.K_t)], n=2)
    query = 'search proc where parent="winword.exe" and name="powershell.exe"'
    step(app, [typed(query), key(pygame.K_RETURN)], n=2)
    assert "o2" in st.done


def test_toolbar_click_and_node_interaction(app):
    scene = enter_zone(app, "sasha", 1)
    rect = scene.hud.tool_rects["matrix"]
    step(app, [click(rect.center)], n=2)
    assert scene.panel is not None and scene.panel.name == "matrix"
    step(app, [key(pygame.K_ESCAPE)], n=2)
    nv = scene.node_views[0]
    scene.player.x, scene.player.y = nv.x, nv.y + TILE
    step(app, n=2)
    step(app, [key(pygame.K_e)], n=2)
    assert scene.panel is not None and scene.panel.name == "evidence"
    step(app, [key(pygame.K_RETURN)], n=2)
    assert st_has(scene, nv.node["evidence"][0])
    step(app, [key(pygame.K_ESCAPE)], n=3)
    assert scene.panel is None


def st_has(scene, eid):
    return scene.state.has_evidence(eid)


def test_finishing_a_zone_moves_to_the_next_and_autosaves(app):
    scene = enter_zone(app, "sasha", 3)
    solve_zone(scene.state)
    step(app, n=3)
    assert scene.map.gate_open
    while scene.dialogue.active or scene.deferred:
        step(app, [key(pygame.K_ESCAPE)], n=2)
    gx = scene.map.gate[0][0]
    scene.player.x = (gx + 1.6) * TILE
    step(app, n=2)
    assert scene.exiting
    step(app, [key(pygame.K_ESCAPE)], n=60)
    nxt = app.scenes.current
    assert type(nxt).__name__ == "ZoneScene" and nxt.zone.index == 4
    assert app.saves.load_run()["zone"] == 4


def test_last_zone_leads_to_debrief(app):
    scene = enter_zone(app, "demetri", 8)
    solve_zone(scene.state)
    step(app, n=3)
    while scene.dialogue.active or scene.deferred:
        step(app, [key(pygame.K_ESCAPE)], n=2)
    scene.player.x = (scene.map.gate[0][0] + 1.6) * TILE
    step(app, n=2)
    step(app, [key(pygame.K_ESCAPE)], n=60)
    assert type(app.scenes.current).__name__ == "DebriefScene"
    for _ in range(4):
        step(app, [key(pygame.K_RIGHT)], n=2)
    assert app.saves.load_run() is None
    assert "demetri" in app.saves.load_profile()["best"]


def test_pause_freezes_the_clock(app):
    scene = enter_zone(app, "demetri", 4)
    step(app, [key(pygame.K_ESCAPE)], n=2)
    assert type(app.scenes.current).__name__ == "PauseScene"
    before = app.run.breach
    step(app, n=120)
    assert app.run.breach == before
    step(app, [key(pygame.K_ESCAPE)], n=2)
    assert app.scenes.current is scene
