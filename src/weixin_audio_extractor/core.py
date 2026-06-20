from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import shutil
import ssl
import subprocess
from typing import Any
from urllib import error, parse, request

import imageio_ffmpeg


DEFAULT_PARSER_ENDPOINT = "https://sph.litao.workers.dev/api/fetch_video_profile"
DEFAULT_TIMEOUT_SECONDS = 30
VIDEO_SUFFIX = ".mp4"
AUDIO_SUFFIX = ".mp3"
METADATA_SUFFIX = ".json"
_SLUG_SANITIZER = re.compile(r"[^A-Za-z0-9._-]+")
_BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/137.0.0.0 Safari/537.36"
)


class WeixinAudioExtractorError(RuntimeError):
    """Base exception for user-facing extraction failures."""


class ParserRequestError(WeixinAudioExtractorError):
    """Raised when the parser endpoint cannot be reached successfully."""


class ParserResponseError(WeixinAudioExtractorError):
    """Raised when the parser endpoint returns an unusable payload."""


class DownloadError(WeixinAudioExtractorError):
    """Raised when the resolved video cannot be downloaded."""


class ExtractionError(WeixinAudioExtractorError):
    """Raised when ffmpeg fails to extract audio."""


@dataclass(frozen=True)
class ExtractionResult:
    share_url: str
    source_video_url: str
    audio_path: Path
    metadata_path: Path
    video_path: Path | None

    def to_dict(self) -> dict[str, str | None]:
        return {
            "share_url": self.share_url,
            "source_video_url": self.source_video_url,
            "audio_path": str(self.audio_path),
            "metadata_path": str(self.metadata_path),
            "video_path": str(self.video_path) if self.video_path is not None else None,
        }


def fetch_video_profile(
    share_url: str,
    *,
    parser_endpoint: str = DEFAULT_PARSER_ENDPOINT,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    _validate_share_url(share_url)
    payload = json.dumps({"url": share_url}).encode("utf-8")
    parser_request = request.Request(
        parser_endpoint,
        data=payload,
        headers={
            "Accept": "application/json",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Content-Type": "application/json",
            "Origin": "https://weixin.qq.com",
            "Referer": "https://weixin.qq.com/",
            "User-Agent": _BROWSER_USER_AGENT,
        },
        method="POST",
    )

    try:
        with request.urlopen(
            parser_request,
            timeout=timeout,
            context=_build_ssl_context(),
        ) as response:
            raw_body = response.read().decode("utf-8")
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace").strip()
        raise ParserRequestError(
            f"Parser request failed with HTTP {exc.code}: {body or exc.reason}"
        ) from exc
    except (error.URLError, OSError) as exc:
        raise ParserRequestError(f"Parser request failed: {exc}") from exc

    try:
        data = json.loads(raw_body)
    except json.JSONDecodeError as exc:
        raise ParserResponseError("Parser response was not valid JSON.") from exc

    if not isinstance(data, dict):
        raise ParserResponseError("Parser response was not a JSON object.")

    return data


def select_video_url(profile: dict[str, Any]) -> str:
    feed_info = _extract_feed_info(profile)
    if not isinstance(feed_info, dict):
        raise ParserResponseError("Parser response did not contain feedInfo.")

    for key in ("h264VideoInfo", "h265VideoInfo"):
        candidate = feed_info.get(key)
        if not isinstance(candidate, dict):
            continue
        video_url = candidate.get("videoUrl")
        if isinstance(video_url, str) and video_url.strip():
            return video_url.strip()

    raise ParserResponseError(
        "Parser response did not contain an H.264 or H.265 video URL."
    )


def build_output_stem(share_url: str) -> str:
    parsed_url = parse.urlparse(share_url)
    segments = [segment for segment in parsed_url.path.split("/") if segment]
    if segments:
        slug = _sanitize_slug(parse.unquote(segments[-1]))
    else:
        slug = ""

    if not slug:
        slug = hashlib.sha1(share_url.encode("utf-8")).hexdigest()[:10]

    return f"weixin_{slug}"


def extract_weixin_audio(
    share_url: str,
    output_dir: Path,
    *,
    keep_video: bool = False,
    parser_endpoint: str = DEFAULT_PARSER_ENDPOINT,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> ExtractionResult:
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = build_output_stem(share_url)
    audio_path = output_dir / f"{stem}{AUDIO_SUFFIX}"
    metadata_path = output_dir / f"{stem}{METADATA_SUFFIX}"
    video_path = output_dir / f"{stem}{VIDEO_SUFFIX}"

    profile = fetch_video_profile(
        share_url,
        parser_endpoint=parser_endpoint,
        timeout=timeout,
    )
    source_video_url = select_video_url(profile)

    _write_metadata(profile, metadata_path)
    _download_file(source_video_url, video_path, timeout=timeout)

    try:
        _extract_audio_with_ffmpeg(video_path, audio_path)
    finally:
        if not keep_video and video_path.exists():
            video_path.unlink()

    return ExtractionResult(
        share_url=share_url,
        source_video_url=source_video_url,
        audio_path=audio_path,
        metadata_path=metadata_path,
        video_path=video_path if keep_video else None,
    )


def _sanitize_slug(raw_slug: str) -> str:
    sanitized = _SLUG_SANITIZER.sub("-", raw_slug).strip("-._")
    return sanitized[:64]


def _extract_feed_info(profile: dict[str, Any]) -> dict[str, Any] | None:
    direct_feed_info = profile.get("feedInfo")
    if isinstance(direct_feed_info, dict):
        return direct_feed_info

    data = profile.get("data")
    if not isinstance(data, dict):
        return None

    nested_feed_info = data.get("feedInfo")
    if isinstance(nested_feed_info, dict):
        return nested_feed_info

    return None


def _validate_share_url(share_url: str) -> None:
    parsed_url = parse.urlparse(share_url)
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
        raise WeixinAudioExtractorError(
            "Share URL must be an absolute http(s) URL."
        )


def _build_ssl_context() -> ssl.SSLContext:
    context = ssl.create_default_context()
    if hasattr(context, "set_alpn_protocols"):
        context.set_alpn_protocols(["http/1.1"])
    return context


def _write_metadata(profile: dict[str, Any], metadata_path: Path) -> None:
    try:
        metadata_path.write_text(
            json.dumps(profile, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError as exc:
        raise WeixinAudioExtractorError(
            f"Failed to write metadata file: {metadata_path}"
        ) from exc


def _download_file(source_url: str, destination: Path, *, timeout: int) -> None:
    try:
        with request.urlopen(
            source_url,
            timeout=timeout,
            context=_build_ssl_context(),
        ) as response:
            with destination.open("wb") as handle:
                shutil.copyfileobj(response, handle)
    except (error.URLError, OSError) as exc:
        raise DownloadError(f"Failed to download video from {source_url}") from exc


def _extract_audio_with_ffmpeg(video_path: Path, audio_path: Path) -> None:
    ffmpeg_executable = imageio_ffmpeg.get_ffmpeg_exe()
    command = [
        ffmpeg_executable,
        "-y",
        "-loglevel",
        "error",
        "-i",
        str(video_path),
        "-vn",
        "-acodec",
        "libmp3lame",
        "-q:a",
        "2",
        str(audio_path),
    ]
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        error_output = completed.stderr.strip() or completed.stdout.strip() or "ffmpeg failed"
        raise ExtractionError(error_output)
