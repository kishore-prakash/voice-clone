"""Local web UI: uv run voiceclone-ui, then open http://127.0.0.1:7860"""

import os

os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")  # keep the app fully local

import gradio as gr

from .core import PRESETS, Style, VoiceCloner, parse_script, with_base_emotion

_cloner: VoiceCloner | None = None
TAG_HELP = (
    "**Emotion tags.** Put a tag before any sentence. It applies until the next tag. "
    f"Emotions: `{'` `'.join(f'[{name}]' for name in PRESETS)}`. Pause: `[pause=1]`. "
    "Fine-tune: `[happy pitch=+2 ex=1.0 pace=0.3]`. "
    "Real emotion from your recording: `[ref=95]` takes the voice from 95 s into the reference file "
    "(pick a spot where the speaker sounds the way you want). Blank lines add a longer pause."
)
EXAMPLE = ("[calm] Welcome back. Today I have some news to share.\n\n"
           "[excited] We finally did it! The project is live! [pause=0.5]\n\n"
           "[sad] It was not easy, and some days felt very long. [neutral] Thank you for listening.")


def _get_cloner() -> VoiceCloner:
    global _cloner
    if _cloner is None:
        _cloner = VoiceCloner()
    return _cloner


def generate(ref_path, ref_start, ref_seconds, script, emotion, pitch, custom, exaggeration, cfg, temperature,
             progress=gr.Progress()):
    if not ref_path:
        raise gr.Error("Upload or record a reference clip first.")
    if custom:
        script = with_base_emotion(script or "", emotion, exaggeration, cfg, temperature)
    else:
        script = with_base_emotion(script or "", emotion)
    base = Style(pitch=pitch, ref_start=ref_start or 0.0)
    try:
        if not parse_script(script, base):
            raise gr.Error("Script is empty.")
    except ValueError as err:
        raise gr.Error(str(err))
    progress(0, desc="Loading model (first run downloads it)")
    cloner = _get_cloner()
    audio = cloner.speak(script, ref_path, base, ref_seconds or None,
                         progress=lambda i, n, _: progress((i - 1) / n, desc=f"Segment {i} of {n}"))
    return cloner.sample_rate, audio


def build() -> gr.Blocks:
    with gr.Blocks(title="Voice Clone") as demo:
        gr.Markdown("## Voice Clone\nRuns on this Mac. Use a clean 10–30 s clip of one speaker, "
                    "no music. The first ~10 s shape the voice most.")
        with gr.Row():
            with gr.Column():
                ref = gr.Audio(label="Reference voice", type="filepath", sources=["upload", "microphone"])
                with gr.Row():
                    ref_start = gr.Number(label="Clip start (s)", value=0, minimum=0)
                    ref_seconds = gr.Number(label="Clip length (s, 0 = all)", value=20, minimum=0)
                script = gr.Textbox(label="Script", lines=12, value=EXAMPLE)
                gr.Markdown(TAG_HELP)
                with gr.Row():
                    emotion = gr.Dropdown(list(PRESETS), value="neutral", label="Base emotion (untagged text)")
                    pitch = gr.Slider(-4, 4, 0, step=0.5, label="Voice pitch (semitones)")
                with gr.Accordion("Fine-tune base emotion", open=False):
                    custom = gr.Checkbox(False, label="Use these values instead of the emotion preset")
                    exaggeration = gr.Slider(0.25, 2.0, 0.5, step=0.05, label="Exaggeration (emotion strength)")
                    cfg = gr.Slider(0.0, 1.0, 0.5, step=0.05, label="Pace (lower = slower)")
                    temperature = gr.Slider(0.05, 2.0, 0.8, step=0.05, label="Temperature (lower = steadier)")
                run = gr.Button("Generate", variant="primary")
            with gr.Column():
                out = gr.Audio(label="Cloned speech", type="numpy")
        emotion.change(lambda e: [PRESETS[e]["exaggeration"], PRESETS[e]["cfg"], PRESETS[e]["temperature"]],
                       emotion, [exaggeration, cfg, temperature])
        run.click(generate, [ref, ref_start, ref_seconds, script, emotion, pitch, custom,
                             exaggeration, cfg, temperature], out)
    return demo


def main() -> None:
    build().queue().launch(server_name="127.0.0.1", share=False, inbrowser=True)


if __name__ == "__main__":
    main()
