# Voice Clone

Local, free voice cloning on Apple Silicon. It uses [Chatterbox](https://github.com/resemble-ai/chatterbox) (MIT) via `chatterbox-tts==0.1.7`.

## Layout
- `voiceclone/core.py`: holds `VoiceCloner`, which loads the model once, picks MPS with a CPU fallback, and caches speaker conditioning per clip. It also has the text chunking (`split_sentences`, `chunk_text`) and `trim_reference`.
- `voiceclone/cli.py`: the `voiceclone` command.
- `voiceclone/app.py`: the `voiceclone-ui` Gradio app, bound to `127.0.0.1` only, with `share=False`.
- `tests/test_text.py`: an assert-based self-check for chunking.

## Commands
- Install: `uv sync` (Python 3.11 is pinned in `.python-version`)
- Test: `uv run python tests/test_text.py`
- CLI: `uv run voiceclone --ref ref.wav --text script.txt --out outputs/out.wav`
- UI: `uv run voiceclone-ui`

## Rules
- Use Python 3.11. Chatterbox pins `torch==2.6.0`, `numpy<2`, `gradio==6.8.0` and `transformers==5.2.0`. Never add your own versions of these. Let `chatterbox-tts` own them.
- Keep the app local. Never set `share=True`, and never bind to `0.0.0.0` or add cloud TTS APIs. With `HF_HUB_OFFLINE=1`, it runs offline after the first model download.
- Never commit audio, voice recordings or `outputs/`. They are personal biometric data.
- Chatterbox uses only the first ~6 s (T3) and ~10 s (S3Gen) of the reference for prosody (`ENC_COND_LEN`, `DEC_COND_LEN` in `chatterbox/tts.py`). The speaker embedding uses the whole clip. Trim the reference to a clean segment, not the full recording.
- Scripts can carry tags (`[happy]`, `[pause=1]`, `[pitch=+1 ex=0.9 pace=0.3 temp=0.7 ref=95]`). These are parsed by `parse_script` into `Segment`s with a `Style`. Preset pitch is relative to the base `Style.pitch`, so presets never stack. Unknown tags raise `ValueError`. Never let an unknown tag be read aloud. Pitch is a librosa post-shift. Emotion is Chatterbox `exaggeration`, plus `cfg` for pace and `temperature` for variation.
- `VoiceCloner` caches conditioning per `(file, mtime, start, seconds)`, so `[ref=]` switches are cheap after the first use.
- Keep chunks at or below `MAX_CHARS` (280). Longer inputs degrade or get cut off at `max_new_tokens=1000`.
- After editing `voiceclone/` or `tests/`, a PostToolUse hook (`.claude/hooks/check-core.sh`) reruns the self-check. Fix any failure it reports.
- Only clone voices with the speaker's consent.

## Skill
- `.claude/skills/clone-voice`: a guided workflow for turning a recording plus a script into cloned speech.
