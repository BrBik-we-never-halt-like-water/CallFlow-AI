"""The STT scoring harness (`scripts/score_stt.py`).

Tested because the number it produces decides a vendor, and `docs/VOICE_STACK.md`
§6.3 lets one of its outputs disqualify a stack outright. A scorer nobody checks
is a way of being confidently wrong about which STT can hear an Indian caller.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "score_stt.py"
_spec = importlib.util.spec_from_file_location("score_stt", _SCRIPT)
assert _spec and _spec.loader
score_stt = importlib.util.module_from_spec(_spec)
sys.modules["score_stt"] = score_stt
_spec.loader.exec_module(score_stt)


class TestNormalisation:
    def test_case_and_punctuation_are_not_transcription_errors(self) -> None:
        assert score_stt.normalise("Haan, sir!") == score_stt.normalise("haan sir")

    def test_devanagari_and_latin_split_in_one_sentence(self) -> None:
        words = score_stt.normalise("मुझे EMI option chahiye")
        assert words == ["मुझे", "emi", "option", "chahiye"]


class TestWordErrorRate:
    def test_an_identical_transcript_scores_zero(self) -> None:
        line = "around five years experience hai"
        assert score_stt.word_error_rate(line, line) == 0.0

    def test_one_wrong_word_in_five_is_twenty_percent(self) -> None:
        rate = score_stt.word_error_rate(
            "around five years experience hai", "around fine years experience hai"
        )
        assert rate == pytest.approx(0.2)

    def test_an_empty_transcript_loses_every_word(self) -> None:
        assert score_stt.word_error_rate("teen char paanch", "") == pytest.approx(1.0)


class TestFieldSurvival:
    def test_a_phrase_survives_when_transcribed_intact(self) -> None:
        assert score_stt.phrase_survived(
            "five years", "main around five years se kaam kar raha hoon"
        )

    def test_the_garbled_case_wer_barely_notices(self) -> None:
        """One word wrong out of nine is ~11% WER and a lost eligibility field.

        This is §2.1's whole argument, as an assertion.
        """
        truth = "main around five years se kaam kar raha hoon"
        heard = "main around fine years se kaam kar raha hoon"

        assert score_stt.word_error_rate(truth, heard) < 0.15
        assert not score_stt.phrase_survived("five years", heard)

    def test_scattered_words_are_not_a_surviving_phrase(self) -> None:
        """Contiguity matters - a substring check would call this a pass."""
        assert not score_stt.phrase_survived(
            "five years", "five hundred rupees, and I have years of experience"
        )


def _corpus(tmp_path: Path, clips: dict[str, tuple[str, dict[str, str]]]) -> Path:
    root = tmp_path / "corpus"
    root.mkdir()
    for name, (truth, fields) in clips.items():
        (root / f"{name}.txt").write_text(truth, encoding="utf-8")
        (root / f"{name}.fields.json").write_text(json.dumps(fields), encoding="utf-8")
    (root / "candidates").mkdir()
    return root


def _candidate(root: Path, name: str, transcripts: dict[str, str]) -> None:
    directory = root / "candidates" / name
    directory.mkdir(parents=True)
    for clip, text in transcripts.items():
        (directory / f"{clip}.txt").write_text(text, encoding="utf-8")


class TestScoring:
    def test_a_perfect_candidate_scores_zero_on_both(self, tmp_path: Path) -> None:
        root = _corpus(tmp_path, {"c1": ("main five years se kaam", {"exp": "five years"})})
        _candidate(root, "good", {"c1": "main five years se kaam"})

        score = score_stt.score_candidate("good", root / "candidates" / "good", score_stt.load_corpus(root))

        assert score.wer == 0.0
        assert score.fer == 0.0
        assert not score.disqualified

    def test_losing_the_opt_out_disqualifies_whatever_else_it_scores(self, tmp_path: Path) -> None:
        """§6.3's first kill criterion, and the reason it is not a tiebreak."""
        root = _corpus(
            tmp_path,
            {"c1": ("mujhe call mat karo dobara", {"do_not_contact": "call mat karo"})},
        )
        # Near-perfect transcript - one word - and it still must not ship.
        _candidate(root, "nearly", {"c1": "mujhe call mat karna dobara"})

        score = score_stt.score_candidate(
            "nearly", root / "candidates" / "nearly", score_stt.load_corpus(root)
        )

        assert score.wer < 0.25
        assert score.optout_recall == 0.0
        assert score.disqualified

    def test_a_missing_transcript_counts_as_total_loss_not_a_skip(self, tmp_path: Path) -> None:
        """Averaging over what a stack managed would flatter the one that
        returned nothing for the hardest clip."""
        root = _corpus(
            tmp_path,
            {
                "c1": ("ek do teen", {"f": "ek do"}),
                "c2": ("chaar paanch chhe", {"f": "chaar paanch"}),
            },
        )
        _candidate(root, "partial", {"c1": "ek do teen"})

        score = score_stt.score_candidate(
            "partial", root / "candidates" / "partial", score_stt.load_corpus(root)
        )

        assert score.clips == 2
        assert score.wer == pytest.approx(0.5)
        assert score.fer == pytest.approx(0.5)
        assert score.missing == ["c2"]

    def test_the_disqualified_candidate_sorts_last_however_good_its_fer(self) -> None:
        clean = score_stt.Score(candidate="clean", clips=1, fields_expected=10, fields_lost=5)
        leaky = score_stt.Score(
            candidate="leaky", clips=1, fields_expected=10, fields_lost=0,
            optouts_expected=1, optouts_lost=1,
        )

        table = score_stt.render([leaky, clean])

        assert table.index("clean") < table.index("leaky")
        assert "DISQUALIFIED" in table


class TestEntryPoint:
    def test_an_empty_corpus_says_where_the_protocol_is(self, tmp_path: Path, capsys) -> None:
        assert score_stt.main(["score_stt.py", str(tmp_path)]) == 1
        assert "VOICE_STACK.md" in capsys.readouterr().out

    def test_every_candidate_disqualified_exits_non_zero(self, tmp_path: Path) -> None:
        """So this can gate a decision, not only inform one."""
        root = _corpus(tmp_path, {"c1": ("call mat karo", {"do_not_contact": "call mat karo"})})
        _candidate(root, "bad", {"c1": "kal baat karo"})

        assert score_stt.main(["score_stt.py", str(root)]) == 1

    def test_one_eligible_candidate_exits_zero(self, tmp_path: Path, capsys) -> None:
        root = _corpus(tmp_path, {"c1": ("call mat karo", {"do_not_contact": "call mat karo"})})
        _candidate(root, "bad", {"c1": "kal baat karo"})
        _candidate(root, "good", {"c1": "call mat karo"})

        assert score_stt.main(["score_stt.py", str(root)]) == 0
        assert "| good |" in capsys.readouterr().out
