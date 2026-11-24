"""The Hunt Terminal query language.

    search <table> [where <conditions>] [| fields a, b] [| sort f [desc]]
                   [| head N] [| count [by f]] [| dedup f]

Conditions: field=value, field!=value, field~substring, field>N, field<N,
field>=N, field<=N, field in ("a", "b"). Combine with and / or / not and
parentheses; conditions written side by side are joined with 'and'.
String matching is case-insensitive and '=' accepts '*' wildcards.
"""

from __future__ import annotations

import difflib
import re
from collections import Counter
from dataclasses import dataclass, field

KEYWORDS = {"search", "where", "and", "or", "not", "in", "by", "asc", "desc"}
PIPE_COMMANDS = ("fields", "sort", "head", "count", "dedup")
COMPARE_OPS = {"=", "!=", "~", ">", "<", ">=", "<="}
NUM_RE = re.compile(r"-?\d+(\.\d+)?")


class QueryError(Exception):
    pass


@dataclass
class Table:
    name: str
    rows: list[dict]
    columns: list[str] = field(default_factory=list)
    description: str = ""

    @property
    def fields(self) -> list[str]:
        seen = list(self.columns)
        for row in self.rows:
            for k in row:
                if k not in seen:
                    seen.append(k)
        return seen


@dataclass
class Token:
    kind: str  # str, num, word, op
    value: str
    pos: int


@dataclass
class Query:
    table: str
    where: tuple | None
    pipes: list[tuple]


@dataclass
class QueryResult:
    table: str
    columns: list[str]
    rows: list[dict]
    matched: list[dict]
    aggregated: bool = False

    @property
    def matched_ids(self) -> set[str]:
        return {r["id"] for r in self.matched if "id" in r}


def tokenize(text: str) -> list[Token]:
    tokens: list[Token] = []
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c.isspace():
            i += 1
            continue
        if c in "\"'":
            j, buf = i + 1, []
            while j < n and text[j] != c:
                if text[j] == "\\" and j + 1 < n and text[j + 1] == c:
                    buf.append(c)
                    j += 2
                    continue
                buf.append(text[j])
                j += 1
            if j >= n:
                raise QueryError(f"Unclosed quote starting at position {i + 1}.")
            tokens.append(Token("str", "".join(buf), i))
            i = j + 1
            continue
        two = text[i:i + 2]
        if two in ("!=", ">=", "<="):
            tokens.append(Token("op", two, i))
            i += 2
            continue
        if c in "=~<>(),|":
            tokens.append(Token("op", c, i))
            i += 1
            continue
        if c == "!":
            raise QueryError("Use != for 'not equal'.")
        j = i
        while j < n and not text[j].isspace() and text[j] not in "\"'=~<>(),|!":
            j += 1
        word = text[i:j]
        tokens.append(Token("num" if NUM_RE.fullmatch(word) else "word", word, i))
        i = j
    return tokens


