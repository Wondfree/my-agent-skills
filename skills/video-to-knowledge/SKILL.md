---
name: video-to-knowledge
description: Process authorized videos (including Bilibili links and multipart tutorials) or local audio recordings into timestamped transcripts, summaries, and source-grounded notes. Use for audio/video transcription and course notes, with visual verification when relevant; not for creating animation/sprite assets or unrelated video editing.
---

# Video to Knowledge

Turn authorized audio/video into **traceable knowledge**, not just an unverified summary. The deterministic script handles media and verbatim ASR artifacts; the agent handles semantic correction, frame inspection, organization, and honest uncertainty.

## Choose the processing depth

Infer audio-only, screen recording, or other video from the input, metadata, and conversation. Do not routinely ask whether a file is a recording. Ask only when an unresolved distinction materially changes the requested scope or verification.

Before committing to a long transcription, briefly check representative speech and trial recognition. For long recordings, include the beginning, middle, and end. Reuse existing recognition when it already establishes quality; do not repeat a trial merely to satisfy a checklist. Clear-sounding audio can still misrecognize names, numbers, and specialist terms.

| Observed quality | Minimum useful workflow |
| --- | --- |
| Speech and trial recognition are clear and coherent | One transcription pass, basic full-text review, and the requested transcript or summary. |
| Isolated unclear speech, overlap, or recognition errors | Revisit the affected intervals; compare channels or retry locally only when useful. |
| Widespread wrong words, omissions, or repeated nonsense | Compare representative problem samples using relevant channel/model choices, then select a route. Use semantic reconstruction only when requested or clearly useful, and label it separately from verbatim text. |

Escalate in response to observed problems, not by default through every technique. Do not automatically run channel comparisons, multiple models, repeated full-file recognition, and semantic reconstruction for a clear recording. If a retry does not materially address the identified problem, preserve uncertainty rather than continuing unbounded reruns. Segmentation may help checkpoint long recordings and retry locally; it does not guarantee greater accuracy. Preserve raw output and check consequential names, numbers, negation, and commitments at every processing depth.

## Start here

1. Establish input: public/authorized video URL or local video/audio file; user's desired scope and destination. The caller selects an output directory for each source. Prefer a task-specific location within the requested workspace, or a fresh folder chosen with the user's normal file conventions. Never bind output to an author's username, absolute path, or an unrelated project.
2. **For remote URLs, discover scope before downloading**. Use `probe` for URLs; local recordings do not need remote discovery. Check title, duration, discoverable video parts, and whether the link is one episode within a multipart video/course. Some Bilibili 合集/series connect separate BVs and will not appear in yt-dlp's part list: inspect the source collection/page as needed before claiming full-series coverage. Process only the user-requested scope; if unclear, tell the user what was found rather than silently claiming one part is the whole series.
3. Download only content that the user can lawfully access; respect site access controls and relevant licensing. Do not bypass DRM, paywalls, account restrictions, or rate limits. Never expose cookies or account data. Use browser cookies only on explicit authorization.
4. Check `doctor`, apply the quality route above, then run `capture` for the chosen source. Pick the spoken language (or `auto`) from the available source information. Preserve raw ASR output as immutable evidence. When download fails, work from a user-provided local file or subtitle track if one exists; report exactly what was and was not obtained.
5. Review the **entire** raw transcript in time-ordered chunks, not just search snippets or the introduction. Correct domain terms, names, and punctuation **without silently inventing missing speech**. When delivering an edited transcript, create `transcript_corrected.md` with timestamps and an explicit disclosure that it is an ASR-based edit rather than fully audited verbatim speech.
6. When video visuals are relevant to the requested result, inspect **representative original frames** and all key frames with settings, parameter values, commands, UI labels, diagrams, or prompts using `frames` and an image-capable viewer. Skip frame review for audio-only input. If speech and screen disagree, state both, favor what the visible UI demonstrably shows, and flag unresolved discrepancies. For suspicious quantitative data, compute/check the arithmetic.
7. Create the requested source-grounded deliverables: `tutorial_structured.md` for tutorial notes, or `knowledge_structured.md` for non-tutorial notes; optional `prompts_from_video.md` when requested and supported by the source. Do not expand a transcript-only request into an unsolicited tutorial or note bundle. Record verification, coverage, corrections, uncertainty, and missing materials in a concise result note or `quality_report.md` as appropriate. Use the appropriate [review and output standards](references/review-and-outputs.md).
8. Run `verify` plus a manual final check of source metadata, time coverage, output existence, factual fidelity, unresolved uncertainties, and reproducibility. Report local paths and precisely what is complete.

## Commands

