import io
import sys
from pathlib import Path
import tempfile
import unittest
from unittest import mock
from urllib.error import HTTPError


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from weixin_audio_extractor.core import (  # noqa: E402
    ExtractionError,
    ParserResponseError,
    build_output_stem,
    extract_weixin_audio,
    fetch_video_profile,
    select_video_url,
)


class SelectVideoUrlTests(unittest.TestCase):
    def test_select_video_url_prefers_h264(self) -> None:
        payload = {
            "feedInfo": {
                "h264VideoInfo": {"videoUrl": "https://cdn.example.com/video-h264.mp4"},
                "h265VideoInfo": {"videoUrl": "https://cdn.example.com/video-h265.mp4"},
            }
        }

        self.assertEqual(
            select_video_url(payload),
            "https://cdn.example.com/video-h264.mp4",
        )

    def test_select_video_url_falls_back_to_h265(self) -> None:
        payload = {
            "feedInfo": {
                "h264VideoInfo": {},
                "h265VideoInfo": {"videoUrl": "https://cdn.example.com/video-h265.mp4"},
            }
        }

        self.assertEqual(
            select_video_url(payload),
            "https://cdn.example.com/video-h265.mp4",
        )

    def test_select_video_url_supports_nested_data_feed_info(self) -> None:
        payload = {
            "data": {
                "feedInfo": {
                    "h264VideoInfo": {
                        "videoUrl": "https://cdn.example.com/video-h264.mp4"
                    },
                    "h265VideoInfo": {
                        "videoUrl": "https://cdn.example.com/video-h265.mp4"
                    },
                }
            }
        }

        self.assertEqual(
            select_video_url(payload),
            "https://cdn.example.com/video-h264.mp4",
        )

    def test_select_video_url_raises_when_missing(self) -> None:
        payload = {
            "feedInfo": {
                "h264VideoInfo": {},
                "h265VideoInfo": {},
            }
        }

        with self.assertRaises(ParserResponseError):
            select_video_url(payload)


class BuildOutputStemTests(unittest.TestCase):
    def test_build_output_stem_uses_share_slug(self) -> None:
        self.assertEqual(
            build_output_stem("https://weixin.qq.com/sph/AWU0OMKvVm"),
            "weixin_AWU0OMKvVm",
        )

    def test_build_output_stem_hashes_when_path_has_no_slug(self) -> None:
        stem = build_output_stem("https://weixin.qq.com/")

        self.assertRegex(stem, r"^weixin_[0-9a-f]{10}$")


class FailureHandlingTests(unittest.TestCase):
    def test_fetch_video_profile_raises_on_http_error(self) -> None:
        http_error = HTTPError(
            url="https://parser.example.com",
            code=503,
            msg="Service Unavailable",
            hdrs=None,
            fp=io.BytesIO(b"temporarily unavailable"),
        )
        self.addCleanup(http_error.close)
        with mock.patch(
            "weixin_audio_extractor.core.request.urlopen",
            side_effect=http_error,
        ):
            with self.assertRaisesRegex(Exception, "HTTP 503"):
                fetch_video_profile("https://weixin.qq.com/sph/AWU0OMKvVm")

    def test_extract_weixin_audio_rejects_invalid_share_url(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaisesRegex(Exception, "absolute http"):
                extract_weixin_audio("not-a-url", Path(temp_dir))

    def test_extract_weixin_audio_cleans_up_video_on_ffmpeg_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)

            def fake_download(_: str, destination: Path, *, timeout: int) -> None:
                del timeout
                destination.write_bytes(b"video-bytes")

            with mock.patch(
                "weixin_audio_extractor.core.fetch_video_profile",
                return_value={
                    "feedInfo": {
                        "h264VideoInfo": {"videoUrl": "https://cdn.example.com/video.mp4"}
                    }
                },
            ), mock.patch(
                "weixin_audio_extractor.core._download_file",
                side_effect=fake_download,
            ), mock.patch(
                "weixin_audio_extractor.core._extract_audio_with_ffmpeg",
                side_effect=ExtractionError("ffmpeg failed"),
            ):
                with self.assertRaises(ExtractionError):
                    extract_weixin_audio(
                        "https://weixin.qq.com/sph/AWU0OMKvVm",
                        output_dir,
                    )

            self.assertFalse((output_dir / "weixin_AWU0OMKvVm.mp4").exists())


if __name__ == "__main__":
    unittest.main()
