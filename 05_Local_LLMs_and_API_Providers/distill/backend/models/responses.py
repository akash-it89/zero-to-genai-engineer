from __future__ import annotations
"""Pydantic response models for all Distill API endpoints."""

from typing import Literal
from datetime import datetime
from pydantic import BaseModel, Field, field_validator


class KeyConcept(BaseModel):
    concept: str
    explanation: str
    topic: str


_VALID_SIGNAL_TYPES = {"student_question", "teacher_repeated", "explicit_check", "silence"}


class ConfusionZone(BaseModel):
    topic: str
    signal_type: Literal["student_question", "teacher_repeated", "explicit_check", "silence"]
    description: str
    timestamp_approx: str | None = None

    @field_validator("signal_type", mode="before")
    @classmethod
    def coerce_signal_type(cls, v: str) -> str:
        if v in _VALID_SIGNAL_TYPES:
            return v
        # Map common LLM hallucinations to the closest valid value
        v_lower = v.lower().replace("-", "_").replace(" ", "_")
        if "question" in v_lower or "ask" in v_lower:
            return "student_question"
        if "repeat" in v_lower or "rephrase" in v_lower or "re_explain" in v_lower:
            return "teacher_repeated"
        if "check" in v_lower or "understand" in v_lower or "explicit" in v_lower:
            return "explicit_check"
        if "silence" in v_lower or "pause" in v_lower:
            return "silence"
        # Generic confusion/difficulty signals → student_question as best default
        return "student_question"


class SummaryResponse(BaseModel):
    session_title: str
    topics_covered: list[str]
    key_concepts: list[KeyConcept]
    learning_objectives: list[str]
    teacher_insight: str
    confusion_zones: list[ConfusionZone]


class MCQOption(BaseModel):
    key: Literal["A", "B", "C", "D"]
    text: str


class Question(BaseModel):
    id: int
    type: Literal["mcq", "teach_it_back"]
    topic: str
    difficulty: Literal["easy", "medium", "hard"]
    bloom_level: Literal["remember", "understand", "apply", "analyze", "evaluate"] | None = None
    question: str
    options: list[MCQOption] | None = None        # MCQ only
    correct_answer: str | None = None             # MCQ only (A/B/C/D)
    explanation: str | None = None                # MCQ only
    evaluation_rubric: str | None = None          # teach_it_back only


class ConceptMapResponse(BaseModel):
    mermaid_syntax: str
    nodes: list[str] = Field(default_factory=list)
    edges: list[dict] = Field(default_factory=list)


class AnalyzeResponse(BaseModel):
    session_id: str
    summary: SummaryResponse
    questions: list[Question]
    concept_map: ConceptMapResponse


class TranscribeResponse(BaseModel):
    transcript: str
    duration_seconds: float | None = None
    language_detected: str | None = None


class MCQEvaluationResponse(BaseModel):
    is_correct: bool
    correct_answer: str
    explanation: str
    hint: str | None = None
    next_difficulty: Literal["easy", "medium", "hard"]


class DimensionScore(BaseModel):
    key: str
    label: str
    score: int = Field(ge=1, le=5)
    weight: float


class VoiceEvaluationResponse(BaseModel):
    dimension_scores: list[DimensionScore]
    weighted_score: float = Field(ge=1.0, le=5.0)
    narrative_debrief: str
    verdict: str
    verdict_type: Literal["success", "info", "warning", "error"]
    follow_up_question: str | None = None
    study_recommendations: list[str] = Field(default_factory=list)


class SessionMeta(BaseModel):
    session_id: str
    student_name: str
    session_label: str | None = None
    created_at: datetime
    mcq_score_pct: float | None = None
    overall_verdict: str | None = None
    topics_covered: list[str] = Field(default_factory=list)


class SessionResults(BaseModel):
    mcq_results: list[dict]
    voice_results: list[dict]
    topic_scores: dict[str, dict]
    overall_mcq_pct: float
    overall_voice_score: float


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded", "error"]
    llm_provider: str
    llm_model: str
    stt_provider: str
    version: str


class UIConfigResponse(BaseModel):
    brand_name: str
    brand_tagline: str
    features: dict
    assessment_config: dict
