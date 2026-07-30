from pathlib import Path

from wristalpha.operations.pipeline import run_pipeline


def test_pipeline_reports_missing_user_inputs_as_blocking() -> None:
    outcome = run_pipeline(str(Path("config/default.yaml")))
    assert outcome.status == "blocked"
    assert any("budget" in reason for reason in outcome.blocking_reasons)
    assert any("cost assumptions" in reason for reason in outcome.blocking_reasons)
