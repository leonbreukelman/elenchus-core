from elenchus_core import evaluate_request
from elenchus_core.models import EvaluationRequest, TypedAction


def _project_model_v0() -> dict:
    return {
        "schemaVersion": "project-model/v0",
        "id": "daily_brief_event_provenance_model",
        "source": {
            "task": "Evaluate a daily brief architecture proposal before implementation.",
            "primaryBacklogItem": "https://github.com/leonbreukelman/build-arena/issues/2",
            "repo": "leonbreukelman/build-arena",
            "issue": "Project Model v0 parent coordination issue",
        },
        "goal": "Make the daily brief replayable from typed event provenance before polishing dashboard presentation.",
        "nonGoals": [
            "Do not make Elenchus a truth oracle or production allow/deny gate.",
            "Do not treat a visible dashboard smoke test as proof of project-level success.",
        ],
        "components": [
            {
                "id": "event_provenance",
                "name": "Event provenance",
                "kind": "architecture",
                "riskLevel": "high",
                "responsibilities": [
                    "Persist stable signal ids, issue links, and replayable provenance before rendering daily briefs.",
                    "Keep the event log as the source of truth for generated brief state.",
                ],
                "ownedSurfaces": ["event log", "signal provenance", "issue linkage"],
                "observableCheckIds": ["provenance_replay_check"],
            },
            {
                "id": "dashboard_rendering",
                "name": "Dashboard rendering",
                "kind": "source",
                "riskLevel": "medium",
                "responsibilities": [
                    "Render the daily brief from typed state after event provenance exists."
                ],
                "ownedSurfaces": ["daily brief dashboard", "HTML route smoke test"],
                "observableCheckIds": ["dashboard_state_check"],
            },
        ],
        "dependencies": [
            {
                "id": "provenance_precedes_dashboard",
                "fromComponent": "event_provenance",
                "toComponent": "dashboard_rendering",
                "kind": "precedes",
                "description": "Replayable event provenance must exist before dashboard rendering can be judged aligned.",
                "observableCheckIds": ["provenance_replay_check"],
            }
        ],
        "invariants": [
            {
                "id": "no_dashboard_only_fix",
                "description": "Do not treat dashboard-only rendering changes or visible smoke tests as sufficient without replayable event provenance.",
                "componentIds": ["event_provenance", "dashboard_rendering"],
                "observableCheckIds": ["provenance_replay_check", "dashboard_state_check"],
            }
        ],
        "observableChecks": [
            {
                "id": "provenance_replay_check",
                "componentId": "event_provenance",
                "mode": "artifact-audit",
                "description": "Audit the event log for stable signal ids, issue links, and replayable provenance.",
                "observableSignal": "The same daily brief state can be regenerated from event provenance without dashboard-only state.",
                "evidenceRequired": ["event log transcript", "issue link audit", "replay transcript"],
                "noLiveApi": True,
            },
            {
                "id": "dashboard_state_check",
                "componentId": "dashboard_rendering",
                "mode": "inspection",
                "description": "Inspect dashboard output for typed state sourced from the event log.",
                "observableSignal": "Dashboard cells map to typed event-state fields rather than copied presentation text.",
                "evidenceRequired": ["rendered dashboard sample", "state contract fixture"],
                "noLiveApi": True,
            },
        ],
        "evidenceRequirements": [
            {
                "id": "provenance_artifacts",
                "description": "Evidence must show event provenance, issue linkage, and replay behavior.",
                "acceptedArtifactTypes": ["design_doc", "event_log", "test_log", "audit_report"],
                "requiredFor": ["event_provenance", "provenance_replay_check", "no_dashboard_only_fix"],
            }
        ],
        "assumptions": [
            {
                "id": "event_log_available",
                "description": "The implementation can access an event log with signal ids and issue links.",
                "status": "assumed",
            }
        ],
        "risks": [
            {
                "id": "presentation_overfit",
                "level": "high",
                "description": "The proposal may overfit to the visible dashboard example while leaving provenance unverifiable.",
                "componentId": "event_provenance",
                "mitigation": "Use a held-out replay probe and event-log audit before accepting presentation changes.",
            }
        ],
        "nearNeighborAlternatives": [
            {
                "id": "dashboard_only_polish",
                "description": "Polish the visible dashboard route and copy without changing provenance.",
                "whyNotPrimary": "It can pass the visible smoke test while failing replayability and issue-link provenance.",
                "distinguishingEvidence": ["replay transcript", "event provenance audit"],
            }
        ],
        "heldOutProbes": [
            {
                "id": "duplicate_signal_replay_probe",
                "componentId": "event_provenance",
                "probeType": "held-out-example",
                "scenario": "A duplicate signal id appears after the dashboard route still renders a plausible table.",
                "expectedBehavior": "The proposal must explain how replayable event provenance catches the duplicate signal, not only how the dashboard looks.",
                "evidenceRequired": ["duplicate signal fixture", "replay transcript"],
            }
        ],
        "verificationGaps": [],
        "unclassifiedProjectSurface": [],
        "advisorySignalHandoff": {
            "consumer": "elenchus-core",
            "expectedFields": [
                "projectModelPresence",
                "projectModelValidity",
                "goalAlignment",
                "componentAlignment",
                "invariantViolations",
                "dependencyViolations",
                "unsupportedAssumptions",
                "evidenceGroundingGaps",
                "nearNeighborResistance",
                "heldOutProbeFailures",
            ],
            "optionalFLabelHint": True,
        },
    }


