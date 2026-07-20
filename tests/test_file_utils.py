"""Tests for file_utils module."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest

from hls_packager.file_utils import get_output_root, is_video_file, scan_folder


class TestIsVideoFile:
    def test_mp4(self):
        assert is_video_file(Path("clip.mp4")) is True

    def test_uppercase(self):
        assert is_video_file(Path("CLIP.MP4")) is True

    def test_mov(self):
        assert is_video_file(Path("movie.MOV")) is True

    def test_mkv(self):
        assert is_video_file(Path("film.mkv")) is True

    def test_m4v(self):
        assert is_video_file(Path("video.m4v")) is True

    def test_avi(self):
        assert is_video_file(Path("old.avi")) is True

    def test_webm(self):
        assert is_video_file(Path("stream.webm")) is True

    def test_non_video_jpg(self):
        assert is_video_file(Path("photo.jpg")) is False

    def test_non_video_json(self):
        assert is_video_file(Path("data.json")) is False

    def test_non_video_m3u8(self):
        assert is_video_file(Path("playlist.m3u8")) is False

    def test_non_video_txt(self):
        assert is_video_file(Path("readme.txt")) is False


class TestGetOutputRoot:
    def test_basic(self):
        result = get_output_root(Path("/home/user/my_project"))
        assert result == Path("/home/user/my_project_optimized")

    def test_nested(self):
        result = get_output_root(Path("/a/b/c"))
        assert result == Path("/a/b/c_optimized")

    def test_name_with_underscores(self):
        result = get_output_root(Path("/data/my_videos"))
        assert result == Path("/data/my_videos_optimized")


class TestScanFolder:
    def test_scan_mixed(self, tmp_path):
        # Setup
        (tmp_path / "sub").mkdir()
        (tmp_path / "video.mp4").write_text("fake")
        (tmp_path / "doc.json").write_text("{}")
        (tmp_path / "sub" / "clip.mkv").write_text("fake")
        (tmp_path / "sub" / "thumb.jpg").write_text("img")

        output_root = tmp_path.parent / f"{tmp_path.name}_optimized"
        items = scan_folder(tmp_path, output_root)

        video_items = [i for i in items if i.is_video]
        non_video_items = [i for i in items if not i.is_video]

        assert len(video_items) == 2
        assert len(non_video_items) == 2

    def test_video_output_is_directory_path(self, tmp_path):
        (tmp_path / "myvideo.mp4").write_text("fake")
        output_root = tmp_path.parent / f"{tmp_path.name}_optimized"
        items = scan_folder(tmp_path, output_root)

        video_items = [i for i in items if i.is_video]
        assert len(video_items) == 1
        # Output path for video is a directory (no extension, named after stem)
        assert video_items[0].output_path.name == "myvideo"
        assert video_items[0].output_path.suffix == ""

    def test_non_video_mirrors_path(self, tmp_path):
        (tmp_path / "sub").mkdir()
        (tmp_path / "sub" / "data.json").write_text("{}")
        output_root = tmp_path.parent / f"{tmp_path.name}_optimized"
        items = scan_folder(tmp_path, output_root)

        non_video = [i for i in items if not i.is_video]
        assert len(non_video) == 1
        assert non_video[0].output_path == output_root / "sub" / "data.json"

    def test_empty_folder(self, tmp_path):
        output_root = tmp_path.parent / f"{tmp_path.name}_optimized"
        items = scan_folder(tmp_path, output_root)
        assert items == []

    def test_no_videos(self, tmp_path):
        (tmp_path / "readme.txt").write_text("hello")
        output_root = tmp_path.parent / f"{tmp_path.name}_optimized"
        items = scan_folder(tmp_path, output_root)
        assert all(not i.is_video for i in items)
        assert len(items) == 1
