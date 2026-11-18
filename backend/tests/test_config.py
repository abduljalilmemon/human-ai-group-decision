import copy
import os
from pathlib import Path

import pytest
import yaml

from app.config import ConfigError, load_config

# In the container CONFIG_PATH points at the mounted config.yml; locally it is the repo root.
REPO_CONFIG = Path(os.getenv("CONFIG_PATH") or Path(__file__).resolve().parents[2] / "config.yml")

VALID = {
    "experiment": {
        "rounds": 2,
        "discussion_seconds": 60,
        "voting_seconds": 20,
        "results_pause_seconds": 8,
        "show_round_results": True,
        "min_wait_seconds": [3, 8],
    },
    "labels": ["Player A", "Player B", "Player C"],
    "participants": [{"type": "human"}, {"type": "human"}, {"type": "ai"}],
    "ai": {"provider": "scripted", "model": "claude-haiku-5-5", "reply_timeout_seconds": 8},
}


def write(tmp_path, data) -> Path:
    path = tmp_path / "config.yml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return path


def variant(**changes):
    """Copy VALID and apply dotted-path changes, e.g. variant(**{'experiment.voting_seconds': 0})."""
    data = copy.deepcopy(VALID)
    for dotted, value in changes.items():
        *parents, key = dotted.split(".")
        target = data
        for p in parents:
            target = target[p]
        target[key] = value
    return data


def test_repo_config_is_valid():
    assert load_config(REPO_CONFIG).human_slots >= 1


@pytest.mark.parametrize(
    "types, condition",
    [
        (["human", "human", "human"], "3_human_0_ai"),
        (["human", "human", "ai"], "2_human_1_ai"),
        (["human", "ai", "ai"], "1_human_2_ai"),
    ],
)
def test_three_conditions(tmp_path, types, condition):
    cfg = load_config(write(tmp_path, variant(participants=[{"type": t} for t in types])))
    assert cfg.condition == condition
    assert cfg.human_slots == types.count("human")


@pytest.mark.parametrize(
    "data, expected",
    [
        (variant(participants=[{"type": "human"}] * 4), "participants"),
        (variant(participants=[{"type": "human"}] * 2), "participants"),
        (variant(participants=[{"type": "ai"}] * 3), "at least 1 human"),
        (variant(participants=[{"type": "robot"}] * 3), "participants.0.type"),
        (variant(labels=["A", "A", "B"]), "unique"),
        (variant(**{"experiment.voting_seconds": 0}), "experiment.voting_seconds"),
        (variant(**{"experiment.discussion_seconds": -5}), "experiment.discussion_seconds"),
        (variant(**{"experiment.min_wait_seconds": [8, 3]}), "min <= max"),
        (variant(**{"experiment.rounds": 3}), "experiment.rounds"),
        (variant(**{"ai.provider": "other"}), "ai.provider"),
        (variant(**{"ai.gemini_model": ""}), "ai.gemini_model"),
        (variant(**{"experiment.typo_key": 1}), "typo_key"),
    ],
)
def test_invalid_configs_give_readable_errors(tmp_path, data, expected):
    with pytest.raises(ConfigError) as exc:
        load_config(write(tmp_path, data))
    assert expected in str(exc.value)


def test_missing_file(tmp_path):
    with pytest.raises(ConfigError, match="not found"):
        load_config(tmp_path / "nope.yml")


def test_bad_yaml(tmp_path):
    path = tmp_path / "config.yml"
    path.write_text("participants: [unclosed", encoding="utf-8")
    with pytest.raises(ConfigError, match="not valid YAML"):
        load_config(path)


@pytest.mark.parametrize("provider", ["anthropic", "gemini", "scripted"])
def test_ai_providers_accepted(tmp_path, provider):
    cfg = load_config(write(tmp_path, variant(**{"ai.provider": provider})))
    assert cfg.ai.provider == provider
    assert cfg.ai.gemini_model == "gemini-3.5-flash-lite"  # default when not set
