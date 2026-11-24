"""Case Files: challenges loaded as text from a folder.

The campaign never reads this folder. Files are parsed, not executed.
"""

from __future__ import annotations

import codecs
import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from game.systems.decode import DecodeError, decode, encode

ENCODINGS = ("base64", "hex", "xor", "rot13")
MAX_BYTES = 64 * 1024
MAX_LAYERS = 4
_ID_CHARS = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-")
_HEX = set("0123456789abcdefABCDEF")
_B64 = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=")
_FLAG = re.compile(r"FLAG\{[^}]{1,80}\}", re.I)
_ENGLISH = {"the", "and", "was", "to", "of", "on", "for", "with", "a", "in", "is", "it", "that",
            "by", "at", "from", "not", "no", "are", "our", "your", "we", "you", "then", "one"}


def digest(answer: str) -> str:
    return hashlib.sha256(answer.strip().lower().encode()).hexdigest()


@dataclass
class Challenge:
    id: str
    title: str
    clue: str
    layers: list[tuple[str, str | None]]
    answer_hash: str
    ciphertext: str
    source: str
    evidence: list[str] = field(default_factory=list)
    hints: list[str] = field(default_factory=list)
    difficulty: int = 1

    def plaintext(self) -> str:
        text = self.ciphertext
        for kind, key in self.layers:
            text = decode(kind, text, key)
        return text

    def accepts(self, answer: str) -> bool:
        return digest(answer) == self.answer_hash


@dataclass
class CaseSession:
    """One player's working copy of a case: what has been peeled so far."""

    buffer: str
    history: list[str] = field(default_factory=list)
    hints: int = 0
    misses: int = 0
    solved: bool = False

    @classmethod
    def start(cls, challenge: Challenge) -> "CaseSession":
        return cls(challenge.ciphertext)


@dataclass
class CommandResult:
    lines: list[tuple[str, str]]
    solved: bool = False


def _challenge_id(raw, stem: str) -> str | None:
    text = stem if not isinstance(raw, str) or not raw.strip() else raw.strip()
    if not text or len(text) > 40 or any(ch not in _ID_CHARS for ch in text):
        return None
    return text


def _artifact(folder: Path, name) -> str:
    if not isinstance(name, str) or name != Path(name).name or not name.lower().endswith(".txt"):
        raise ValueError("artifact must be a .txt file in this folder")
    path = (folder / name).resolve()
    if path.parent != folder.resolve():
        raise ValueError("artifact must stay inside the challenges folder")
    if not path.is_file():
        raise ValueError(f"missing artifact {name}")
    if path.stat().st_size > MAX_BYTES:
        raise ValueError(f"{name} is too large")
    return path.read_text(encoding="utf-8").strip()


def _layers(data: dict) -> list[tuple[str, str | None]]:
    raw = data.get("layers")
    if raw is None:
        raw = [{"kind": data.get("encoding", ""), "key": data.get("key")}]
    if not isinstance(raw, list) or not raw or len(raw) > MAX_LAYERS:
        raise ValueError(f"layers must list 1 to {MAX_LAYERS} encodings")
    out = []
    for item in raw:
        if isinstance(item, str):
            item = {"kind": item}
        if not isinstance(item, dict):
            raise ValueError("each layer is an encoding name or {kind, key}")
        kind = str(item.get("kind", "")).lower()
        key = item.get("key")
        if kind not in ENCODINGS:
            raise ValueError("encoding must be base64, hex, xor, or rot13")
        if key is not None and not isinstance(key, str):
            raise ValueError("key must be text")
        if kind == "xor" and not key:
            raise ValueError("xor needs a key")
        out.append((kind, key or None))
    return out


def _text_list(data: dict, name: str) -> list[str]:
    raw = data.get(name, [])
    if not isinstance(raw, list) or not all(isinstance(x, str) for x in raw):
        raise ValueError(f"{name} must be a list of text lines")
    return [x.strip() for x in raw if x.strip()]


