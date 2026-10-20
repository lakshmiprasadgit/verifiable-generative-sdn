"""Text syntax for STL formulas in configuration files.

Grammar (lowest to highest precedence):

    formula := or_expr
    or_expr := and_expr (('|' | '||' | 'or') and_expr)*
    and_expr:= until   (('&' | '&&' | 'and') until)*
    until   := unary [ 'U' '[' INT ',' INT ']' unary ]       # not chainable; use parentheses
    unary   := ('!' | '~' | 'not') unary
             | ('G' | 'always')     '[' INT ',' INT ']' unary
             | ('F' | 'eventually') '[' INT ',' INT ']' unary
             | primary
    primary := 'true' | 'false' | '(' formula ')' | SIGNAL ('<=' | '>=') NUMBER

INT bounds are non-negative integers counted in control slots. G, F and U are
operators only when directly followed by '['. Strict comparisons are rejected
(see Predicate). Derived operators expand to the core syntax of paper Eq 7.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from vgcp.stl.ast import And, Always, Eventually, Formula, Not, Or, Predicate, Top, Until, false


class ParseError(ValueError):
    pass


_TOKEN = re.compile(
    r"(?P<num>[-+]?(?:\d+\.\d*|\.\d+|\d+)(?:[eE][-+]?\d+)?)"
    r"|(?P<sym><=|>=|==|!=|&&|\|\||[<>()\[\],!~&|])"
    r"|(?P<id>[A-Za-z_][A-Za-z0-9_.]*)"
)


@dataclass(frozen=True)
class _Tok:
    kind: str  # num | sym | id | end
    text: str
    pos: int


def _tokenize(text: str) -> list[_Tok]:
    toks, pos = [], 0
    while pos < len(text):
        if text[pos].isspace():
            pos += 1
            continue
        m = _TOKEN.match(text, pos)
        if not m:
            raise ParseError(f"unexpected character {text[pos]!r} at position {pos}")
        kind = m.lastgroup
        assert kind is not None
        toks.append(_Tok(kind, m.group(), pos))
        pos = m.end()
    toks.append(_Tok("end", "", len(text)))
    return toks


class _Parser:
    def __init__(self, text: str) -> None:
        self.text = text
        self.toks = _tokenize(text)
        self.i = 0

    def peek(self, offset: int = 0) -> _Tok:
        return self.toks[min(self.i + offset, len(self.toks) - 1)]

    def take(self) -> _Tok:
        tok = self.peek()
        self.i += 1
        return tok

    def expect(self, text: str) -> _Tok:
        tok = self.take()
        if tok.text != text:
            raise ParseError(f"expected {text!r} at position {tok.pos}, found {tok.text or 'end'!r}")
        return tok

    def is_temporal(self, names: tuple[str, ...]) -> bool:
        return self.peek().kind == "id" and self.peek().text in names and self.peek(1).text == "["

    def parse(self) -> Formula:
        phi = self.or_expr()
        if self.peek().kind != "end":
            tok = self.peek()
            raise ParseError(f"unexpected {tok.text!r} at position {tok.pos}")
        return phi

    def or_expr(self) -> Formula:
        phi = self.and_expr()
        while self.peek().text in ("|", "||", "or"):
            self.take()
            phi = Or(phi, self.and_expr())
        return phi

    def and_expr(self) -> Formula:
        phi = self.until()
        while self.peek().text in ("&", "&&", "and"):
            self.take()
            phi = And(phi, self.until())
        return phi

    def until(self) -> Formula:
        left = self.unary()
        if self.is_temporal(("U",)):
            self.take()
            a, b = self.interval()
            right = self.unary()
            if self.is_temporal(("U",)):
                raise ParseError(
                    f"chained 'U' at position {self.peek().pos}; add parentheses"
                )
            return Until(left, right, a, b)
        return left

    def interval(self) -> tuple[int, int]:
        self.expect("[")
        a = self.bound()
        self.expect(",")
        b = self.bound()
        self.expect("]")
        if a > b:
            raise ParseError(f"time interval [{a},{b}] must satisfy a <= b")
        return a, b

    def bound(self) -> int:
        tok = self.take()
        if tok.kind != "num" or not tok.text.isdigit():
            raise ParseError(
                f"time bound at position {tok.pos} must be a non-negative integer "
                f"number of slots, found {tok.text or 'end'!r}"
            )
        return int(tok.text)

    def unary(self) -> Formula:
        tok = self.peek()
        if tok.text in ("!", "~", "not"):
            self.take()
            return Not(self.unary())
        if self.is_temporal(("G", "always")):
            self.take()
            a, b = self.interval()
            return Always(a, b, self.unary())
        if self.is_temporal(("F", "eventually")):
            self.take()
            a, b = self.interval()
            return Eventually(a, b, self.unary())
        return self.primary()

    def primary(self) -> Formula:
        tok = self.take()
        if tok.text == "(":
            phi = self.or_expr()
            self.expect(")")
            return phi
        if tok.kind == "id" and tok.text == "true":
            return Top()
        if tok.kind == "id" and tok.text == "false":
            return false()
        if tok.kind == "id":
            op = self.take()
            if op.text in ("<", ">", "==", "!="):
                raise ParseError(
                    f"operator {op.text!r} at position {op.pos} is not supported; "
                    "use '<=' or '>=' (robustness cannot distinguish strict comparisons)"
                )
            if op.text not in ("<=", ">="):
                raise ParseError(f"expected '<=' or '>=' after signal {tok.text!r} at position {op.pos}")
            num = self.take()
            if num.kind != "num":
                raise ParseError(f"expected a number at position {num.pos}, found {num.text or 'end'!r}")
            value = float(num.text)
            if value in (float("inf"), float("-inf")):
                raise ParseError(f"threshold {num.text!r} at position {num.pos} must be a finite number")
            return Predicate(tok.text, op.text, value)
        raise ParseError(f"unexpected {tok.text or 'end'!r} at position {tok.pos}")


def parse(text: str) -> Formula:
    if not isinstance(text, str) or not text.strip():
        raise ParseError("formula text must be a non-empty string")
    try:
        return _Parser(text).parse()
    except RecursionError:
        raise ParseError("formula is too deeply nested") from None
