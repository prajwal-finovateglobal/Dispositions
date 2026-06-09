import os
import asyncio
import json
import re
from dotenv import load_dotenv
load_dotenv()
os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")
from fastapi import APIRouter, HTTPException
from summary_agent import get_summary
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
import loguru
from langchain_openai import ChatOpenAI
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
import pandas as pd
from openai import LengthFinishReasonError

# Disposition classifier agent is a agent that classifies the disposition of the transcript
router = APIRouter()

# Disposition result is a model that contains the disposition code, confidence, explanation, summary, and key points
class DispositionResult(BaseModel):
    Disposition_code: str
    confidence: float = Field(ge=0.0, le=1.0)
    explanation: str = Field(
        description="At most 2 short sentences citing transcript evidence."
    )
    summary: Optional[str] = None
    key_points: List[str] = Field(
        max_length=3,
        description="At most 3 brief bullets (under 15 words each).",
    )


# Default completion cap; stepped retries on truncation, then compact JSON fallback.
DISPOSITION_BASE_MAX_TOKENS = 1024
DISPOSITION_MAX_RETRY_TOKENS = 8192
DISPOSITION_COMPACT_MAX_TOKENS = 1024
DISPOSITION_MAX_CONTEXT = int(os.getenv("VLLM_MAX_MODEL_LEN", "32768"))
DISPOSITION_RETRY_STEPS = (2048, 4096, DISPOSITION_MAX_RETRY_TOKENS)


openai_cost = 0
total_tokens = 0

# Disposition classifier model is a model that classifies the disposition of the transcript
# model = ChatOpenAI(model=os.getenv("OPENAI_MODEL"), temperature=0.7)
# model = ChatOpenAI(
#     base_url="http://localhost:1234/v1",
#     api_key='sk-lm-COIGf9Y3:mSMCpR1zsaXD8wrPs45P',
#     model="mistralai/ministral-3-3b", 
#     temperature=0.7)
model = ChatOpenAI(
    base_url=f"http://{os.getenv('IP_ADDRESS')}:8000/v1",
    api_key="not-needed",
    model="openai/gpt-oss-20b",
    temperature=0,
    max_tokens=DISPOSITION_BASE_MAX_TOKENS,
)
# from langchain_openai import ChatOpenAI
# model = ChatOpenAI(
#     base_url="https://api.euron.one/api/v1/euri",
#     api_key=os.getenv("EURON_API_KEY"),
#     model="openai/gpt-oss-20b",
#     temperature=0.7,
# )

# model = ChatOpenAI(
#     base_url=f"http://{os.getenv('IP_ADDRESS')}:8000/v1",
#     api_key="not-needed",
#     model="openai/gpt-oss-20b",
#     temperature=0.7,
#     max_tokens=8192,  # enough for full structured output (summary, key_points, explanation); avoids LengthFinishReasonError
# )

# Structured output runnable (avoids sending `tools: []` to OpenAI-compatible backends)
# include_raw=True keeps access to usage metadata for token counting.
disposition_llm = model.with_structured_output(DispositionResult, include_raw=True)

DEFAULT_DISPOSITION = "CONTACT ESTABLISHED NO OUTCOME"
SHORT_CALL_DISPOSITION = "ANSWERED DISCONNECTED"

VALID_DISPOSITION_CODES = frozenset(
    {
        "ANSWERED BY FAMILY MEMBER",
        "WRONG NUMBER",
        "CALLBACK REQUESTED",
        "ANSWERED DISCONNECTED",
        "ANSWERED LANDED ON VOICEMAIL",
        "INCORRECT LANGUAGE",
        "GRIEVANCE (LOAN AMOUNT NOT RECEIVED)",
        "GRIEVANCE (LOAN NOT TAKEN)",
        "GRIEVANCE (SERVICE BEHAVIOUR COMPLAINT)",
        "UNABLE TO PAY OTHER",
        "DENIED TO PAY",
        "PTP ON SPECIFIC DATE",
        "PTP SOFT PROMISE",
        "ALREADY PAID",
        "DO NOT DISTURB REQUESTED",
        DEFAULT_DISPOSITION,
    }
)