def _one(folder: Path, path: Path) -> Challenge:
    if path.stat().st_size > MAX_BYTES:
        raise ValueError("file is too large")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("the file must be a JSON object")
    cid = _challenge_id(data.get("id"), path.stem)
    title = data.get("title")
    clue = data.get("clue")
    if cid is None:
        raise ValueError("id must be letters, numbers, _ or -")
    if not isinstance(title, str) or not title.strip():
        raise ValueError("needs a title")
    if not isinstance(clue, str) or not clue.strip():
        raise ValueError("needs a clue")
    layers = _layers(data)
    answer = data.get("answer")
    answer_hash = data.get("answer_sha256")
    if isinstance(answer, str) and answer.strip() and len(answer) <= 200:
        answer_hash = digest(answer)
    elif not (isinstance(answer_hash, str) and re.fullmatch(r"[0-9a-f]{64}", answer_hash)):
        raise ValueError("needs an answer or answer_sha256")
    if data.get("artifact"):
        ciphertext = _artifact(folder, data["artifact"])
    elif isinstance(answer, str):
        ciphertext = answer.strip()
        for kind, key in reversed(layers):
            ciphertext = encode(kind, ciphertext, key)
    else:
        raise ValueError("a hashed answer needs an artifact")
    if not ciphertext:
        raise ValueError("nothing to decode")
    difficulty = data.get("difficulty", len(layers))
    if not isinstance(difficulty, int) or not 1 <= difficulty <= 5:
        raise ValueError("difficulty must be 1 to 5")
    challenge = Challenge(cid, title.strip(), clue.strip(), layers, answer_hash, ciphertext,
                          path.name, _text_list(data, "evidence"), _text_list(data, "hints"),
                          difficulty)
    challenge.plaintext()
    return challenge


def load_challenges(folder: Path) -> tuple[list[Challenge], list[str]]:
    """Read every ``*.json`` sitting directly in ``folder``. Returns challenges and skip notes."""
    folder = Path(folder)
    if not folder.is_dir():
        return [], []
    found: list[Challenge] = []
    notes: list[str] = []
    seen: set[str] = set()
    for path in sorted(folder.glob("*.json")):
        if not path.is_file():
            continue
        try:
            challenge = _one(folder, path)
        except (OSError, ValueError, json.JSONDecodeError, DecodeError) as exc:
            notes.append(f"{path.name}: {exc}")
            continue
        if challenge.id in seen:
            notes.append(f"{path.name}: duplicate id {challenge.id}")
            continue
        seen.add(challenge.id)
        found.append(challenge)
    found.sort(key=lambda c: (c.difficulty, c.title.lower()))
    return found, notes


def _readable(text: str) -> float:
    if not text:
        return 0.0
    good = sum(1 for ch in text if (ch.isprintable() or ch in "\n\t") and ch != "\ufffd")
    return good / len(text)


def _sanitize(text: str, limit: int = 160) -> str:
    clean = "".join(ch if ch.isprintable() and ch != "\ufffd" else "." for ch in text)
    return clean if len(clean) <= limit else clean[:limit] + "..."


def _english_words(text: str) -> int:
    return sum(1 for word in re.findall(r"[a-z]+", text.lower()) if word in _ENGLISH)


def identify(text: str) -> list[tuple[str, str]]:
    """Describe what the buffer looks like without naming the answer outright."""
    body = text.strip()
    compact = body.replace(" ", "").replace("\n", "")
    if not compact:
        return [("Nothing here.", "dim")]
    lines = [(f"{len(compact)} characters.", "dim")]
    if set(compact) <= _HEX and len(compact) % 2 == 0:
        lines.append(("Only 0-9 and a-f, even length. Two characters could be one byte.", "text"))
        lines.append(("Plain hex reads as text when decoded. Hex of keyed bytes does not.", "dim"))
    elif set(compact) <= _B64 and len(compact) % 4 == 0 and "=" not in compact.rstrip("="):
        pad = " Ends in = padding." if compact.endswith("=") else ""
        lines.append((f"Upper and lower case, digits, + and /, length a multiple of 4.{pad}", "text"))
        lines.append(("That is a 64-character alphabet: 6 bits per character.", "dim"))
    elif _readable(body) < 0.9:
        lines.append(("Mostly unprintable bytes. Something keyed is probably still on top.", "warn"))
    elif _english_words(body) >= 3 and _english_words(body) > _english_words(codecs.decode(body, "rot13")):
        lines.append(("Reads as plain English. Look for what the clue asks.", "ok"))
    elif sum(ch.isalpha() for ch in body) > len(body) * 0.5 and " " in body:
        lines.append(("Word-shaped groups and normal punctuation, but the words aren't English.", "text"))
        lines.append(("Something that swaps letters keeps word lengths and punctuation intact.", "dim"))
    else:
        lines.append(("No obvious pattern.", "dim"))
    return lines


