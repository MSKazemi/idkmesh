# Conversation record — local gate-audit interface and GUI

**Date:** 2026-09-21  
**Base revision:** 2df1d454ff454e266c1cd4f46caa1fec0a36d232  
**Working branch:** gui/gate-audit-local-ui

## Project-owner requirement

> work on the interface and also GUI

## Repository context checked

The repository already has a dependency-free GitHub Pages front door under
docs/, while the currently installable product surface is the
idkmesh gate-audit CLI. No open issue or pull request was found that already
implements a gate-audit browser GUI.

## Implementation direction

Add a small local browser interface around the existing gate-audit engine
rather than starting a second frontend framework or copying the audit
mathematics into JavaScript.

The intended properties are:

- idkmesh gate-audit-ui [optional-input.json] starts the interface;
- it binds only to 127.0.0.1 by design;
- verdict data is posted only to the local Python process;
- the backend calls the same idkmesh.gate_audit implementation as the CLI;
- no runtime dependency is added;
- the UI can load a JSON file, show headline metrics and warnings, and export
  the generated report;
- the existing static project site remains dependency-free and does not become
  the execution surface for private audit data.

## Community impact

This gives newcomers and reviewers a lower-friction way to use the one
installable IDKMesh diagnostic without requiring them to read JSON output in a
terminal. Keeping the GUI local also avoids asking contributors to upload
potentially sensitive review verdicts to a hosted service.

## Verification plan

Add focused tests for the text parsing API, the local HTTP surface, clean
contract-error handling, the built-in example, and the new CLI command. The
branch should then pass the repository PR gate before integration.
