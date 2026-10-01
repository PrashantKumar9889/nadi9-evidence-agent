"""The verifier must be able to reject a line the translator did not approve."""

from nadi9.pipeline import run_episode
from nadi9.verifier import verify_subtitle


def _cue(source: str) -> dict:
    return {
        "id": "SX",
        "source": source,
        "speaker": "Devan",
        "addressee": "Mira",
        "speaker_status": "higher",
        "addressee_status": "lower",
        "start": "00:00:01,000",
        "end": "00:00:04,000",
    }


def test_verifier_catches_missing_negation(data_dir, tmp_path):
    result = run_episode(data_dir, tmp_path / "out")
    report = verify_subtitle(
        source_text="I did not eat.",
        nadi_9_text="mi korava",
        cue=_cue("I did not eat."),
        learned=result.learned,
        start="00:00:01,000",
        end="00:00:04,000",
    )
    assert report.passed is False
    assert any("negation" in issue.lower() for issue in report.issues)


def test_verifier_catches_unsupported_token(data_dir, tmp_path):
    result = run_episode(data_dir, tmp_path / "out")
    report = verify_subtitle(
        source_text="I want water.",
        nadi_9_text="mi nira zorblax",
        cue=_cue("I want water."),
        learned=result.learned,
        start="00:00:01,000",
        end="00:00:02,000",
    )
    assert report.passed is False
    assert any("unsupported" in issue.lower() for issue in report.issues)


def test_verifier_catches_reading_speed(data_dir, tmp_path):
    result = run_episode(data_dir, tmp_path / "out")
    report = verify_subtitle(
        source_text="I want water.",
        nadi_9_text="mi nira hilara",
        cue=_cue("I want water."),
        learned=result.learned,
        start="00:00:01,000",
        end="00:00:01,200",
    )
    assert report.passed is False
    assert any("reading speed" in issue.lower() for issue in report.issues)