HELP = [
    ("identify            describe the current text", "dim"),
    ("decode <kind>       base64, hex, or rot13 on the current text", "dim"),
    ("decode xor <key>    hex bytes xor'd with a key (find it in the evidence)", "dim"),
    ("undo / reset        step back one decode / back to the artifact", "dim"),
    ("show                print the current text in full", "dim"),
    ("evidence            logs and notes for this case", "dim"),
    ("hint                next hint (counts against a clean solve)", "dim"),
    ("submit <flag>       answer the clue's question", "dim"),
]


def run_command(challenge: Challenge, line: str, session: CaseSession | None = None) -> CommandResult:
    session = session or CaseSession.start(challenge)
    text = line.strip()
    if not text:
        return CommandResult([])
    parts = text.split()
    cmd = parts[0].lower()
    if cmd == "help":
        return CommandResult(list(HELP))
    if cmd in ("show", "cat"):
        return CommandResult([(session.buffer, "amber")])
    if cmd == "identify":
        return CommandResult(identify(session.buffer))
    if cmd == "evidence":
        if not challenge.evidence:
            return CommandResult([("No evidence for this case. The artifact is all you get.", "dim")])
        return CommandResult([(f"[{i}] {item}", "text") for i, item in enumerate(challenge.evidence, 1)])
    if cmd == "hint":
        if not challenge.hints:
            return CommandResult([("No hints for this case.", "dim")])
        if session.hints >= len(challenge.hints):
            return CommandResult([("That was the last hint.", "dim")])
        session.hints += 1
        return CommandResult([(f"Hint {session.hints}/{len(challenge.hints)}: "
                               f"{challenge.hints[session.hints - 1]}", "warn")])
    if cmd == "reset":
        session.buffer = challenge.ciphertext
        session.history.clear()
        return CommandResult([("Back to the original artifact.", "dim")])
    if cmd == "undo":
        if not session.history:
            return CommandResult([("Nothing to undo.", "dim")])
        session.buffer = session.history.pop()
        return CommandResult([("Stepped back one decode.", "dim")])
    if cmd == "decode":
        return _decode(parts, session)
    if cmd == "submit":
        return _submit(challenge, text[len(parts[0]):].strip(), session)
    return CommandResult([("Type help for the commands.", "dim")])


def _decode(parts: list[str], session: CaseSession) -> CommandResult:
    if len(parts) < 2:
        return CommandResult([("Name the encoding: decode base64 | hex | rot13 | xor <key>. "
                               "Not sure? Type identify.", "warn")])
    kind = parts[1].lower()
    key = " ".join(parts[2:]) or None
    if kind not in ENCODINGS:
        return CommandResult([("decode supports base64, hex, rot13, and xor <key>.", "bad")])
    if kind == "xor" and not key:
        return CommandResult([("xor needs a key. Read the evidence.", "bad")])
    try:
        plain = decode(kind, session.buffer, key)
    except DecodeError as exc:
        message = "xor works on hex bytes, and this isn't hex." if kind == "xor" else str(exc)
        return CommandResult([(message, "bad")])
    session.history.append(session.buffer)
    session.buffer = plain
    if _readable(plain) < 0.9:
        return CommandResult([
            (_sanitize(plain), "dim"),
            ("Mostly unreadable. Wrong kind or wrong key, or a keyed layer is underneath. "
             "Type undo.", "warn"),
        ])
    return CommandResult([(plain, "ok")])


def _submit(challenge: Challenge, answer: str, session: CaseSession) -> CommandResult:
    if not answer:
        return CommandResult([("submit FLAG{...}", "dim")])
    if challenge.accepts(answer):
        session.solved = True
        if session.misses == 0 and session.hints == 0:
            grade = "Clean solve: no hints, no wrong answers."
        else:
            grade = f"Solved with {session.misses} wrong answer(s) and {session.hints} hint(s)."
        return CommandResult([("Flag accepted.", "ok"), (grade, "ok")], solved=True)
    session.misses += 1
    try:
        found = {f.lower() for f in _FLAG.findall(challenge.plaintext())}
    except DecodeError:
        found = set()
    if answer.lower() in found:
        return CommandResult([("That flag is in the note, but it doesn't answer the question. "
                               "Reread the clue and the evidence.", "bad")])
    return CommandResult([("That's not the flag.", "bad")])
