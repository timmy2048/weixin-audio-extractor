---
name: weixin-audio-extractor
description: Extract MP3 audio and parser metadata from a Weixin share link with the bundled Python CLI.
---

Use this skill when the user wants audio from a Weixin share link.

Before running:

1. Work from the plugin root.
2. Ensure Python 3 is available.
3. If `imageio_ffmpeg` is missing, run `python -m pip install -r requirements.txt`.

Inputs:

- Required: a Weixin share URL
- Optional: output directory
- Optional: whether to keep the downloaded MP4

Run:

```bash
python scripts/extract_weixin_audio.py --url "<share-url>"
```

Add options only when requested:

```bash
python scripts/extract_weixin_audio.py --url "<share-url>" --output-dir "<dir>"
python scripts/extract_weixin_audio.py --url "<share-url>" --output-dir "<dir>" --keep-video
```

Behavior:

- Uses `https://sph.litao.workers.dev/api/fetch_video_profile`
- Writes `<stem>.mp3` and `<stem>.json`
- Deletes `<stem>.mp4` unless `--keep-video` is set
- Prints JSON with absolute output paths

After the command finishes:

1. Confirm the generated file paths to the user.
2. If the command fails, surface the exact parser or ffmpeg error.
3. Do not claim success unless the files were actually written.