def _customer_turn_count(transcript: List[Dict[str, Any]]) -> int:
    count = 0
    for msg in transcript:
        speaker = msg.get("speaker", msg.get("role"))
        text = (msg.get("text") or msg.get("content") or "").strip()
        if not text:
            continue
        if speaker in (1, "1", "user", "customer"):
            count += 1
        elif speaker in (0, "0", "assistant", "agent"):
            continue
        elif msg.get("role") == "user":
            count += 1
    return count


def normalize_disposition_code(
    code: str | None, transcript: List[Dict[str, Any]]
) -> str:
    """Map null/invalid model output to a valid disposition code."""
    if not code:
        raw = ""
    else:
        raw = str(code).strip().replace("_", " ")

    lowered = raw.lower()
    if lowered in {"", "null", "none", "nan", "n/a", "unknown", "undefined"}:
        if _customer_turn_count(transcript) <= 1:
            return SHORT_CALL_DISPOSITION
        return DEFAULT_DISPOSITION

    normalized = raw.upper().replace("GREVIENCE", "GRIEVANCE")
    if normalized in VALID_DISPOSITION_CODES:
        return normalized

    loguru.logger.warning(f"Unknown disposition '{raw}', using {DEFAULT_DISPOSITION}")
    return DEFAULT_DISPOSITION


def _compact_classifier_prompt() -> str:
    codes = ", ".join(sorted(VALID_DISPOSITION_CODES))
    return f"""
You classify loan collection call transcripts. Return ONE JSON object only (no markdown, no extra text).

Schema:
{{"Disposition_code":"<code>","confidence":0.0,"explanation":"<max 25 words>","key_points":["<max 12 words>"]}}

Valid Disposition_code values (exact match):
{codes}

Rules: pick the best match from evidence; never use null; if unsure use {DEFAULT_DISPOSITION}.
Keep explanation and key_points very short so the JSON fits in under 400 tokens.
"""


def _usage_from_length_error(exc: LengthFinishReasonError) -> tuple[int | None, int | None]:
    """Parse completion_tokens and prompt_tokens from the error message."""
    m = re.search(
        r"completion_tokens=(\d+).*prompt_tokens=(\d+)",
        str(exc),
        re.DOTALL,
    )
    if not m:
        return None, None
    return int(m.group(1)), int(m.group(2))


def _completion_token_ceiling(prompt_tokens: int | None) -> int:
    """Max completion tokens allowed without exceeding vLLM context."""
    prompt = prompt_tokens if prompt_tokens is not None else 2048
    ctx_room = max(DISPOSITION_BASE_MAX_TOKENS, DISPOSITION_MAX_CONTEXT - prompt)
    return min(ctx_room, DISPOSITION_MAX_RETRY_TOKENS)


def _next_max_tokens(current: int, prompt_tokens: int | None) -> int | None:
    """Next step in retry ladder; None if no room to grow."""
    ceiling = _completion_token_ceiling(prompt_tokens)
    if current >= ceiling:
        return None
    for step in DISPOSITION_RETRY_STEPS:
        if step > current:
            return min(step, ceiling)
    return None


def _retry_exhausted(max_tokens: int, completion_tokens: int | None) -> bool:
    """True when raising max_tokens no longer increases output (server cap ~1024)."""
    if completion_tokens is None:
        return False
    return max_tokens > DISPOSITION_BASE_MAX_TOKENS and completion_tokens <= DISPOSITION_BASE_MAX_TOKENS + 64


