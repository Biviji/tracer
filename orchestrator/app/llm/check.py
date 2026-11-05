"""Check that the configured AI model works:

    python -m app.llm.check "Say hi in five words"

Uses the same settings as the orchestrator (.env), so a green check here
means experiments will reach the model too.
"""

import asyncio
import sys

from app.agents import list_agents
from app.config import get_settings
from app.llm import LLMError, build_llm


async def main(prompt: str) -> int:
    settings = get_settings()
    llm = build_llm(settings)
    agents = list_agents(settings)
    print(f"provider : {llm.name}")
    print(f"models   : {', '.join(a.model for a in agents) or '(none - set LLM_MODELS)'}")
    if not agents:
        return 1
    try:
        print(f"reachable: {await llm.ping()}")
        reply = await llm.chat(agents[0].model, [{"role": "user", "content": prompt}])
        print(f"reply    : {reply.get('content')}")
        return 0
    except LLMError as err:
        print(f"FAILED   : {err}")
        return 1
    finally:
        await llm.aclose()


if __name__ == "__main__":
    sys.exit(asyncio.run(main(" ".join(sys.argv[1:]) or "Reply with the single word: pong")))
