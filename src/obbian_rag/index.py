import hashlib
import json
import os
import uuid
from datetime import UTC, date, datetime

from qdrant_client import QdrantClient, models

from .parser import chunk_sections, parse_isolated

COLLECTION = "policies"
PIPELINE_VERSION = "parser-chunks-v1"


def corpus(settings):
    root = settings.data_dir.resolve()
    manifest = json.loads((root / "manifest.json").read_text())
    documents = manifest["documents"]
    seen = set()
    content = []
    for doc in documents:
        if doc["id"] in seen:
            raise ValueError("Duplicate document ID / conflicting active policy versions.")
        seen.add(doc["id"])
        if (
            doc["status"] != "approved"
            or date.fromisoformat(doc["effective_date"]) > datetime.now(UTC).date()
        ):
            raise ValueError("Only approved, currently effective policies can be indexed.")
        candidate = root / doc["path"]
        path = candidate.resolve()
        if candidate.is_symlink() or not path.is_relative_to(root):
            raise ValueError("Document path escapes approved corpus.")
        raw = path.read_bytes()
        if len(raw) > 10 * 1024**2 or hashlib.sha256(raw).hexdigest() != doc["sha256"]:
            raise ValueError("Document size or checksum mismatch: review the source and update manifest.")
        content.append((doc, path))
    if not content:
        raise ValueError("No approved policies found.")
    fingerprint = hashlib.sha256(
        json.dumps(
            {"manifest": manifest, "profile": settings.profile, "pipeline": PIPELINE_VERSION}, sort_keys=True
        ).encode()
    ).hexdigest()[:24]
    return content, fingerprint


def build_index(settings, provider):
    import fcntl

    settings.index_dir.mkdir(parents=True, exist_ok=True)
    with (settings.index_dir / ".ingest.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        documents, version = corpus(settings)
        destination = settings.index_dir / version
        if not (destination / "index.json").exists():
            staging = settings.index_dir / f".building-{uuid.uuid4().hex}"
            staging.mkdir()
            chunks = []
            for doc, path in documents:
                for n, part in enumerate(chunk_sections(parse_isolated(path))):
                    identifier = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{doc['id']}:{doc['sha256']}:{n}"))
                    chunks.append(
                        {
                            **part,
                            "chunk_id": identifier,
                            "document_id": doc["id"],
                            "title": doc["title"],
                            "version": doc["version"],
                            "source": doc["path"],
                        }
                    )
            if not chunks or len(chunks) > 10000:
                raise ValueError("Corpus must contain 1–10,000 chunks.")
            vectors = provider.embed([c["title"] + "\n" + c["text"] for c in chunks])
            client = QdrantClient(path=str(staging / "qdrant"))
            try:
                client.create_collection(
                    COLLECTION,
                    vectors_config=models.VectorParams(
                        size=settings.dimensions, distance=models.Distance.COSINE
                    ),
                )
                for start in range(0, len(chunks), 64):
                    client.upsert(
                        COLLECTION,
                        points=[
                            models.PointStruct(id=c["chunk_id"], vector=v, payload=c)
                            for c, v in zip(chunks[start : start + 64], vectors[start : start + 64])
                        ],
                    )
            finally:
                client.close()
            (staging / "index.json").write_text(
                json.dumps(
                    {"version": version, "profile": settings.profile, "chunks": chunks},
                    ensure_ascii=False,
                    indent=2,
                )
            )
            os.replace(staging, destination)
        current = settings.index_dir / ".CURRENT.tmp"
        current.write_text(version)
        os.replace(current, settings.index_dir / "CURRENT")
        return version


class Index:
    def __init__(self, settings):
        _, expected = corpus(settings)
        version = (settings.index_dir / "CURRENT").read_text().strip()
        if version != expected:
            raise ValueError(
                "Index does not match approved corpus/embedding profile. Run ingest and restart."
            )
        directory = settings.index_dir / version
        metadata = json.loads((directory / "index.json").read_text())
        if metadata["profile"] != settings.profile:
            raise ValueError("Embedding profile mismatch.")
        self.version = version
        self.chunks = metadata["chunks"]
        self.client = QdrantClient(path=str(directory / "qdrant"))

    def close(self):
        self.client.close()
