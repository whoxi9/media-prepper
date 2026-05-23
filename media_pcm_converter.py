#!/usr/bin/env python3
"""
Batch-convert media to editing-friendly PCM outputs.

Videos are remuxed to .mov with video streams copied and audio streams converted
to PCM. Audio-only files are converted to .wav PCM.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


VIDEO_EXTENSIONS = {
    ".3g2",
    ".3gp",
    ".avi",
    ".flv",
    ".m2ts",
    ".m4v",
    ".mkv",
    ".mov",
    ".mp4",
    ".mpeg",
    ".mpg",
    ".mts",
    ".mxf",
    ".ogv",
    ".ts",
    ".vob",
    ".webm",
    ".wmv",
}

AUDIO_EXTENSIONS = {
    ".aac",
    ".ac3",
    ".aif",
    ".aiff",
    ".alac",
    ".ape",
    ".caf",
    ".dts",
    ".flac",
    ".m4a",
    ".mka",
    ".mp3",
    ".oga",
    ".ogg",
    ".opus",
    ".wav",
    ".wma",
}

PCM_CODECS = {
    "s16": "pcm_s16le",
    "s24": "pcm_s24le",
    "s32": "pcm_s32le",
    "f32": "pcm_f32le",
}


@dataclass(frozen=True)
class Job:
    source: Path
    output: Path
    is_video: bool


def die(message: str) -> None:
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(1)


def is_relative_to(path: Path, other: Path) -> bool:
    try:
        path.resolve().relative_to(other.resolve())
        return True
    except ValueError:
        return False


def iter_candidate_files(inputs: list[Path], output_root: Path | None) -> Iterable[tuple[Path, Path]]:
    include_top_folder = len(inputs) > 1
    for input_path in inputs:
        input_path = input_path.resolve()
        if input_path.is_file():
            yield input_path, input_path.parent
            continue

        if not input_path.is_dir():
            print(f"skip: {input_path} does not exist", file=sys.stderr)
            continue

        for path in input_path.rglob("*"):
            if not path.is_file():
                continue
            if output_root is not None and is_relative_to(path, output_root):
                continue
            if path.suffix.lower() not in VIDEO_EXTENSIONS | AUDIO_EXTENSIONS:
                continue
            base = input_path.parent if include_top_folder else input_path
            yield path.resolve(), base.resolve()


def build_jobs(inputs: list[Path], output_root: Path) -> list[Job]:
    jobs: list[Job] = []
    for source, base in iter_candidate_files(inputs, output_root):
        relative = source.relative_to(base.resolve())
        suffix = source.suffix.lower()
        if suffix in VIDEO_EXTENSIONS:
            output = output_root / relative.with_suffix(".mov")
            jobs.append(Job(source=source, output=output, is_video=True))
        elif suffix in AUDIO_EXTENSIONS:
            output = output_root / relative.with_suffix(".wav")
            jobs.append(Job(source=source, output=output, is_video=False))

    return jobs


def video_command(
    ffmpeg: str,
    source: Path,
    output: Path,
    audio_codec: str,
    overwrite: bool,
    transcode_video: bool,
    video_codec: str,
) -> list[str]:
    command = [
        ffmpeg,
        "-hide_banner",
        "-y" if overwrite else "-n",
        "-i",
        str(source),
        "-map",
        "0:v?",
        "-map",
        "0:a?",
        "-map_metadata",
        "0",
        "-map_chapters",
        "0",
        "-c:a",
        audio_codec,
    ]

    if transcode_video:
        command.extend(["-c:v", video_codec])
        if video_codec == "prores_ks":
            command.extend(["-profile:v", "3"])
    else:
        command.extend(["-c:v", "copy"])

    command.extend(["-movflags", "+faststart", str(output)])
    return command


def audio_command(ffmpeg: str, source: Path, output: Path, audio_codec: str, overwrite: bool) -> list[str]:
    return [
        ffmpeg,
        "-hide_banner",
        "-y" if overwrite else "-n",
        "-i",
        str(source),
        "-map",
        "0:a:0",
        "-map_metadata",
        "0",
        "-vn",
        "-c:a",
        audio_codec,
        str(output),
    ]


def convert_job(
    job: Job,
    ffmpeg: str,
    audio_codec: str,
    overwrite: bool,
    dry_run: bool,
    transcode_video: bool,
    video_codec: str,
) -> bool:
    if job.output.exists() and not overwrite:
        print(f"skip: {job.output} already exists")
        return True

    job.output.parent.mkdir(parents=True, exist_ok=True)
    if job.is_video:
        command = video_command(
            ffmpeg,
            job.source,
            job.output,
            audio_codec,
            overwrite,
            transcode_video,
            video_codec,
        )
    else:
        command = audio_command(ffmpeg, job.source, job.output, audio_codec, overwrite)

    print(f"{job.source} -> {job.output}")
    if dry_run:
        print("  " + " ".join(command))
        return True

    result = subprocess.run(command)
    if result.returncode == 0:
        return True

    print(f"failed: {job.source}", file=sys.stderr)
    if job.is_video and not transcode_video:
        print(
            "       video was set to stream-copy. If this codec cannot go in MOV, "
            "rerun with --transcode-video.",
            file=sys.stderr,
        )
    return False


def default_output_root(inputs: list[Path]) -> Path:
    if len(inputs) == 1 and inputs[0].is_dir():
        source = inputs[0].resolve()
        return source.with_name(f"{source.name}_pcm")
    if len(inputs) == 1 and inputs[0].is_file():
        return inputs[0].resolve().parent / "pcm_output"
    return Path.cwd() / "pcm_output"


def resolve_ffmpeg(ffmpeg_arg: str) -> str:
    if ffmpeg_arg != "auto":
        ffmpeg = shutil.which(ffmpeg_arg) if Path(ffmpeg_arg).name == ffmpeg_arg else ffmpeg_arg
        if ffmpeg is None:
            die(f"{ffmpeg_arg} was not found on PATH.")
        return ffmpeg

    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        ffmpeg = shutil.which("ffmpeg")
        if ffmpeg is not None:
            return ffmpeg
        die(
            "ffmpeg was not found. Install this project's Python dependency with "
            "`python -m pip install -r requirements.txt`, or install ffmpeg on PATH."
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Recursively convert videos to MOV with PCM audio and audio-only files "
            "to WAV PCM, preserving folder organization."
        )
    )
    parser.add_argument("inputs", nargs="+", type=Path, help="Input file(s) or folder(s).")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Output folder. Defaults to INPUT_pcm for a folder or ./pcm_output for mixed inputs.",
    )
    parser.add_argument(
        "--pcm",
        choices=sorted(PCM_CODECS),
        default="s16",
        help="PCM format for output audio. Default: s16.",
    )
    parser.add_argument("--overwrite", action="store_true", help="Replace existing output files.")
    parser.add_argument("--dry-run", action="store_true", help="Print ffmpeg commands without converting.")
    parser.add_argument(
        "--ffmpeg",
        default="auto",
        help="ffmpeg executable name/path, or 'auto' to prefer imageio-ffmpeg. Default: auto.",
    )
    parser.add_argument(
        "--transcode-video",
        action="store_true",
        help="Transcode video only when MOV stream-copy is not possible. Off by default.",
    )
    parser.add_argument(
        "--video-codec",
        default="prores_ks",
        help="Video codec used with --transcode-video. Default: prores_ks.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    ffmpeg = resolve_ffmpeg(args.ffmpeg)

    inputs = [path.resolve() for path in args.inputs]
    output_root = (args.output.resolve() if args.output else default_output_root(inputs))
    audio_codec = PCM_CODECS[args.pcm]

    jobs = build_jobs(inputs, output_root)
    if not jobs:
        print("No matching media files found.")
        return 0

    print(f"Output folder: {output_root}")
    print(f"Jobs: {len(jobs)}")

    failures = 0
    for job in jobs:
        ok = convert_job(
            job=job,
            ffmpeg=ffmpeg,
            audio_codec=audio_codec,
            overwrite=args.overwrite,
            dry_run=args.dry_run,
            transcode_video=args.transcode_video,
            video_codec=args.video_codec,
        )
        if not ok:
            failures += 1

    if failures:
        print(f"Done with {failures} failed job(s).", file=sys.stderr)
        return 1

    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
