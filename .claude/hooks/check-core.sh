#!/bin/bash
# PostToolUse hook: after Claude edits package code, rerun the chunking self-check.
# Exit 2 sends the failure back to Claude so it fixes the regression.
file=$(jq -r '.tool_input.file_path // empty')
case "$file" in
  */voiceclone/*.py|*/tests/*.py) ;;
  *) exit 0 ;;
esac
cd "$CLAUDE_PROJECT_DIR" || exit 0
if ! out=$(uv run python tests/test_text.py 2>&1); then
  echo "tests/test_text.py failed after editing $file:" >&2
  echo "$out" | tail -15 >&2
  exit 2
fi
