import os
import time
import random
import asyncio
from typing import Type, TypeVar, Optional, Any
from pydantic import BaseModel
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_anthropic import ChatAnthropic
from .models import AgentResult

T = TypeVar('T', bound=BaseModel)

RPM_SLEEP_SECONDS = int(os.getenv("RPM_SLEEP_SECONDS", "4"))

def get_llm(tier: str):
    if tier == 'lite':
        model_name = os.getenv("GEMINI_LITE_MODEL", "gemini-2.0-flash-lite")
        return ChatGoogleGenerativeAI(model=model_name, temperature=0.2)
    elif tier == 'wireframe':
        flash_default = os.getenv("GEMINI_FLASH_MODEL", "gemini-3.6-flash")
        model_name = os.getenv("WIREFRAME_MODEL", flash_default)
        if model_name.startswith('claude'):
            return ChatAnthropic(model=model_name, temperature=0.2)
        else:
            return ChatGoogleGenerativeAI(model=model_name, temperature=0.2)
    else: # default 'flash'
        model_name = os.getenv("GEMINI_FLASH_MODEL", "gemini-3.6-flash")
        return ChatGoogleGenerativeAI(model=model_name, temperature=0.2)

async def call_agent_with_degradation(
    system_prompt: str,
    context: str,
    output_schema: Type[T],
    fallback_instruction: Optional[str] = None,
    tier: str = 'flash'
) -> AgentResult[T]:
    llm = get_llm(tier)
    structured_llm = llm.with_structured_output(output_schema)
    
    full_prompt = f"{system_prompt}\n\nINPUT CONTEXT:\n{context}"
    
    max_retries = 4
    base_delay = 2.0
    
    for attempt in range(max_retries + 1):
        try:
            result = await structured_llm.ainvoke(full_prompt)
            return AgentResult(status="success", payload=result)
        except Exception as e:
            error_str = str(e).lower()
            if "429" in error_str or "resourceexhausted" in error_str or "rate limit" in error_str:
                if attempt < max_retries:
                    delay = (base_delay * (2 ** attempt)) + random.uniform(0, 1)
                    await asyncio.sleep(delay)
                    continue
            return AgentResult(
                status="degraded",
                fallback_instruction=fallback_instruction or "No fallback provided",
                error_message=str(e)
            )
