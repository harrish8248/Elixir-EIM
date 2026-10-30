"""
Unit tests for IDP metrics: CER, WER, Wilson confidence intervals, and auto-approval safety.
"""

from apps.api.app.content.idp.evaluation import (
    compute_cer,
    compute_wer,
    wilson_confidence_interval,
)


def test_cer_identical_is_zero():
    ref = "Invoice Number: INV-2026-1000 Total: $1,500.00 Due Date: 2026-05-20"
    assert compute_cer(ref, ref) == 0.0
    # Whitespace variation between tokens should normalize to zero
    hyp_whitespace = "Invoice  Number:   INV-2026-1000\nTotal: $1,500.00\nDue Date: 2026-05-20 "
    assert compute_cer(ref, hyp_whitespace) == 0.0


def test_cer_known_corruption():
    # 100-character reference string
    ref = "a" * 100
    # 5 character substitutions
    hyp_5 = ("a" * 95) + ("b" * 5)
    assert round(compute_cer(ref, hyp_5), 2) == 0.05

    # 10 character substitutions
    hyp_10 = ("a" * 90) + ("b" * 10)
    assert round(compute_cer(ref, hyp_10), 2) == 0.10


def test_wer_identical_is_zero():
    ref = "The quick brown fox jumps over the lazy dog"
    assert compute_wer(ref, ref) == 0.0
    hyp_whitespace = "The   quick\nbrown\tfox jumps over the lazy dog\n"
    assert compute_wer(ref, hyp_whitespace) == 0.0


def test_wer_known_corruption():
    words = ["word"] * 20
    ref = " ".join(words)
    # Substitute 2 words out of 20 = 10% WER
    corrupted_words = list(words)
    corrupted_words[0] = "diff1"
    corrupted_words[1] = "diff2"
    hyp = " ".join(corrupted_words)
    assert round(compute_wer(ref, hyp), 2) == 0.10


def test_wilson_confidence_interval():
    # Known benchmark test vector: 80 successes out of 100 trials
    low, high = wilson_confidence_interval(80, 100)
    assert 70.0 < low < 73.0  # Approx 71.1%
    assert 86.0 < high < 88.0  # Approx 86.7%

    # 0 successes
    low_0, high_0 = wilson_confidence_interval(0, 50)
    assert low_0 == 0.0
    assert high_0 > 0.0

    # 100% successes
    low_full, high_full = wilson_confidence_interval(50, 50)
    assert low_full > 90.0
    assert high_full == 100.0
