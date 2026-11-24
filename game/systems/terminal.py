"""Hunt Terminal command processor. Output is a list of (text, style) lines."""

from __future__ import annotations

import re

from game.systems.decode import DecodeError, decode
from game.systems.query import QueryResult
from game.systems.zone_state import TABLE_ALIASES, ZoneState

HELP = [
    ("HUNT TERMINAL COMMANDS", "header"),
    ("  search <table> [where <conditions>] [| pipes]   run a hunt query", "normal"),
    ("  tables                 list the telemetry tables in this zone", "normal"),
    ("  fields <table>         list the fields of a table", "normal"),
    ("  examples               show example queries", "normal"),
    ("  decode <kind> <data> [key]   kind = base64, hex, xor, rot13", "normal"),
    ("                         <data> can be raw text, a row id (p-202), an evidence id, or 'cache'", "normal"),
    ("  submit <answer>        submit a flag", "normal"),
    ("  history / clear        show past commands / clear the screen", "normal"),
    ("CONDITIONS", "header"),
    ('  name="powershell.exe"   equals (case-insensitive, * wildcard)', "normal"),
    ('  cmdline~"-enc"          contains          host!="DC-01"   not equal', "normal"),
    ("  bytes_out>100000        numeric compare   and / or / not / ( )", "normal"),
    ('  name in ("net.exe", "nltest.exe")', "normal"),
    ("PIPES", "header"),
    ("  | fields a, b   | sort time [desc]   | head 10   | count by host   | dedup user", "normal"),
]

EXAMPLES = [
    ("EXAMPLE QUERIES", "header"),
    ('  search proc where parent="winword.exe" and name="powershell.exe"', "normal"),
    ('  search proc where host="WS-FIN-0142" | sort time | fields time, parent, name, cmdline', "normal"),
    ('  search net where dport=445 | count by src', "normal"),
    ('  search dns where qtype="TXT" | head 20', "normal"),
]

BLOB_PATTERNS = {
    "base64": re.compile(r"[A-Za-z0-9+/]{16,}={0,2}"),
    "hex": re.compile(r"(?:[0-9a-fA-F]{2}){6,}"),
    "xor": re.compile(r"(?:[0-9a-fA-F]{2}){4,}"),
}
MAX_WIDTH = 132
MAX_ROWS = 40


def _cell(value) -> str:
    return "" if value is None else str(value)


def format_table(result: QueryResult, max_width: int = MAX_WIDTH, max_rows: int = MAX_ROWS):
    cols = result.columns
    rows = result.rows
    if not rows:
        return [("(no results)", "dim")]
    widths = {c: max([len(c)] + [len(_cell(r.get(c))) for r in rows[:max_rows]]) for c in cols}
    budget = max_width - 2 * (len(cols) - 1)
    while sum(widths.values()) > budget:
        widest = max(widths, key=widths.get)
        if widths[widest] <= 8:
            break
        widths[widest] -= 1

    def fit(text: str, w: int) -> str:
        return text if len(text) <= w else text[: max(1, w - 1)] + "~"

    out = [("  ".join(fit(c.upper(), widths[c]).ljust(widths[c]) for c in cols), "header")]
    for r in rows[:max_rows]:
        out.append(("  ".join(fit(_cell(r.get(c)), widths[c]).ljust(widths[c]) for c in cols), "normal"))
    if len(rows) > max_rows:
        out.append((f"... {len(rows) - max_rows} more rows (use | head, | count by, or a tighter filter)",
                    "dim"))
    return out


