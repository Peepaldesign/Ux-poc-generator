from typing import Type, TypeVar, Any, Optional
from pydantic import BaseModel
from langchain_google_genai import ChatGoogleGenerativeAI
from backend.models import AgentResult
import traceback

T = TypeVar('T', bound=BaseModel)

# Ensure to set GOOGLE_API_KEY environment variable
llm = ChatGoogleGenerativeAI(model="gemini-3.6-flash", temperature=0)

def call_agent_with_degradation(
    prompt_text: str,
    user_input: str,
    response_model: Type[T],
    fallback_seed: Optional[str] = None
) -> AgentResult[T]:
    """
    Calls the LLM enforcing a strict structured output.
    If it fails to parse or errors out, applies the Degradation Contract.
    """
    structured_llm = llm.with_structured_output(response_model)
    full_prompt = f"{prompt_text}\n\nINPUT DATA:\n{user_input}"
    
    try:
        payload = structured_llm.invoke(full_prompt)
        return AgentResult(
            status="success",
            payload=payload,
            fallback_instruction=None,
            error_message=None
        )
    except Exception as e:
        print(f"Agent degradation triggered: {str(e)}")
        # Degradation Contract: set to degraded/skipped and populate fallback
        return AgentResult(
            status="degraded",
            payload=None,
            fallback_instruction=fallback_seed,
            error_message=str(e)
        )
