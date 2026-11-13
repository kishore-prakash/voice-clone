# Voice Clone

Clone a voice from a short recording and have it read any English script. Everything runs locally on an Apple Silicon Mac, free and offline after setup.

It is built on [Chatterbox](https://github.com/resemble-ai/chatterbox) by Resemble AI (MIT license). It is zero-shot: there is no training step, and a 10–30 second clip is enough.

## Requirements
- An Apple Silicon Mac, running on MPS (the Apple GPU) with automatic fallback to CPU
- [uv](https://docs.astral.sh/uv/) and [ffmpeg](https://ffmpeg.org/) (`brew install uv ffmpeg`)
- Disk space measured on the dev Mac: 995 MB for the Python environment (`.venv`) and 3.0 GB for the Chatterbox weights in `~/.cache/huggingface`

## Setup
```bash
uv sync
```
The first generation downloads the model weights from Hugging Face into `~/.cache/huggingface`. After that, set `HF_HUB_OFFLINE=1` to run fully offline (see below).

## Prepare the reference clip
Quality depends mostly on this clip:
- Use one speaker only, with no music, no background noise and no echo.
- Use 10–30 seconds of natural speech. The **first ~10 seconds matter most**.
- Use a clean section of your 10-minute recording, not the whole file.

To cut a 20-second clip that starts 1m05s into the recording:
```bash
ffmpeg -ss 65 -t 20 -i recording.m4a -ac 1 ref.wav
```
Or skip cutting and pass `--ref-start 65 --ref-seconds 20` to the CLI, or set **Clip start** and **Clip length** in the UI.

If the recording has background music, separate the vocals first (this downloads a model):
```bash
uvx demucs --two-stems=vocals recording.m4a
```

## Use: web UI
```bash
uv run voiceclone-ui
```
This opens http://127.0.0.1:7860. Upload or record a reference clip, paste the script (emotion tags work here too), pick a base emotion and voice pitch, then press **Generate**. The app is only reachable from this Mac.

## Use: command line
```bash
uv run voiceclone --ref ref.wav --text script.txt --out outputs/speech.wav
uv run voiceclone --ref recording.m4a --ref-start 65 --ref-seconds 20 --say "Hello there!"
```

Long scripts are split into sentence-sized chunks (at most 280 characters each), generated one by one, and joined with short pauses into one WAV. Blank lines between paragraphs give a longer pause.

| Option | Default | Effect |
|---|---|---|
| `--emotion` | neutral | Base emotion for untagged text: `neutral` `happy` `excited` `sad` `calm` `angry` `serious` |
| `--pitch` | 0 | Voice pitch shift in semitones, e.g. `-1.5`. Emotion pitch is added on top. |
| `--exaggeration` | from emotion | Emotion strength, 0.25–2.0 |
| `--cfg` | from emotion | Pace. Lower is slower and more deliberate. |
| `--temperature` | from emotion | Variation. Lower is steadier. |
| `--device` | auto | `mps` or `cpu` |

## Emotions, pitch and pauses
Put tags in the script. A tag applies to everything after it, until the next tag.

```text
[calm] Welcome back. Today I have some news to share.

[excited] We finally did it! The project is live! [pause=0.5]

[sad] It was not easy. [neutral] Thank you for listening.
```

| Tag | Effect |
|---|---|
| `[happy]` `[excited]` `[sad]` `[calm]` `[angry]` `[serious]` | Emotion preset: sets strength, pace, variation and a small pitch change |
| `[neutral]` | Back to the base settings |
| `[pause=1]` | Adds 1 s of silence |
| `[happy pitch=+2 ex=1.0 pace=0.3 temp=0.7]` | Preset plus fine-tuning. Any of the values work alone too, e.g. `[pitch=-1]` |
| `[ref=95]` | Takes the voice from 95 s into the reference recording |

**How each one works:**
- **Emotion** uses Chatterbox's built-in emotion control (`exaggeration`), plus pace and variation. The preset values are starting points tuned by ear, not measured. Adjust them in `PRESETS` in [voiceclone/core.py](voiceclone/core.py).
- **The most natural emotion comes from the reference itself.** Chatterbox copies the delivery of the clip it hears. If your 10-minute recording has a part where the speaker laughs or sounds excited, point an `[excited ref=…]` tag at that timestamp. That gives real emotion in the real voice, which no setting can fake.
- **Pitch** is shifted after generation with librosa. ±2 semitones sounds natural. Beyond about ±3 it starts to change who the voice sounds like.
- **Not possible with this model:** whispering, laughing, crying and other non-speech sounds. Tags for these are rejected rather than read aloud.

## Run offline
Once the weights are cached, prefix any command with `HF_HUB_OFFLINE=1` and it never touches the network. The CLI and UI were both tested this way.
```bash
HF_HUB_OFFLINE=1 uv run voiceclone-ui
HF_HUB_OFFLINE=1 uv run voiceclone --ref ref.wav --text script.txt
```

## Tests
```bash
uv run python tests/test_text.py
```

## Project layout
```
voiceclone/core.py   model loading, reference trimming, script chunking, generation
voiceclone/cli.py    `voiceclone` command
voiceclone/app.py    `voiceclone-ui` Gradio app (localhost only)
tests/test_text.py   chunking self-check
CLAUDE.md            project rules for Claude Code
.claude/             Claude Code settings, post-edit test hook, `clone-voice` skill
```

## Notes
- **Consent:** only clone voices you own or have explicit permission to use.
- **Watermark:** Chatterbox embeds an inaudible [Perth](https://github.com/resemble-ai/Perth) watermark in every output, so the audio can be identified as AI-generated. Pitch-shifted segments are watermarked again after the shift.
- **Privacy:** recordings and outputs are git-ignored (`outputs/`, `*.wav`, `*.mp3`, `*.m4a`, …). Don't commit them.
- **Not yet supported:** fine-tuning on the full 10 minutes. If zero-shot likeness isn't close enough, the next step is fine-tuning [GPT-SoVITS](https://github.com/RVC-Boss/GPT-SoVITS), which needs an NVIDIA GPU or Google Colab.
