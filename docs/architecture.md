# Architecture

## Overview

`weixin-audio-extractor` is a hybrid-ready plugin with a deliberately small `v0.1.0` surface:

- plugin manifest for Codex discovery
- one bundled skill for interactive use
- one Python CLI for deterministic execution
- one reusable Python core module for future wrappers

`v0.1.0` does not expose an MCP server. The plugin layout leaves room for that later without changing the extraction logic.

## Runtime flow

1. The skill or CLI receives a Weixin share URL.
2. The core module posts the URL to `https://sph.litao.workers.dev/api/fetch_video_profile`.
3. The response selector prefers `feedInfo.h264VideoInfo.videoUrl`.
4. If H.264 is missing, it falls back to `feedInfo.h265VideoInfo.videoUrl`.
5. The downloader writes a temporary MP4 into the output directory.
6. ffmpeg from `imageio-ffmpeg` extracts MP3 audio.
7. The plugin writes the parser payload to `<stem>.json`.
8. The plugin deletes the MP4 unless `--keep-video` is set.

## Module boundaries

- `src/weixin_audio_extractor/core.py`
  Owns parser calls, URL selection, output naming, download, ffmpeg invocation, and error mapping.
- `src/weixin_audio_extractor/cli.py`
  Owns argument parsing and process exit behavior.
- `scripts/extract_weixin_audio.py`
  Thin repo-local entrypoint that adds `src/` to `sys.path` and calls the CLI module.
- `skills/weixin-audio-extractor/SKILL.md`
  Owns the human-facing Codex instructions.

## Why no MCP server in v0.1.0

The current user-proven workflow only needs one action: extract audio from a share link. A skill plus CLI keeps the initial plugin small, inspectable, and easy to publish.

When an MCP layer is added later, it should call the existing Python core module directly instead of duplicating network, naming, or ffmpeg logic.
