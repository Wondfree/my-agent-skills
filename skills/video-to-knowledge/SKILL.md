---
name: video-to-knowledge
description: Download or process a video (including Bilibili links and multipart tutorials), transcribe speech locally with Whisper, correct ASR terminology, verify on-screen steps and values, and organize a timestamped, source-grounded tutorial or knowledge note with reusable prompts. Use for video-to-text and video-course notes; not for creating animation/sprite assets or unrelated video editing.
---

# Video to Knowledge

Turn an authorized source video into **traceable knowledge**, not just an unverified summary. The deterministic script handles media and verbatim ASR artifacts; the agent handles semantic correction, frame inspection, organization, and honest uncertainty.

## Start here

1. Establish input: public/authorized video URL or local video/audio file; user's desired scope and destination. The caller selects an output directory for each source. Prefer a task-specific location within the requested workspace, or a fresh folder chosen with the user's normal file conventions. Never bind output to an author's username, absolute path, or an unrelated project.
2. **Discover scope before downloading**. Use `probe` for URLs. Check title, duration, discoverable video parts, and whether the link is one episode within a multipart video/course. Some Bilibili 合集/series connect separate BVs and will not appear in yt-dlp's part list: inspect the source collection/page as needed before claiming full-series coverage. Process only the user-requested scope; if unclear, tell the user what was found rather than silently claiming one part is the whole series.
3. Download only content that the user can lawfully access; respect site access controls and relevant licensing. Do not bypass DRM, paywalls, account restrictions, or rate limits. Never expose cookies or account data. Use browser cookies only on explicit authorization.
4. Check `doctor`, then run `capture`. Preserve raw ASR output as immutable evidence. When download fails, work from a user-provided local file or subtitle track if one exists; report exactly what was and was not obtained.
5. Review the **entire** raw transcript in time-ordered chunks, not just search snippets or the introduction. Correct domain terms, names, and punctuation **without silently inventing missing speech**. Create `transcript_corrected.md` with timestamps and an explicit disclosure that it is an ASR-based edit rather than fully audited verbatim speech.
6. Inspect **representative original frames** and all key frames with settings, parameter values, commands, UI labels, diagrams, or prompts using `frames` and an image-capable viewer. If speech and screen disagree, state both, favor what the visible UI demonstrably shows, and flag unresolved discrepancies. For suspicious quantitative data, compute/check the arithmetic.
7. Create source-grounded deliverables: `tutorial_structured.md` for a tutorial, or `knowledge_structured.md` for non-tutorial content; optional `prompts_from_video.md` when the source genuinely contains prompts; and a short `quality_report.md` capturing verification, coverage, corrections, uncertainty, and missing materials. Use the appropriate [review and output standards](references/review-and-outputs.md).
8. Run `verify` plus a manual final check of source metadata, time coverage, output existence, factual fidelity, unresolved uncertainties, and reproducibility. Report local paths and precisely what is complete.

## Commands

Locate this Skill by the directory containing the loaded `SKILL.md` (do not assume it is in `~/.codex/skills` or any specific home directory). The sibling executable `scripts/run.sh` resolves a Python interpreter with the requested engine from `PATH`. If necessary, set `VIDEO_TO_KNOWLEDGE_PYTHON` to a specific interpreter; do not bake that interpreter path into this Skill. Dependencies are checked by `doctor`. Do not install or update packages unless needed and authorized.

```bash
# Resolve SKILL_DIR from this loaded SKILL.md; choose OUTPUT_DIR for this source.
# Both are runtime inputs, not fixed user-, machine-, or workspace-specific paths.
SKILL_DIR="<directory containing the active SKILL.md>"
OUTPUT_DIR="<fresh task-specific destination directory>"
VIDEO_URL="<source video URL>"

"$SKILL_DIR/scripts/run.sh" doctor
"$SKILL_DIR/scripts/run.sh" probe --url "$VIDEO_URL"
"$SKILL_DIR/scripts/run.sh" capture --url "$VIDEO_URL" --out-dir "$OUTPUT_DIR" --model base
# Or process user-supplied local media instead of a URL:
"$SKILL_DIR/scripts/run.sh" capture --input "$INPUT_FILE" --out-dir "$OUTPUT_DIR"
# Resolve VIDEO_FILE from the capture result/source.json; use the actual file extension.
VIDEO_FILE="<actual downloaded or copied video file>"
"$SKILL_DIR/scripts/run.sh" frames --input "$VIDEO_FILE" --out-dir "$OUTPUT_DIR/frames_review" --at 00:03:00,00:14:30,00:35:00
"$SKILL_DIR/scripts/run.sh" verify --out-dir "$OUTPUT_DIR"
```

`capture` runs the download/transcribe stage, not the AI editorial stages. Default transcription uses local Faster Whisper Base on CPU (int8); configure `--engine whisper` for OpenAI Whisper, `--model` for accuracy, `--language` or `auto` for language, and `--audio-only` if the user does not want video. If screen verification is needed, keep the video. Run `--help` for full options.

Automatic ASR output:
- `video.mp4` (or `video.<source-ext>` for local sources) and `audio.*` when applicable;
- `transcript.txt`, `transcript_with_timestamps.txt`, `transcript.srt`, `transcript.json`, `source.json`;
- agent-produced `transcript_corrected.md`, `tutorial_structured.md` / `knowledge_structured.md`, `prompts_from_video.md` (only if appropriate), `quality_report.md`.

The `--out-dir` parameter is mandatory so the caller chooses placement explicitly; generated media paths in `source.json` are relative to the output folder, so moving that folder does not invalidate the manifest. For local inputs, retain the original filename rather than its external absolute path. The video-to-knowledge output is complete **only after** the editorial and verification steps, not merely when `capture` succeeds.

## Essential quality rules

- **Raw vs corrected**: never rewrite raw `transcript.*` to make ASR look accurate. Preserve a copy of the actual recognized words and timings; editable documents are separate.
- **Evidence labels**: distinguish verbatim screen text, a faithful paraphrase of spoken content, a plausible ASR correction, and the agent's additional advice. Never pass an illustrative prompt, guessed button, URL, file, version, or parameter off as a verbatim source.
- **Coverage**: process all requested episodes/chapters; cite `[mm:ss]` next to substantive procedures. Build a series index and per-episode outputs if multiple episodes were requested; avoid merging identities and timebases.
- **Scene-aware checks**: timestamps enable targeted key-frame review. Inspect original video rather than relying exclusively on subtitles for visible code, equations, configuration or on-screen prompts. When visual access is impossible, say `未进行画面核验`.
- **Safety and scale**: avoid huge accidental series downloads, paid cloud transcribers, unintended repository commits, and automatic removal of user originals. Prefer offline ASR; pretrained model initialization may fetch weights on first run, so do not promise completely offline availability without checking cache.
- **Boundaries**: This is not `video2dsprite` (character video → animation assets); it handles video → **textual knowledge and evidence**.

## Successful response

Report the source, episode coverage and duration, tools/models actually used, output directory, which files were generated, any significant corrections or contradictions, outstanding uncertainties, and the next useful action. Never claim unverified word-perfect transcription or that a multipart series has been fully processed when it has not.
