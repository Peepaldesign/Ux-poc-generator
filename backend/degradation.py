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
        model_name = os.getenv("GEMINI_LITE_MODEL", "gemini-3.5-flash-lite")
        return ChatGoogleGenerativeAI(model=model_name, temperature=0.2)
    elif tier == 'hifi':
        flash_default = os.getenv("GEMINI_FLASH_MODEL", "gemini-3.6-flash")
        model_name = os.getenv("HIFI_MODEL", flash_default)
        if model_name.startswith('claude'):
            return ChatAnthropic(model=model_name, temperature=0.2)
        else:
            return ChatGoogleGenerativeAI(model=model_name, temperature=0.2)
    else: # default 'flash'
        model_name = os.getenv("GEMINI_FLASH_MODEL", "gemini-3.6-flash")
        return ChatGoogleGenerativeAI(model=model_name, temperature=0.2)

import re

def _extract_nouns(text: str) -> set:
    words = [w.lower() for w in re.findall(r'\b[a-zA-Z]{4,}\b', text)]
    stop_words = {'this','that','with','from','your','have','more','will','about','which','their','they','what','when','where','there','these','those','would','could','should'}
    generic_words = {'user','system','app','application','product','platform','data','time','role','task','step'}
    return set(w for w in words if w not in stop_words and w not in generic_words)

def check_grounding(brief: str, output_text: str) -> bool:
    brief_nouns = _extract_nouns(brief)
    if not brief_nouns: return True
    output_nouns = _extract_nouns(output_text)
    return len(brief_nouns.intersection(output_nouns)) > 0

async def call_agent_with_degradation(
    system_prompt: str,
    context: str,
    output_schema: Type[T],
    fallback_instruction: Optional[str] = None,
    tier: str = 'flash',
    raw_brief: Optional[str] = None
) -> AgentResult[T]:
    llm = get_llm(tier)
    structured_llm = llm.with_structured_output(output_schema)
    
    base_prompt = f"{system_prompt}\n\nINPUT CONTEXT:\n{context}"
    current_prompt = base_prompt
    
    max_retries = 4
    base_delay = 2.0
    parse_retries = 0
    
    for attempt in range(max_retries + 1):
        try:
            result = await structured_llm.ainvoke(current_prompt)
            
            # Grounding check
            if raw_brief:
                result_str = result.model_dump_json()
                if not check_grounding(raw_brief, result_str):
                    if parse_retries < 1:
                        parse_retries += 1
                        current_prompt = base_prompt + "\n\n[SYSTEM NOTE: Domain drift detected! Your previous output drifted into a generic or incorrect domain. Ground strictly in the SOURCE BRIEF.]"
                        continue
                    else:
                        raise ValueError("domain drift detected")
                        
            return AgentResult(status="success", payload=result)
        except Exception as e:
            error_str = str(e).lower()
            if "429" in error_str or "resourceexhausted" in error_str or "rate limit" in error_str:
                if attempt < max_retries:
                    delay = (base_delay * (2 ** attempt)) + random.uniform(0, 1)
                    await asyncio.sleep(delay)
                    continue
            else:
                # Validation / parse error retry
                if parse_retries < 1:
                    parse_retries += 1
                    current_prompt = base_prompt + f"\n\n[SYSTEM NOTE: Your previous attempt failed validation: {str(e)[:100]}. Ensure you output ONLY the required valid JSON structure.]"
                    continue
            
            return AgentResult(
                status="degraded",
                fallback_instruction=fallback_instruction or "No fallback provided",
                error_message=str(e)
            )
