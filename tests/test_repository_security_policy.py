from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
PATCHED_PYPI_ACTION = (
    "pypa/gh-action-pypi-publish"
    "@dc37677b2e1c63e2034f94d8a5b11f265b73ba33"
)
EXPECTED_GRYPE_IGNORE = {
    "vulnerability": "GHSA-vxmw-7h4f-hqxh",
    "package": {
        "name": "pypa/gh-action-pypi-publish",
        "version": "dc37677b2e1c63e2034f94d8a5b11f265b73ba33",
        "type": "github-action",
    },
}


def _load_yaml(relative_path: str) -> dict:
    with (ROOT / relative_path).open(encoding="utf-8") as stream:
        return yaml.safe_load(stream)


def test_ci_uses_read_only_default_permissions():
    workflow = _load_yaml(".github/workflows/ci.yml")

    assert workflow["permissions"] == {"contents": "read"}


def test_dependabot_does_not_open_routine_version_update_prs():
    config = _load_yaml(".github/dependabot.yml")

    assert {update["package-ecosystem"] for update in config["updates"]} == {
        "pip",
        "github-actions",
    }
    assert all(
        update["open-pull-requests-limit"] == 0 for update in config["updates"]
    )


def test_publish_uses_the_patched_pypi_action():
    workflow = _load_yaml(".github/workflows/publish-pypi.yml")
    publish_steps = workflow["jobs"]["publish"]["steps"]

    assert PATCHED_PYPI_ACTION in {
        step.get("uses") for step in publish_steps if isinstance(step, dict)
    }


def test_grype_exception_is_exact_and_only_for_the_patched_action():
    config = _load_yaml(".grype.yaml")

    assert config == {"ignore": [EXPECTED_GRYPE_IGNORE]}
