from __future__ import annotations

import re
from collections import Counter

from .actions import action_terms
from .hash import sha256_hex
from .models import (
    EvaluationRequest,
    EvidenceArtifact,
    EvidenceGroundAssessment,
    EvidenceMechanicalStatus,
    EvidenceRefAssessment,
    EvidenceResolutionAssessment,
    EvidenceResolutionSummary,
    EvidenceSupportStatus,
    RationaleGround,
)

STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "because",
    "but",
    "by",
    "can",
    "for",
    "from",
    "has",
    "have",
    "in",
    "into",
    "is",
    "it",
    "must",
    "of",
    "on",
    "or",
    "so",
    "that",
    "the",
    "there",
    "this",
    "to",
    "was",
    "were",
    "will",
    "with",
}
TOKEN_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9_'-]*")
NUMERIC_RE = re.compile(r"(?<![a-zA-Z0-9])\d+(?:\.\d+)?%?(?![a-zA-Z0-9])")
NEGATION_RE = re.compile(r"\b(no|not|never|without|none|zero)\b")


def _clamp01(value: float) -> float:
    return round(max(0.0, min(1.0, value)), 4)


def _tokens(text: str) -> list[str]:
    return [token.lower().strip("'-") for token in TOKEN_RE.findall(text) if token.lower() not in STOPWORDS]


def _numbers(text: str) -> list[str]:
    return [match.group(0).lower() for match in NUMERIC_RE.finditer(text)]


def _artifact_index(bundle: list[EvidenceArtifact]) -> tuple[dict[str, EvidenceArtifact], set[str]]:
    counts = Counter(artifact.id for artifact in bundle)
    duplicate_ids = {artifact_id for artifact_id, count in counts.items() if count > 1}
    indexed = {artifact.id: artifact for artifact in bundle if artifact.id not in duplicate_ids}
    return indexed, duplicate_ids


def _ref_assessment(
    ref: str,
    artifacts: dict[str, EvidenceArtifact],
    duplicate_ids: set[str],
) -> tuple[EvidenceRefAssessment, float, str | None]:
    statuses: list[EvidenceMechanicalStatus] = []
    notes: list[str] = []
    artifact = artifacts.get(ref)
    if ref in duplicate_ids:
        statuses.append("duplicate_artifact_id")
        notes.append("Artifact ID is duplicated in the evidence bundle, so the ref is treated as unresolved.")
        return (
            EvidenceRefAssessment(
                artifactId=ref,
                statuses=statuses,
                pointerPresent=False,
                contentPresent=False,
                hashVerified=False,
                notes=notes,
            ),
            0.0,
            None,
        )
    if artifact is None:
        statuses.append("missing_ref")
        notes.append("No artifact with this ID exists in the task-local evidence bundle.")
        return (
            EvidenceRefAssessment(
                artifactId=ref,
                statuses=statuses,
                pointerPresent=False,
                contentPresent=False,
                hashVerified=False,
                notes=notes,
            ),
            0.0,
            None,
        )

    pointer_present = artifact.contentPointer is not None
    content_present = artifact.content is not None
    hash_verified = False
    if not pointer_present:
        statuses.append("pointer_missing")
        notes.append("Artifact has no content pointer; it can be inspected locally but cannot earn top trust.")
    if not content_present:
        statuses.append("pointer_unresolved")
        notes.append("Artifact content is not local to this request; this slice has no dereferencer.")
    if artifact.sha256 is not None:
        if artifact.content is None:
            statuses.append("hash_unverifiable")
            notes.append("sha256 was supplied without local content, so the hash cannot be verified.")
        elif sha256_hex(artifact.content) == artifact.sha256.lower():
            statuses.append("hash_verified")
            hash_verified = True
        else:
            statuses.append("hash_mismatch")
            notes.append("sha256 does not match the supplied artifact content.")

    if content_present and "hash_mismatch" not in statuses:
        statuses.append("resolved")

    if "hash_mismatch" in statuses:
        score = 0.15
    elif "pointer_unresolved" in statuses:
        score = 0.2
    elif content_present:
        score = 0.55
        if pointer_present:
            score += 0.2
        score += 0.25 if hash_verified else 0.05
    else:  # pragma: no cover - defensive fallback; absent content is classified as pointer_unresolved above.
        score = 0.0

    return (
        EvidenceRefAssessment(
            artifactId=ref,
            statuses=statuses,
            pointerPresent=pointer_present,
            contentPresent=content_present,
            hashVerified=hash_verified,
            notes=notes,
        ),
        _clamp01(score),
        artifact.content,
    )


