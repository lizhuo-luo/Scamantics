import pytest

from scamantiq.config import Settings


@pytest.fixture
def settings(tmp_path):
    return Settings(
        preset="mock",
        provider="mock",
        base_url="",
        model="cached-demo",
        api_key="",
        max_retries=1,
        cache_path=str(tmp_path / "cache.json"),
        use_cache=False,
    )