def _message_content_to_text(content: Any) -> str:
    """Normalize AIMessage.content (str or list of blocks) to plain text."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                if block.get("type") == "text" and block.get("text"):
                    parts.append(str(block["text"]))
                elif block.get("text"):
                    parts.append(str(block["text"]))
                elif block.get("type") == "output_text" and block.get("content"):
                    parts.append(str(block["content"]))
        return "\n".join(parts).strip()
    return str(content).strip()


def _default_disposition_result(
    transcript: List[Dict[str, Any]], reason: str = ""
) -> DispositionResult:
    code = normalize_disposition_code(None, transcript)
    explanation = "Default disposition applied."
    if reason:
        explanation = f"{explanation} ({reason})"
    return DispositionResult(
        Disposition_code=code,
        confidence=0.2,
        explanation=explanation,
        key_points=[],
    )


def _extract_json_object(text: str) -> dict:
    text = text.strip()
    if not text:
        raise ValueError("empty model response")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        raise ValueError("no JSON object in model response")
    return json.loads(match.group(0))


def _compact_transcript_for_prompt(transcript: List[Dict[str, Any]], max_chars: int = 14000) -> str:
    lines: list[str] = []
    for msg in transcript:
        text = (msg.get("text") or msg.get("content") or "").strip()
        if not text:
            continue
        speaker = msg.get("speaker", msg.get("role", "?"))
        lines.append(f"[{speaker}] {text[:500]}")
    blob = "\n".join(lines) if lines else str(transcript)
    if len(blob) > max_chars:
        return blob[:max_chars] + "\n...[truncated]"
    return blob


async def _invoke_disposition(messages: list, max_tokens: int) -> dict:
    return await disposition_llm.bind(max_tokens=max_tokens).ainvoke(messages)


async def _invoke_compact_fallback(transcript: List[Dict[str, Any]]) -> DispositionResult:
    """Plain chat completion + JSON parse when structured output hits length limit."""
    loguru.logger.warning("Using compact JSON fallback for disposition")
    last_err: str | None = None
    for cap in (DISPOSITION_COMPACT_MAX_TOKENS, 1024, 2048):
        try:
            response = await model.bind(max_tokens=cap).ainvoke(
                [
                    SystemMessage(content=_compact_classifier_prompt()),
                    HumanMessage(
                        content=f"Transcript:\n{_compact_transcript_for_prompt(transcript)}\n\nJSON:"
                    ),
                ]
            )
            raw = _message_content_to_text(
                getattr(response, "content", None) or getattr(response, "text", None)
            )
            if not raw and getattr(response, "additional_kwargs", None):
                raw = _message_content_to_text(
                    response.additional_kwargs.get("content")
                    or response.additional_kwargs.get("reasoning_content")
                )
            if not raw:
                last_err = "empty model response"
                loguru.logger.warning(
                    f"Compact fallback empty content at max_tokens={cap}, retrying"
                )
                continue
            data = _extract_json_object(raw)
            result = DispositionResult.model_validate(data)
            result.Disposition_code = normalize_disposition_code(
                result.Disposition_code, transcript
            )
            return result
        except LengthFinishReasonError:
            loguru.logger.warning(f"Compact fallback truncated at max_tokens={cap}, retrying")
            last_err = "truncated"
            continue
        except (ValueError, json.JSONDecodeError) as e:
            last_err = str(e)
            loguru.logger.warning(f"Compact fallback parse failed at max_tokens={cap}: {e}")
            continue

    # Last resort: ask for disposition code only (no JSON)
    try:
        response = await model.bind(max_tokens=128).ainvoke(
            [
                SystemMessage(
                    content=(
                        "Reply with exactly ONE disposition code from this list, "
                        "no other text:\n"
                        + ", ".join(sorted(VALID_DISPOSITION_CODES))
                    )
                ),
                HumanMessage(
                    content=f"Transcript:\n{_compact_transcript_for_prompt(transcript)}\n\nCode:"
                ),
            ]
        )
        text = _message_content_to_text(
            getattr(response, "content", None) or getattr(response, "text", None)
        ).upper()
        for code in sorted(VALID_DISPOSITION_CODES, key=len, reverse=True):
            if code.upper() in text:
                return DispositionResult(
                    Disposition_code=code,
                    confidence=0.5,
                    explanation="Code-only fallback classification.",
                    key_points=[],
                )
    except Exception as e:
        last_err = str(e)
        loguru.logger.warning(f"Code-only fallback failed: {e}")

    return _default_disposition_result(transcript, reason=last_err or "compact fallback failed")


async def _classify_with_retries(messages: list, transcript: List[Dict[str, Any]]) -> dict:
    max_tokens = DISPOSITION_BASE_MAX_TOKENS
    while True:
        try:
            return await _invoke_disposition(messages, max_tokens)
        except LengthFinishReasonError as e:
            completion_tokens, prompt_tokens = _usage_from_length_error(e)
            if _retry_exhausted(max_tokens, completion_tokens):
                loguru.logger.warning(
                    f"max_tokens={max_tokens} but completion_tokens={completion_tokens}; "
                    "server cap detected, switching to compact fallback"
                )
                compact = await _invoke_compact_fallback(transcript)
                return {"parsed": compact, "raw": None}
            nxt = _next_max_tokens(max_tokens, prompt_tokens)
            if nxt is None:
                loguru.logger.warning(
                    f"Disposition truncated at max_tokens={max_tokens}, using compact fallback: {e}"
                )
                compact = await _invoke_compact_fallback(transcript)
                return {"parsed": compact, "raw": None}
            loguru.logger.warning(
                f"Truncated at max_tokens={max_tokens} "
                f"(completion_tokens={completion_tokens}), retrying with {nxt}"
            )
            max_tokens = nxt


# Function to load and format CSV data for the prompt
def load_disposition_csv_for_prompt():
    """
    Reads the dispositions.csv file and formats it into a structured string
    for the system prompt with priority labels.
    """
    df = pd.read_csv("csv/dispositions.csv")
    
    # Priority labels mapping
    priority_labels = {
        1: "HIGHEST",
        2: "HIGH",
        3: "MEDIUM",
        4: "LOW"
    }
    
    # Format each row
    formatted_rows = []
    for _, row in df.iterrows():
        category = row['Category']
        priority = row['Priority']
        priority_label = priority_labels.get(priority, "UNKNOWN")
        code = row['Disposition Code']
        description = row['Description']
        
        formatted_row = f"""Category: {category} | Priority: {priority} ({priority_label})
