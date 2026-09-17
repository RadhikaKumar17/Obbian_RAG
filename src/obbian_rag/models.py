from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Question(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=3, max_length=2000)


class Citation(BaseModel):
    document_id: str
    title: str
    version: str
    source: str
    locator: str
    chunk_id: str
    quote: str


class Answer(BaseModel):
    status: Literal["answered", "abstained", "blocked", "requires_backend"]
    answer: str
    citations: list[Citation] = Field(default_factory=list)
    request_id: str = ""
    index_version: str = ""
    mode: str = ""
    latency_ms: float = 0
    usage: dict[str, int] | None = None
    trace_id: str | None = None


class Selection(BaseModel):
    """The LLM selects complete approved passages; it cannot invent answer text or URLs."""

    model_config = ConfigDict(extra="forbid", strict=True)
    sufficient: bool
    evidence_ids: list[str] = Field(max_length=4)
