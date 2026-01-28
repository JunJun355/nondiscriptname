#!/usr/bin/env python3
"""
Gemma AI abstraction layer for PollEV answering.

Provides structured responses for multiple choice questions.
"""
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent))

import google.generativeai as genai
from config import DATA_DIR


class AnswerStatus(Enum):
    """Status of the AI answer."""
    ANSWERED = "answered"
    LOW_CONFIDENCE = "low_confidence"
    ERROR = "error"


@dataclass
class AIAnswer:
    """Structured AI answer response."""
    status: AnswerStatus
    option_number: Optional[int] = None  # 1-indexed
    confidence: str = ""  # high, medium, low
    question_type: str = ""  # factual, subjective, requires_context
    reasoning: str = ""
    explanation: str = ""
    raw_response: str = ""


def send_mac_notification(title: str, message: str, sound: str = "Glass") -> None:
    """Send a macOS notification with sound."""
    # Escape quotes in message
    message = message.replace('"', '\\"')
    title = title.replace('"', '\\"')
    script = f'display notification "{message}" with title "{title}" sound name "{sound}"'
    subprocess.run(["osascript", "-e", script], check=False)


def _load_api_key() -> str:
    """Load API key from file."""
    api_key_file = DATA_DIR / "API_KEY_GEMINI"
    if not api_key_file.exists():
        raise FileNotFoundError(f"API key not found at {api_key_file}")
    return api_key_file.read_text().strip()


def _build_prompt(question: str, options: list[str]) -> str:
    """Build strictly structured prompt for Gemma with required best answer."""
    options_list = "\n".join(f"  {i+1}. {opt}" for i, opt in enumerate(options))
    
    return f"""You are an AI assistant answering a multiple choice poll question.

QUESTION: {question}

OPTIONS:
{options_list}

INSTRUCTIONS:
Analyze the question and provide a structured JSON response. You MUST ALWAYS provide your best answer (integer 1-{len(options)}), even if the question is subjective or requires outside knowledge.

CONFIDENCE RULES (STRICT):
- "high": The question is completely self-contained, objective, and you are >95% sure of the answer.
- "medium": The question is self-contained but might have minor ambiguity, or you are >70% sure.
- "low": The question requires external context (e.g. "shown on the board", "this diagram", "previous slide", "what did the speaker say"), OR is highly subjective, OR you are guessing. 
- IMPORTANT: If a question asks about "the correct node", "this code", or "the image", and no code/image is provided, you MUST set confidence to "low".

RESPONSE FORMAT (respond with ONLY this JSON, no other text):
{{
  "analysis": {{
    "question_type": "factual" | "subjective" | "requires_context",
    "reasoning": "<your step-by-step reasoning>"
  }},
  "answer": {{
    "best_option": <integer 1-{len(options)}>,
    "confidence": "high" | "medium" | "low",
    "explanation": "<why this is the best answer>"
  }}
}}

EXAMPLE for "What is 2+2?" with options ["3", "4", "5", "6"]:
{{
  "analysis": {{
    "question_type": "factual",
    "reasoning": "This is a basic arithmetic question. 2+2=4."
  }},
  "answer": {{
    "best_option": 2,
    "confidence": "high",
    "explanation": "4 is the mathematically correct answer"
  }}
}}

EXAMPLE for "What is the correct node?" (with no diagram):
{{
  "analysis": {{
    "question_type": "requires_context",
    "reasoning": "The question refers to 'the correct node' but no graph or diagram is provided."
  }},
  "answer": {{
    "best_option": 1,
    "confidence": "low",
    "explanation": "Guessing Option 1 because context is missing."
  }}
}}

Now respond with ONLY the JSON for the given question:"""


def _parse_response(response_text: str, num_options: int) -> AIAnswer:
    """Parse Gemma's JSON response into structured AIAnswer."""
    raw = response_text.strip()
    
    # Try to extract JSON from response (handle nested braces)
    try:
        # Find the outermost JSON object
        start = raw.find('{')
        if start == -1:
            raise ValueError("No JSON found")
        
        depth = 0
        end = start
        for i, char in enumerate(raw[start:], start):
            if char == '{':
                depth += 1
            elif char == '}':
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        
        json_str = raw[start:end]
        data = json.loads(json_str)
    except (json.JSONDecodeError, ValueError) as e:
        return AIAnswer(
            status=AnswerStatus.ERROR,
            reason=f"Could not parse JSON: {e}",
            raw_response=raw
        )
    
    # Extract fields from nested structure
    analysis = data.get("analysis", {})
    answer = data.get("answer", {})
    
    question_type = analysis.get("question_type", "unknown")
    reasoning = analysis.get("reasoning", "")
    
    best_option = answer.get("best_option")
    confidence = answer.get("confidence", "low")
    explanation = answer.get("explanation", "")
    
    # Validate option number
    if not isinstance(best_option, int) or best_option < 1 or best_option > num_options:
        return AIAnswer(
            status=AnswerStatus.ERROR,
            reasoning=f"Invalid option number: {best_option}",
            raw_response=raw
        )
    
    # Determine status based on confidence
    if confidence == "low":
        status = AnswerStatus.LOW_CONFIDENCE
    else:
        status = AnswerStatus.ANSWERED
    
    return AIAnswer(
        status=status,
        option_number=best_option,
        confidence=confidence,
        question_type=question_type,
        reasoning=reasoning,
        explanation=explanation,
        raw_response=raw
    )


def ask_gemma(question: str, options: list[str]) -> AIAnswer:
    """
    Ask Gemma 3 27B to answer a multiple choice question.
    
    Args:
        question: The poll question text
        options: List of answer options
    
    Returns:
        AIAnswer with structured response
    """
    try:
        api_key = _load_api_key()
        genai.configure(api_key=api_key)
        
        model = genai.GenerativeModel("gemma-3-27b-it")
        prompt = _build_prompt(question, options)
        
        response = model.generate_content(prompt)
        return _parse_response(response.text, len(options))
    
    except Exception as e:
        return AIAnswer(
            status=AnswerStatus.ERROR,
            reasoning=str(e),
            raw_response=""
        )


def notify_low_confidence(question: str, answer: AIAnswer) -> None:
    """Send Mac notification for low confidence or error answers."""
    if answer.status == AnswerStatus.LOW_CONFIDENCE:
        send_mac_notification(
            f"PollEV: Low Confidence ({answer.question_type})",
            f"Clicked option {answer.option_number}: {question[:40]}..."
        )
    elif answer.status == AnswerStatus.ERROR:
        send_mac_notification(
            "PollEV: AI Error",
            f"Error: {answer.reasoning[:50]}"
        )

