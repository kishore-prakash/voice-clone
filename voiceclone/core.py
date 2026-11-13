"""Voice cloning core: load Chatterbox once, clone a reference voice, speak long scripts."""

import os

os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")  # ops missing on MPS run on CPU instead of crashing

import re
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np

MAX_CHARS = 280  # Chatterbox degrades / truncates on long inputs; keep chunks short
PAUSE_SECONDS = 0.2
PARAGRAPH_PAUSE_SECONDS = 0.6
_ABBREVIATIONS = {"mr", "mrs", "ms", "dr", "prof", "sr", "jr", "st", "vs", "etc", "e.g", "i.e", "no", "fig", "inc", "ltd"}


def split_sentences(text: str) -> list[str]:
    """Split text into sentences without breaking on common abbreviations like 'Dr.'."""
    pieces = re.split(r"(?<=[.!?])\s+|(?<=[.!?][\"')\]])\s+", " ".join(text.split()))
    sentences: list[str] = []
    for piece in filter(None, (p.strip() for p in pieces)):
        prev_word = sentences[-1].rsplit(" ", 1)[-1].rstrip(".").lower() if sentences else ""
        if sentences and sentences[-1].endswith(".") and prev_word in _ABBREVIATIONS:
            sentences[-1] += " " + piece
        else:
            sentences.append(piece)
    return sentences


def _split_long(sentence: str, max_chars: int) -> list[str]:
    """Break one oversized sentence on clause punctuation, then on words."""
    parts, current = [], ""
    for token in re.split(r"(?<=[,;:])\s+|\s+", sentence):
        candidate = f"{current} {token}".strip()
        if len(candidate) > max_chars and current:
            parts.append(current)
            current = token
        else:
            current = candidate
    return parts + ([current] if current else [])


def chunk_text(text: str, max_chars: int = MAX_CHARS) -> list[str]:
    """Pack sentences into chunks of at most max_chars (a single word longer than that stays whole)."""
    chunks, current = [], ""
    for sentence in split_sentences(text):
        for part in _split_long(sentence, max_chars) if len(sentence) > max_chars else [sentence]:
            candidate = f"{current} {part}".strip()
            if len(candidate) > max_chars and current:
                chunks.append(current)
                current = part
            else:
                current = candidate
    return chunks + ([current] if current else [])


@dataclass(frozen=True)
class Style:
    """How a stretch of the script is spoken."""
    exaggeration: float = 0.5  # emotion intensity (Chatterbox emotion_adv), 0.25-2.0
    cfg: float = 0.5           # pace / adherence; lower = slower, more deliberate
    temperature: float = 0.8   # variation; lower = steadier
    pitch: float = 0.0         # semitones, applied after generation; beyond +/-3 starts to change the voice
    ref_start: float | None = None  # seconds into the reference recording to take the voice from


# Starting points tuned by ear, not measured. Pitch in presets is added to the base pitch.
PRESETS: dict[str, dict] = {
    "neutral": dict(exaggeration=0.5, cfg=0.5, temperature=0.8, pitch=0.0),
    "happy":   dict(exaggeration=0.8, cfg=0.4, temperature=0.9, pitch=1.0),
    "excited": dict(exaggeration=1.1, cfg=0.3, temperature=0.9, pitch=1.5),
    "sad":     dict(exaggeration=0.35, cfg=0.3, temperature=0.7, pitch=-1.0),
    "calm":    dict(exaggeration=0.3, cfg=0.4, temperature=0.6, pitch=-0.5),
    "angry":   dict(exaggeration=1.2, cfg=0.5, temperature=0.9, pitch=0.5),
    "serious": dict(exaggeration=0.4, cfg=0.5, temperature=0.6, pitch=-0.5),
}
_KEYS = {"ex": "exaggeration", "exaggeration": "exaggeration", "pace": "cfg", "cfg": "cfg",
         "temp": "temperature", "temperature": "temperature", "pitch": "pitch", "ref": "ref_start"}
_TAG = re.compile(r"\[([^\[\]]*)\]")


@dataclass(frozen=True)
class Segment:
    text: str
    style: Style
    pause_after: float


def _apply_tag(tag: str, current: Style, base: Style) -> tuple[Style, float | None]:
    """Turn '[happy pitch=+2]' into a Style; '[pause=1]' into a pause. Unknown tags raise ValueError.

    Presets are set relative to `base` (the user's global settings), so '[happy] [happy]' does not stack.
    """
    style, pause = current, None
    for word in tag.lower().replace(",", " ").split():
        key, _, value = word.partition("=")
        if key == "neutral" and not value:
            style = base
        elif not value and key in PRESETS:
            preset = PRESETS[key]
            style = replace(style, **{**preset, "pitch": base.pitch + preset["pitch"]})
        elif key == "pause" and value:
            pause = float(value.rstrip("s"))
        elif key in _KEYS and value:
            style = replace(style, **{_KEYS[key]: float(value)})
        else:
            raise ValueError(f"Unknown tag [{tag}]. Use an emotion ({', '.join(PRESETS)}), "
                             "pause=SECONDS, or ex=/pace=/temp=/pitch=/ref= values.")
    return style, pause


