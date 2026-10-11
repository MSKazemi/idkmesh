"""Property/fuzz qualification for the strict-JSON API boundaries.

Part of the API release qualification suite (issue #745, "Property/fuzz:
JSON parser/validator fuzz; Unicode and pathological nesting"). Every
strict-JSON parser on the API path must be *total*: for any byte or string
input it either returns a dict or raises its own controlled error -- never
a raw ``RecursionError``, ``MemoryError``, or other interpreter exception
that callers do not catch.

The pathological-nesting cases are load-bearing regression coverage. Before
issue #745 the parsers let ``RecursionError`` escape on deeply nested input,
so a caller catching only its domain error (``ControlTowerInputError``,
``ProtocolError``, ...) would crash instead of rejecting the document.

Deterministic on purpose: the mutation corpus is seeded, so a failure is
reproducible from the reported case.

Class-based on purpose: module-level ``def test_*`` functions here would
change the figures ``tests/test_documented_test_counts.py`` guards.
"""

from __future__ import annotations

import random
import tempfile
import unittest
from pathlib import Path

from idkmesh import api_client as ac
from idkmesh import cli
from idkmesh import control_tower_api as cta
from idkmesh import enterprise_audit as ea

# Interpreter-level failures that must never escape a parser. Their
# appearance means the parser is not total and would take a request worker
# down rather than reject a document.
FORBIDDEN = (RecursionError, MemoryError, SystemExit, KeyboardInterrupt, TypeError)


# --- deterministic pathological corpus -------------------------------------

_VALID = '{"kind":"k","n":1,"s":"str","arr":[1,2,3],"o":{"x":null}}'


def _mutations(rng: random.Random) -> list[str]:
    """Seeded single-edit mutations of a valid document."""
    out: list[str] = []
    alphabet = '{}[]",:0123456789.eE+-truefalsnl\\u\t\n\r \x00'
    for _ in range(240):
        s = _VALID
        for _ in range(rng.randint(1, 3)):
            op = rng.randrange(4)
            if not s:
                break
            i = rng.randrange(len(s))
            if op == 0:  # delete
                s = s[:i] + s[i + 1 :]
            elif op == 1:  # insert
                s = s[:i] + rng.choice(alphabet) + s[i:]
            elif op == 2:  # replace
                s = s[:i] + rng.choice(alphabet) + s[i + 1 :]
            else:  # truncate
                s = s[: rng.randrange(len(s) + 1)]
        out.append(s)
    return out


def corpus() -> list[str]:
    """Every input the totality property must survive."""
    rng = random.Random(0x9F45)
    cases: list[str] = []

    # Pathological nesting (the regression that motivated the fix).
    for depth in (50, 500, 2000, 20000):
        cases.append("[" * depth + "]" * depth)
        cases.append('{"a":' * depth + "1" + "}" * depth)
        cases.append("[" * depth)  # truncated deep nesting

    # Duplicate keys at several depths.
    cases += [
        '{"a":1,"a":2}',
        '{"a":{"b":1,"b":2}}',
        '{"a":[{"b":1},{"b":1}],"a":[]}',
    ]

    # Non-finite constants (strict JSON forbids these).
    cases += [
        '{"a":NaN}',
        '{"a":Infinity}',
        '{"a":-Infinity}',
        '{"a":[1,NaN]}',
        '{"a":{"b":Infinity}}',
    ]

    # Unicode edge cases: lone surrogates, NUL, emoji, BOM, control chars.
    cases += [
        '{"a":"\\ud800"}',
        '{"a":"\\udfff"}',
        '{"a":"\\ud83d\\ude00"}',
        '{"a":"\\u0000"}',
        '{"a":"\\u0001"}',
        '\ufeff{"a":1}',
        '{"a":"\x01\x02"}',
        '{"é":"中"}',
    ]

    # Truncated / malformed / wrong root.
    cases += [
        '{"a":', '[1,2,', '{"a":1', '}', '{', '[', '"', 'tru', 'nul', '',
        '   ', '\t\n\r', '5', '"str"', 'true', 'null', '[]', '[1,2,3]',
        '{"a":1}}', '{{"a":1}',
    ]

    # Pathological numbers.
    cases += [
        '{"a":' + "9" * 400 + "}",
        '{"a":1e999999}',
        '{"a":-1e999999}',
        '{"a":0.' + "0" * 400 + "1}",
    ]

    cases += _mutations(rng)
    return cases


def _assert_total(
    case: unittest.TestCase,
    name: str,
    run,
    expected,
    text: str,
) -> None:
    """The parser returns a dict or raises exactly ``expected`` -- nothing else."""
    try:
        value = run()
    except FORBIDDEN as exc:  # pragma: no cover - failure path
        case.fail(f"{name}: raw {type(exc).__name__} escaped on input {text!r}")
    except expected:
        return
    except Exception as exc:  # pragma: no cover - failure path
        case.fail(
            f"{name}: unexpected {type(exc).__name__}: {exc} on input {text!r}"
        )
    else:
        case.assertIsInstance(value, dict, f"{name}: non-dict root for {text!r}")