Code: {code}
Description: {description}"""
        formatted_rows.append(formatted_row)
    
    # Join all rows with separator
    return "\n---------------------------------------------------------------------------\n".join(formatted_rows)

# Load disposition table dynamically from CSV
disposition_table_formatted = load_disposition_csv_for_prompt()


# Disposition classifier system prompt is a prompt that classifies the disposition of the transcript
system_prompt = f"""
You are a Senior Call Center Disposition Classifier for Loan Collections.

You MUST classify the call using ONLY the provided disposition table below.
Do NOT invent, infer, or generalize dispositions outside this table.

## DISPOSITION TABLE (CONNECTED CALLS ONLY):
This table contains ALL valid dispositions you can assign. Each disposition has:
- Category: The broad classification group
- Priority: Importance level (1 = HIGHEST, 2 = HIGH, 3 = MEDIUM, 4 = LOW)
- Disposition Code: The exact code you must return
- Description: Detailed scenario that must match the transcript

DISPOSITION REFERENCE TABLE:
---------------------------------------------------------------------------
{disposition_table_formatted}
---------------------------------------------------------------------------

## PRIORITY-BASED CLASSIFICATION RULES (MANDATORY):
1. **PRIORITY ORDERING**: When multiple dispositions could potentially match, ALWAYS prefer the disposition with HIGHER PRIORITY (lower priority number):
   - Priority 1 (HIGHEST) > Priority 2 (HIGH) > Priority 3 (MEDIUM) > Priority 4 (LOW)
   
2. **DECISION FLOW**:
   Step 1: Identify all potential disposition matches based on transcript evidence
   Step 2: If multiple matches exist, SELECT THE ONE WITH HIGHEST PRIORITY NUMBER (lowest number = highest priority)
   Step 3: Only select lower priority dispositions when higher priority ones clearly DO NOT match
   
