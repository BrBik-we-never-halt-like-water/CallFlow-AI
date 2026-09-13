"""Score a candidate STT against our own Hinglish audio.

`docs/VOICE_STACK.md` §4 describes the protocol and §5 is the empty scoring
sheet. This turns the one into the other: point it at the corpus and it prints
the markdown rows to paste into §5.

Deliberately knows nothing about any vendor. It scores *transcripts*, so a
candidate is added by dropping its output in a directory - no API key, no SDK,
no network, and a vendor that only offers a web console can still be measured.

    python scripts/score_stt.py corpus/

Expected layout, where `<clip>` is any stem you like:

    corpus/
      <clip>.txt              hand transcript - the ground truth
      <clip>.fields.json      the fields §3 of GRADING.md says are in this clip
      candidates/
        sarvam/<clip>.txt     what that vendor returned
        deepgram/<clip>.txt

Three numbers come out, and §2.1 explains why the middle one decides:

  WER   overall word error rate, for comparison with published figures
  FER   field error rate - of the extraction fields actually present in the
        audio, the share a transcript loses. The deciding number: a stack with
        worse WER and better FER wins, because "five years" becoming "fine
        years" costs an eligibility field while barely moving WER
  OPT   opt-out recall. Anything below 100% disqualifies the stack outright -
        losing a do-not-call to a transcription error is the one failure here
        with a legal consequence (GRADING.md §4.0)

A `<clip>.fields.json` is a flat object of the field values a correct
transcript must make recoverable, e.g.

    {"work_experience_years": "five years",
     "budget_amount_paise": "12 lakh",
     "do_not_contact": "mujhe call mat karo"}

The value is the *phrase as spoken*, not the parsed result - this measures the
transcript, not the extractor. `do_not_contact` is the key OPT looks for.
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path

# Devanagari and Latin both appear mid-sentence, so word splitting cannot
# assume either script. Keep any run of letters or digits, drop everything else.
_WORD_RE = re.compile(r"[\wऀ-ॿ]+", re.UNICODE)

OPT_OUT_FIELD = "do_not_contact"


def normalise(text: str) -> list[str]:
    """Words, casefolded and stripped of accents and punctuation.

    Punctuation and case are formatting choices a vendor makes, not
    transcription accuracy, and scoring them would rank a vendor's comma policy
    above whether it heard the number.
    """
    folded = unicodedata.normalize("NFKC", text).casefold()
    return _WORD_RE.findall(folded)


def edit_distance(a: list[str], b: list[str]) -> int:
    """Levenshtein over words. Two rows rather than a full matrix - a clip is
    short, but there is no reason to allocate the square."""
    if not a:
        return len(b)
    previous = list(range(len(a) + 1))
    for j, bw in enumerate(b, start=1):
        current = [j]
        for i, aw in enumerate(a, start=1):
            current.append(
                previous[i - 1] if aw == bw else 1 + min(previous[i - 1], previous[i], current[i - 1])
            )
        previous = current
    return previous[-1]


def word_error_rate(truth: str, heard: str) -> float:
    reference = normalise(truth)
    if not reference:
        return 0.0
    return edit_distance(reference, normalise(heard)) / len(reference)


def phrase_survived(phrase: str, heard: str) -> bool:
    """Whether a spoken phrase is recoverable from a transcript.

    Contiguous word match, not substring: "five years" must survive as two
    adjacent words. A transcript containing both words pages apart has not
    preserved the field, and a substring check would score it as if it had.
    """
    needle = normalise(phrase)
    haystack = normalise(heard)
    if not needle:
        return True
    return any(
        haystack[i : i + len(needle)] == needle for i in range(len(haystack) - len(needle) + 1)
    )


@dataclass(frozen=True)
class Clip:
    name: str
    truth: str
    fields: dict[str, str]


@dataclass
class Score:
    candidate: str
    clips: int = 0
    wer_total: float = 0.0
    fields_expected: int = 0
    fields_lost: int = 0
    optouts_expected: int = 0
    optouts_lost: int = 0
    missing: list[str] | None = None

    @property
    def wer(self) -> float:
        return self.wer_total / self.clips if self.clips else 0.0

    @property
    def fer(self) -> float:
        if not self.fields_expected:
            return 0.0
        return self.fields_lost / self.fields_expected

    @property
    def optout_recall(self) -> float:
        if not self.optouts_expected:
            return 1.0
        return 1 - (self.optouts_lost / self.optouts_expected)

    @property
    def disqualified(self) -> bool:
        """§6.3's first kill criterion. Nothing else outranks it."""
        return self.optouts_expected > 0 and self.optouts_lost > 0


