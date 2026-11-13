"""Self-check for script chunking. Run: uv run python tests/test_text.py"""

from voiceclone.core import (PARAGRAPH_PAUSE_SECONDS, PAUSE_SECONDS, PRESETS, Style, chunk_text, parse_script,
                             split_sentences, with_base_emotion)

assert chunk_text("") == [] and chunk_text("   \n ") == []
assert split_sentences("Hello there. How are you?\nFine!") == ["Hello there.", "How are you?", "Fine!"]
assert split_sentences("I met Dr. Rao and Mr. Iyer. Then left.") == ["I met Dr. Rao and Mr. Iyer.", "Then left."]
assert split_sentences('He said "stop." Then ran.') == ['He said "stop."', "Then ran."]

long_sentence = ", ".join(f"clause number {i}" for i in range(60)) + "."
chunks = chunk_text(long_sentence, max_chars=100)
assert all(len(c) <= 100 for c in chunks), chunks
assert " ".join(chunks) == long_sentence  # nothing lost or reordered

many = " ".join(f"Sentence {i} is short." for i in range(50))
chunks = chunk_text(many, max_chars=120)
assert all(len(c) <= 120 for c in chunks) and " ".join(chunks) == many
assert all(c.endswith(".") for c in chunks)  # packing never splits mid-sentence when sentences fit

# --- emotion tags ---
base = Style(pitch=1.0)
segs = parse_script("Plain start. [happy] Good news! [sad] Bad news. [neutral] Back to normal.", base)
assert [s.text for s in segs] == ["Plain start.", "Good news!", "Bad news.", "Back to normal."]
assert segs[0].style == base and segs[3].style == base  # untagged and [neutral] use the base
assert segs[1].style.exaggeration == PRESETS["happy"]["exaggeration"]
assert segs[1].style.pitch == base.pitch + PRESETS["happy"]["pitch"]  # emotion pitch adds to voice pitch
assert segs[2].style.pitch == base.pitch + PRESETS["sad"]["pitch"]   # presets don't stack

segs = parse_script("[happy] One. [happy] Two.")
assert segs[0].style == segs[1].style

segs = parse_script("[excited pitch=+2 ex=1.3 pace=0.2 temp=0.5 ref=95] Hi.")
st = segs[0].style
assert (st.pitch, st.exaggeration, st.cfg, st.temperature, st.ref_start) == (2.0, 1.3, 0.2, 0.5, 95.0)

segs = parse_script("First. [pause=1.5] Second.\n\nNew paragraph.")
assert segs[0].pause_after == PAUSE_SECONDS + 1.5
assert segs[1].pause_after == PARAGRAPH_PAUSE_SECONDS and segs[2].text == "New paragraph."

try:
    parse_script("[whisper] hi")
    raise AssertionError("unknown tag must raise")
except ValueError as err:
    assert "Unknown tag" in str(err)

assert with_base_emotion("Hi.") == "Hi."
assert with_base_emotion("Hi.", "calm", ex=0.9) == "[calm ex=0.9] Hi."
assert parse_script(with_base_emotion("Hi.", "calm", ex=0.9))[0].style.exaggeration == 0.9

print("ok")