def parse_script(script: str, base: Style = Style()) -> list[Segment]:
    """Split a tagged script into generation-sized segments, each with its style and trailing pause.

    A tag changes the style for everything after it until the next tag; '[neutral]' resets.
    """
    segments: list[Segment] = []
    style = base
    parts = _TAG.split(script)  # even indexes: text, odd indexes: tag bodies
    for i, part in enumerate(parts):
        if i % 2:
            style, pause = _apply_tag(part, style, base)
            if pause and segments:
                last = segments[-1]
                segments[-1] = replace(last, pause_after=last.pause_after + pause)
            continue
        paragraphs = [p for p in re.split(r"\n\s*\n", part) if p.strip()]
        for p_index, paragraph in enumerate(paragraphs):
            chunks = chunk_text(paragraph)
            for c_index, chunk in enumerate(chunks):
                end_of_paragraph = c_index == len(chunks) - 1 and (
                    p_index < len(paragraphs) - 1 or re.search(r"\n\s*\n\s*$", part))
                segments.append(Segment(chunk, style, PARAGRAPH_PAUSE_SECONDS if end_of_paragraph else PAUSE_SECONDS))
    return segments


def with_base_emotion(script: str, emotion: str = "neutral", ex: float | None = None,
                      pace: float | None = None, temp: float | None = None) -> str:
    """Prefix the script with a tag so the base emotion and any overrides use the same rules as inline tags."""
    words = [emotion] + [f"{k}={v}" for k, v in (("ex", ex), ("pace", pace), ("temp", temp)) if v is not None]
    return script if words == ["neutral"] else f"[{' '.join(words)}] {script}"


def trim_reference(path: str, start: float = 0.0, seconds: float | None = None) -> str:
    """Return a path to the reference audio, cut to [start, start+seconds] when asked."""
    if not start and not seconds:
        return path
    import librosa
    import soundfile as sf

    wav, sr = librosa.load(path, sr=None, mono=True, offset=start, duration=seconds)
    if wav.size == 0:
        raise ValueError(f"No audio at start={start}s in {path}")
    out = Path(tempfile.gettempdir()) / "voiceclone-reference.wav"  # one reused file, no temp-dir pileup
    sf.write(out, wav, sr)
    return str(out)


class VoiceCloner:
    def __init__(self, device: str | None = None):
        import torch
        from chatterbox.tts import ChatterboxTTS

        self.device = device or ("mps" if torch.backends.mps.is_available() else "cpu")
        try:
            self.model = ChatterboxTTS.from_pretrained(device=self.device)
        except Exception as err:
            if self.device == "cpu":
                raise
            print(f"Loading on {self.device} failed ({err}); falling back to CPU.")
            self.device = "cpu"
            self.model = ChatterboxTTS.from_pretrained(device="cpu")
        self.sample_rate = self.model.sr
        self._conds: dict[tuple, object] = {}

    def set_reference(self, path: str, start: float = 0.0, seconds: float | None = None) -> None:
        """Condition the model on a clip of `path`. Cached per clip, so switching between [ref=] clips is cheap."""
        key = (path, os.path.getmtime(path), start, seconds)
        if key not in self._conds:  # speaker conditioning is the slow part; compute once per clip
            self.model.prepare_conditionals(trim_reference(path, start, seconds))
            self._conds[key] = self.model.conds
        self.model.conds = self._conds[key]

    def speak(self, script: str, ref_path: str, base: Style = Style(), ref_seconds: float | None = None,
              progress=None) -> np.ndarray:
        """Speak a (optionally tagged) script in the reference voice; returns mono float32 audio."""
        segments = parse_script(script, base)
        if not segments:
            raise ValueError("Script is empty.")
        audio = []
        for i, seg in enumerate(segments, 1):
            if progress:
                progress(i, len(segments), seg.text)
            s = seg.style
            self.set_reference(ref_path, s.ref_start or 0.0, ref_seconds)
            wav = self.model.generate(seg.text, exaggeration=s.exaggeration, cfg_weight=s.cfg,
                                      temperature=s.temperature).squeeze(0).numpy().astype(np.float32)
            if s.pitch:
                import librosa
                wav = librosa.effects.pitch_shift(wav, sr=self.sample_rate, n_steps=s.pitch)
                # re-mark: the shift may damage the AI-audio watermark Chatterbox added during generate()
                wav = self.model.watermarker.apply_watermark(wav, sample_rate=self.sample_rate).astype(np.float32)
            audio += [wav, np.zeros(int(seg.pause_after * self.sample_rate), dtype=np.float32)]
        return np.concatenate(audio[:-1])
