#!/usr/bin/env python3
"""Run one secret-safe OpenAI-compatible model smoke.

Examples:

  python scripts/smoke_openai_compatible.py \
    --base-url http://127.0.0.1:11434/v1 \
    --model qwen3:8b \
    --local

  GEMINI_API_KEY=... python scripts/smoke_openai_compatible.py \
    --base-url https://generativelanguage.googleapis.com/v1beta/openai \
    --model <configured-model> \
    --secret-env GEMINI_API_KEY
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from idkmesh.connector_errors import ConnectorError
from idkmesh.openai_compatible import OpenAICompatibleModelConfig
from idkmesh.openai_compatible_smoke import run_openai_compatible_smoke


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a bounded OpenAI-compatible probe + chat smoke."
    )
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--connection-id", default="smoke-model")
    parser.add_argument(
        "--secret-env",
        help="Environment variable containing the runtime API key. Never pass a key directly.",
    )
    parser.add_argument(
        "--local",
        action="store_true",
        help="Declare this endpoint as local/non-external processing.",
    )
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    parser.add_argument(
        "--prompt",
        default="Return a short plain-text acknowledgement.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    forbidden_literal_options = (
        "--api-key",
        "--token",
        "--authorization",
    )
    if any(
        item == option or item.startswith(option + "=")
        for item in raw_argv
        for option in forbidden_literal_options
    ):
        print(
            json.dumps(
                {
                    "error": {
                        "code": "configuration_error",
                        "message": "Literal credential CLI options are forbidden; use --secret-env.",
                        "retryable": False,
                    }
                },
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2

    args = _parser().parse_args(raw_argv)

    api_key = None
    secret_ref = None
    if args.secret_env:
        secret_ref = f"env:{args.secret_env}"
        api_key = os.environ.get(args.secret_env)
        if not api_key:
            print(
                json.dumps(
                    {
                        "error": {
                            "code": "authentication_error",
                            "message": "Requested smoke credential environment variable is unavailable.",
                            "secret_ref": secret_ref,
                        }
                    },
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
            timeout_seconds=args.timeout_seconds,
            external_processing=not args.local,
            project_spend_usd_max=0,
        )
        evidence = run_openai_compatible_smoke(
            config,
            api_key=api_key,
            prompt=args.prompt,
        )
    except (ConnectorError, ValueError) as exc:
        if isinstance(exc, ConnectorError):
            payload = exc.to_envelope()
        else:
            payload = {
                "error": {
                    "code": "configuration_error",
                    "message": str(exc),
                    "retryable": False,
                }
            }
        print(json.dumps(payload, sort_keys=True), file=sys.stderr)
        return 1

    print(json.dumps(evidence.to_dict(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