def _action_evidence_present(request: EvaluationRequest, content: str) -> bool:
    lowered_content = content.lower()
    terms = action_terms(request.proposedAction.type)
    if request.proposedAction.target:
        terms.extend(_tokens(request.proposedAction.target))
    meaningful_terms = [term.lower() for term in terms if len(term.strip()) >= 3]
    if not meaningful_terms:
        return True
    return any(term in lowered_content for term in meaningful_terms)


def _polarity_contradicts(ground_text: str, content: str, ground_tokens: list[str]) -> bool:
    ground_negated = NEGATION_RE.search(ground_text.lower()) is not None
    content_negated = NEGATION_RE.search(content.lower()) is not None
    if ground_negated == content_negated:
        return False
    meaningful = {token for token in ground_tokens if token not in {"no", "not", "never", "without", "none", "zero"}}
    if len(meaningful) < 2:
        return False
    content_tokens = set(_tokens(content))
    shared = meaningful & content_tokens
    coverage = len(shared) / len(meaningful)
    return len(shared) >= 2 and coverage >= 0.45


def _support_for_ground(
    request: EvaluationRequest,
    ground: RationaleGround,
    cited_contents: list[str],
) -> tuple[EvidenceSupportStatus, float, list[str]]:
    notes: list[str] = []
    if not cited_contents:
        notes.append("No local cited artifact content is available for advisory support scoring.")
        return "unresolved", 0.0, notes
    combined_content = "\n".join(cited_contents).lower()
    ground_tokens = _tokens(ground.text)
    if len(ground_tokens) < 3:
        notes.append("Ground has fewer than three meaningful tokens; support defaults to unresolved.")
        return "unresolved", 0.0, notes
    missing_numbers = [number for number in _numbers(ground.text) if number not in combined_content]
    if missing_numbers:
        notes.append("At least one numeric value in the ground is absent from the cited artifact content.")
        return "unresolved", 0.0, notes
    overlap = [token for token in ground_tokens if token in combined_content]
    coverage = len(set(overlap)) / len(set(ground_tokens)) if ground_tokens else 0.0
    if coverage < 0.45:
        notes.append("Token coverage is below the frozen support threshold.")
        return "unresolved", _clamp01(coverage * 0.8), notes
    if _polarity_contradicts(ground.text, combined_content, ground_tokens):
        notes.append("Ground polarity appears to conflict with the cited artifact content; this is advisory only.")
        return "advisory_contradiction", 0.0, notes
    if not _action_evidence_present(request, combined_content):
        notes.append("Cited artifacts overlap lexically but do not contain the proposed action or target vocabulary.")
        return "unresolved", _clamp01(coverage * 0.7), notes
    return "supported", _clamp01(0.55 + coverage * 0.45), notes


def _summarize(refs: list[EvidenceRefAssessment], grounds: list[EvidenceGroundAssessment]) -> EvidenceResolutionSummary:
    summary = EvidenceResolutionSummary()
    for ref in refs:
        if "resolved" in ref.statuses:
            summary.resolved += 1
        if "missing_ref" in ref.statuses:
            summary.missingRef += 1
        if "hash_verified" in ref.statuses:
            summary.hashVerified += 1
        if "hash_mismatch" in ref.statuses:
            summary.hashMismatch += 1
        if "hash_unverifiable" in ref.statuses:
            summary.hashUnverifiable += 1
        if "pointer_missing" in ref.statuses:
            summary.pointerMissing += 1
        if "pointer_unresolved" in ref.statuses:
            summary.pointerUnresolved += 1
        if "duplicate_artifact_id" in ref.statuses:
            summary.duplicateArtifactId += 1
    for ground in grounds:
        if ground.loadBearing:
            summary.loadBearingGrounds += 1
        if "unreferenced_load_bearing_ground" in ground.mechanicalStatuses:
            summary.unreferencedLoadBearing += 1
        if ground.supportStatus == "supported":
            summary.supported += 1
        elif ground.supportStatus == "advisory_contradiction":
            summary.advisoryContradiction += 1
        else:
            summary.unresolved += 1
    return summary


