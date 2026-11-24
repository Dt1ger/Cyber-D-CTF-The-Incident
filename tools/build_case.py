"""Build a Case Files artifact from a plaintext note.

    python tools/build_case.py sim_swap --flag "FLAG{sim_swap}"

Reads tools/case_sources/<id>.txt, wraps it in the layers listed in challenges/<id>.json
(listed in the order the player peels them), writes challenges/<id>.txt, and stores the
answer as a sha256 so it isn't readable in the json. Run with --all to rebuild every case
that has a source note, keeping the stored answers.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from game.systems.challenges import digest, load_challenges  # noqa: E402
from game.systems.decode import decode, encode  # noqa: E402

CHALLENGES = ROOT / "challenges"
SOURCES = ROOT / "tools" / "case_sources"


def _layers(data: dict) -> list[tuple[str, str | None]]:
    out = []
    for item in data["layers"]:
        item = {"kind": item} if isinstance(item, str) else item
        out.append((item["kind"], item.get("key")))
    return out


def build(case_id: str, flag: str | None) -> None:
    spec_path = CHALLENGES / f"{case_id}.json"
    data = json.loads(spec_path.read_text(encoding="utf-8"))
    note = (SOURCES / f"{case_id}.txt").read_text(encoding="utf-8").strip()
    layers = _layers(data)
    text = note
    for kind, key in reversed(layers):
        text = encode(kind, text, key)
    check = text
    for kind, key in layers:
        check = decode(kind, check, key)
    if check != note:
        raise SystemExit(f"{case_id}: layers don't round-trip; put rot13 after hex/base64/xor")
    if flag:
        if flag.lower() not in note.lower():
            raise SystemExit(f"{case_id}: {flag} is not in the note")
        data.pop("answer", None)
        data["answer_sha256"] = digest(flag)
    data["artifact"] = f"{case_id}.txt"
    (CHALLENGES / f"{case_id}.txt").write_text(text + "\n", encoding="utf-8")
    spec_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"{case_id}: {len(layers)} layer(s), {len(text)} characters")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("case", nargs="?", help="case id, e.g. sim_swap")
    parser.add_argument("--flag", help="the correct flag; must appear in the note")
    parser.add_argument("--all", action="store_true", help="rebuild every case with a source note")
    args = parser.parse_args()
    if args.all:
        for src in sorted(SOURCES.glob("*.txt")):
            build(src.stem, None)
    elif args.case:
        build(args.case, args.flag)
    else:
        parser.error("give a case id or --all")
    _cases, notes = load_challenges(CHALLENGES)
    for note in notes:
        print("skipped:", note)


if __name__ == "__main__":
    main()