class Parser:
    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.i = 0

    def peek(self, k: int = 0) -> Token | None:
        idx = self.i + k
        return self.tokens[idx] if idx < len(self.tokens) else None

    def at_kw(self, *kws: str) -> bool:
        t = self.peek()
        return t is not None and t.kind == "word" and t.value.lower() in kws

    def at_op(self, *ops: str) -> bool:
        t = self.peek()
        return t is not None and t.kind == "op" and t.value in ops

    def advance(self) -> Token | None:
        t = self.peek()
        self.i += 1
        return t

    @staticmethod
    def error(msg: str):
        raise QueryError(msg)

    def parse(self) -> Query:
        if not self.at_kw("search"):
            self.error('Queries start with "search". Example: search proc where name="powershell.exe"')
        self.advance()
        t = self.advance()
        if t is None or t.kind != "word":
            self.error("Name a table after 'search'. Type 'tables' to list them.")
        table = t.value.lower()
        where = None
        if self.at_kw("where"):
            self.advance()
            if self.peek() is None or self.at_op("|"):
                self.error('"where" needs at least one condition, e.g. host="WS-FIN-0142".')
            where = self.or_()
        pipes = []
        while self.at_op("|"):
            self.advance()
            pipes.append(self.pipe())
        t = self.peek()
        if t is not None:
            self.error(f"Unexpected '{t.value}' at position {t.pos + 1}. "
                       "Missing 'and' / 'or', a quote, or a '|'?")
        return Query(table, where, pipes)

    def or_(self):
        node = self.and_()
        while self.at_kw("or"):
            self.advance()
            node = ("or", node, self.and_())
        return node

    def and_(self):
        node = self.not_()
        while True:
            if self.at_kw("and"):
                self.advance()
                node = ("and", node, self.not_())
            elif self.starts_condition():
                node = ("and", node, self.not_())
            else:
                return node

    def starts_condition(self) -> bool:
        t = self.peek()
        if t is None:
            return False
        if t.kind == "op":
            return t.value == "("
        if t.kind == "word" and t.value.lower() == "not":
            return True
        if t.kind == "word" and t.value.lower() not in KEYWORDS:
            n = self.peek(1)
            return n is not None and ((n.kind == "op" and n.value in COMPARE_OPS)
                                      or (n.kind == "word" and n.value.lower() == "in"))
        return False

    def not_(self):
        if self.at_kw("not"):
            self.advance()
            return ("not", self.not_())
        return self.atom()

    def atom(self):
        if self.at_op("("):
            self.advance()
            node = self.or_()
            if not self.at_op(")"):
                self.error("Missing ')'.")
            self.advance()
            return node
        t = self.advance()
        if t is None:
            self.error("A condition is missing after 'and' / 'or' / 'not'.")
        if t.kind != "word":
            self.error(f"Expected a field name at position {t.pos + 1}, got '{t.value}'.")
        name = t.value.lower()
        if self.at_kw("in"):
            self.advance()
            if not self.at_op("("):
                self.error('Use in ("a", "b") with parentheses.')
            self.advance()
            values = [self.value()]
            while self.at_op(","):
                self.advance()
                values.append(self.value())
            if not self.at_op(")"):
                self.error("Missing ')' after the 'in' list.")
            self.advance()
            return ("in", name, values)
        op = self.peek()
        if op is None or op.kind != "op" or op.value not in COMPARE_OPS:
            self.error(f"Expected an operator after '{t.value}': =  !=  ~  >  <  >=  <=")
        self.advance()
        return ("cmp", name, op.value, self.value())

    def value(self) -> str:
        t = self.advance()
        if t is None or t.kind == "op":
            self.error('Expected a value. Wrap text in quotes, e.g. name="cmd.exe".')
        return t.value

    def ident(self) -> str:
        t = self.advance()
        if t is None or t.kind != "word":
            self.error("Expected a field name.")
        return t.value.lower()

    def pipe(self) -> tuple:
        t = self.advance()
        if t is None or t.kind != "word" or t.value.lower() not in PIPE_COMMANDS:
            self.error("After '|' use: fields, sort, head, count, or dedup.")
        cmd = t.value.lower()
        if cmd == "fields":
            names = [self.ident()]
            while self.at_op(",") or (self.peek() is not None and self.peek().kind == "word"):
                if self.at_op(","):
                    self.advance()
                names.append(self.ident())
            return ("fields", names)
        if cmd == "sort":
            name, desc = self.ident(), False
            if self.at_kw("desc"):
                self.advance()
                desc = True
            elif self.at_kw("asc"):
                self.advance()
            return ("sort", name, desc)
        if cmd == "head":
            t = self.advance()
            if t is None or t.kind != "num":
                self.error("head needs a number, e.g. | head 10")
            return ("head", max(0, int(float(t.value))))
        if cmd == "count":
            if self.at_kw("by"):
                self.advance()
                return ("count", self.ident())
            return ("count", None)
        return ("dedup", self.ident())


def parse(text: str) -> Query:
    return Parser(tokenize(text)).parse()


def _num(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str) and NUM_RE.fullmatch(v.strip()):
        return float(v)
    return None


def _glob(pattern: str) -> re.Pattern:
    return re.compile("^" + ".*".join(re.escape(p) for p in pattern.split("*")) + "$", re.S)


