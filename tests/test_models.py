"""Tests for models and rendition selection."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from hls_packager.ffmpeg import select_renditions
from hls_packager.models import FileStatus, Rendition, STANDARD_RENDITIONS


class TestSelectRenditions:
    def test_1080p_source_all_three(self):
        renditions = select_renditions(1080)
        names = [r.name for r in renditions]
        assert names == ["1080p", "720p", "480p"]

    def test_720p_source_no_1080p(self):
        renditions = select_renditions(720)
        names = [r.name for r in renditions]
        assert "1080p" not in names
        assert "720p" in names
        assert "480p" in names

    def test_480p_source_only_480p(self):
        renditions = select_renditions(480)
        names = [r.name for r in renditions]
        assert names == ["480p"]

    def test_360p_source_low_rendition(self):
        renditions = select_renditions(360)
        assert len(renditions) == 1
        assert renditions[0].name == "low"
        assert renditions[0].height == 360

    def test_240p_source_low_rendition(self):
        renditions = select_renditions(240)
        assert len(renditions) == 1
        assert renditions[0].name == "low"
        assert renditions[0].height == 240
        assert renditions[0].video_bitrate >= 400  # minimum bitrate enforced

    def test_4k_source_limited_to_1080p(self):
        # Even if source is 4K, we only produce up to 1080p
        renditions = select_renditions(2160)
        names = [r.name for r in renditions]
        assert "1080p" in names
        assert "720p" in names
        assert "480p" in names
        # No 2160p or 4K rendition
        assert all(r.height <= 1080 for r in renditions)

    def test_no_upscaling_for_479p(self):
        renditions = select_renditions(479)
        for r in renditions:
            assert r.height <= 479

    def test_low_rendition_min_bitrate(self):
        # Even for very small source, bitrate should not go below 400 kbps
        renditions = select_renditions(100)
        assert renditions[0].video_bitrate >= 400


class TestFileStatus:
    def test_enum_values_are_spanish(self):
        assert FileStatus.PENDING.value == "Pendiente"
        assert FileStatus.DONE.value == "Listo"
        assert FileStatus.ERROR.value == "Error"

    def test_all_statuses_exist(self):
        statuses = {s.name for s in FileStatus}
        assert statuses == {"PENDING", "PROCESSING", "DONE", "COPIED", "SKIPPED", "ERROR"}


class TestStandardRenditions:
    def test_three_renditions_defined(self):
        assert len(STANDARD_RENDITIONS) == 3

    def test_renditions_ordered_descending(self):
        heights = [r.height for r in STANDARD_RENDITIONS]
        assert heights == sorted(heights, reverse=True)

    def test_bitrates_positive(self):
        for r in STANDARD_RENDITIONS:
            assert r.video_bitrate > 0

    def test_rendition_names(self):
        names = [r.name for r in STANDARD_RENDITIONS]
        assert names == ["1080p", "720p", "480p"]