Locate this skill by the directory containing the loaded `SKILL.md` (do not assume it is in `~/.codex/skills` or any specific home directory). The sibling executable `scripts/run.sh` resolves a Python interpreter with the requested engine from `PATH`. If necessary, set `VIDEO_TO_KNOWLEDGE_PYTHON` to a specific interpreter; do not bake that interpreter path into this skill. Dependencies are checked by `doctor`. Do not install or update packages unless needed and authorized.

```bash
# Resolve SKILL_DIR from this loaded SKILL.md; choose OUTPUT_DIR for this source.
# Both are runtime inputs, not fixed user-, machine-, or workspace-specific paths.
SKILL_DIR="<directory containing the active SKILL.md>"
OUTPUT_DIR="<fresh task-specific destination directory>"
VIDEO_URL="<source video URL>"

"$SKILL_DIR/scripts/run.sh" doctor
"$SKILL_DIR/scripts/run.sh" probe --url "$VIDEO_URL"
"$SKILL_DIR/scripts/run.sh" capture --url "$VIDEO_URL" --out-dir "$OUTPUT_DIR" --model base --language auto
# Use --resume only to continue partial media for the same source and part.
# Or process user-supplied local media instead of a URL:
"$SKILL_DIR/scripts/run.sh" capture --input "$INPUT_FILE" --out-dir "$OUTPUT_DIR"
# Resolve VIDEO_FILE from the capture result/source.json; use the actual file extension.
VIDEO_FILE="<actual downloaded or copied video file>"
# Only when video visuals matter to the requested result:
"$SKILL_DIR/scripts/run.sh" frames --input "$VIDEO_FILE" --out-dir "$OUTPUT_DIR/frames_review" --at 00:03:00,00:14:30,00:35:00
"$SKILL_DIR/scripts/run.sh" verify --out-dir "$OUTPUT_DIR"
```

`capture` runs the download/transcribe stage, not the AI editorial stages. Default transcription uses local Faster Whisper Base on CPU (int8); configure `--engine whisper` for OpenAI Whisper, `--model` for accuracy, `--language` for language (default: `zh`; use `--language auto` to detect), and `--audio-only` if the user does not want video. If screen verification is needed, keep the video. Use `--max-filesize` to set an optional per-download size limit; it is unset by default. All yt-dlp calls use `--ignore-config`, so user-configured proxies, cookies, and rate limits are not loaded. Run `--help` for full options.

Automatic ASR output:
- `video.mp4` (or `video.<source-ext>` for local sources) and `audio.*` when applicable;
- `transcript.txt`, `transcript_with_timestamps.txt`, `transcript.srt`, `transcript.json`, `source.json`;
- agent-produced `transcript_corrected.md`, `tutorial_structured.md` / `knowledge_structured.md`, `prompts_from_video.md` (only if appropriate), `quality_report.md`.

Use `--resume` to reuse partial media only when `capture_state.json` matches the same source and part; otherwise choose a fresh directory.

The `--out-dir` parameter is mandatory so the caller chooses placement explicitly; generated media paths in `source.json` are relative to the output folder, so moving that folder does not invalidate the manifest. Published source and transcript JSON redact URL queries and fragments while retaining the video id and selected part separately. For local inputs, retain the original filename rather than its external absolute path. The requested output is complete **only after** its relevant editorial work and verification, not merely when `capture` succeeds. In `verify`, `passed` checks raw transcript structure; `editorial_complete` reports the presence of the corrected-transcript, structured-note, and quality-report bundle. That bundle is not required for a transcript-only request.

## Essential quality rules

- **Raw vs corrected**: never overwrite `source.json` or rewrite raw `transcript.*` to make ASR look accurate. Preserve a copy of the actual recognized words and timings; editable documents are separate.
- **Evidence labels**: distinguish verbatim screen text, a faithful paraphrase of spoken content, a plausible ASR correction, and the agent's additional advice. Never pass an illustrative prompt, guessed button, URL, file, version, or parameter off as a verbatim source.
- **Coverage**: process all requested episodes/chapters; cite `[mm:ss]` next to substantive procedures. Build a series index and per-episode outputs if multiple episodes were requested; avoid merging identities and timebases.
- **Scene-aware checks**: timestamps enable targeted key-frame review. Inspect original video rather than relying exclusively on subtitles for visible code, equations, configuration or on-screen prompts. For audio-only input, visual review is not applicable; when relevant video visuals cannot be inspected, say `未进行画面核验`.
- **Safety and scale**: avoid huge accidental series downloads, paid cloud transcribers, unintended repository commits, and automatic removal of user originals. Prefer offline ASR; pretrained model initialization may fetch weights on first run, so do not promise completely offline availability without checking cache.
- **Boundaries**: This skill produces textual knowledge and evidence; animation assets are outside its scope.

## Successful response

Report the source, episode coverage and duration, tools/models actually used, output directory, which files were generated, any significant corrections or contradictions, outstanding uncertainties, and the next useful action. Never claim unverified word-perfect transcription or that a multipart series has been fully processed when it has not.