class TerminalSession:
    def __init__(self, state: ZoneState):
        self.state = state
        self.history: list[str] = []
        self.lines: list[tuple[str, str]] = []
        self.intro()

    def intro(self) -> None:
        zone = self.state.zone
        self.lines = [(f"HALCYON SOC // HUNT TERMINAL // {zone.name.upper()}", "accent"),
                      ("Type 'help' for commands, 'tables' to see what telemetry you have.", "dim")]
        if self.state.flag_sense and zone.pivot_tip:
            self.lines.append((f"FLAG SENSE: {zone.pivot_tip}", "accent"))

    def execute(self, line: str) -> list[tuple[str, str]]:
        line = line.strip()
        if not line:
            return []
        self.history.append(line)
        out: list[tuple[str, str]] = [(f"> {line}", "prompt")]
        word, _, rest = line.partition(" ")
        cmd = word.lower()
        if cmd == "clear":
            self.lines = []
            return []
        if cmd == "help":
            out += HELP
        elif cmd == "examples":
            out += EXAMPLES
        elif cmd == "tables":
            out.append(("TABLE      ROWS  DESCRIPTION", "header"))
            for t in self.state.zone.tables.values():
                out.append((f"{t.name:<10} {len(t.rows):>4}  {t.description}", "normal"))
        elif cmd == "fields":
            name = TABLE_ALIASES.get(rest.strip().lower(), rest.strip().lower())
            table = self.state.zone.tables.get(name)
            if table is None:
                out.append((f"No table '{rest.strip()}'. Try: {', '.join(self.state.zone.tables)}", "bad"))
            else:
                out.append((f"{table.name}: {', '.join(table.fields)}", "normal"))
        elif cmd == "history":
            out += [(f"  {i + 1:>3}  {h}", "dim") for i, h in enumerate(self.history[:-1])]
        elif cmd == "decode":
            out += self._decode(rest)
        elif cmd == "submit":
            ok, msg = self.state.submit(rest)
            out.append((msg, "ok" if ok else "bad"))
        elif cmd == "search":
            result, error, feedback = self.state.run_query(line)
            if error:
                out.append((error, "bad"))
            else:
                out += format_table(result)
                note = f"{len(result.matched)} matching event(s)"
                if result.aggregated:
                    note += f", {len(result.rows)} group(s)"
                out.append((note, "dim"))
                out += [(text, style) for style, text in feedback]
        else:
            out.append((f"Unknown command '{word}'. Type 'help'.", "bad"))
        self.lines += out
        return out

    def _resolve(self, kind: str, ref: str) -> tuple[str | None, str | None]:
        """Turn 'cache', a row id, or an evidence id into the blob to decode."""
        zone = self.state.zone
        if ref.lower() == "cache":
            if not zone.puzzle:
                return None, "There's no CTF cache in this zone."
            if not self.state.flag_sense:
                return None, "No cache in sight. (Sasha's Flag Sense is what spots those.)"
            return zone.puzzle["ciphertext"], None
        pattern = BLOB_PATTERNS.get(kind)
        texts: list[str] | None = None
        for table in zone.tables.values():
            row = next((r for r in table.rows if str(r.get("id", "")).lower() == ref.lower()), None)
            if row is not None:
                texts = [str(v) for k, v in row.items() if k != "id" and isinstance(v, str)]
                break
        if texts is None and ref in zone.evidence:
            if not self.state.has_evidence(ref):
                return None, f"You haven't collected {ref} yet."
            texts = list(zone.evidence[ref].get("lines", []))
        if texts is None:
            return ref, None
        if pattern is None:
            return max(texts, key=len), None
        blobs = [m.group(0) for t in texts for m in pattern.finditer(t)]
        if not blobs:
            return None, f"Nothing that looks like {kind} in {ref}."
        return max(blobs, key=len), None

    def _decode(self, rest: str) -> list[tuple[str, str]]:
        parts = rest.split()
        if len(parts) < 2:
            return [("Usage: decode base64 <data|row id|cache>   decode hex <data>   "
                     "decode xor <hex> <key>   decode rot13 <text>", "warn")]
        kind = parts[0].lower()
        if kind == "b64":
            kind = "base64"
        key = parts[2] if kind == "xor" and len(parts) > 2 else None
        if kind == "rot13" and len(parts) > 2:
            blob, err = " ".join(parts[1:]), None
        else:
            blob, err = self._resolve(kind, parts[1])
        if err:
            return [(err, "warn")]
        if kind == "xor" and key is None and parts[1].lower() == "cache" and self.state.zone.puzzle:
            key = self.state.zone.puzzle.get("key")
        try:
            text = decode(kind, blob, key)
        except DecodeError as exc:
            return [(str(exc), "bad")]
        out = [("DECODED:", "header"), (text, "accent")]
        out += [(msg, style) for style, msg in self.state.decoded(text)]
        return out
