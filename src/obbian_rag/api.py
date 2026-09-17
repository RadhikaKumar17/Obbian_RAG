import asyncio
import hmac
import json
import logging
import time
from collections import Counter, deque
from contextlib import asynccontextmanager
from threading import Lock

import anyio
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import Settings
from .index import Index, build_index
from .models import Answer, Question
from .pipeline import Pipeline
from .providers import Provider

log = logging.getLogger("obbian_rag")


class BodyLimit:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        data = bytearray()
        while True:
            event = await receive()
            if event["type"] == "http.disconnect":
                return
            data.extend(event.get("body", b""))
            if len(data) > 8192:
                return await JSONResponse({"detail": "Request body too large."}, status_code=413)(
                    scope, receive, send
                )
            if not event.get("more_body", False):
                break
        delivered = False

        async def replay():
            nonlocal delivered
            if delivered:
                return await receive()
            delivered = True
            return {"type": "http.request", "body": bytes(data), "more_body": False}

        await self.app(scope, replay, send)


def create_app(settings=None, pipeline=None):
    settings = settings or Settings()
    security = HTTPBearer(auto_error=False)
    calls = deque()
    lock = Lock()
    metrics = Counter()
    capacity = asyncio.Semaphore(settings.max_concurrency)

    @asynccontextmanager
    async def lifespan(app):
        provider = index = None
        try:
            if pipeline is None:
                provider = Provider(settings)
                if settings.bootstrap:
                    build_index(settings, provider)
                index = Index(settings)
                app.state.pipeline = Pipeline(settings, provider, index)
            else:
                app.state.pipeline = pipeline
            yield
        finally:
            if index:
                index.close()
            if provider:
                provider.close()

    app = FastAPI(
        title="Obbian Policy RAG",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs" if settings.environment != "production" else None,
        redoc_url=None,
        openapi_url="/openapi.json" if settings.environment != "production" else None,
    )
    app.add_middleware(BodyLimit)

    def authorize(credentials: HTTPAuthorizationCredentials | None = Depends(security)):
        expected = settings.api_key.get_secret_value()
        supplied = credentials.credentials if credentials else ""
        if not expected or not hmac.compare_digest(supplied, expected):
            raise HTTPException(
                401, "Valid service authentication required.", headers={"WWW-Authenticate": "Bearer"}
            )

    @app.get("/health/live")
    def live():
        return {"status": "alive"}

    @app.get("/health/ready")
    def ready(request: Request):
        if not getattr(request.app.state, "pipeline", None):
            raise HTTPException(503, "Index is not ready.")
        return {"status": "ready", "mode": settings.provider}

    @app.get("/v1/metrics", dependencies=[Depends(authorize)])
    def statistics():
        return {"counts": dict(metrics), "scope": "single process; reset on restart"}

    @app.post("/v1/answer", response_model=Answer, dependencies=[Depends(authorize)])
    async def answer(body: Question, request: Request):
        now = time.monotonic()
        with lock:
            while calls and now - calls[0] > 60:
                calls.popleft()
            if len(calls) >= settings.requests_per_minute:
                raise HTTPException(429, "Rate limit reached.", headers={"Retry-After": "60"})
            calls.append(now)
        try:
            await asyncio.wait_for(capacity.acquire(), timeout=0.05)
        except TimeoutError:
            raise HTTPException(
                429, "Service is busy. Retry shortly.", headers={"Retry-After": "2"}
            ) from None
        try:
            result = await anyio.to_thread.run_sync(request.app.state.pipeline.ask, body.question)
            metrics[result.status] += 1
            log.info(
                json.dumps(
                    {
                        "request_id": result.request_id,
                        "status": result.status,
                        "latency_ms": result.latency_ms,
                        "index_version": result.index_version,
                    }
                )
            )
            return result
        except Exception:
            # Never expose SDK errors, raw prompts, file paths, keys or document text.
            metrics["upstream_error"] += 1
            log.warning("RAG request failed; inspect provider availability and configured models.")
            raise HTTPException(
                503, "Policy service is temporarily unavailable. Please retry.", headers={"Retry-After": "5"}
            ) from None
        finally:
            capacity.release()

    return app
