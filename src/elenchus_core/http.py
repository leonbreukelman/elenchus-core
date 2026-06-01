from __future__ import annotations

import os
from typing import Annotated, Any

from fastapi import Body, Depends, FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse, Response
from pydantic import ValidationError

from .audit import FileAuditLogger
from .evaluator import evaluate_request
from .models import EvaluationRequest, TypedAction
from .report import build_error_report

app = FastAPI(title="Elenchus Core", version="0.1.0")


def require_bearer_token(authorization: Annotated[str | None, Header()] = None) -> None:
    token = os.environ.get("ELENCHUS_API_TOKEN", "").strip()
    if not token:
        return
    if authorization != f"Bearer {token}":
        raise HTTPException(status_code=401, detail="missing or invalid bearer token")


def _fallback_request(trace_id: str = "invalid-request") -> EvaluationRequest:
    return EvaluationRequest(
        traceId=trace_id if len(trace_id) >= 3 else "invalid-request",
        domain="generic",
        context="invalid request placeholder context",
        proposedAction=TypedAction(type="invalid"),
        rationale="invalid request placeholder rationale",
    )


@app.post("/api/v2/evaluate", dependencies=[Depends(require_bearer_token)])
def evaluate_v2(body: Annotated[dict[str, Any], Body()]) -> Response:
    try:
        request = EvaluationRequest.model_validate(body)
    except ValidationError as exc:
        raw_trace = body.get("traceId")
        trace_id: str = raw_trace if isinstance(raw_trace, str) else "invalid-request"
        report = build_error_report(_fallback_request(trace_id), exc.errors()[0]["msg"])
        return JSONResponse(status_code=400, content=report.model_dump(mode="json"))
    report = evaluate_request(request, audit_logger=FileAuditLogger())
    return JSONResponse(status_code=200, content=report.model_dump(mode="json"))


@app.post("/api/v1/intercept", dependencies=[Depends(require_bearer_token)])
def intercept_v1(body: Annotated[dict[str, Any], Body()]) -> dict[str, Any]:
    try:
        request = EvaluationRequest(
            traceId=str(body.get("traceId") or "legacy-request"),
            domain="generic",
            context=str(body.get("context") or ""),
            proposedAction=TypedAction.model_validate(body.get("proposedAction") or {"type": "invalid"}),
            rationale=str(body.get("reasoning") or body.get("rationale") or ""),
        )
    except ValidationError:
        return {"score": 0, "terminalLog": ["Invalid legacy request."]}
    report = evaluate_request(request)
    score = int(round((report.overallSignal or 0.0) * 100))
    return {"score": score, "terminalLog": [f"status={report.status}", f"recommendation={report.recommendation}"]}


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}
