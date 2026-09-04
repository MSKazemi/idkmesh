# IDKMesh developer entry points.
#
# The tiers are documented in docs/TESTING.md. Everything below delegates to
# scripts/testkit.py so the local gate, the git hooks, the Claude Code hooks
# and CI all execute the same code path and cannot drift apart.

PY := .venv/bin/python

.DEFAULT_GOAL := help

.PHONY: help setup smoke test integration nightly gate profile clean-cache

help: ## Show this help
	@echo "IDKMesh test tiers (see docs/TESTING.md):"
	@echo
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

setup: ## Create .venv and install test dependencies
	python3 -m venv .venv
	$(PY) -m pip install --disable-pip-version-check --upgrade pip
	$(PY) -m pip install --disable-pip-version-check pytest -r requirements-phase0.txt
	@echo "Environment ready. Run 'make test'."

smoke: ## Tier 1 - only the tests affected by your uncommitted changes (~1s)
	@$(PY) scripts/testkit.py smoke

test: ## Tier 2 - the full unit suite; the pre-commit gate (~35s)
	@$(PY) scripts/testkit.py unit

integration: ## Tier 3 - unit suite plus schema and link gates; the pre-push gate
	@$(PY) scripts/testkit.py integration

nightly: ## Tier 4 - everything, simulations included; no time budget
	@$(PY) scripts/testkit.py nightly

gate: ## Run whichever tier your current changes actually require
	@$(PY) scripts/testkit.py auto

profile: ## Show the 25 slowest tests - use this when a budget is exceeded
	@$(PY) -m pytest -q --durations=25 | tail -30

clean-cache: ## Forget cached tier results and force a full re-run
	@rm -f .claude/state/testkit-cache.json
	@echo "testkit cache cleared"
