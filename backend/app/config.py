"""Load and validate config.yml. Invalid config fails fast with a readable message."""
import os
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, PositiveFloat, ValidationError, model_validator


class ConfigError(Exception):
    pass


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Experiment(_Strict):
    rounds: Literal[2] = 2
    discussion_seconds: PositiveFloat
    voting_seconds: PositiveFloat
    results_pause_seconds: PositiveFloat
    show_round_results: bool = True
    min_wait_seconds: tuple[PositiveFloat, PositiveFloat]

    @model_validator(mode="after")
    def _wait_range(self):
        lo, hi = self.min_wait_seconds
        if lo > hi:
            raise ValueError("min_wait_seconds must be [min, max] with min <= max")
        return self


class Participant(_Strict):
    type: Literal["human", "ai"]


class AI(_Strict):
    provider: Literal["anthropic", "gemini", "scripted"] = "scripted"
    model: str = Field(min_length=1)  # Anthropic model, used when provider is anthropic
    gemini_model: str = Field(default="gemini-3.5-flash-lite", min_length=1)  # used when provider is gemini
    reply_timeout_seconds: PositiveFloat = 8


class Config(_Strict):
    experiment: Experiment
    labels: list[str] = Field(min_length=3, max_length=3)
    participants: list[Participant] = Field(min_length=3, max_length=3)
    ai: AI

    @model_validator(mode="after")
    def _checks(self):
        if len(set(self.labels)) != 3 or any(not label.strip() for label in self.labels):
            raise ValueError("labels must be 3 unique, non-empty names")
        if self.human_slots < 1:
            raise ValueError("participants must include at least 1 human")
        return self

    @property
    def human_slots(self) -> int:
        return sum(p.type == "human" for p in self.participants)

    @property
    def condition(self) -> str:
        """Readable condition name, e.g. '2_human_1_ai'."""
        return f"{self.human_slots}_human_{3 - self.human_slots}_ai"


def _format_errors(err: ValidationError) -> str:
    lines = []
    for e in err.errors():
        where = ".".join(str(part) for part in e["loc"]) or "(root)"
        lines.append(f"  - {where}: {e['msg']}")
    return "\n".join(lines)


def load_config(path: str | Path | None = None) -> Config:
    path = Path(path or os.getenv("CONFIG_PATH", "config.yml"))
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ConfigError(f"Config file not found: {path}") from None
    except yaml.YAMLError as e:
        raise ConfigError(f"Config file {path} is not valid YAML:\n  {e}") from None
    if not isinstance(raw, dict):
        raise ConfigError(f"Config file {path} must contain a YAML mapping")
    try:
        return Config.model_validate(raw)
    except ValidationError as e:
        raise ConfigError(f"Invalid config in {path}:\n{_format_errors(e)}") from None
