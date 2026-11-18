"""Gemini agent (Google Interactions API, google-genai). Persona, prompts, filter, timeout and the
scripted fallback are shared with the Anthropic agent through PromptedAgent in llm.py."""
from google import genai
from google.genai import errors, types

from .llm import Fallback, PromptedAgent, short


class GeminiAgent(PromptedAgent):
    provider = "gemini"

    async def _call(self, system: str, prompt: str, max_tokens: int) -> str:
        try:
            interaction = await self._client.aio.interactions.create(
                model=self._model,
                system_instruction=system,
                input=prompt,
                # "minimal" is near-off thinking, so the small token budget goes to the reply itself.
                generation_config={"max_output_tokens": max_tokens, "thinking_level": "minimal"},
                store=False,  # single-turn request; nothing needs to be kept server-side
            )
        except errors.APIError as e:
            if e.code == 429:
                raise Fallback("rate limited (429)") from None
            raise Fallback(f"API error {e.code}: {short(e.message)}") from None
        if interaction.status != "completed":  # e.g. incomplete when cut off at max_output_tokens
            raise Fallback(f"status={interaction.status}")
        return interaction.output_text or ""


def make_client(api_key: str, timeout_s: float) -> genai.Client:
    """The key is passed explicitly so GOOGLE_API_KEY can never take precedence. The SDK does not
    retry by default, and its timeout is in milliseconds."""
    return genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=int(timeout_s * 1000)))
