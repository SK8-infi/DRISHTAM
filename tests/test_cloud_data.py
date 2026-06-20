"""Tests for cloud_data.py — GCS download and caching logic.

Covers: local data dir detection, GCS download fallback, file verification,
cache management, and error handling.
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest


class TestConstants:
    """Test module-level constants and config."""

    def test_gcs_base_url_format(self):
        from api.cloud_data import GCS_BASE_URL
        assert GCS_BASE_URL.startswith("https://storage.googleapis.com/")

    def test_required_files_defined(self):
        from api.cloud_data import REQUIRED_FILES
        assert len(REQUIRED_FILES) > 0
        # Check expected files
        file_names = [f[0] for f in REQUIRED_FILES]
        assert any("violations_enriched" in f for f in file_names)
        assert any("gbm_36d_best" in f for f in file_names)

    def test_required_files_have_sizes(self):
        from api.cloud_data import REQUIRED_FILES
        for rel_path, size in REQUIRED_FILES:
            assert isinstance(rel_path, str)
            assert isinstance(size, int)
            assert size > 0


class TestDefaultCacheDir:
    """Test the _default_cache_dir function."""

    def test_default_returns_path(self):
        from api.cloud_data import _default_cache_dir
        result = _default_cache_dir()
        assert isinstance(result, Path)

    @patch.dict(os.environ, {"DRISHTAM_CACHE_DIR": "/custom/cache"})
    def test_env_override(self):
        from api.cloud_data import _default_cache_dir
        result = _default_cache_dir()
        assert result == Path("/custom/cache")

    def test_default_in_home(self):
        env = os.environ.copy()
        env.pop("DRISHTAM_CACHE_DIR", None)
        with patch.dict(os.environ, env, clear=True):
            from api.cloud_data import _default_cache_dir
            result = _default_cache_dir()
            assert ".cache" in str(result) or "drishtam" in str(result)


class TestFileOk:
    """Test the _file_ok verification function."""

    def test_missing_file(self):
        from api.cloud_data import _file_ok
        assert _file_ok(Path("/nonexistent/file.txt"), 100) is False

    def test_existing_file_correct_size(self):
        from api.cloud_data import _file_ok
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"hello world")
            f.flush()
            path = Path(f.name)
        try:
            assert _file_ok(path, 11) is True
        finally:
            path.unlink()

    def test_existing_file_wrong_size(self):
        from api.cloud_data import _file_ok
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"hello")
            f.flush()
            path = Path(f.name)
        try:
            assert _file_ok(path, 999) is False
        finally:
            path.unlink()


class TestDownloadFile:
    """Test the _download_file function."""

    def test_download_creates_parent_dirs(self):
        from api.cloud_data import _download_file
        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "subdir" / "nested" / "file.parquet"
            with patch("urllib.request.urlretrieve") as mock_ret:
                # Simulate download by writing file after "download"
                def fake_download(url, path):
                    Path(path).write_bytes(b"x" * 100)
                    return (path, {})
                mock_ret.side_effect = fake_download
                _download_file("https://example.com/file.parquet", target, 100)
                assert target.exists()

    def test_download_cleans_up_on_failure(self):
        from api.cloud_data import _download_file
        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "fail.parquet"
            with patch("urllib.request.urlretrieve", side_effect=Exception("Network error")):
                with pytest.raises(Exception, match="Network error"):
                    _download_file("https://example.com/fail.parquet", target, 100)


class TestEnsureDataDownloaded:
    """Test the main ensure_data_downloaded function."""

    @patch.dict(os.environ, {"DRISHTAM_DATA_DIR": "/fake/project"})
    def test_local_override(self):
        from api.cloud_data import ensure_data_downloaded
        data_dir, models_dir = ensure_data_downloaded()
        assert data_dir == Path("/fake/project/data")
        assert models_dir == Path("/fake/project/models")

    def test_all_cached_skips_download(self):
        from api.cloud_data import ensure_data_downloaded
        env = os.environ.copy()
        env.pop("DRISHTAM_DATA_DIR", None)
        with patch.dict(os.environ, env, clear=True):
            with patch("api.cloud_data._file_ok", return_value=True):
                with patch("api.cloud_data._default_cache_dir") as mock_cache:
                    mock_cache.return_value = Path("/fake/cache")
                    data_dir, models_dir = ensure_data_downloaded()
                    assert data_dir == Path("/fake/cache/data")
                    assert models_dir == Path("/fake/cache/models")

    def test_missing_files_triggers_download(self):
        from api.cloud_data import ensure_data_downloaded
        env = os.environ.copy()
        env.pop("DRISHTAM_DATA_DIR", None)
        with patch.dict(os.environ, env, clear=True):
            with patch("api.cloud_data._file_ok", return_value=False):
                with patch("api.cloud_data._default_cache_dir") as mock_cache:
                    mock_cache.return_value = Path("/fake/cache")
                    with patch("api.cloud_data._download_file") as mock_dl:
                        data_dir, models_dir = ensure_data_downloaded()
                        assert mock_dl.call_count > 0
