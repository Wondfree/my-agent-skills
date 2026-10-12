#!/bin/sh
# Locate a compatible Python on the current host, or honor an explicit override.
set -eu
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
script="$script_dir/video_pipeline.py"
if [ -n "${VIDEO_TO_KNOWLEDGE_PYTHON:-}" ]; then
  exec "$VIDEO_TO_KNOWLEDGE_PYTHON" "$script" "$@"
fi

engine="faster_whisper"
previous=""
for arg in "$@"; do
  if [ "$previous" = "--engine" ]; then
    if [ "$arg" = "whisper" ]; then engine="whisper"; fi
    previous=""
  elif [ "$arg" = "--engine" ]; then
    previous="--engine"
  fi
done
# Only capture demands its selected ASR module. Doctor prefers an environment
# with ASR installed to prevent a misleading "modules unavailable" result.
need_engine=""
if [ "${1:-}" = "capture" ] || [ "${1:-}" = "doctor" ]; then need_engine="$engine"; fi
fallback_python=""
fallback_whisper=""
old_ifs="$IFS"
IFS=:
for dir in $PATH; do
  [ -n "$dir" ] || dir=.
  for binary in python3 python; do
    candidate="$dir/$binary"
    [ -x "$candidate" ] && [ ! -d "$candidate" ] || continue
    if "$candidate" -c 'import sys; assert sys.version_info >= (3,9)' >/dev/null 2>&1; then
      [ -n "$fallback_python" ] || fallback_python="$candidate"
      if [ -z "$need_engine" ] || "$candidate" -c "import $need_engine" >/dev/null 2>&1; then
        IFS="$old_ifs"
        exec "$candidate" "$script" "$@"
      fi
      if [ "${1:-}" = "doctor" ] && [ -z "$fallback_whisper" ] &&
        "$candidate" -c 'import whisper' >/dev/null 2>&1; then
        fallback_whisper="$candidate"
      fi
    fi
  done
done
IFS="$old_ifs"
if [ "${1:-}" = "doctor" ] && [ -n "$fallback_whisper" ]; then
  exec "$fallback_whisper" "$script" "$@"
fi
if [ "${1:-}" = "doctor" ] && [ -n "$fallback_python" ]; then
  exec "$fallback_python" "$script" "$@"
fi
echo "ERROR: No compatible Python environment with the requested ASR engine was found in PATH." >&2
echo "Set VIDEO_TO_KNOWLEDGE_PYTHON to an interpreter with the required package, or activate the right environment." >&2
exit 2
