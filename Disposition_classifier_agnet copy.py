import os
import asyncio
from dotenv import load_dotenv
load_dotenv()
os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")
from fastapi import APIRouter
from summary_agent import get_summary
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
import loguru
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent
from langchain.agents.middleware.types import AgentMiddleware, ModelRequest, ModelResponse, ModelCallResult
import pandas as pd

# Disposition classifier agent is a agent that classifies the disposition of the transcript
router = APIRouter()

# Disposition result is a model that contains the disposition code, confidence, explanation, summary, and key points
class DispositionResult(BaseModel):
    Disposition_code: str
    confidence: float
    explanation: str
    summary: Optional[str] = None
    key_points: List[str]


openai_cost = 0
total_tokens = 0

# Disposition classifier model is a model that classifies the disposition of the transcript
model = ChatOpenAI(model=os.getenv("OPENAI_MODEL"), temperature=0.5)
# model = ChatOpenAI(
#     base_url="http://localhost:1234/v1",
#     api_key='sk-lm-COIGf9Y3:mSMCpR1zsaXD8wrPs45P',
#     model="mistralai/ministral-3-3b", 
#     temperature=0.7)
# from langchain_openai import ChatOpenAI

# model = ChatOpenAI(
#     base_url="http://127.0.0.1:1234/v1",
#     api_key="lm-studio",
#     model="mistralai/ministral-3-3b",
#     temperature=0.7,
# )

# Disposition classifier agent is a agent that classifies the disposition of the transcript
agent = create_agent(
    model=model,
    tools=[],
    response_format=DispositionResult
)

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

## OUTPUT FORMAT:
"Disposition_code": "EXACT_CODE_FROM_TABLE_ABOVE"
"confidence": [0.0 to 1.0 decimal value]
"explanation": "[Detailed reasoning with evidence + confidence justification]"
"summary": None
"key_points": ["point 1", "point 2", "..."]

## FINAL REMINDER:
- ONLY use disposition codes from the table above
- FOLLOW PRIORITY ORDERING: Higher priority (lower number) dispositions take precedence when multiple could match
- Match descriptions EXACTLY - do not infer or generalize
- Provide precise confidence scores with detailed explanations

"""

# Disposition classifier agent is a agent that classifies the disposition of the transcript
@router.post("/disposition")
async def get_disposition(transcript: List[Dict[str, Any]]) -> DispositionResult:
    global total_tokens

    # user_turns = len([msg for msg in transcript if msg['role'] == 'user'])
    
    # **RULE #1**: Ultra-short connected calls = DISCONNECTED
    # if user_turns <= 2:  
    #     return DispositionResult(Disposition_code="ANSWERED DISCONNECTED", confidence=-1.0, explanation="Less than 2 borrower turns", summary="", key_points=[])

    # Get summary (only using connected calls, so no connection status check needed)
    summary_result = await get_summary(transcript)
    print(f"********** Summary Result **********\n",summary_result,"\n********** Total Tokens:**********")
    summary = summary_result['summary']
    total_tokens += summary_result['tokens']
    loguru.logger.info(f"Summary: {summary}")

    # Classify the disposition (all dispositions are in the system prompt already)
    result = await agent.ainvoke({
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"""
Here is the summarized transcript. Classify it using the disposition table in the system prompt:

SUMMARY:
{summary}
""",}
        ]
    })
    
    # openai_cost += result['usage']['total_tokens']
    total_tokens += result['messages'][-1].usage_metadata['total_tokens']
    
    print(f"********** OpenAI Tokens **********\n",total_tokens,"\n********** Total Tokens:**********")
    # loguru.logger.info(f"Disposition Result: {result}")
    result['structured_response'].summary = summary
    loguru.logger.info(f"Disposition Result: {result['structured_response'].Disposition_code}")

    # if result['structured_response'].Disposition_code == 'GRIEVANCE' and connection_status == "CONNECTED":
    #     loguru.logger.info(f"Grievance detected")
    #     result_grievance = await get_grievance(summary)
    #     result['structured_response'].Disposition_code = result_grievance['structured_response'].Disposition_code
    #     return result['structured_response']
    # else:
    result['structured_response'].Disposition_code = result['structured_response'].Disposition_code.replace("_", " ")
    return result['structured_response']

