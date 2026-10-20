"""STL text syntax used in configs/intents.yaml."""

import pytest

from vgcp.stl import Always, And, Eventually, Not, Or, ParseError, Predicate, Top, Until, false, parse

p = Predicate("a", "<=", 1.0)
q = Predicate("b.c", ">=", -2.5)


@pytest.mark.parametrize(
    "text, expected",
    [
        ("a <= 1", p),
        ("b.c >= -2.5", q),
        ("true", Top()),
        ("false", false()),
        ("!a <= 1", Not(p)),
        ("not (a <= 1)", Not(p)),
        ("a <= 1 & b.c >= -2.5", And(p, q)),
        ("a <= 1 and b.c >= -2.5", And(p, q)),
        ("a <= 1 | b.c >= -2.5", Or(p, q)),
        ("a <= 1 || b.c >= -2.5", Or(p, q)),
        ("G[0,5](a <= 1)", Always(0, 5, p)),
        ("always[0,5] a <= 1", Always(0, 5, p)),
        ("F[2,3] a <= 1", Eventually(2, 3, p)),
        ("a <= 1 U[1,4] b.c >= -2.5", Until(p, q, 1, 4)),
        # precedence: & binds tighter than |
        ("a <= 1 | a <= 1 & b.c >= -2.5", Or(p, And(p, q))),
        # U binds tighter than &
        ("a <= 1 & a <= 1 U[0,1] b.c >= -2.5", And(p, Until(p, q, 0, 1))),
        ("G[0,5] F[0,3] a <= 1", Always(0, 5, Eventually(0, 3, p))),
        ("a <= 1e-3", Predicate("a", "<=", 0.001)),
    ],
)
def test_parse(text, expected):
    assert parse(text) == expected


def test_signal_named_like_operator():
    # "G" not followed by '[' is a signal name
    assert parse("G >= 1") == Predicate("G", ">=", 1.0)


@pytest.mark.parametrize(
    "text, fragment",
    [
        ("a < 1", "not supported"),
        ("a > 1", "not supported"),
        ("a == 1", "not supported"),
        ("G[0,1.5] a <= 1", "integer"),
        ("G[-1,2] a <= 1", "integer"),
        ("G[3,2] a <= 1", "a <= b"),
        ("a <= 1 U[0,1] a <= 1 U[0,1] a <= 1", "chained"),
        ("(a <= 1", "expected ')'"),
        ("a <= 1)", "unexpected"),
        ("a <= b", "expected a number"),
        ("a <= 1 -> a <= 1", "unexpected"),
        ("", "non-empty"),
        ("a <= 1 $", "unexpected character"),
    ],
)
def test_parse_errors(text, fragment):
    with pytest.raises(ParseError) as exc:
        parse(text)
    assert fragment in str(exc.value)