def compare(actual, op: str, expected: str) -> bool:
    if actual is None or actual == "":
        return op == "!="
    if op in (">", "<", ">=", "<="):
        a, b = _num(actual), _num(expected)
        if a is None or b is None:
            a, b = str(actual).lower(), str(expected).lower()
        return {">": a > b, "<": a < b, ">=": a >= b, "<=": a <= b}[op]
    a, b = str(actual).lower(), str(expected).lower()
    if op == "~":
        return b in a
    eq = bool(_glob(b).match(a)) if "*" in b else a == b
    if not eq:
        na, nb = _num(actual), _num(expected)
        eq = na is not None and nb is not None and na == nb
    return eq if op == "=" else not eq


def evaluate(node, row: dict) -> bool:
    kind = node[0]
    if kind == "and":
        return evaluate(node[1], row) and evaluate(node[2], row)
    if kind == "or":
        return evaluate(node[1], row) or evaluate(node[2], row)
    if kind == "not":
        return not evaluate(node[1], row)
    if kind == "in":
        return any(compare(row.get(node[1]), "=", v) for v in node[2])
    return compare(row.get(node[1]), node[2], node[3])


def _fields_used(node) -> list[str]:
    if node is None:
        return []
    if node[0] in ("and", "or"):
        return _fields_used(node[1]) + _fields_used(node[2])
    if node[0] == "not":
        return _fields_used(node[1])
    return [node[1]]


def _check_field(name: str, table: Table) -> None:
    fields = table.fields
    if name in fields:
        return
    close = difflib.get_close_matches(name, fields, n=1)
    hint = f" Did you mean '{close[0]}'?" if close else ""
    raise QueryError(f"Unknown field '{name}' in table '{table.name}'.{hint} "
                     f"Fields: {', '.join(fields)}")


def _sort_key(name: str):
    def key(row):
        v = row.get(name)
        n = _num(v)
        if v is None:
            return (1, 0, 0.0, "")
        return (0, 0, n, "") if n is not None else (0, 1, 0.0, str(v).lower())
    return key


def resolve_table(name: str, tables: dict[str, Table], aliases: dict[str, str] | None = None) -> Table:
    name = (aliases or {}).get(name, name)
    if name in tables:
        return tables[name]
    close = difflib.get_close_matches(name, list(tables), n=1)
    hint = f" Did you mean '{close[0]}'?" if close else ""
    raise QueryError(f"No table named '{name}' in this zone.{hint} Tables: {', '.join(tables)}")


def execute(text: str, tables: dict[str, Table], aliases: dict[str, str] | None = None) -> QueryResult:
    q = parse(text)
    table = resolve_table(q.table, tables, aliases)
    for name in _fields_used(q.where):
        _check_field(name, table)
    matched = [r for r in table.rows if q.where is None or evaluate(q.where, r)]
    rows = list(matched)
    columns = list(table.columns or table.fields)
    aggregated = False
    for pipe in q.pipes:
        cmd = pipe[0]
        if cmd == "fields":
            for name in pipe[1]:
                _check_field(name, table)
            columns = pipe[1]
        elif cmd == "sort":
            _check_field(pipe[1], table)
            rows = sorted(rows, key=_sort_key(pipe[1]), reverse=pipe[2])
        elif cmd == "head":
            rows = rows[:pipe[1]]
        elif cmd == "dedup":
            _check_field(pipe[1], table)
            seen, unique = set(), []
            for r in rows:
                v = str(r.get(pipe[1])).lower()
                if v not in seen:
                    seen.add(v)
                    unique.append(r)
            rows = unique
        elif cmd == "count":
            aggregated = True
            if pipe[1] is None:
                rows, columns = [{"count": len(rows)}], ["count"]
            else:
                _check_field(pipe[1], table)
                counts = Counter(str(r.get(pipe[1], "")) for r in rows)
                rows = [{pipe[1]: k, "count": v} for k, v in counts.most_common()]
                columns = [pipe[1], "count"]
    return QueryResult(table.name, columns, rows, matched, aggregated)