3. **PRIORITY 1 DISPOSITIONS** (Check First - Highest Business Impact):
   - CUSTOMER EXPIRED: Customer death reported
   - PTP ON SPECIFIC DATE: Customer commits to pay on specific date
   - ALREADY PAID: Customer claims payment already made
   - PTP SOFT PROMISE: Customer willing to pay but no specific date
   
4. **PRIORITY 2 DISPOSITIONS** (Check Second - High Business Impact):
   - Any GRIEVANCE raised by customer (loan disputes, payment issues, service complaints, etc.)
   
5. **PRIORITY 3 DISPOSITIONS** (Check Third - Medium Business Impact):
   - Answered but no outcomes (family member, disconnected, voicemail)
   - Wrong number, denied to pay, unable to pay (various reasons)
   - Callback requested, do not disturb
   
6. **PRIORITY 4 DISPOSITIONS** (Check Last - Low Business Impact):
   - Language barrier issues

## STRICT MATCHING RULES (MANDATORY):
1. Match EXACT scenario from DESCRIPTION text in the table above
2. Look for SPECIFIC OUTCOMES and EXPLICIT STATEMENTS in transcript
3. IGNORE generic conversation - focus on actionable outcomes
4. When in doubt between two similar dispositions, choose the HIGHER PRIORITY one

## CLASSIFICATION EXAMPLES:
EX1: "Customer said: I already paid last week"
→ Match: ALREADY PAID (Priority 1) - Highest priority takes precedence

EX2: "Customer said: I will pay tomorrow"
→ Match: PTP ON SPECIFIC DATE (Priority 1) - Specific date commitment

EX3: "Customer said: I'll try to pay soon but not sure when"
→ Match: PTP SOFT PROMISE (Priority 1) - Willing but no specific date

EX4: "Customer said: This loan is not mine, I never took it"
→ Match: GREVIENCE (LOAN NOT TAKEN) (Priority 2) - Grievance about ownership

EX5: "Customer said: I paid through agent but it's not updated in system"
→ Match: GREVIENCE (PAYMENT DONE NOT UPDATED) (Priority 2) - Payment tracking grievance

EX6: "Hello? Hello? [silence] [call drops]"
→ Match: ANSWERED DISCONNECTED (Priority 3) - No meaningful communication

EX7: "Customer said: I lost my job, cannot pay right now"
→ Match: UNABLE TO PAY JOB LOSS (Priority 3) - Specific reason for inability

EX8: "Agent and customer cannot understand each other's language"
→ Match: INCORRECT LANGUAGE (Priority 4) - Only when language barrier is clear

## BLOCKED MATCHES (Use ONLY if EXACT match):
- ANSWERED BY FAMILY MEMBER → ONLY if "family member answered" + "customer unavailable" explicitly stated
- WRONG NUMBER → ONLY if person confirms "wrong number" or "not the customer you're looking for"
- DO NOT DISTURB REQUESTED → ONLY if customer EXPLICITLY asks to stop calling

## CONFIDENCE SCORE PROTOCOL:
i. Confidence Score (clarity/confusion-based):
    a. If transcript provides CLEAR and UNAMBIGUOUS evidence for a SINGLE disposition (no confusion, no overlap), confidence = 0.95-1.0
    b. If PARTIAL MATCH or AMBIGUITY exists (could fit multiple dispositions, some evidence missing), confidence = 0.50-0.94
    c. If transcript is VAGUE or UNCERTAIN (must guess among several options), confidence = 0.00-0.49
    d. Confidence reflects how SURE you are the evidence matches ONLY the chosen disposition
    e. ALWAYS explain confidence rating in "explanation" field
    f. Use precise decimals (e.g., 0.88, 0.94, 0.73) - do NOT restrict to round numbers

