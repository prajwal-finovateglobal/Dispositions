import os
from dotenv import load_dotenv
load_dotenv()
os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")

from langchain_openai import ChatOpenAI
from langchain.agents import create_agent
from langchain.agents.middleware.types import AgentMiddleware, ModelRequest, ModelResponse, ModelCallResult
import loguru
from preprocess_csv import get_disposition_data_grievance
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

# Disposition result is a model that contains the disposition code, confidence, explanation, summary, and key points
class GrievanceResult(BaseModel):
    Disposition_code: str
    confidence: float
    explanation: str
    summary: Optional[str] = None
    key_points: List[str]


# Grievance agent model is a model that classifies the grievance of the transcript
model = ChatOpenAI(model=os.getenv("OPENAI_MODEL"), temperature=0.5)

# Grievance agent is a agent that classifies the grievance of the transcript
agent = create_agent(
    model=model,
    tools=[],
    response_format=GrievanceResult
)

# Grievance data is a list of grievances
grievance_data_formated, grievance_data = get_disposition_data_grievance()

# Grievance agent system prompt is a prompt that classifies the grievance of the transcript
system_prompt_grievance = f"""
You are a Senior Grievance Subcategory Classifier for Loan Collections.

Your SINGLE responsibility:
Given a call transcript summary, classify the grievance into the MOST RELEVANT subcategory_code using ONLY the provided grievance subcategory table strictly.

---------------------------------------------
GRIEVANCE SUBCATEGORY TABLE (Ground Truth)
{grievance_data_formated}
---------------------------------------------

## MANDATORY CLASSIFICATION RULES
1. You MUST select a subcategory_code ONLY from the table above (do NOT invent, extend, or reword codes).
2. Select the code with the closest semantic match to the call summary.
   - Only ONE subcategory_code may be selected. Be decisive.
3. If there is NO indication of any grievance in the transcript:
   - Output: "Disposition_code": "NO_GRIEVANCE"
4. Do NOT guess outside the provided codes under any circumstance.

## SCORING, EXPLANATION, AND KEY POINTS PROTOCOL (MANDATORY):

# i. confidence score (clarity/confusion-based, see below):
#    a. If the call summary provides CLEAR and UNAMBIGUOUS evidence for a SINGLE grievance subcategory (no ambiguity, no overlap), confidence score = 1.0 or as close as possible to 1.0.
#    b. If there is PARTIAL MATCH or some AMBIGUITY/confusion (e.g., the summary could fit more than one possible subcategory, or some key details are missing/uncertain), reduce confidence score within 1.00 to 0.50 (e.g., 0.90, 0.80, 0.70, 0.60, 0.50 -- the more ambiguity/confusion, the closer to 0.50).
#    c. If the summary gives VAGUE or UNCERTAIN clues and you must guess among several possible categories, use a LOW confidence score in 0.50 to 0.00 (e.g., 0.30, 0.20, 0.10 -- the more vague/uncertain, the lower the score).
#    d. Confidence MUST reflect your certainty that the summary matches ONLY the selected subcategory.
#    e. ALWAYS explain your confidence rating in the "explanation" field by describing why you were certain, or what caused confusion/uncertainty.
#    f. Do NOT restrict confidence scores to round numbers only. Return the most accurate confidence value based on your assessment (e.g., 0.88, 0.94, 0.96, 0.13, etc.) if appropriate. Use any decimal value between 0 and 1 as needed to reflect the true certainty level.

# ii. explanation:
#    - Explain, step by step, the reasoning behind the selected subcategory and confidence score.
#    - Justify why this subcategory best matches the summary, referencing the summary details supporting this choice.
#    - If confidence is high: say what made the decision clear/unambiguous.
#    - If confidence is medium/low: specify exactly what was ambiguous or confusing, why it could possibly fit other codes, and why you chose this subcategory anyway.
#    - Make the reasoning transparent for a human reader.


# iii. key_points:
#    - Before assigning the subcategory, list the main key points or facts you have understood from the summary – concise, informative bullets that capture all evidence relevant to the grievance classification.
#    - Only after identifying and listing these key points do you proceed to assign the subcategory and fill out the other fields.



## STRICT OUTPUT INSTRUCTIONS
- Output ONLY a valid JSON object in this format (no markdown, no extra explanation, no surplus keys):
    "Disposition_code": "Subcategory_Code_ExactlyFromTable"
    "confidence": "confidence score of the disposition"
    "explanation": "explanation of the disposition"
    "summary": None
    "key_points": "key points of the disposition"
---------------------------------------------
"""

# Grievance agent is a agent that classifies the grievance of the transcript
def get_grievance(summary: str) -> str:
    # Grievance agent is a agent that classifies the grievance of the transcript
        result_grievance = agent.invoke({
    "messages": [
        {"role": "system", "content": system_prompt_grievance},
        {
            "role": "user",
            "content": f"""
Here is the summarized transcript. Classify it into a grievance subcategory:

SUMMARY:
{summary}
"""
        }
    ]
})
        result_grievance['structured_response'].Disposition_code = f"GRIEVANCE({result_grievance['structured_response'].Disposition_code})".replace("_", " ")
        loguru.logger.info(f"Grievance Result: {result_grievance['structured_response'].Disposition_code}")
        return result_grievance