class StrictJsonTotalityTests(unittest.TestCase):
    """For every corpus input, each parser is total."""

    def test_control_tower_parse_report_text_is_total(self) -> None:
        for text in corpus():
            _assert_total(
                self,
                "parse_report_text",
                lambda t=text: cta.parse_report_text(t),
                cta.ControlTowerInputError,
                text,
            )

    def test_api_client_json_object_is_total(self) -> None:
        for text in corpus():
            _assert_total(
                self,
                "_json_object",
                lambda t=text: ac._json_object(t.encode("utf-8", "surrogatepass")),
                ac.ProtocolError,
                text,
            )

    def test_enterprise_audit_strict_json_is_total(self) -> None:
        for text in corpus():
            _assert_total(
                self,
                "_strict_json",
                lambda t=text: ea._strict_json(t),
                ea.EnterpriseAuditError,
                text,
            )

    def test_cli_strict_json_file_is_total(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            for n, text in enumerate(corpus()):
                path = Path(tmp) / f"case{n}.json"
                path.write_bytes(text.encode("utf-8", "surrogatepass"))
                _assert_total(
                    self,
                    "_strict_json_file",
                    lambda p=path: cli._strict_json_file(str(p)),
                    ValueError,
                    text,
                )


class PathologicalNestingRegressionTests(unittest.TestCase):
    """Deep nesting is a controlled rejection, not a crash (issue #745)."""

    DEEP = "[" * 20000 + "]" * 20000

    def test_deep_array_nesting_is_a_controlled_rejection(self) -> None:
        with self.assertRaises(cta.ControlTowerInputError):
            cta.parse_report_text(self.DEEP)
        with self.assertRaises(ac.ProtocolError):
            ac._json_object(self.DEEP.encode())
        with self.assertRaises(ea.EnterpriseAuditError):
            ea._strict_json(self.DEEP)

    def test_deep_object_nesting_is_a_controlled_rejection(self) -> None:
        deep_obj = '{"a":' * 20000 + "1" + "}" * 20000
        with self.assertRaises(cta.ControlTowerInputError):
            cta.parse_report_text(deep_obj)
        with self.assertRaises(ac.ProtocolError):
            ac._json_object(deep_obj.encode())
        with self.assertRaises(ea.EnterpriseAuditError):
            ea._strict_json(deep_obj)

    def test_no_raw_recursion_error_reaches_the_caller(self) -> None:
        # Explicitly assert the forbidden class does not escape, so a future
        # refactor cannot silently reintroduce it behind a broad except.
        for parser, run in (
            ("cta", lambda: cta.parse_report_text(self.DEEP)),
            ("ac", lambda: ac._json_object(self.DEEP.encode())),
            ("ea", lambda: ea._strict_json(self.DEEP)),
        ):
            with self.subTest(parser=parser):
                with self.assertRaises(Exception) as caught:
                    run()
                self.assertNotIsInstance(caught.exception, FORBIDDEN)


class StrictRejectionPropertiesTests(unittest.TestCase):
    """Documented strict-JSON rejections hold across the shared parsers."""

    def test_duplicate_keys_are_rejected(self) -> None:
        for text in ('{"a":1,"a":2}', '{"a":{"b":1,"b":2}}'):
            with self.assertRaises(cta.ControlTowerInputError):
                cta.parse_report_text(text)
            with self.assertRaises(ac.ProtocolError):
                ac._json_object(text.encode())
            with self.assertRaises(ea.EnterpriseAuditError):
                ea._strict_json(text)

    def test_non_finite_constants_are_rejected(self) -> None:
        for text in ('{"a":NaN}', '{"a":Infinity}', '{"a":-Infinity}'):
            with self.assertRaises(cta.ControlTowerInputError):
                cta.parse_report_text(text)
            with self.assertRaises(ac.ProtocolError):
                ac._json_object(text.encode())
            with self.assertRaises(ea.EnterpriseAuditError):
                ea._strict_json(text)

    def test_non_object_roots_are_rejected(self) -> None:
        for text in ("5", '"str"', "true", "null", "[]", "[1,2,3]"):
            with self.assertRaises(cta.ControlTowerInputError):
                cta.parse_report_text(text)
            with self.assertRaises(ac.ProtocolError):
                ac._json_object(text.encode())
            with self.assertRaises(ea.EnterpriseAuditError):
                ea._strict_json(text)

    def test_valid_minimal_object_is_accepted_by_agnostic_parsers(self) -> None:
        # Sanity check that the fuzz did not over-tighten the parsers that
        # accept any JSON object (schema validation is separate for cta).
        text = '{"a":1}'
        self.assertEqual({"a": 1}, ac._json_object(text.encode()))
        self.assertEqual({"a": 1}, ea._strict_json(text))


if __name__ == "__main__":
    unittest.main()