def load_corpus(root: Path) -> list[Clip]:
    clips: list[Clip] = []
    for truth_path in sorted(root.glob("*.txt")):
        fields_path = truth_path.with_suffix(".fields.json")
        fields: dict[str, str] = {}
        if fields_path.exists():
            fields = {k: str(v) for k, v in json.loads(fields_path.read_text("utf-8")).items()}
        clips.append(
            Clip(truth_path.stem, truth_path.read_text("utf-8"), fields)
        )
    return clips


def score_candidate(name: str, directory: Path, clips: list[Clip]) -> Score:
    score = Score(candidate=name, missing=[])
    for clip in clips:
        heard_path = directory / f"{clip.name}.txt"
        if not heard_path.exists():
            # Counted against the candidate rather than skipped: a stack that
            # returned nothing for a clip did not transcribe it, and averaging
            # over what it managed would flatter it.
            assert score.missing is not None
            score.missing.append(clip.name)
            score.clips += 1
            score.wer_total += 1.0
            score.fields_expected += len(clip.fields)
            score.fields_lost += len(clip.fields)
            if OPT_OUT_FIELD in clip.fields:
                score.optouts_expected += 1
                score.optouts_lost += 1
            continue

        heard = heard_path.read_text("utf-8")
        score.clips += 1
        score.wer_total += word_error_rate(clip.truth, heard)
        for field, phrase in clip.fields.items():
            survived = phrase_survived(phrase, heard)
            score.fields_expected += 1
            if not survived:
                score.fields_lost += 1
            if field == OPT_OUT_FIELD:
                score.optouts_expected += 1
                if not survived:
                    score.optouts_lost += 1
    return score


def render(scores: list[Score]) -> str:
    lines = [
        "| Candidate | WER | **FER** | Opt-out recall | Verdict |",
        "| --------- | --- | ------- | -------------- | ------- |",
    ]
    for s in sorted(scores, key=lambda s: (s.disqualified, s.fer)):
        verdict = "**DISQUALIFIED** - lost an opt-out" if s.disqualified else "eligible"
        lines.append(
            f"| {s.candidate} | {s.wer:.1%} | **{s.fer:.1%}** | "
            f"{s.optout_recall:.0%} | {verdict} |"
        )
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2

    root = Path(argv[1])
    clips = load_corpus(root)
    if not clips:
        print(f"No `<clip>.txt` ground truth found in {root}. See docs/VOICE_STACK.md §4.1.")
        return 1

    candidates_root = root / "candidates"
    candidate_dirs = sorted(d for d in candidates_root.glob("*") if d.is_dir())
    if not candidate_dirs:
        print(f"No candidate output under {candidates_root}. One directory per stack.")
        return 1

    scores = [score_candidate(d.name, d, clips) for d in candidate_dirs]

    print(f"\n{len(clips)} clips, {sum(len(c.fields) for c in clips)} expected fields\n")
    print(render(scores))

    for s in scores:
        if s.missing:
            print(f"\n{s.candidate}: no transcript for {len(s.missing)} clip(s), "
                  f"scored as total loss - {', '.join(s.missing[:5])}")

    print("\nPaste into docs/VOICE_STACK.md §5. FER decides (§2.1); an opt-out")
    print("recall below 100% disqualifies regardless of every other number (§6.3).")

    # Exit non-zero when every candidate is disqualified, so this can gate a
    # decision rather than only inform one.
    return 1 if scores and all(s.disqualified for s in scores) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
