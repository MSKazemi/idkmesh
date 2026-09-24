#!/usr/bin/env python3
"""Run one secret-safe OpenAI-compatible model smoke.

Examples:

  python scripts/smoke_openai_compatible.py \
    --base-url http://127.0.0.1:11434/v1 \
    --model qwen3:8b \
    --local

  MODEL_API_KEY=... python scripts/smoke_openai_compatible.py \
    --base-url <compatible-base-url> \
    --model <configured-model> \
    --secret-env MODEL_API_KEY

--secret-env takes the NAME of an environment variable, never a credential
value. The command line is scanned before argparse sees it, and argparse is
configured so that no rejected token's value can reach stdout or stderr.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

from idkmesh.connector_errors import ConnectorError
from idkmesh.openai_compatible import OpenAICompatibleModelConfig
from idkmesh.openai_compatible_smoke import run_openai_compatible_smoke


# POSIX-conventional environment variable name. A credential value
# ("sk-live-...", "AIzaSy...", "ghp_...") never matches, because every known
# key format carries a lowercase letter or a hyphen.
_ENV_NAME = re.compile(r"^[A-Z][A-Z0-9_]*$")

_KNOWN_OPTIONS = frozenset(
    {
        "-h",
        "--help",
        "--base-url",
        "--model",
        "--connection-id",
        "--secret-env",
        "--local",
        "--timeout-seconds",
        "--prompt",
    }
)


class _RejectedCommandLine(Exception):
    """A command line refused without echoing any argument value."""

    def __init__(self, message: str, *, details: dict[str, object] | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class _RedactingParser(argparse.ArgumentParser):
    """argparse that never routes an argument value into its own output.

    argparse's default diagnostics quote the offending value -- "unrecognized
    arguments: --key sk-live-...", "invalid float value: 'sk-live-...'" -- which
    writes a credential straight to stderr. Every such path is funnelled into
    _RejectedCommandLine, whose message is built here and contains option names
    only.
    """

    def error(self, message: str) -> None:  # noqa: D102 - argparse hook
        raise _RejectedCommandLine(
            "Command line was rejected; see --help for the accepted options."
        )

    def exit(self, status: int = 0, message: str | None = None) -> None:  # noqa: D102
        if status:
            raise _RejectedCommandLine(
                "Command line was rejected; see --help for the accepted options."
            )
        raise SystemExit(status)


def _parser() -> argparse.ArgumentParser:
    parser = _RedactingParser(
        description="Run a bounded OpenAI-compatible probe + chat smoke.",
        allow_abbrev=False,
    )
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--connection-id", default="smoke-model")
    parser.add_argument(
        "--secret-env",
        metavar="NAME",
        help=(
            "Name of the environment variable holding the runtime API key. "
            "Never pass a key value here."
        ),
    )
    parser.add_argument(
        "--local",
        action="store_true",
        help="Declare this endpoint as local/non-external processing.",
    )
    # Parsed as text and converted below: argparse's own type= failure quotes
    # the rejected value.
    parser.add_argument("--timeout-seconds", default="30.0")
    parser.add_argument(
        "--prompt",
        default="Return a short plain-text acknowledgement.",
    )
    return parser


def _screen_argv(raw_argv: list[str]) -> None:
    """Reject unknown or credential-shaped tokens without echoing any value.

    This replaces an enumerated denylist of literal-credential flags. Anything
    that is not a known option, and any bare token in option position, is
    refused by option NAME only.
    """

    expecting_value = False
    for token in raw_argv:
        if expecting_value:
            expecting_value = False
            continue
        if not token.startswith("-") or token == "-":
            raise _RejectedCommandLine(
                "This command takes options only; positional arguments are "
                "refused so that no value is echoed.",
            )
        name = token.split("=", 1)[0]
        if name not in _KNOWN_OPTIONS:
            # The rejected token is not echoed: an unknown option name can
            # itself be a mistyped credential.
            raise _RejectedCommandLine(
                "Unknown or literal-credential option refused; see --help and "
                "pass credentials only as --secret-env NAME."
            )
        if "=" not in token and name not in {"-h", "--help", "--local"}:
            expecting_value = True


def _envelope(
    code: str,
    message: str,
    *,
    connection_id: str | None = None,
    details: dict[str, object] | None = None,
) -> dict[str, object]:
    return ConnectorError(
        code=code,
        message=message,
        connection_id=connection_id,
        details=details or {},
    ).to_envelope()


def main(argv: list[str] | None = None) -> int:
    raw_argv = list(sys.argv[1:] if argv is None else argv)

    try:
        _screen_argv(raw_argv)
        args = _parser().parse_args(raw_argv)

        try:
            timeout_seconds = float(args.timeout_seconds)
        except (TypeError, ValueError) as exc:
            raise _RejectedCommandLine(
                "--timeout-seconds must be a positive number."
            ) from exc

        secret_ref = None
        api_key = None
        if args.secret_env is not None:
            if not _ENV_NAME.match(args.secret_env):
                raise _RejectedCommandLine(
                    "--secret-env must name an environment variable "
                    "(A-Z, 0-9 and underscore), not a credential value."
                )
            secret_ref = f"env:{args.secret_env}"
            api_key = os.environ.get(args.secret_env)
            if not api_key:
                print(
                    json.dumps(
                        _envelope(
                            "authentication_error",
                            "Requested smoke credential environment variable "
                            "is unavailable.",
                            connection_id=args.connection_id,
                            details={"secret_ref": secret_ref},
                        ),
                        sort_keys=True,
                    ),
                    file=sys.stderr,
                )
                return 2
    except _RejectedCommandLine as exc:
        print(
            json.dumps(
                _envelope(
                    "configuration_error",
                    exc.message,
                    details=exc.details,
                ),
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2

    try:
        config = OpenAICompatibleModelConfig(
            connection_id=args.connection_id,
            base_url=args.base_url,
            model=args.model,
            allowed_models=frozenset({args.model}),
            secret_ref=secret_ref,
            timeout_seconds=timeout_seconds,
            external_processing=not args.local,
            project_spend_usd_max=0,
        )
        evidence = run_openai_compatible_smoke(
            config,
            api_key=api_key,
            prompt=args.prompt,
        )
    except ConnectorError as exc:
        print(json.dumps(exc.to_envelope(), sort_keys=True), file=sys.stderr)
        return 1
    except ValueError as exc:
        print(
            json.dumps(
                _envelope("configuration_error", str(exc)),
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 1

    print(json.dumps(evidence.to_dict(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
