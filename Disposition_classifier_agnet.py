import os
from dotenv import load_dotenv
load_dotenv()
os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")
from fastapi import APIRouter
from preprocess_csv import get_disposition_data, get_disposition_data_grievance
from grivance_agent import get_grievance
from connection_status import detect_connection_status
from summary_agent import get_summary
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
import loguru
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent
from langchain.agents.middleware.types import AgentMiddleware, ModelRequest, ModelResponse, ModelCallResult

# Disposition classifier agent is a agent that classifies the disposition of the transcript
router = APIRouter()

# Disposition result is a model that contains the disposition code, confidence, explanation, summary, and key points
class DispositionResult(BaseModel):
    Disposition_code: str
    confidence: float
    explanation: str
    summary: Optional[str] = None
    key_points: List[str]

# Disposition classifier model is a model that classifies the disposition of the transcript
model = ChatOpenAI(model=os.getenv("OPENAI_MODEL"), temperature=0.5)

# Disposition classifier agent is a agent that classifies the disposition of the transcript
agent = create_agent(
    model=model,
    tools=[],
    response_format=DispositionResult
)

# Disposition data is a list of dispositions
disposition_data_formated, disposition_data = get_disposition_data()


# Disposition classifier system prompt is a prompt that classifies the disposition of the transcript
system_prompt = f"""
 You are a Senior Call Center Disposition Classifier for Loan Collections.

You MUST classify the call using ONLY the provided disposition table.
Do NOT invent, infer, or generalize.

INPUTS YOU WILL RECEIVE:
1. RAW CALL TRANSCRIPT
2. DISPOSITION TABLE divided into:
   - CONNECTED DISPOSITIONS
   - NOT CONNECTED DISPOSITIONS

This is a RAW CALL TRANSCRIPT between a loan collections agent (lender) and a customer (borrower). The conversation represents a real interaction in the context of loan repayment or follow-up on overdue payments.


CONNECTION STATUS GROUPS:
CONNECTED DISPOSITIONS: {disposition_data_formated.split('Not Connected')[0]}
NOT CONNECTED DISPOSITIONS: {disposition_data_formated.split('Not Connected')[1]}


## CLASSIFICATION RULES (MANDATORY)
1. FIRST check CONNECTION STATUS from RAW transcript evidence
2. ONLY pick dispositions matching that status
3. Match by SEMANTIC similarity to label + description
4. NEVER cross status groups

## EXAMPLES (Follow these exactly):
EX1: Transcript="Hello! Hello."
→ STATUS: CONNECTED (human spoke) → "ANSWERED_DISCONNECTED"

EX2: Transcript="Ringing... no answer"
→ STATUS: NOT CONNECTED → "NO_ANSWER (RINGING_NOT_ANSWERED)"

EX3: Transcript="Wrong number, not here"
→ STATUS: CONNECTED → "WRONG_NUMBER"

EX4: Transcript="Will pay tomorrow"
→ STATUS: CONNECTED → "PTP_ON_SPECIFIC_DATE"

## STRICT MATCHING RULES (MANDATORY):
1. Match EXACT scenario from DESCRIPTION text
2. IGNORE generic conversation - look for SPECIFIC OUTCOMES

## BLOCKED MATCHES (Do NOT use unless EXACT):
- ANSWERED_BY_FAMILY_MEMBER → ONLY if "family/third person" + "customer unavailable" + "call later"
- WRONG_NUMBER → ONLY if "not customer" + "wrong number"

you also need to provide the confidence score and explanation for the disposition, key points for the transcript.
protocol to calculate the confidence score and explanation:
--------------------------------------------
i. confidence score (clarity/confusion-based):
    a. If the transcript provides CLEAR and UNAMBIGUOUS evidence for a SINGLE disposition (no confusion, no overlap with other labels/descriptions), confidence score = 1.0 or nearest to 1.0
    b. If there is PARTIAL MATCH or some AMBIGUITY/confusion (e.g., transcript could fit more than one possible disposition, or some key evidence is missing/uncertain), reduce confidence score within the range of 1.00 to 0.50 (e.g., 0.90, 0.80, 0.70, 0.60, 0.50 -- the more confusion or ambiguity, the closer to 0.50).
    c. If transcript gives VAGUE or UNCERTAIN clues and you must GUESS among several possible dispositions, use a LOW confidence score within the range of 0.50 to 0.00(e.g., 0.30, 0.20, 0.10 -- the more vague or uncertain, the closer to 0.50).
    d. Confidence should ALWAYS reflect how SURE you are that the evidence matches ONLY the chosen disposition (high = sure, low = confused/uncertain)
    e. ALWAYS explain your rating of confidence in your "explanation" field by describing why you were sure or what caused any confusion/uncertainty.
    f. Do NOT restrict confidence scores to round numbers only. Return the most accurate confidence value based on your assessment (e.g., 0.88, 0.94, 0.96, 0.13, etc.) if appropriate. Use any decimal value between 0 and 1 as needed to reflect the true certainty level.

---------------------------------------------
ii. explanation:
Describe, in detail, the reasoning behind the chosen disposition and confidence score. Specifically:
- Explain why this disposition best matches the transcript, pointing out the key text or evidence from the transcript that fits the disposition label/description.
- If the confidence is high, state what made the decision clear and unambiguous.
- If the confidence is medium/low, clearly specify:
    - Exactly what aspects of the transcript caused uncertainty, ambiguity, or overlap with other dispositions.
    - Describe the specific point(s) in the transcript that were confusing or could be interpreted in multiple ways.
    - State why, despite possible confusion, the selected disposition was chosen over others.
- Always make the explanation transparent, so that anyone reading it understands exactly why the confidence is rated as it is, and what evidence supported or limited your certainty.
- When constructing the explanation for the disposition, include not only the reasons that support the confidence rating, but also, if the confidence is less than 1.0, explicitly state what accounts for the "unconfident" portion (e.g., for confidence = 0.88, explain both why you are 0.88 sure and what causes the remaining 0.12 uncertainty/confusion). The explanation should have a sentence or clause such as: "Confidence is 0.88 because XYZ concrete evidence supports this disposition, but there is a 0.12 uncertainty due to [specific ambiguity, missing detail, overlap with another possible disposition, or confusing part in the transcript]." This should always be made explicit.

---------------------------------------------
iii. key points: First, clearly list the main key points you have understood from the transcript before making any classification or decision. These should be concise statements capturing the most important details, facts, or events in the transcript that will inform your disposition choice. Only after identifying and listing these key points should you proceed to assign the disposition and fill out the remaining fields.
---------------------------------------------

## CLASSIFY NOW:
"Disposition_code": "EXACT_CODE_FROM_TABLE"
"confidence": "confidence score of the disposition"
"explanation": "explanation of the disposition"
"summary": None
"key_points": "key points of the transcript"

"""

