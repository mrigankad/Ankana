"""POST /v1/charts/{chart_id}/ask (also mounted under /api/v1).

chart_id is the chart job id from POST /api/v1/charts/generate. Returns JSON, or
Server-Sent Events when the request sets stream=true or Accept: text/event-stream
(events: status, answer, error, done).
"""

from __future__ import annotations

import json
import queue
import threading
from collections.abc import Callable
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.db import ChartArtifact, ChartRequest

from .assistant import AskResult, ask
from .providers import Provider, provider_from_env
from .tools import LalKitabProvider, load_lalkitab


class HistoryTurn(BaseModel):
    role: str
    content: str


class AskIn(BaseModel):
    question: str = Field(min_length=2, max_length=2000)
    history: list[HistoryTurn] = Field(default_factory=list)
    deep: bool = False  # opt in to the Opus "deep reading" tier
    stream: bool = False


def build_ask_router(
    engine,
    provider_factory: Callable[[], Provider | None] = provider_from_env,
    lalkitab: LalKitabProvider | None = None,
) -> APIRouter:
    router = APIRouter()
    lk = lalkitab or load_lalkitab()

    def load_artifact(chart_id: str) -> dict:
        with Session(engine) as session:
            job = session.get(ChartRequest, chart_id)
            if job is None:
                raise HTTPException(status_code=404, detail="chart not found")
            stored = session.exec(
                select(ChartArtifact).where(ChartArtifact.chartRequestId == chart_id)
            ).first()
            if stored is None:
                raise HTTPException(status_code=404, detail="artifact not ready")
            return json.loads(stored.artifactJson)

    def get_provider() -> Provider:
        provider = provider_factory()
        if provider is None:
            raise HTTPException(
                status_code=503,
                detail="AI provider not configured (set ANTHROPIC_API_KEY, OLLAMA_BASE_URL "
                       "or ANKANA_AI_PROVIDER)",
            )
        return provider

    def run(provider: Provider, artifact: dict, body: AskIn,
            on_status: Callable[[str], None] | None = None) -> AskResult:
        return ask(
            provider, artifact, body.question, now=datetime.now(tz=UTC),
            history=[t.model_dump() for t in body.history], lalkitab=lk,
            deep=body.deep, on_status=on_status,
        )

    def sse(event: str, data: dict) -> str:
        return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

    @router.post("/charts/{chart_id}/ask")
    def ask_chart(chart_id: str, body: AskIn, request: Request):
        artifact = load_artifact(chart_id)
        provider = get_provider()
        wants_stream = body.stream or "text/event-stream" in request.headers.get("accept", "")

        if not wants_stream:
            try:
                return run(provider, artifact, body).as_dict()
            except HTTPException:
                raise
            except Exception as error:  # provider/network failure
                raise HTTPException(status_code=502, detail=f"AI provider error: {error}") from error

        events: queue.Queue = queue.Queue()

        def worker() -> None:
            try:
                result = run(provider, artifact, body, lambda m: events.put(("status", {"message": m})))
                events.put(("answer", result.as_dict()))
            except Exception as error:
                events.put(("error", {"message": f"AI provider error: {error}"}))
            finally:
                events.put(("done", {}))

        threading.Thread(target=worker, daemon=True).start()

        def stream():
            while True:
                event, data = events.get()
                yield sse(event, data)
                if event == "done":
                    return

        return StreamingResponse(stream(), media_type="text/event-stream")

    return router
