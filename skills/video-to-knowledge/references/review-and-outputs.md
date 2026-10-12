# Review and output standards

## Review passes

1. **Source inventory**: source URL/file; playlist/episode title and ordering; duration; publication info if available; audio/subtitle/video availability and legal/access limitations. For a multipart series create `series_index.md` with one row per requested episode, status, link and output path.
2. **ASR pass**: read the entire transcript chronologically (e.g. 30–60 s per chunk or manageable token windows), normalize punctuation and paragraphs, correct homophones and terminology using local context. Keep timing anchored to original ASR segments. Do NOT run unchecked global find/replace: e.g. generic Chinese characters can be valid words in other contexts. Maintain `uncertain_term → candidate → evidence → resolution` notes for consequential words.
3. **Visual pass**: make a time-ordered list of high-value timestamps: dialog boxes, model/version settings, sizes, UI names, code/commands, complete prompt blocks, charts. Extract several frames near each event, adjusting ±seconds to capture the correct state. Look at images personally with available visual tools. State that a screenshot cannot prove a hidden setting or unshown part of a prompt.
4. **Cross-check pass**: compare transcript instructions with screen settings. Annotate `[语音]`, `[画面已核实]`, `[推断/整理建议]`, or `[待核实]`. Numerically validate dimensions, units and quantities; note demonstrable conflicts even if the speaker makes an error.
5. **Editorial pass**: correct terminology, then produce a task-oriented artifact. Do not use a generic tutorial template for interviews. Use chapters/timecodes and clear distinctions between original steps and optional improved practice.
6. **QC pass**: confirm all requested coverage, representative beginning/middle/end timestamps, deliverable links/paths, no unexplained claims and uncertainty flags.

## Minimum structured outputs

For **tool/tutorial videos** use `tutorial_structured.md`:
- Source and scope; verified vs unverified
- Learning objective and short high-level workflow
- Timecoded chapter table
- Prerequisites/software/version/platform
- Step-by-step operation with inputs, outputs, checks and pitfalls
- Prompt/code/config extraction; literal original only when it can be read in full and accurately
- Conflicts and uncertainty; source advice vs assistant suggestions
- Repeatable checklist; references and optional next experiment

For **talks/interviews/concept lectures** use `knowledge_structured.md`:
- Source and scope
- Chapter/timestamp table
- Arguments/claims and evidence
- Vocabulary and definitions
- Practical implications and open questions
- Unsupported claims or source conflicts, each labeled

For **prompts** use `prompts_from_video.md` only when warranted:
- Label each as `画面逐字核实`, `口播内容整理`, or `整理者构造的复用模板`.
- Retain exact variable placeholders and image/reference dependencies, including what was not visible.
- Never portray an AI reconstruction as an author's downloadable original.

For `quality_report.md`:
- Source media and episodes processed
- Full/partial duration coverage and model/engine
- Key frames inspected and consequential corrections
- Confidence/known gaps (ASR errors, missing images or source files)
- Final deliverable inventory and what remains unverified

## Failure modes to avoid

- Downloading only part 1 of a 10-part Bilibili tutorial and saying the series was completed.
- Publishing a transcript produced by Base model as 100% accurate; relying on an unverified technical term.
- Treating voice-recognized `1280×170` as correct when the Photoshop dialog visibly reads `1280×720`.
- Saying `8×8 at 1280px per cell` fits into `4096px`: the calculation yields `10240px`.
- Claiming a prompt is a verbatim copy when only paraphrased from speech.
- Mixing user-provided material, model-generated improvements and source instructions.
- Overwriting a user's video, source SRT, transcript or unrelated project files.
