"""AI participants. make_agent_factory() picks the LLM agent or the scripted fallback from config."""
import logging
import os
import random
from typing import Callable

from ..config import AI
from .base import Agent
from .scripted import ScriptedAgent

log = logging.getLogger(__name__)

# Called once per AI seat with a set shared by all AI seats of the same session.
AgentFactory = Callable[[set[str]], Agent]

KEY_VARS = {"anthropic": "ANTHROPIC_API_KEY", "gemini": "GEMINI_API_KEY"}


def make_agent_factory(ai: AI, rng: random.Random | None = None) -> AgentFactory:
    rng = rng or random.Random()
    if ai.provider == "scripted":
        log.info("AI agents: scripted")
        return lambda used: ScriptedAgent(rng, used)

    key = os.getenv(KEY_VARS[ai.provider])
    if not key:
        log.warning("%s agent fell back to scripted: %s is not set", ai.provider, KEY_VARS[ai.provider])
        return lambda used: ScriptedAgent(rng, used)

    if ai.provider == "gemini":
        from . import gemini

        client = gemini.make_client(key, ai.reply_timeout_seconds)
        log.info("AI agents: gemini (%s)", ai.gemini_model)
        return lambda used: gemini.GeminiAgent(client, ai.gemini_model, ai.reply_timeout_seconds,
                                               ScriptedAgent(rng, used))

    from .llm import LLMAgent, make_client

    client = make_client(ai.reply_timeout_seconds)
    log.info("AI agents: anthropic (%s)", ai.model)
    return lambda used: LLMAgent(client, ai.model, ai.reply_timeout_seconds, ScriptedAgent(rng, used))
