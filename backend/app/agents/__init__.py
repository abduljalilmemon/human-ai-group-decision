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


def make_agent_factory(ai: AI, rng: random.Random | None = None) -> AgentFactory:
    rng = rng or random.Random()
    if ai.provider == "anthropic" and os.getenv("ANTHROPIC_API_KEY"):
        from .llm import LLMAgent, make_client

        client = make_client(ai.reply_timeout_seconds)
        log.info("AI agents: LLM (%s)", ai.model)
        return lambda used: LLMAgent(client, ai.model, ai.reply_timeout_seconds, ScriptedAgent(rng, used))
    log.info("AI agents: scripted (provider=%s, API key %s)", ai.provider,
             "set" if os.getenv("ANTHROPIC_API_KEY") else "missing")
    return lambda used: ScriptedAgent(rng, used)
