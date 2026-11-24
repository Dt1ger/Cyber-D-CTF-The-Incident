from game.ui.panels.base import InfoPanel, Panel
from game.ui.panels.board import BoardPanel
from game.ui.panels.evidence import EvidencePanel
from game.ui.panels.hint import HintPanel
from game.ui.panels.journal import JournalPanel
from game.ui.panels.matrix import MatrixPanel
from game.ui.panels.respond import RespondPanel
from game.ui.panels.terminal import TerminalPanel
from game.ui.panels.timeline import TimelinePanel

TOOL_PANELS = {
    "terminal": TerminalPanel,
    "journal": JournalPanel,
    "board": BoardPanel,
    "matrix": MatrixPanel,
    "timeline": TimelinePanel,
    "respond": RespondPanel,
    "hint": HintPanel,
}

__all__ = ["Panel", "InfoPanel", "EvidencePanel", "TOOL_PANELS", "BoardPanel", "HintPanel", "JournalPanel",
           "MatrixPanel", "RespondPanel", "TerminalPanel", "TimelinePanel"]