def _request_with_model(*, trace_id: str, target: str, rationale: str, structured: dict | None = None) -> EvaluationRequest:
    payload = {
        "traceId": trace_id,
        "domain": "tech",
        "context": (
            "The daily brief currently has a visible dashboard smoke test, but event provenance, "
            "stable signal ids, issue links, and replay transcript evidence are the project risk."
        ),
        "proposedAction": {"type": "define_mechanism", "target": target, "riskLevel": "medium"},
        "rationale": rationale,
        "projectModel": _project_model_v0(),
        "evidenceBundle": [
            {
                "id": "provenance-audit",
                "type": "event_log",
                "contentPointer": "file://artifacts/provenance-audit.txt",
                "content": "event provenance includes stable signal ids, issue links, and a replay transcript for duplicate signal detection",
            },
            {
                "id": "dashboard-smoke",
                "type": "test_log",
                "contentPointer": "file://artifacts/dashboard-smoke.txt",
                "content": "visible dashboard route renders a plausible daily brief table",
            },
        ],
    }
    if structured is not None:
        payload["structuredRationale"] = structured
    return EvaluationRequest.model_validate(payload)


def test_project_model_v0_request_is_additive_and_absent_for_legacy_callers():
    request = EvaluationRequest(
        traceId="legacy-project-model-absent",
        domain="sre",
        context=(
            "Postgres primary shows 95% I/O wait and 12 idle in transaction sessions older than "
            "30 minutes holding locks on audit_logs. VACUUM is blocked."
        ),
        proposedAction=TypedAction(type="terminate_idle_sessions", target="postgres", riskLevel="medium"),
        rationale=(
            "Because 12 idle in transaction sessions older than 30 minutes hold locks on audit_logs, "
            "terminating idle sessions releases the locks and unblocks VACUUM."
        ),
    )

    report = evaluate_request(request)

    assert report.status == "complete"
    assert report.projectModelAlignment.projectModelPresence == "absent"
    assert report.projectModelAlignment.projectModelValidity.status == "absent"
    assert report.projectModelAlignment.failureModeHint is None
    assert report.readiness.reviewNeeded is False


def test_valid_project_model_emits_structured_advisory_alignment_signals():
    request = _request_with_model(
        trace_id="project-model-f1-aligned",
        target="event_provenance",
        rationale=(
            "Because the event log lacks stable signal ids and issue links, define the event provenance mechanism "
            "before dashboard rendering. The provenance replay check and duplicate signal replay probe show why "
            "dashboard-only polish is a weaker near neighbor."
        ),
        structured={
            "claim": "Define replayable event provenance before dashboard rendering.",
            "grounds": [
                {
                    "text": "The event log needs stable signal ids, issue links, and a replay transcript.",
                    "evidenceRefs": ["provenance-audit"],
                    "loadBearing": True,
                }
            ],
            "warrants": ["Replayable provenance catches duplicate signal ids rather than merely rendering a visible table."],
            "rejectedAlternatives": [
                {
                    "actionId": "dashboard_only_polish",
                    "reason": "Dashboard-only polish can pass a smoke test while failing the replay transcript requirement.",
                    "evidenceRefs": ["provenance-audit"],
                }
            ],
            "uncertainty": ["Operator review still decides whether the mechanism is sufficient."],
            "wouldChangeIf": ["If the event log already had replayable signal provenance, dashboard rendering could be next."],
        },
    )

    report = evaluate_request(request)
    alignment = report.projectModelAlignment

    assert report.status == "complete"
    assert alignment.projectModelPresence == "present"
    assert alignment.projectModelValidity.status == "valid"
    assert alignment.projectModelValidity.qualityGatePassed is True
    assert alignment.goalAlignment.status in {"aligned", "partial"}
    assert "event_provenance" in alignment.componentAlignment.matchedIds
    assert alignment.invariantViolations == []
    assert alignment.dependencyViolations == []
    assert alignment.evidenceGroundingGaps == []
    assert alignment.nearNeighborResistance.status in {"resistant", "partial"}
    assert alignment.heldOutProbeFailures == []
    assert alignment.failureModeHint == "F1"
    assert "objective truth" in alignment.notes[0]


