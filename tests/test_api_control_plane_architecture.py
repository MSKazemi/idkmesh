"""Regression guards for API-3's single control-plane architecture (#738)."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARCHITECTURE = ROOT / "docs" / "architecture" / "API_CONTROL_PLANE_ARCHITECTURE.md"


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_api3_architecture_is_current_implementation_contract():
    text = ARCHITECTURE.read_text(encoding="utf-8")
    assert "**Status:** implemented API convergence contract" in text
    assert "API-3 acceptance evidence" in text
    assert "Broader API program gates that remain open" in text


def test_api3_resource_ownership_map_covers_full_issue_scope():
    text = ARCHITECTURE.read_text(encoding="utf-8")
    required_rows = (
        "projects",
        "connections",
        "connector probes",
        "WorkUnit preview",
        "routes",
        "runs",
        "attempts/candidates",
        "verification",
        "run evidence",
        "human decisions",
        "integration handoff/execution",
        "resource/compute admission",
        "events",
    )
    for resource in required_rows:
        assert f"| {resource} |" in text


def test_cli_and_http_share_connector_control_persistence_and_read_service():
    cli = _text("idkmesh/cli.py")
    http = _text("idkmesh/control_tower_ui.py")
    read_service = _text("idkmesh/connector_control_read.py")

    assert "LocalMetadataStore(store_path)" in cli
    assert "store.record_connection(" in cli
    assert "ConnectorControlReadService(" in http
    assert "LocalMetadataStore(product_spine_store_path)" in http
    assert "self.store.list_connections_page(" in read_service


def test_cli_and_http_share_product_spine_application_service():
    cli = _text("idkmesh/cli.py")
    http = _text("idkmesh/control_tower_ui.py")

    assert "ProductSpineRunStore(" in cli
    assert "ProductSpineRunStore(" in http
    assert "LocalMetadataStore(args.store)" in cli
    assert "LocalMetadataStore(product_spine_store_path)" in http


def test_human_decision_has_one_transport_neutral_owner_and_no_http_shortcut():
    architecture = ARCHITECTURE.read_text(encoding="utf-8")
    service = _text("idkmesh/human_decision_service.py")
    http = _text("idkmesh/control_tower_ui.py")
    openapi = _text("openapi.yaml")

    assert "human_decision_service.py" in architecture
    assert "transport-neutral" in service
    assert "never dispatches work" in service
    assert "pushes Git, or" in service
    assert "/api/v1/human-decisions" not in http
    assert "/api/v1/human-decisions:" not in openapi


def test_single_api_namespace_and_current_converged_read_surfaces_are_catalogued():
    openapi = _text("openapi.yaml")
    required_paths = (
        "/api/v1/status:",
        "/api/v1/connections:",
        "/api/v1/connections/{connection_id}:",
        "/api/v1/connector-drivers:",
        "/api/v1/runs:",
        "/api/v1/runs/{run_id}:",
        "/api/v1/runs/{run_id}/attempts:",
        "/api/v1/runs/{run_id}/evidence:",
        "/api/v1/work-units:",
        "/api/v1/work-units/{work_unit_id}:",
        "/api/v1/projects/{project_id}:",
        "/api/v1/events:",
        "/api/v1/events/stream:",
    )
    for path in required_paths:
        assert path in openapi


def test_transport_authority_boundary_remains_explicit():
    text = ARCHITECTURE.read_text(encoding="utf-8").lower()
    for phrase in (
        "worker success",
        "verifier recommendation",
        "protected integration authority",
        "no shared transport is allowed to invent it",
    ):
        assert phrase in text