def assess_evidence_resolution(request: EvaluationRequest) -> EvidenceResolutionAssessment | None:
    if request.structuredRationale is None:
        return None
    bundle = request.evidenceBundle or []
    artifacts, duplicate_ids = _artifact_index(bundle)
    ref_rows: list[EvidenceRefAssessment] = []
    ground_rows: list[EvidenceGroundAssessment] = []
    mechanical_scores: list[float] = []
    support_scores: list[float] = []
    notes: list[str] = [
        "Mechanical artifact validation is separate from advisory fuzzy support scoring.",
        "Advisory support is a conservative lexical proxy, not entailment or objective truth validation.",
    ]
    if duplicate_ids:
        notes.append("Duplicate artifact IDs were found and treated as unresolved.")

    for index, ground in enumerate(request.structuredRationale.grounds):
        statuses: list[EvidenceMechanicalStatus] = []
        cited_contents: list[str] = []
        ref_scores: list[float] = []
        if not ground.evidenceRefs and ground.loadBearing:
            statuses.append("unreferenced_load_bearing_ground")
            mechanical_score = 0.0
        else:
            for ref in ground.evidenceRefs:
                ref_row, ref_score, content = _ref_assessment(ref, artifacts, duplicate_ids)
                ref_rows.append(ref_row)
                ref_scores.append(ref_score)
                statuses.extend(ref_row.statuses)
                if content is not None and "hash_mismatch" not in ref_row.statuses and "duplicate_artifact_id" not in ref_row.statuses:
                    cited_contents.append(content)
            mechanical_score = sum(ref_scores) / len(ref_scores) if ref_scores else (0.6 if not ground.loadBearing else 0.0)
        support_status, support_score, support_notes = _support_for_ground(request, ground, cited_contents)
        ground_score = _clamp01(mechanical_score * 0.8 + support_score * 0.2)
        mechanical_scores.append(mechanical_score)
        support_scores.append(support_score)
        ground_rows.append(
            EvidenceGroundAssessment(
                index=index,
                textHash=sha256_hex(ground.text),
                evidenceRefs=list(ground.evidenceRefs),
                loadBearing=ground.loadBearing,
                mechanicalStatuses=list(dict.fromkeys(statuses)),
                supportStatus=support_status,
                mechanicalScore=_clamp01(mechanical_score),
                supportScore=support_score,
                score=ground_score,
                notes=support_notes,
            )
        )

    if not request.structuredRationale.grounds:
        notes.append("Structured rationale contains no grounds, so evidence resolution cannot earn a high score.")
        mechanical_score = 0.0
        support_score = 0.0
    else:
        load_bearing_indexes = [
            index for index, ground in enumerate(request.structuredRationale.grounds) if ground.loadBearing
        ]
        selected_mechanical = [mechanical_scores[index] for index in load_bearing_indexes] or mechanical_scores
        selected_support = [support_scores[index] for index in load_bearing_indexes] or support_scores
        mechanical_score = sum(selected_mechanical) / len(selected_mechanical) if selected_mechanical else 0.0
        support_score = sum(selected_support) / len(selected_support) if selected_support else 0.0
    summary = _summarize(ref_rows, ground_rows)
    score = _clamp01(mechanical_score * 0.8 + support_score * 0.2)
    return EvidenceResolutionAssessment(
        score=score,
        mechanicalScore=_clamp01(mechanical_score),
        supportScore=_clamp01(support_score),
        summary=summary,
        refs=ref_rows,
        grounds=ground_rows,
        notes=notes,
    )