def test_invalid_project_model_is_reported_as_input_model_quality_issue():
    request = EvaluationRequest.model_validate(
        {
            "traceId": "invalid-project-model-v0",
            "domain": "tech",
            "context": "A technical proposal with enough context for evaluation.",
            "proposedAction": {"type": "define_mechanism", "target": "event_provenance"},
            "rationale": "Because provenance matters, define a mechanism for it.",
            "projectModel": {
                "schemaVersion": "project-model/v0",
                "id": "bad_model",
                "goal": "Improve things.",
                "components": [],
            },
        }
    )

    report = evaluate_request(request)
    alignment = report.projectModelAlignment

    assert report.status == "complete"
    assert alignment.projectModelPresence == "present"
    assert alignment.projectModelValidity.status == "invalid"
    assert alignment.projectModelValidity.qualityGatePassed is False
    assert alignment.projectModelValidity.findings
    assert alignment.goalAlignment.status == "not_available"
    assert "invalid_project_model" in report.readiness.reviewReasons
    assert any("Project Model v0 is invalid" in weakness for weakness in report.topWeaknesses)
    assert report.recommendation in {"reconsider", "escalate"}


def test_f2_decorative_rationale_is_not_confused_with_f3_misaimed_rationale():
    f2_request = _request_with_model(
        trace_id="project-model-f2-decorative",
        target="event_provenance",
        rationale="This is a robust and excellent best-practice improvement that aligns the project and makes everything better.",
    )
    f3_request = _request_with_model(
        trace_id="project-model-f3-dashboard-overfit",
        target="dashboard_rendering",
        rationale=(
            "Because the visible dashboard smoke test renders a plausible daily brief table, update dashboard rendering "
            "and treat the visible route as sufficient rather than building event provenance or replay transcript support."
        ),
        structured={
            "claim": "Update only dashboard rendering based on the visible smoke test.",
            "grounds": [
                {
                    "text": "The visible dashboard route renders a plausible daily brief table.",
                    "evidenceRefs": ["dashboard-smoke"],
                    "loadBearing": True,
                }
            ],
            "warrants": ["A rendered table demonstrates that the visible example works."],
            "rejectedAlternatives": [
                {"actionId": "event_provenance", "reason": "The route already renders the example."}
            ],
        },
    )

    f2_report = evaluate_request(f2_request)
    f3_report = evaluate_request(f3_request)

    assert f2_report.projectModelAlignment.failureModeHint == "F2"
    assert f3_report.projectModelAlignment.failureModeHint == "F3"
    assert f3_report.subscores is not None
    assert f2_report.subscores is not None
    assert f3_report.subscores.rationaleSpecificity > f2_report.subscores.rationaleSpecificity
    assert "event_provenance" in f3_report.projectModelAlignment.componentAlignment.missingIds
    assert f3_report.projectModelAlignment.dependencyViolations
    assert f3_report.projectModelAlignment.heldOutProbeFailures
    assert "F3" in f3_report.projectModelAlignment.failureModeHintReason


def test_project_model_report_shape_serializes_for_api_clients():
    request = _request_with_model(
        trace_id="project-model-api-shape",
        target="event_provenance",
        rationale=(
            "Because event provenance and replay transcript evidence are required, define the provenance mechanism "
            "before dashboard rendering rather than dashboard-only polish."
        ),
    )

    report = evaluate_request(request)
    body = report.model_dump(mode="json")

    assert body["projectModelAlignment"]["projectModelPresence"] == "present"
    assert body["projectModelAlignment"]["projectModelValidity"]["status"] == "valid"
    assert "goalAlignment" in body["projectModelAlignment"]
    assert "componentAlignment" in body["projectModelAlignment"]
    assert "nearNeighborResistance" in body["projectModelAlignment"]
