# Weixin Audio Extractor

`weixin-audio-extractor` is a local Codex plugin that turns a Weixin share link into an MP3 file on disk.

The plugin ships with:

- a Codex skill for interactive use
- a Python CLI for deterministic local runs
- a reusable core module that can be wrapped by a future MCP server

## What it does

Given a share URL such as `https://weixin.qq.com/sph/AWU0OMKvVm`, the plugin:

1. sends the link to the parser endpoint `https://sph.litao.workers.dev/api/fetch_video_profile`
2. prefers `feedInfo.h264VideoInfo.videoUrl`
3. falls back to `feedInfo.h265VideoInfo.videoUrl`
4. downloads the resolved MP4
5. extracts MP3 audio with `imageio-ffmpeg`
6. writes parser metadata to `<stem>.json`
7. deletes the MP4 unless `--keep-video` is requested

## Repository layout

- `.codex-plugin/plugin.json`: plugin manifest
- `skills/weixin-audio-extractor/SKILL.md`: Codex skill instructions
- `scripts/extract_weixin_audio.py`: thin CLI entrypoint
- `src/weixin_audio_extractor/`: reusable runtime logic
- `tests/test_core.py`: lightweight unit tests
- `docs/architecture.md`: implementation notes

## Prerequisites

- Python 3
- `imageio-ffmpeg`

Install the runtime dependency with:

```bash
python -m pip install -r requirements.txt
```

## CLI usage

Run the bundled CLI from the plugin root:

```bash
python scripts/extract_weixin_audio.py --url "https://weixin.qq.com/sph/AWU0OMKvVm"
```

Write outputs to a different directory:

```bash
python scripts/extract_weixin_audio.py \
  --url "https://weixin.qq.com/sph/AWU0OMKvVm" \
  --output-dir "D:\\videos"
```

Keep the downloaded MP4:

```bash
python scripts/extract_weixin_audio.py \
  --url "https://weixin.qq.com/sph/AWU0OMKvVm" \
  --output-dir "D:\\videos" \
  --keep-video
```

Successful runs print JSON with absolute output paths.

## Installing as a local Codex plugin

This repository is already shaped as a plugin root. The default local install flow is:

1. Clone the repository into `~/plugins/weixin-audio-extractor`
2. Ensure `~/.agents/plugins/marketplace.json` contains an entry for `weixin-audio-extractor`
3. Install it in Codex from the `personal` marketplace

If your Codex CLI is available, the install command is:

```bash
codex plugin add weixin-audio-extractor@personal
```

## Using the skill in Codex

After installation, ask Codex to do one of these:

- `Extract audio from https://weixin.qq.com/sph/AWU0OMKvVm`
- `Extract audio from https://weixin.qq.com/sph/AWU0OMKvVm into D:\videos`
- `Extract audio from https://weixin.qq.com/sph/AWU0OMKvVm and keep the video`

## Development

Run tests:

```bash
python -m unittest discover -s tests -v
```

Validate the plugin manifest:

```bash
python C:\Users\Administrator\.codex\skills\.system\plugin-creator\scripts\validate_plugin.py .
```

## Troubleshooting

- `Parser response did not contain an H.264 or H.265 video URL`
  The parser endpoint responded, but did not expose a playable video URL for that share link.
- `Parser request failed`
  The third-party parser endpoint was unavailable or rejected the request.
- `error: [ffmpeg output]`
  `imageio-ffmpeg` resolved an ffmpeg binary, but ffmpeg could not decode the downloaded video.

## Third-party dependency notice

This plugin intentionally depends on the public parser endpoint:

`https://sph.litao.workers.dev/api/fetch_video_profile`

That endpoint is not controlled by this repository. If it changes behavior, rate-limits requests, or goes offline, extraction will fail even if the local code is unchanged.

## License

MIT
