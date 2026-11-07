#!/usr/bin/env python3
"""Local video acquisition and raw speech transcription for video-to-knowledge.

Requires yt-dlp, ffmpeg/ffprobe; transcription uses faster_whisper or whisper.
No external paid transcription service or AI editorial editing is performed here.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import re
from pathlib import Path
import shutil
import subprocess
import sys
import time
from urllib.parse import parse_qs, urlsplit, urlunsplit


def fail(message: str) -> None:
    raise RuntimeError(message)


def run(argv: list[str], *, capture: bool = False) -> str:
    try:
        result = subprocess.run(argv, check=True, text=True,
                                stdout=subprocess.PIPE if capture else None)
        return result.stdout if capture else ""
    except FileNotFoundError as e:
        fail(f"Missing command: {argv[0]} ({e})")
    except subprocess.CalledProcessError as e:
        fail(f"Command failed (exit {e.returncode}): {' '.join(argv[:5])}; see tool output")


def validate_url(url: str) -> None:
    if not re.match(r"^https?://", url):
        fail("--url must start with http:// or https://")


def redact_url(source: str | None) -> str | None:
    if source and re.match(r"^https?://", source):
        parts = urlsplit(source)
        return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))
    return source


def capture_part(args: argparse.Namespace) -> int | None:
    """Keep the selected Bilibili page when its URL query is redacted."""
    if args.part is not None:
        return args.part
    if args.url:
        url = urlsplit(args.url)
        host = url.hostname or ""
        if host == "bilibili.com" or host.endswith(".bilibili.com"):
            pages = parse_qs(url.query).get("p", [])
            if len(pages) == 1 and re.fullmatch(r"[0-9]+", pages[0]):
                page = int(pages[0])
                if page > 0:
                    return page
    return None


def source_json(src: str) -> dict:
    validate_url(src)
    raw = run(["yt-dlp", "--ignore-config", "--socket-timeout", "30",
               "--flat-playlist", "--dump-single-json",
               "--skip-download", "--no-warnings", "--", src], capture=True)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        fail("yt-dlp did not return valid JSON. Check the URL, network and access requirements.")


def source_summary(raw: dict) -> dict:
    entries = raw.get("entries")
    parts = []
    if isinstance(entries, list):
        parts = [{"index": n, "title": p.get("title") if isinstance(p, dict) else None,
                  "id": p.get("id") if isinstance(p, dict) else None}
                 for n, p in enumerate(entries, 1)]
    return {"title": raw.get("title"), "id": raw.get("id"),
            "uploader": raw.get("uploader"), "duration_seconds": raw.get("duration"),
            "url": redact_url(raw.get("webpage_url") or raw.get("url")),
            "multipart": len(parts) > 1, "part_count": len(parts),
            "parts": parts}


def cmd_doctor(_args: argparse.Namespace) -> None:
    home = Path.home()
    info = {
        "python": sys.executable,
        "yt_dlp": shutil.which("yt-dlp"),
        "ffmpeg": shutil.which("ffmpeg"),
        "ffprobe": shutil.which("ffprobe"),
        "faster_whisper": importlib.util.find_spec("faster_whisper") is not None,
        "openai_whisper": importlib.util.find_spec("whisper") is not None,
        "local_openai_whisper_models": [p.name for p in (home / ".cache/whisper").glob("*.pt")],
    }
    print(json.dumps(info, ensure_ascii=False, indent=2))


def cmd_probe(args: argparse.Namespace) -> None:
    raw = source_json(args.url)
    summary = source_summary(raw)
    if args.out_dir:
        out = Path(args.out_dir).expanduser()
        out.mkdir(parents=True, exist_ok=True)
        path = out / "source_probe.json"
        if path.exists():
            fail(f"Already exists, will not overwrite: {path}")
        path.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
        summary["saved_source_probe"] = str(path)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def unique_media(directory: Path, stem: str) -> Path | None:
    candidates = [p for p in directory.glob(stem + ".*")
                  if p.is_file() and p.suffix.lower() not in
                  (".part", ".json", ".ytdl", ".description", ".txt", ".srt")]
    if len(candidates) > 1:
        fail(f"Multiple {stem} files in {directory}: {candidates}")
    return candidates[0] if candidates else None


def copy_source(src: Path, out: Path) -> Path:
    dest = out / ("audio" if src.suffix.lower() in
                  {".mp3", ".m4a", ".wav", ".aac", ".flac", ".ogg", ".opus"} else "video")
    dest = dest.with_suffix(src.suffix.lower())
    if src.resolve() == dest.resolve():
        return dest
    if dest.exists():
        fail(f"Destination exists, will not overwrite: {dest}")
    shutil.copy2(src, dest)
    return dest


def select_part(raw: dict, part: int | None) -> list[str]:
    n = source_summary(raw)["part_count"]
    if n > 1 and part is None:
        fail(f"This URL contains {n} parts. Use --part N for one part, or run once per requested part in separate directories.")
    if part is not None:
        if part < 1 or (n and part > n):
            fail(f"Invalid --part {part}; discovered {n} parts")
        return ["--yes-playlist", "--playlist-items", str(part)]
    return ["--no-playlist"]


def download_url(url: str, out: Path, audio_only: bool, part_flags: list[str],
                 max_filesize: str | None = None) -> tuple[Path | None, Path]:
    validate_url(url)
    common = ["yt-dlp", "--ignore-config", "--socket-timeout", "30", *part_flags,
              "--retries", "4", "--fragment-retries", "4",
              "--no-mtime", "--no-overwrites"]
    if max_filesize is not None:
        common.extend(["--max-filesize", max_filesize])
    size_hint = (f" With --max-filesize {max_filesize}, yt-dlp may have skipped an "
                 "oversized stream; check the limit and tool output." if max_filesize else "")
    # Download separately: Bilibili's separate audio stream often needs an independent retry.
    audio = unique_media(out, "audio")
    if audio is None:
        run([*common, "-f", "ba/bestaudio/best", "-o",
             str(out / "audio.%(ext)s"), "--", url])
        audio = unique_media(out, "audio")
    if audio is None:
        fail("Audio download did not produce a usable media file." + size_hint)
    if audio_only:
        return None, audio

    video = unique_media(out, "video")
    if video:
        return video, audio
    video_only = unique_media(out, "video_only")
    if video_only is None:
        run([*common, "-f",
             "bv*[vcodec^=avc1][height<=720]/bv*[height<=720]/bv*/bestvideo",
             "-o", str(out / "video_only.%(ext)s"), "--", url])
        video_only = unique_media(out, "video_only")
    if video_only is None:
        fail("Video stream download did not produce a usable file." + size_hint)
    video = out / "video.mp4"
    if video.exists():
        fail(f"Destination exists, will not overwrite: {video}")
    run(["ffmpeg", "-hide_banner", "-loglevel", "error",
         "-i", str(video_only), "-i", str(audio),
         "-map", "0:v:0", "-map", "1:a:0", "-c", "copy",
         "-movflags", "+faststart", str(video)])
    return video, audio


def timestamp(seconds: float, srt: bool = False) -> str:
    ms = max(0, round(seconds * 1000))
    hours, rem = divmod(ms, 3600000)
    minutes, rem = divmod(rem, 60000)
    sec, rem = divmod(rem, 1000)
    return f"{hours:02}:{minutes:02}:{sec:02}" + (f",{rem:03}" if srt else "")


def get_duration(media: Path | None) -> float | None:
    if media is None or not shutil.which("ffprobe"):
        return None
    try:
        raw = run(["ffprobe", "-v", "error", "-show_entries",
                   "format=duration", "-of", "default=nw=1:nk=1", str(media)],
                  capture=True)
        return float(raw.strip())
    except (ValueError, RuntimeError):
        return None


def recognize(media: Path, args: argparse.Namespace):
    if args.engine == "faster-whisper":
        from faster_whisper import WhisperModel
        model = WhisperModel(args.model, device=args.device,
                             compute_type="int8" if args.device == "cpu" else "default",
                             cpu_threads=args.threads)
        segments, _info = model.transcribe(str(media),
                                           language=None if args.language == "auto" else args.language,
                                           beam_size=args.beam_size, vad_filter=True)
        for seg in segments:
            yield {"start": float(seg.start), "end": float(seg.end),
                   "text": seg.text.strip()}
    else:
        import whisper
        model = whisper.load_model(args.model, device=args.device)
        result = model.transcribe(str(media), language=None if args.language == "auto"
                                  else args.language, fp16=args.device != "cpu",
                                  beam_size=args.beam_size, verbose=False)
        for seg in result["segments"]:
            yield {"start": float(seg["start"]), "end": float(seg["end"]),
                   "text": seg["text"].strip()}


def write_transcripts(out: Path, segments: list[dict], source: str, args: argparse.Namespace,
                      source_id: str | None = None) -> None:
    paths = [out / x for x in ("transcript.txt", "transcript_with_timestamps.txt",
                               "transcript.srt", "transcript.json")]
    occupied = [str(p) for p in paths if p.exists()]
    if occupied:
        fail("Transcript files already exist; will not overwrite: " + ", ".join(occupied))
    flat = []
    timed = []
    srt = []
    for i, seg in enumerate(segments, 1):
        flat.append(seg["text"])
        timed.append(f"[{timestamp(seg['start'])}] {seg['text']}")
        srt.extend([str(i),
                    f"{timestamp(seg['start'], True)} --> {timestamp(seg['end'], True)}",
                    seg["text"], ""])
    payloads = [
        "\n".join(flat) + "\n",
        "\n".join(timed) + "\n",
        "\n".join(srt) + "\n",
        json.dumps({"source": redact_url(source), "source_id": source_id,
                    "part": capture_part(args), "model": args.model, "engine": args.engine,
                    "language": args.language, "segments": segments},
                   ensure_ascii=False, indent=2) + "\n",
    ]
    for path, payload in zip(paths, payloads):
        path.write_text(payload, encoding="utf-8")


def existing_media(out: Path) -> list[Path]:
    return [p for stem in ("audio", "video", "video_only")
            for p in out.glob(stem + ".*") if p.is_file()]


def prepare_capture(out: Path, args: argparse.Namespace) -> None:
    """Bind partial media to one source before any external command runs."""
    source = args.url or str(Path(args.input).expanduser().resolve())
    if args.url:
        validate_url(source)
    state = {"source": redact_url(source) if args.url else Path(source).name,
             "source_sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
             "part": args.part}
    media = existing_media(out)
    state_path = out / "capture_state.json"
    if media and not args.resume:
        fail("Existing media in output directory; use --resume for the same source or a new directory")
    if args.resume and state_path.exists():
        previous = json.loads(state_path.read_text(encoding="utf-8"))
        if previous != state:
            fail(f"Resume source mismatch: previous {previous.get('source')!r} "
                 f"(part {previous.get('part')}, hash {previous.get('source_sha256', 'unknown')[:12]}), "
                 f"current {state['source']!r} "
                 f"(part {state['part']}, hash {state['source_sha256'][:12]}). Use a new directory.")
    elif args.resume and media:
        fail("Cannot resume existing media without capture_state.json; use a new directory")
    else:
        if state_path.exists():
            fail("Capture state already exists; use --resume or a new directory")
        with state_path.open("x", encoding="utf-8") as handle:
            json.dump(state, handle, ensure_ascii=False, indent=2)


def cmd_capture(args: argparse.Namespace) -> None:
    out = Path(args.out_dir).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    for file in ("transcript.txt", "transcript.json", "transcript.srt",
                 "transcript_with_timestamps.txt"):
        if (out / file).exists():
            fail(f"Found existing ASR output: {out / file}. Use a new directory, do not overwrite raw evidence.")
    if (out / "source.json").exists():
        fail("Source manifest exists; will not overwrite raw evidence. Use a new directory.")
    prepare_capture(out, args)
    try:
        capture_prepared(args, out)
    except Exception:
        # Retain state for partial streams (including .part files), but allow a
        # plain retry when acquisition failed before producing any media.
        if not existing_media(out):
            (out / "capture_state.json").unlink(missing_ok=True)
        raise


def capture_prepared(args: argparse.Namespace, out: Path) -> None:
    if args.url:
        source = args.url
        raw = source_json(source)
        summary = source_summary(raw)
        part_flags = select_part(raw, args.part)
        video, audio = download_url(source, out, args.audio_only, part_flags, args.max_filesize)
    else:
        src = Path(args.input).expanduser().resolve()
        if not src.is_file():
            fail(f"Input media not found: {src}")
        source = src.name  # portable provenance: avoid recording machine-specific absolute paths
        local = src if args.audio_only else copy_source(src, out)
        video = None if args.audio_only else (local if local.name.startswith("video.") else None)
        audio = None if args.audio_only else (local if local.name.startswith("audio.") else None)
        if audio is None:
            audio = out / "audio.wav"
            if audio.exists():
                fail(f"Destination exists: {audio}")
            run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(local),
                 "-vn", "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", str(audio)])
        summary = {"title": src.stem, "url": None, "multipart": False, "source_type": "local_file"}
    if audio is None:
        fail("No available audio for transcription")
    print(json.dumps({"media": str(video) if video else None,
                      "audio": str(audio), "engine": args.engine,
                      "model": args.model}, ensure_ascii=False), flush=True)
    begun = time.monotonic()
    segments = []
    for segment in recognize(audio, args):
        if not segment["text"]:
            continue
        segments.append(segment)
        if len(segments) % 30 == 0:
            print(f"Transcribed {len(segments)} segments through "
                  f"{timestamp(segment['end'])}, elapsed {round(time.monotonic()-begun)}s",
                  flush=True)
    if not segments:
        fail("Speech recognizer returned no text; no empty transcript was published")
    write_transcripts(out, segments, source, args, source_id=summary.get("id"))
    meta = {"source": redact_url(source), "part": capture_part(args),
            "source_metadata": summary, "video": video.name if video else None,
            "audio": audio.name, "duration_seconds": get_duration(video or audio),
            "engine": args.engine, "model": args.model, "language": args.language,
            "segment_count": len(segments), "last_speech_seconds": segments[-1]["end"],
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "status": "raw_asr_complete_editorial_review_pending"}
    dest = out / "source.json"
    if dest.exists():
        fail(f"Source manifest exists; will not overwrite: {dest}")
    dest.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": "raw_asr_complete_editorial_review_pending",
                      "output_dir": str(out), "segment_count": len(segments),
                      "last_speech_at": timestamp(segments[-1]["end"])},
                     ensure_ascii=False))


def seconds_from_text(value: str) -> float:
    parts = value.strip().split(":")
    if len(parts) > 3 or not parts or not all(parts):
        fail(f"Invalid timestamp: {value}")
    try:
        nums = [float(v) for v in parts]
    except ValueError:
        fail(f"Invalid timestamp: {value}")
    if any(v < 0 for v in nums):
        fail(f"Invalid timestamp: {value}")
    sec = 0.
    for v in nums:
        sec = sec * 60 + v
    return sec


def cmd_frames(args: argparse.Namespace) -> None:
    media = Path(args.input).expanduser().resolve()
    if not media.is_file():
        fail(f"Missing video: {media}")
    out = Path(args.out_dir).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    for value in args.at.split(","):
        t = seconds_from_text(value)
        dest = out / f"frame_{int(t*1000):010d}ms.jpg"
        if dest.exists():
            print(f"Already exists: {dest}", flush=True)
            continue
        run(["ffmpeg", "-hide_banner", "-loglevel", "error",
             "-ss", str(t), "-i", str(media), "-frames:v", "1",
             "-q:v", "3", str(dest)])
        if not dest.exists() or dest.stat().st_size == 0:
            fail(f"Could not extract a frame near {value}")
        print(f"{value} -> {dest}", flush=True)


def cmd_verify(args: argparse.Namespace) -> None:
    out = Path(args.out_dir).expanduser()
    data_path = out / "transcript.json"
    if not data_path.exists():
        fail(f"Missing transcript JSON: {data_path}")
    data = json.loads(data_path.read_text(encoding="utf-8"))
    segments = data.get("segments", [])
    issues = []
    if not segments:
        issues.append("Transcript has no segments")
    prev = 0.
    for i, seg in enumerate(segments):
        start, end = seg.get("start"), seg.get("end")
        if not isinstance(start, (int, float)) or not isinstance(end, (int, float)):
            issues.append(f"Invalid timestamps at segment {i}")
            continue
        if end < start or start + .01 < prev:
            issues.append(f"Nonmonotonic timestamps at segment {i}")
        prev = max(prev, start)
        if not seg.get("text", "").strip():
            issues.append(f"Blank text in segment {i}")
    for name in ("transcript.txt", "transcript.srt", "transcript_with_timestamps.txt"):
        if not (out / name).is_file() or (out / name).stat().st_size == 0:
            issues.append(f"Missing/empty {name}")
    video = unique_media(out, "video")
    audio = unique_media(out, "audio")
    duration = get_duration(video or audio)
    if duration is None and (out / "source.json").is_file():
        meta = json.loads((out / "source.json").read_text(encoding="utf-8"))
        recorded_duration = meta.get("duration_seconds")
        if isinstance(recorded_duration, (int, float)) and recorded_duration > 0:
            duration = recorded_duration
    warnings = []
    last_speech = segments[-1].get("end") if segments else None
    if duration and isinstance(last_speech, (int, float)):
        if last_speech > duration + 10:
            issues.append("Transcript extends more than 10s past source duration")
        if last_speech < .8 * duration:
            warnings.append("Last speech is before 80% of source duration; review coverage")

    def nonempty(name: str) -> bool:
        path = out / name
        return path.is_file() and bool(path.read_text(encoding="utf-8").strip())

    result = {"passed": not issues, "issues": issues, "warnings": warnings, "segments": len(segments),
              "media_duration_seconds": duration, "video": str(video) if video else None,
              "audio": str(audio) if audio else None, "last_speech_seconds":
              last_speech,
              "editorial_complete": nonempty("transcript_corrected.md")
                                    and (nonempty("tutorial_structured.md") or
                                         nonempty("knowledge_structured.md"))
                                    and nonempty("quality_report.md")}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if issues:
        sys.exit(1)


def make_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor", help="Check installed local dependencies").set_defaults(func=cmd_doctor)
    probe = sub.add_parser("probe", help="Check metadata and number of video parts, no download")
    probe.add_argument("--url", required=True)
    probe.add_argument("--out-dir")
    probe.set_defaults(func=cmd_probe)
    cap = sub.add_parser("capture", help="Download/copy media and transcribe raw speech locally")
    group = cap.add_mutually_exclusive_group(required=True)
    group.add_argument("--url")
    group.add_argument("--input")
    cap.add_argument("--out-dir", required=True)
    cap.add_argument("--part", type=int, help="Explicit 1-based part for multipart videos")
    cap.add_argument("--audio-only", action="store_true")
    cap.add_argument("--resume", action="store_true", help="Reuse partial media only for the same source and part")
    cap.add_argument("--max-filesize", help="Optional yt-dlp per-download size limit (e.g. 500M)")
    cap.add_argument("--model", default="base")
    cap.add_argument("--engine", choices=["faster-whisper", "whisper"], default="faster-whisper")
    cap.add_argument("--language", default="zh", help="ASR language; use auto to detect")
    cap.add_argument("--device", default="cpu")
    cap.add_argument("--threads", type=int, default=8)
    cap.add_argument("--beam-size", type=int, default=5)
    cap.set_defaults(func=cmd_capture)
    fr = sub.add_parser("frames", help="Extract exact review frames with ffmpeg")
    fr.add_argument("--input", required=True)
    fr.add_argument("--out-dir", required=True)
    fr.add_argument("--at", required=True, help="Comma-separated timecodes: 01:20,02:30:45")
    fr.set_defaults(func=cmd_frames)
    ve = sub.add_parser("verify", help="Check raw transcript structure and files")
    ve.add_argument("--out-dir", required=True)
    ve.set_defaults(func=cmd_verify)
    return p


if __name__ == "__main__":
    try:
        args = make_parser().parse_args()
        args.func(args)
    except (RuntimeError, ValueError, OSError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(2)
