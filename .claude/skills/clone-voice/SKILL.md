---
name: clone-voice
description: Generate speech in a cloned voice from a reference recording and a script using this repo's local Chatterbox CLI. Use when the user asks to clone a voice, speak a script in someone's voice, prepare a reference clip, or regenerate audio with different settings.
---

# Clone a voice locally

Everything runs on this Mac. Nothing is uploaded.

1. **Confirm consent.** Only clone a voice the user owns or has permission to use. Ask if unclear.
2. **Prepare the reference clip.** Pick 10–30 s of clean, single-speaker speech with no music. The first ~10 s matter most.
   - Find the start: `ffprobe -i <file>` for duration, then ask the user for a clean timestamp, or try `--ref-start`.
   - Optional denoise or music removal: `uvx demucs --two-stems=vocals <file>`. This downloads a model; ask first.
3. **Generate:**
   ```bash
   uv run voiceclone --ref <audio> --ref-start <s> --ref-seconds 20 --text <script.txt> --out outputs/<name>.wav
   ```
   Long scripts are split into sentence chunks automatically.
4. **Add emotion where it helps.** Use inline tags such as `[calm]`, `[excited]`, `[sad]`, `[happy]`, `[angry]`, `[serious]` and `[neutral]`, plus `[pause=0.5]`. Fine-tune with `[happy pitch=+1 ex=0.9 pace=0.3]`. For the most natural result, ask the user for timestamps in the recording where the speaker sounds that way, then use `[excited ref=<seconds>]`. Validate tags before loading the model: the CLI fails fast on unknown tags.
5. **Tune if needed:**
   - Sounds flat: `--emotion happy` or `--exaggeration 0.7`.
   - Too fast or rushed: `--cfg 0.3`.
   - Unstable or odd artefacts: `--temperature 0.6`.
   - Voice too high or low: `--pitch -1` (keep it within ±3).
   - Voice drifts: try a different, cleaner `--ref-start`.
6. **Report** the output path and duration. Outputs carry Chatterbox's inaudible Perth watermark.

Never commit audio. `.gitignore` covers `outputs/` and audio extensions.
