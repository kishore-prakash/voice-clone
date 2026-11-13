"""Command line: voiceclone --ref voice.wav --text script.txt --out speech.wav"""

import argparse
import sys
import time
from pathlib import Path

from .core import PRESETS, Style, parse_script, with_base_emotion  # light imports; torch loads only in VoiceCloner


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Speak a script in a cloned voice (runs locally).")
    p.add_argument("--ref", required=True, help="Reference recording of the voice (wav/mp3/m4a)")
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--text", help="Path to a .txt script")
    src.add_argument("--say", help="Text to speak, inline")
    p.add_argument("--out", default="outputs/speech.wav", help="Output WAV path")
    p.add_argument("--ref-start", type=float, default=0.0, help="Seconds into --ref where the clean clip starts")
    p.add_argument("--ref-seconds", type=float, default=None, help="Length of reference clip to use (e.g. 20)")
    p.add_argument("--emotion", choices=sorted(PRESETS), default="neutral",
                   help="Base emotion; the script can switch with tags like [happy] or [sad]")
    p.add_argument("--exaggeration", type=float, default=None, help="Emotion intensity, 0.25-2.0 (overrides --emotion)")
    p.add_argument("--cfg", type=float, default=None, help="Pace/adherence, lower = slower, 0-1 (overrides --emotion)")
    p.add_argument("--temperature", type=float, default=None, help="Variation, lower = steadier (overrides --emotion)")
    p.add_argument("--pitch", type=float, default=0.0,
                   help="Voice pitch shift in semitones, e.g. -2 or +1.5; emotion pitch is added on top")
    p.add_argument("--device", choices=["mps", "cpu"], default=None, help="Default: mps if available")
    args = p.parse_args(argv)

    text = Path(args.text).read_text(encoding="utf-8") if args.text else args.say
    if not Path(args.ref).is_file():
        p.error(f"reference not found: {args.ref}")

    text = with_base_emotion(text, args.emotion, args.exaggeration, args.cfg, args.temperature)
    base = Style(pitch=args.pitch, ref_start=args.ref_start)
    try:
        parse_script(text, base)  # fail on a bad tag before spending a minute loading the model
    except ValueError as err:
        p.error(str(err))

    import soundfile as sf

    from .core import VoiceCloner

    started = time.time()
    cloner = VoiceCloner(args.device)
    print(f"Model loaded on {cloner.device} in {time.time() - started:.0f}s")
    audio = cloner.speak(text, args.ref, base, args.ref_seconds,
                         progress=lambda i, n, chunk: print(f"[{i}/{n}] {chunk[:70]}"))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    sf.write(out, audio, cloner.sample_rate)
    print(f"Wrote {out} ({len(audio) / cloner.sample_rate:.1f}s audio) in {time.time() - started:.0f}s total")
    return 0


if __name__ == "__main__":
    sys.exit(main())
