from game.engine.scene import Scene, SceneManager


class Recorder(Scene):
    log: list = []

    def on_enter(self, **kwargs):
        self.log.append(("enter", type(self).__name__, kwargs))

    def on_exit(self):
        self.log.append(("exit", type(self).__name__))


class A(Recorder):
    pass


class B(Recorder):
    pass


class Overlay(Recorder):
    opaque = False


def make():
    Recorder.log = []
    m = SceneManager(app=None)
    for cls in (A, B, Overlay):
        m.register(cls.__name__, cls)
    return m


def test_switch_without_fade_is_immediate():
    m = make()
    m.switch("A", fade=False, zone=3)
    assert isinstance(m.current, A)
    assert Recorder.log == [("enter", "A", {"zone": 3})]


def test_fade_switch_happens_at_midpoint():
    m = make()
    m.switch("A", fade=False)
    m.switch("B")
    assert isinstance(m.current, A) and m.transitioning
    m.update(SceneManager.FADE_TIME)
    assert isinstance(m.current, B)
    m.update(SceneManager.FADE_TIME)
    assert not m.transitioning
    assert ("exit", "A") in Recorder.log


def test_push_and_pop_overlay_keeps_scene_below():
    m = make()
    m.switch("A", fade=False)
    m.push("Overlay")
    assert isinstance(m.current, Overlay) and len(m.stack) == 2
    m.pop()
    assert isinstance(m.current, A)
    m.pop()  # never pops the last scene
    assert isinstance(m.current, A)
