import time
import uuid

from rank_bm25 import BM25Okapi

from .guardrails import inspect_query
from .index import COLLECTION
from .models import Answer, Citation
from .providers import tokens

MESSAGES = {
    "blocked": "I can help with rental policies, but cannot follow requests to bypass rules or expose private instructions.",
    "requires_backend": "This needs live vehicle or booking data. The standalone policy service cannot search, reserve, cancel, or track vehicles. Please use the app for that action.",
    "abstained": "The approved policies do not provide enough information to answer that reliably. Please contact Obbian support.",
}


class Pipeline:
    def __init__(self, settings, provider, index):
        self.settings, self.provider, self.index = settings, provider, index
        self.bm25 = BM25Okapi([tokens(c["title"] + " " + c["text"]) for c in index.chunks])

    def retrieve(self, question):
        vector = self.provider.embed([question], query=True)[0]
        matches = self.index.client.query_points(
            COLLECTION, query=vector, limit=min(16, len(self.index.chunks)), with_payload=True
        ).points
        lexical = self.bm25.get_scores(tokens(question))
        lexical_order = sorted(range(len(lexical)), key=lambda n: lexical[n], reverse=True)
        rank = {self.index.chunks[n]["chunk_id"]: i + 1 for i, n in enumerate(lexical_order)}
        query_tokens = set(tokens(question))
        hits = []
        for i, match in enumerate(matches):
            chunk = dict(match.payload)
            overlap = len(query_tokens & set(tokens(chunk["title"] + " " + chunk["text"]))) / max(
                1, len(query_tokens)
            )
            chunk["similarity"] = float(match.score)
            chunk["coverage"] = overlap
            chunk["score"] = 1 / (60 + i + 1) + 1 / (60 + rank[chunk["chunk_id"]])
            # Similarity is evidence relevance, not a calibrated answer-confidence probability.
            if match.score >= self.settings.min_similarity and overlap > 0:
                hits.append(chunk)
        return sorted(hits, key=lambda c: (c["score"], c["coverage"]), reverse=True)[: self.settings.top_k]

    def ask(self, question):
        started = time.monotonic()
        query, route = inspect_query(question)
        result = Answer(
            status=route or "abstained",
            answer=MESSAGES[route or "abstained"],
            request_id=uuid.uuid4().hex,
            index_version=self.index.version,
            mode=self.settings.provider,
        )
        if route is None:
            hits = self.retrieve(query)
            if hits:
                selected = self.provider.select(query, hits)
                lookup = {h["chunk_id"]: h for h in hits}
                ids = list(dict.fromkeys(selected.evidence_ids))
                if selected.sufficient and ids and all(i in lookup for i in ids):
                    # Model-authored prose is never exposed. Full passages preserve qualifications and exact numbers.
                    citations = [
                        Citation(
                            **{
                                k: lookup[i][k]
                                for k in ("document_id", "title", "version", "source", "locator", "chunk_id")
                            },
                            quote=lookup[i]["text"],
                        )
                        for i in ids
                    ]
                    result.status = "answered"
                    result.citations = citations
                    result.answer = "\n\n".join(f"{c.quote} [{n}]" for n, c in enumerate(citations, 1))
        result.latency_ms = round((time.monotonic() - started) * 1000, 2)
        return result
