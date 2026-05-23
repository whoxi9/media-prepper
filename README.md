# Media PCM Converter

Small cross-platform batch converter for preparing media with PCM audio.

- Video files become `.mov`
- Video streams are copied by default, so the whole video is not re-encoded
- Audio streams inside videos become PCM
- Audio-only files become `.wav` PCM
- Folder organization is preserved in the output folder
- Uses `imageio-ffmpeg` by default, so users do not need a separate FFmpeg install
- Can still use a system FFmpeg if you pass `--ffmpeg ffmpeg`

## Requirements

Install the Python dependency:

```powershell
python -m pip install -r requirements.txt
```

`imageio-ffmpeg` provides an FFmpeg binary for the user's OS. The script does
not require `ffprobe`.

If you prefer using your own system FFmpeg, install FFmpeg separately and run:

```bash
python media_pcm_converter.py /path/to/media --ffmpeg ffmpeg
```

## Usage

Convert a whole folder recursively:

```bash
python media_pcm_converter.py /path/to/media
```

By default, a folder named like `/path/to/media_pcm` is created next to the input folder.

Convert multiple folders while keeping each top-level folder name:

```bash
python media_pcm_converter.py /path/to/media-a /path/to/media-b -o /path/to/converted
```

Choose an output folder:

```bash
python media_pcm_converter.py /path/to/media -o /path/to/converted
```

Preview what would run:

```bash
python media_pcm_converter.py /path/to/media --dry-run
```

Overwrite existing converted files:

```bash
python media_pcm_converter.py /path/to/media --overwrite
```

Use 24-bit PCM instead of 16-bit PCM:

```bash
python media_pcm_converter.py /path/to/media --pcm s24
```

## About Video Re-encoding

The default video behavior is `-c:v copy`, which avoids re-encoding the video.
This works when the input video codec can be placed inside a `.mov` container.

Some codecs, especially from `.webm` or unusual `.mkv` files, may not be accepted
by MOV without transcoding. In that case the script will fail that file and tell
you to rerun with:

```bash
python media_pcm_converter.py /path/to/media --transcode-video
```

That fallback uses ProRes by default, which is editor-friendly but creates large files.