ii. Explanation:
- Point out KEY EVIDENCE from transcript that matches the disposition description
- If confidence is high: State what made it clear and unambiguous
- If confidence is medium/low: Specify EXACTLY what caused uncertainty, ambiguity, or overlap
- For confidence < 1.0: Explicitly state what accounts for the "uncertain" portion
  Example: "Confidence is 0.85 because customer clearly mentioned payment commitment (supporting evidence), but the 0.15 uncertainty is due to no specific date being mentioned, creating some overlap with PTP SOFT PROMISE"

iii. Key Points:
- FIRST list the main key points from the transcript BEFORE classification
- Capture important details, facts, events that inform your disposition choice
- Only AFTER listing key points, proceed to assign disposition

## OUTPUT FORMAT (keep very brief — structured JSON must fit in under 800 tokens):
"Disposition_code": "EXACT_CODE_FROM_TABLE_ABOVE"
"confidence": [0.0 to 1.0 decimal value]
"explanation": "[Max 2 short sentences]"
"summary": null
"key_points": ["max 3 brief bullets, under 15 words each"]

## FINAL REMINDER:
- ONLY use disposition codes from the table above
- FOLLOW PRIORITY ORDERING: Higher priority (lower number) dispositions take precedence when multiple could match
- Match descriptions EXACTLY - do not infer or generalize
- Provide precise confidence scores with detailed explanations

"""
# system_prompt = """
# You are a classifier for loan collection call transcripts. Given a transcript in JSON format, output exactly one disposition code.

# INPUT FORMAT:
# Each entry has: start_seconds, end_seconds, text (spoken content), speaker (0 = agent, 1 = customer).
# Only "text" matters. Ignore timestamps.

# PREPROCESSING (internal only):
# Strip filler words (um, uh, like) and exact repetitions
# Preserve incomplete sentences as-is; do not infer missing content
# Preserve speaker roles

# DISPOSITION CODES (output must match exactly):
# ANSWERED BY FAMILY MEMBER
# WRONG NUMBER
# CALLBACK REQUESTED
# ANSWERED DISCONNECTED
# ANSWERED LANDED ON VOICEMAIL
# INCORRECT LANGUAGE
# GRIEVANCE (LOAN AMOUNT NOT RECEIVED)
# GRIEVANCE (LOAN NOT TAKEN)
# GRIEVANCE (SERVICE BEHAVIOUR COMPLAINT)
# UNABLE TO PAY OTHER
# DENIED TO PAY
# PTP ON SPECIFIC DATE
# PTP SOFT PROMISE
# ALREADY PAID
# DO NOT DISTURB REQUESTED
# CONTACT ESTABLISHED NO OUTCOME

# CLASSIFICATION RULES (apply in order, stop at first match):
# 1. Call clearly goes to wrong person/number → WRONG NUMBER
# 2. Language barrier prevents communication → INCORRECT LANGUAGE
# 3. Call reaches voicemail → ANSWERED LANDED ON VOICEMAIL
# 4. Call answered but drops before meaningful exchange → ANSWERED DISCONNECTED
# 5. Customer unavailable; third party answers → ANSWERED BY FAMILY MEMBER
# 6. Customer requests callback / says call later → CALLBACK REQUESTED
# 7. Customer complaint about:
#    - Missing funds / incorrect balance → GRIEVANCE (LOAN AMOUNT NOT RECEIVED)
#    - Denies taking the loan → GRIEVANCE (LOAN NOT TAKEN)
#    - Agent or service conduct → GRIEVANCE (SERVICE BEHAVIOUR COMPLAINT)
# 8. Payment outcome:
#    - Cannot pay → UNABLE TO PAY OTHER
#    - Refuses to pay → DENIED TO PAY
#    - Commits to pay on a named date → PTP ON SPECIFIC DATE
#    - Vague promise to pay → PTP SOFT PROMISE
#    - States payment already made → ALREADY PAID
#    - Requests no further contact → DO NOT DISTURB REQUESTED
# 9. Conversation occurred but no clear outcome → CONTACT ESTABLISHED NO OUTCOME
# 10. None of the above → null

