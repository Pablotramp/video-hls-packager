"""Tests for report and manifest generation."""
from datetime import datetime
import json
from pathlib import Path

import pytest

from hls_packager.models import PackageResult
from hls_packager.report import write_reports


def test_write_reports_generates_manifest_with_sorted_relative_paths(tmp_path: Path) -> None:
    output_root = tmp_path / "output"
    (output_root / "nested" / "video").mkdir(parents=True)
    (output_root / "nested" / "video" / "master.m3u8").write_text("#EXTM3U", encoding="utf-8")
    (output_root / "nested" / "video" / "720p_000.ts").write_text("segment", encoding="utf-8")
    (output_root / "assets").mkdir(parents=True)
    (output_root / "assets" / "poster.jpg").write_text("image", encoding="utf-8")

    # Temporary files must be excluded from the manifest.
    (output_root / "nested" / "video" / "segment.tmp").write_text("tmp", encoding="utf-8")
    (output_root / "scratch.partial").write_text("tmp", encoding="utf-8")
    (output_root / "~$lock.txt").write_text("tmp", encoding="utf-8")

    write_reports(output_root, PackageResult(), [])

    manifest = json.loads((output_root / "_manifest.json").read_text(encoding="utf-8"))
    files = manifest["files"]
    actual_files = sorted(
        path.relative_to(output_root).as_posix()
        for path in output_root.rglob("*")
        if path.is_file()
    )

    assert manifest["version"] == 1
    generated_at = datetime.fromisoformat(manifest["generatedAt"])
    assert generated_at.tzinfo is not None
    assert generated_at.utcoffset() is not None
    assert files == sorted(files)
    assert all("\\" not in path for path in files)
    assert "nested/video/segment.tmp" not in files
    assert "scratch.partial" not in files
    assert "~$lock.txt" not in files
    assert "_manifest.json" in files
    assert files == [p for p in actual_files if p not in {"nested/video/segment.tmp", "scratch.partial", "~$lock.txt"}]


def test_write_reports_raises_runtime_error_when_manifest_write_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_root = tmp_path / "output"
    output_root.mkdir(parents=True, exist_ok=True)

    original_write_text = Path.write_text

    def fail_only_manifest(self: Path, data: str, *args, **kwargs) -> int:
        if self.name == "_manifest.json":
            raise OSError("disk full")
        return original_write_text(self, data, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", fail_only_manifest)

    with pytest.raises(RuntimeError, match="Could not generate _manifest.json"):
        write_reports(output_root, PackageResult(), [])