# Disposition classifier agent is a agent that classifies the disposition of the transcript
@router.post("/disposition")
async def get_disposition(transcript: List[Dict[str, Any]]) -> DispositionResult:

    # user_turns = len([msg for msg in transcript if msg['role'] == 'user'])
    
    # **RULE #1**: Ultra-short connected calls = DISCONNECTED
    # if user_turns <= 2:  
    #     return DispositionResult(Disposition_code="ANSWERED DISCONNECTED", confidence=-1.0, explanation="Less than 2 borrower turns", summary="", key_points=[])

    connection_status = detect_connection_status(transcript)
    summary = get_summary(transcript)
    loguru.logger.info(f"Summary: {summary}")

    filtered_disposition = [
        d for d in disposition_data 
        if d['connected_status'] == connection_status
    ]
    filtered_table = "\n".join([
        f"{i+1}. CODE: {x['disposition_code']} | STATUS: {x['connected_status']} | LABEL: {x['disposition_label']} | DESC: {x['disposition_description']}"
        for i, x in enumerate(filtered_disposition)
    ])

    result = agent.invoke({
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"""
Here is the summarized transcript. Classify it:

SUMMARY:
{summary}

FILTERED TABLE:
{filtered_table}
""",}
        ]
    })
    # loguru.logger.info(f"Disposition Result: {result}")
    result['structured_response'].summary = summary
    loguru.logger.info(f"Disposition Result: {result['structured_response'].Disposition_code}")
    loguru.logger.info(f"Connection Status: {connection_status}")

    if result['structured_response'].Disposition_code == 'GRIEVANCE' and connection_status == "CONNECTED":
        loguru.logger.info(f"Grievance detected")
        result_grievance = get_grievance(summary)
        result['structured_response'].Disposition_code = result_grievance['structured_response'].Disposition_code
        return result['structured_response']
    else:
        result['structured_response'].Disposition_code = result['structured_response'].Disposition_code.replace("_", " ")
        return result['structured_response']