# KEY RULES:
# Base classification solely on transcript evidence
# Weight the LAST meaningful statement most heavily
# Do not guess beyond available evidence
# Handles mixed Hindi-English (Hinglish) speech


# OUTPUT (structured JSON only — be brief):
# - Disposition_code: exact code from the list above
# - confidence: 0.0–1.0
# - explanation: max 2 short sentences
# - key_points: max 3 short bullets
# Do not repeat the transcript. Do not add extra fields or prose.

# EXAMPLES:

# Transcript: [{"text": "Hello main spandana sphoorti se aayasha baat kar rahi hoon. Kya main reshama ji se baat kar rahi hoon?", "speaker": 0}, {"text": "Veshma ji abhi mere paas mein nahin hai.", "speaker": 1}, {"text": "Nahin reshama ko matlab main bol doonga baad mein bata doonga aapko.", "speaker": 1}]
# Output: ANSWERED BY FAMILY MEMBER

# Transcript: [{"text": "Hello, main spandana surabhi se aayasha baat kar rahi hoon. Kya main anita ji se baat kar rahi hoon?", "speaker": 0}, {"text": "suno baarah hazaar yah galat kar rakhi hai mere par rah gai thi tin bakaaya kisht.", "speaker": 1}, {"text": "agent aate hain lene ke lie vah kha gae paison ko.", "speaker": 1}]
# Output: GRIEVANCE (LOAN AMOUNT NOT RECEIVED)
# """
# Disposition classifier agent is a agent that classifies the disposition of the transcript
@router.post("/disposition")
async def get_disposition(transcript: List[Dict[str, Any]]) -> DispositionResult:
    global total_tokens

    # user_turns = len([msg for msg in transcript if msg['role'] == 'user'])
    
    # **RULE #1**: Ultra-short connected calls = DISCONNECTED
    # if user_turns <= 2:  
    #     return DispositionResult(Disposition_code="ANSWERED DISCONNECTED", confidence=-1.0, explanation="Less than 2 borrower turns", summary="", key_points=[])

    # Get summary (only using connected calls, so no connection status check needed)
    # summary_result = await get_summary(transcript)
    # print(f"********** Summary Result **********\n",summary_result,"\n********** Total Tokens:**********")
    # summary = summary_result['summary']
    # total_tokens += summary_result['tokens']
    # loguru.logger.info(f"Summary: {summary}")

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(
            content=f"""
Classify this transcript. Reply with compact JSON only (short explanation, at most 3 key_points).

Transcript:
{_compact_transcript_for_prompt(transcript)}
""".strip()
        ),
    ]

    try:
        result = await _classify_with_retries(messages, transcript)
    except (ValueError, json.JSONDecodeError) as e:
        loguru.logger.error(f"Disposition classification failed: {e}")
        structured = _default_disposition_result(transcript, reason=str(e))
        structured.summary = "summary of the transcript"
        loguru.logger.warning(f"Using default disposition: {structured.Disposition_code}")
        return structured

    # --- Token counting: usage is on the raw AIMessage when available ---
    _raw = result.get("raw")
    _usage = getattr(_raw, "usage_metadata", None) if _raw else None
    if _usage and isinstance(_usage, dict):
        total_tokens += _usage.get("total_tokens", 0)
    print(f"********** OpenAI Tokens **********\n", total_tokens, "\n********** Total Tokens:**********")

    structured = result.get("parsed")
    if structured is None:
        structured = _default_disposition_result(
            transcript, reason="structured output parse returned None"
        )
    structured.summary = "summary of the transcript"
    raw_code = structured.Disposition_code
    structured.Disposition_code = normalize_disposition_code(raw_code, transcript)
    if structured.Disposition_code != (raw_code or "").strip().replace("_", " "):
        loguru.logger.warning(
            f"Disposition mapped from {raw_code!r} -> {structured.Disposition_code}"
        )
    loguru.logger.info(f"Disposition Result: {structured.Disposition_code}")
    return structured

