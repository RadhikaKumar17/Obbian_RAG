from pathlib import Path

import pytest

from obbian_rag.config import Settings
from obbian_rag.index import Index, build_index
from obbian_rag.pipeline import Pipeline
from obbian_rag.providers import Provider


@pytest.fixture
def settings(tmp_path):
    return Settings(
        _env_file=None,
        environment="test",
        provider="offline",
        api_key="test-service-key-that-is-at-least-32-characters",
        data_dir=Path(__file__).resolve().parents[1] / "data",
        index_dir=tmp_path / "index",
    )


@pytest.fixture
def pipeline(settings):
    provider = Provider(settings)
    build_index(settings, provider)
    index = Index(settings)
    yield Pipeline(settings, provider, index)
    index.close()
    provider.close()
