"""Explicit opt-in failure fixture; excluded from normal pytest testpaths."""


def test_expected_failure_for_pipeline_gate():
    assert False, 'Intentional LOCAL pipeline validation: deployment must not run'
