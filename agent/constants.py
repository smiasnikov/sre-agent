"""Finite application values; no investigation instructions."""

from enum import Enum


class ToolName(str, Enum):
    CATALOGUE = "get_service_context"
    HEALTH = "get_health"
    TRACES = "get_failed_traces"
    PROPOSE = "propose_next_step"
    BLOCKER = "report_blocker"


class IncidentStatus(str, Enum):
    OPEN = "open"


class RunStatus(str, Enum):
    INVESTIGATING = "investigating"
    PROPOSED = "proposal_ready"
    BLOCKED = "blocked"


class EvidenceKind(str, Enum):
    ALERT = "alert"
    HEALTH = "health"
    TRACES = "failed_traces"


class ErrorCode(str, Enum):
    INVALID_INPUT = "invalid_input"
    INVALID_HARNESS = "invalid_harness"
    INVALID_RESPONSE = "invalid_source_response"
    OUT_OF_SCOPE = "out_of_scope"
    UNKNOWN_MAPPING = "unknown_source_mapping"
    INCOMPLETE_CONTEXT = "context_incomplete"
    INVALID_REFERENCES = "invalid_evidence_references"
    FINISHED = "investigation_finished"
    TOOL_FAILURE = "source_failure"
    SDK_FAILURE = "sdk_failure"
    TURN_LIMIT = "model_turn_limit"
    TIMEOUT = "run_timeout"
    NO_PROPOSAL = "no_terminal_decision"
    INVALID_STATE = "invalid_persisted_incident"
    STORAGE_FAILURE = "incident_storage_failure"
    REVISION_CONFLICT = "incident_revision_conflict"
    INCIDENT_EXISTS = "incident_already_exists"
    LOCK_TIMEOUT = "incident_lock_timeout"
    RUN_NOT_FINISHED = "previous_run_not_finished"


SOURCE_TOOLS = (ToolName.CATALOGUE, ToolName.HEALTH, ToolName.TRACES)
MCP_SERVER = "incident"
MCP_PREFIX = "mcp__incident__"
CATALOGUE_SOURCE = "service-catalogue"
DEFAULT_MAX_TURNS = 7
DEFAULT_TIMEOUT_SECONDS = 30.0
FIXTURE_MODEL = "claude-haiku-4-5-20251001"
FIXTURE_API_KEY = "offline-fixture-key"
ANTHROPIC_API_URL = "https://api.anthropic.com"

ALERT_ERRORS_REFERENCE = "A1"
ALERT_LATENCY_REFERENCE = "A2"
ALERT_SOURCE = "alert"
ALERT_PREFIX = "A"
CATALOGUE_PREFIX = "C"
OBSERVATION_PREFIX = "E"
MAX_WINDOW_SECONDS = 900
MAX_TRACE_SAMPLE_SIZE = 20
STATE_FORMAT_VERSION = 3
DEFAULT_LOCK_TIMEOUT_SECONDS = 1.0
LOCK_RETRY_SECONDS = 0.01
