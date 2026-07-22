"""Pure test for the spoken-preview truncation (no subprocess / no device).
Run: python -m pytest tests/test_tts.py  (or plain python tests/test_tts.py)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from voice.tts import truncate_for_speech

MARKER = " … full response returned."


def test_short_not_truncated():
    s, tr = truncate_for_speech("4.", 350)
    assert s == "4." and tr is False


def test_zero_disables_truncation():
    t = "x" * 1000
    s, tr = truncate_for_speech(t, 0)
    assert s == t and tr is False


def test_long_gets_marker_and_stays_bounded():
    t = "Sentence. " * 100
    s, tr = truncate_for_speech(t, 350)
    assert tr is True
    assert s.endswith(MARKER)
    assert len(s) <= 350 + len(MARKER)


def test_cuts_on_sentence_boundary_in_back_half():
    t = "A" * 180 + ". " + "B" * 400
    s, tr = truncate_for_speech(t, 350)
    assert tr is True
    assert "B" not in s                    # stopped at the sentence boundary
    assert s.startswith("A" * 180 + ".")


if __name__ == "__main__":
    tests = [test_short_not_truncated, test_zero_disables_truncation,
             test_long_gets_marker_and_stays_bounded,
             test_cuts_on_sentence_boundary_in_back_half]
    for t in tests:
        t()
    print(f"{len(tests)}/{len(tests)} PASS")
