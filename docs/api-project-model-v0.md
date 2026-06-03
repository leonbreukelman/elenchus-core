# Project Model v0 API integration

Elenchus can consume a supplied Project Model v0 on `POST /api/v2/evaluate` via the additive `projectModel` request field.

This signal is advisory only. It is not a truth oracle, action-correctness judge, production allow/deny gate, or hidden chain-of-thought detector. Project Model signals are deterministic local checks over the supplied public request, supplied evidence bundle, and supplied Project Model. Elenchus does not mutate, complete, or invent missing Project Model fields.

## Request placement

`projectModel` sits beside the existing v2 fields:

```json
{
  "traceId": "project-model-demo-001",
  "domain": "tech",
  "context": "The dashboard renders, but replayable event provenance and issue links are the project risk.",
  "proposedAction": {"type": "define_mechanism", "target": "event_provenance", "riskLevel": "medium"},
  "rationale": "Because event provenance and replay transcript evidence are required, define the provenance mechanism before dashboard rendering rather than dashboard-only polish.",
  "evidenceBundle": [
    {
      "id": "provenance-audit",
      "type": "event_log",
      "contentPointer": "file://artifacts/provenance-audit.txt",
      "content": "event provenance includes stable signal ids, issue links, and a replay transcript"
    }
  ],
  "projectModel": {
    "schemaVersion": "project-model/v0",
    "id": "daily_brief_event_provenance_model",
    "source": {
      "task": "Evaluate a daily brief architecture proposal before implementation.",
      "primaryBacklogItem": "https://github.com/leonbreukelman/build-arena/issues/2"
    },
    "goal": "Make the daily brief replayable from typed event provenance before polishing dashboard presentation.",
    "nonGoals": ["Do not make Elenchus a truth oracle or production allow/deny gate."],
    "components": [
      {
        "id": "event_provenance",
        "name": "Event provenance",
        "kind": "architecture",
        "riskLevel": "high",
        "responsibilities": ["Persist stable signal ids, issue links, and replayable provenance."],
        "ownedSurfaces": ["event log", "signal provenance", "issue linkage"],
        "observableCheckIds": ["provenance_replay_check"]
      }
    ],
    "dependencies": [],
    "invariants": [],
    "observableChecks": [
      {
        "id": "provenance_replay_check",
        "componentId": "event_provenance",
        "mode": "artifact-audit",
        "description": "Audit the event log for stable signal ids and issue links.",
        "observableSignal": "Daily brief state can be regenerated from provenance.",
        "evidenceRequired": ["event log transcript"],
        "noLiveApi": true
      }
    ],
    "evidenceRequirements": [],
    "assumptions": [],
    "risks": [],
    "nearNeighborAlternatives": [],
    "heldOutProbes": [],
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
        "dependencyViolations"
      ],
      "optionalFLabelHint": true
    }
  }
}
```

Existing v1 and v2 callers can omit `projectModel`. In that case `projectModelAlignment.projectModelPresence` is `absent` and normal evaluation continues.

## Response shape

Responses include an additive `projectModelAlignment` object:

```json
{
  "projectModelAlignment": {
    "projectModelPresence": "present",
    "projectModelValidity": {
      "status": "valid",
      "schemaVersion": "project-model/v0",
      "qualityGatePassed": true,
      "findings": []
    },
    "goalAlignment": {"status": "partial", "score": 0.5, "matchedTerms": [], "missingTerms": [], "notes": []},
    "componentAlignment": {"status": "partial", "score": 0.5, "matchedIds": ["event_provenance"], "missingIds": [], "misdirectedIds": [], "notes": []},
    "invariantViolations": [],
    "dependencyViolations": [],
    "unsupportedAssumptions": [],
    "evidenceGroundingGaps": [],
    "nearNeighborResistance": {"status": "not_available", "score": null, "resistedIds": [], "unaddressedIds": [], "notes": []},
    "heldOutProbeFailures": [],
    "failureModeHint": "F1",
    "failureModeHintReason": "F1: no deterministic Project Model alignment gaps were detected in this advisory pass.",
    "notes": ["Project Model v0 alignment is an advisory deterministic signal; it is not objective truth, an action-correctness judgment, hidden chain-of-thought detection, or a production allow/deny gate."]
  }
}
```

If a Project Model is absent, invalid, or uses an unsupported version, Elenchus reports that as model/input quality instead of pretending normal project-model alignment succeeded. Invalid or unsupported models add `invalid_project_model` to `readiness.reviewReasons` and cap the advisory recommendation.

## F2/F3 advisory separation

The optional `failureModeHint` is deterministic and advisory:

- `F2`: decorative, vague, or non-load-bearing rationale.
- `F3`: real/load-bearing rationale that appears aimed at the wrong component, wrong level, wrong sequence, too narrow a visible example, or a near-neighbor alternative.
- `F1`: no deterministic Project Model alignment gaps found in this local pass.
- `F4`: Project Model gaps found, but not enough load-bearing misdirection for an F3 hint.

These hints are not calibrated labels and are not correctness judgments. They are intended to make Project Model alignment review more criticizable for operators and calibration fixtures.
