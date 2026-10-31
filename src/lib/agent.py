import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from google.genai import types

from ..models import AgentCue, CueType


load_dotenv()
PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
PROMPT_PATH = PROMPTS_DIR / "auricue_system.md"
SUMMARY_PROMPT_PATH = PROMPTS_DIR / "auricue_summary.md"


class GeminiAdapter:
    """Generates grounded cues and rolling context summaries via Gemini."""

    def __init__(
        self, model: str = "gemini-3.8-flash",
        system_prompt: str | None = None, summary_prompt: str | None = None
    ) -> None:
        self.model = model
        self.client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
        sys_text = (
            system_prompt if system_prompt is not None
            else PROMPT_PATH.read_text(encoding="utf-8")
        )
        sum_text = (
            summary_prompt if summary_prompt is not None
            else SUMMARY_PROMPT_PATH.read_text(encoding="utf-8")
        )
        thinking = types.ThinkingConfig(thinking_level=types.ThinkingLevel.LOW)
        self.config = types.GenerateContentConfig(
            system_instruction=sys_text, thinking_config=thinking,
            tools=[types.Tool(google_search=types.GoogleSearch())],
            response_mime_type="application/json", response_schema=AgentCue
        )
        self.summary_config = types.GenerateContentConfig(
            system_instruction=sum_text, thinking_config=thinking
        )

    @staticmethod
    def _format_cue_prompt(
        sentence: str, history: list[str] | None = None, context: str = "",
        cues: list[str] | None = None
    ) -> str:
        """Format context, history, target sentence, and recent cues."""

        sections: list[str] = []
        if context.strip():
            sections.append(f"# Previous Context\n{context.strip()}")
        if history:
            sections.append("# Dialogue History\n" + "\n".join(history))
        sections.append(f"# Target Sentence\n{sentence.strip()}")
        if cues:
            sections.append("# Recent Cues\n" + "\n".join(cues))
        return "\n\n".join(sections)

    @staticmethod
    def _format_summary_prompt(
        dialogue: list[str], prev_context: str = ""
    ) -> str:
        """Format previous context and dialogue lines for summarisation."""

        sections: list[str] = []
        if prev_context.strip():
            sections.append(f"# Previous Context\n{prev_context.strip()}")
        if dialogue:
            sections.append("# New Dialogue\n" + "\n".join(dialogue))
        return "\n\n".join(sections)

    async def generate_cue(
        self, sentence: str, history: list[str] | None = None,
        context: str = "", cues: list[str] | None = None
    ) -> AgentCue | None:
        """Stream response from Gemini and return structured AgentCue."""

        prompt = self._format_cue_prompt(sentence, history, context, cues)
        stream = await self.client.aio.models.generate_content_stream(
            model=self.model, contents=prompt, config=self.config
        )
        parts: list[str] = []
        async for chunk in stream:
            if chunk.text:
                parts.append(chunk.text)
        raw = "".join(parts).strip()
        if not raw:
            return None
        cue = AgentCue.model_validate_json(raw)
        if cue.cue_type == CueType.NONE or not cue.content.strip():
            return None
        return cue

    async def summarise_context(
        self, dialogue: list[str], prev_context: str = ""
    ) -> str:
        """Fold evicted dialogue lines into the rolling session summary."""

        prompt = self._format_summary_prompt(dialogue, prev_context)
        resp = await self.client.aio.models.generate_content(
            model=self.model, contents=prompt, config=self.summary_config
        )
        text = resp.text or ""
        return text.strip() or prev_context


if __name__ == "__main__":
    async def main() -> None:
        agent = GeminiAdapter()
        ctx = "Chinese military history"
        history = [
            "Speaker 0: Did you know that the Great Wall of China is the "
            "only man-made object visible from the Moon with the naked eye?"
        ]
        sentence = "Speaker 1: Actually wouldn't it be the HS2 instead?"
        print("Testing generate_cue on factual claim...")
        cue1 = await agent.generate_cue(
            history[0], history=[], context=ctx
        )
        print("Result cue 1:", cue1)

        filler = "Speaker 0: Probably."
        print("\nTesting generate_cue on filler sentence...")
        cues = [cue1.content] if cue1 else []
        cue2 = await agent.generate_cue(
            filler, history=[*history, sentence], context=ctx, cues=cues
        )
        print("Result cue 2 (expected None):", cue2)

        print("\nTesting summarise_context...")
        summary = await agent.summarise_context(
            [*history, sentence, filler], prev_context=ctx
        )
        print("Result summary:\n" + summary)

    asyncio.run(main())


__all__ = ["GeminiAdapter"]
