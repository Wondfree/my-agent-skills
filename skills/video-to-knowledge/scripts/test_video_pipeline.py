#!/usr/bin/env python3
"""Offline regression tests; external media tools and ASR are mocked."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("video_pipeline", SCRIPTS / "video_pipeline.py")
pipeline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pipeline)
URL = "https://example.com/watch?v=clip-a&token=secret#chapter"
OTHER_URL = "https://example.com/other?v=clip-b"
SEGMENTS = [{"start": 0., "end": 5., "text": "Example speech"}]


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.out = self.root / "output"
        self.out.mkdir()
        self.args = pipeline.make_parser().parse_args(
            ["capture", "--url", URL, "--out-dir", str(self.out), "--audio-only"])
        self.run = self.enterContext(patch.object(pipeline, "run"))
        self.recognize = self.enterContext(patch.object(pipeline, "recognize", return_value=iter(SEGMENTS)))
        self.enterContext(patch.object(pipeline, "get_duration", return_value=5.))
        self.stdout = self.enterContext(contextlib.redirect_stdout(io.StringIO()))

    def capture(self):
        pipeline.cmd_capture(self.args)

    def probe_and_download(self, argv, **kwargs):
        if "--dump-single-json" in argv:
            # State must exist before the first external command.
            self.assertTrue((self.out / "capture_state.json").is_file())
            return json.dumps({"id": "clip-a", "webpage_url": URL})
        (self.out / "audio.m4a").write_bytes(b"media")
        return ""

    def test_existing_media_without_resume_fails_before_subprocess(self):
        for name in ("audio.m4a", "video.mp4", "video_only.mp4", "audio.m4a.part"):
            with self.subTest(name=name):
                media = self.out / name
                media.touch()
                with self.assertRaisesRegex(RuntimeError, "Existing media.*--resume"):
                    self.capture()
                self.run.assert_not_called()
                media.unlink()

    def test_resume_same_url_reuses_media_and_redacts_manifests(self):
        pipeline.prepare_capture(self.out, self.args)
        (self.out / "audio.m4a").write_bytes(b"media")
        self.args.resume = True
        self.run.side_effect = self.probe_and_download
        self.capture()
        self.assertEqual(self.run.call_count, 1)  # Metadata probe only.
        self.assertIn("--dump-single-json", self.run.call_args.args[0])
        source = json.loads((self.out / "source.json").read_text())
        transcript = json.loads((self.out / "transcript.json").read_text())
        self.assertEqual(source["source"], "https://example.com/watch")
        self.assertEqual(source["source_metadata"]["url"], source["source"])
        self.assertEqual(source["source_metadata"]["id"], "clip-a")
        self.assertEqual(transcript["source"], source["source"])
        self.assertEqual(transcript["source_id"], "clip-a")
        for name in ("source.json", "transcript.json"):
            self.assertNotIn("secret", (self.out / name).read_text())

    def test_resume_different_source_or_part_fails_before_subprocess(self):
        pipeline.prepare_capture(self.out, self.args)
        (self.out / "audio.m4a").touch()
        self.args.resume = True
        self.args.url = OTHER_URL
        with self.assertRaisesRegex(RuntimeError, "previous.*example.com/watch.*current.*example.com/other"):
            self.capture()
        self.args.url = URL
        self.args.part = 2
        with self.assertRaisesRegex(RuntimeError, "part None.*part 2"):
            self.capture()
        # Even query-only source differences must be detected.
        self.args.part = None
        self.args.url = URL.replace("clip-a", "clip-b")
        with self.assertRaisesRegex(RuntimeError, "Resume source mismatch"):
            self.capture()
        self.run.assert_not_called()

    def test_resume_without_state_refuses_unattributed_media(self):
        (self.out / "audio.m4a").touch()
        self.args.resume = True
        with self.assertRaisesRegex(RuntimeError, "without capture_state.json"):
            self.capture()
        self.run.assert_not_called()

    def test_fresh_empty_and_new_directories_capture(self):
        for name in ("output", "new-output"):
            with self.subTest(name=name):
                self.out = self.root / name
                self.args.out_dir = str(self.out)
                self.recognize.return_value = iter(SEGMENTS)
                self.run.side_effect = self.probe_and_download
                self.capture()
                self.assertTrue((self.out / "source.json").is_file())
                for call in self.run.call_args_list:
                    self.assertNotIn("--max-filesize", call.args[0])

    def test_existing_raw_evidence_is_never_overwritten(self):
        for name in ("source.json", "transcript.txt", "transcript.json", "transcript.srt",
                     "transcript_with_timestamps.txt"):
            with self.subTest(name=name):
                path = self.out / name
                path.write_text("original")
                with self.assertRaises(RuntimeError):
                    self.capture()
                self.assertEqual(path.read_text(), "original")
                self.run.assert_not_called()
                path.unlink()

    def test_local_audio_only_extracts_wav_without_copying_video(self):
        src = self.root / "input.mp4"
        src.write_bytes(b"original")
        self.args.url = None
        self.args.input = str(src)
        self.run.side_effect = lambda *a, **k: (self.out / "audio.wav").write_bytes(b"wav")
        with patch.object(pipeline.shutil, "copy2") as copy:
            self.capture()
            copy.assert_not_called()
        self.assertEqual(self.run.call_count, 1)
        argv = self.run.call_args.args[0]
        self.assertEqual(argv[0], "ffmpeg")
        self.assertEqual(argv[argv.index("-i") + 1], str(src.resolve()))
        self.assertIn("-vn", argv)
        self.assertFalse(list(self.out.glob("video.*")))
        meta = json.loads((self.out / "source.json").read_text())
        self.assertIsNone(meta["video"])
        self.assertEqual(meta["audio"], "audio.wav")
        self.assertEqual(src.read_bytes(), b"original")

    def test_local_copy_refuses_overwrite(self):
        src = self.root / "input.mp4"
        src.write_bytes(b"new")
        dest = self.out / "video.mp4"
        dest.write_bytes(b"original")
        with self.assertRaisesRegex(RuntimeError, "will not overwrite"):
            pipeline.copy_source(src, self.out)
        self.assertEqual(dest.read_bytes(), b"original")

    def verify(self, duration):
        args = pipeline.make_parser().parse_args(["verify", "--out-dir", str(self.out)])
        stream = io.StringIO()
        with patch.object(pipeline, "get_duration", return_value=duration), contextlib.redirect_stdout(stream):
            pipeline.cmd_verify(args)
        return json.loads(stream.getvalue())

    def test_verify_editorial_completion_and_coverage_warning(self):
        pipeline.write_transcripts(self.out, SEGMENTS, URL, self.args)
        (self.out / "transcript_corrected.md").touch()
        (self.out / "knowledge_structured.md").write_text(" \n")
        result = self.verify(3600)
        self.assertTrue(result["passed"])
        self.assertFalse(result["editorial_complete"])
        self.assertEqual(len(result["warnings"]), 1)
        self.assertIn("80%", result["warnings"][0])
        for name in ("transcript_corrected.md", "knowledge_structured.md", "quality_report.md"):
            (self.out / name).write_text("Reviewed content")
        result = self.verify(5)
        self.assertTrue(result["passed"])
        self.assertTrue(result["editorial_complete"])
        self.assertEqual(result["warnings"], [])
        for name in ("transcript_corrected.md", "knowledge_structured.md", "quality_report.md"):
            with self.subTest(empty=name):
                (self.out / name).write_text("\n")
                self.assertFalse(self.verify(5)["editorial_complete"])
                (self.out / name).write_text("Reviewed content")
        (self.out / "knowledge_structured.md").unlink()
        (self.out / "tutorial_structured.md").write_text("Tutorial")
        self.assertTrue(self.verify(5)["editorial_complete"])

    def test_verify_uses_known_manifest_duration_without_ffprobe(self):
        pipeline.write_transcripts(self.out, SEGMENTS, URL, self.args)
        (self.out / "source.json").write_text(json.dumps({"duration_seconds": 3600}))
        result = self.verify(None)
        self.assertTrue(result["passed"])
        self.assertEqual(len(result["warnings"]), 1)
        self.assertEqual(result["media_duration_seconds"], 3600)

    def test_verify_raw_asr_problems_still_exit_one(self):
        pipeline.write_transcripts(self.out, SEGMENTS, URL, self.args)
        (self.out / "transcript.srt").unlink()
        with self.assertRaises(SystemExit) as raised:
            self.verify(5)
        self.assertEqual(raised.exception.code, 1)

    def test_url_validation_before_any_external_command(self):
        for url in ("--exec=bad", "file:///input.mp4", "ftp://example.com/video"):
            with self.subTest(url=url):
                self.args.url = url
                for operation in (self.capture, lambda: pipeline.source_json(url),
                                  lambda: pipeline.download_url(url, self.out, True, [])):
                    with self.assertRaisesRegex(RuntimeError, "http:// or https://"):
                        operation()
        self.run.assert_not_called()

    def test_ytdlp_arguments_harden_probe_and_both_downloads(self):
        self.run.return_value = '{}'
        pipeline.source_json(URL)
        probe_argv = self.run.call_args.args[0]

        def download(argv, **kwargs):
            if argv[0] == "yt-dlp":
                stem = "audio.m4a" if "ba/bestaudio/best" in argv else "video_only.mp4"
                (self.out / stem).touch()
            else:
                (self.out / "video.mp4").touch()
            return ""

        self.run.reset_mock()
        self.run.side_effect = download
        pipeline.download_url(URL, self.out, False, ["--no-playlist"], "500M")
        downloads = [call.args[0] for call in self.run.call_args_list if call.args[0][0] == "yt-dlp"]
        self.assertEqual(len(downloads), 2)
        for argv in [probe_argv, *downloads]:
            self.assertIn("--ignore-config", argv)
            self.assertEqual(argv[-2:], ["--", URL])
            self.assertEqual(argv[argv.index("--socket-timeout") + 1], "30")
        for argv in downloads:
            self.assertEqual(argv[argv.index("--max-filesize") + 1], "500M")


class LauncherTests(unittest.TestCase):
    def test_whisper_engine_forms_and_empty_path_entries(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            good = root / "bin"
            good.mkdir()
            # These stubs answer import probes without importing an ASR package.
            stub = good / "python3"
            stub.write_text('''#!/bin/sh
if [ "$1" = "-c" ]; then
  case "$2" in
    'import sys;'*) exit 0 ;;
    'import whisper') exit 0 ;;
    *) exit 1 ;;
  esac
fi
[ -f "$1" ] || exit 1
printf 'selected-whisper\\n'
''')
            stub.chmod(0o755)
            bad = root / "python3"
            bad.write_text("#!/bin/sh\nprintf 'selected-current-directory\\n'\n")
            bad.chmod(0o755)
            env = {**os.environ, "PATH": f":{good}::/usr/bin:/bin"}
            env.pop("VIDEO_TO_KNOWLEDGE_PYTHON", None)
            for engine in (["--engine", "whisper"], ["--engine=whisper"]):
                with self.subTest(engine=engine):
                    result = subprocess.run(["/bin/sh", str(SCRIPTS / "run.sh"), "capture", *engine],
                                            cwd=root, env=env, text=True, capture_output=True)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(result.stdout.strip(), "selected-whisper")


if __name__ == "__main__":
    unittest.main()
