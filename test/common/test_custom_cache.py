from unittest import TestCase
from unittest.mock import mock_open, patch

from splunk_connect_for_snmp.common.custom_cache import ttl_lru_cache


def result_of_cache(x):
    return x


class TestCustomCache(TestCase):
    @patch("time.time")
    def test_ttl(self, m_time):
        m_time.side_effect = [5, 5, 10, 15]
        cached = ttl_lru_cache(ttl=6)(result_of_cache)

        cached(1)
        assert "hits=0" in f"{cached.cache_info()}"
        assert "misses=1" in f"{cached.cache_info()}"

        cached(1)
        assert "hits=1" in f"{cached.cache_info()}"
        assert "misses=1" in f"{cached.cache_info()}"

        cached(1)
        assert "hits=1" in f"{cached.cache_info()}"
        assert "misses=2" in f"{cached.cache_info()}"

        cached.cache_clear()

    @patch("time.time")
    def test_max_size(self, m_time):
        m_time.side_effect = [5, 5, 10, 15, 20, 25]
        maxsize = 2
        cached = ttl_lru_cache(maxsize=maxsize, ttl=300)(result_of_cache)

        cached(1)
        assert "hits=0" in f"{cached.cache_info()}"
        assert "misses=1" in f"{cached.cache_info()}"
        assert f"maxsize={maxsize}" in f"{cached.cache_info()}"
        assert "currsize=1" in f"{cached.cache_info()}"

        cached(1)
        assert "hits=1" in f"{cached.cache_info()}"
        assert "misses=1" in f"{cached.cache_info()}"
        assert f"maxsize={maxsize}" in f"{cached.cache_info()}"
        assert "currsize=1" in f"{cached.cache_info()}"

        cached(2)
        assert "hits=1" in f"{cached.cache_info()}"
        assert "misses=2" in f"{cached.cache_info()}"
        assert f"maxsize={maxsize}" in f"{cached.cache_info()}"
        assert "currsize=2" in f"{cached.cache_info()}"

        cached(3)
        assert "hits=1" in f"{cached.cache_info()}"
        assert "misses=3" in f"{cached.cache_info()}"
        assert f"maxsize={maxsize}" in f"{cached.cache_info()}"
        assert "currsize=2" in f"{cached.cache_info()}"

        cached(3)
        assert "hits=2" in f"{cached.cache_info()}"
        assert "misses=3" in f"{cached.cache_info()}"
        assert f"maxsize={maxsize}" in f"{cached.cache_info()}"
        assert "currsize=2" in f"{cached.cache_info()}"

        cached.cache_clear()
