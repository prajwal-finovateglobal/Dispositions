import os
from dotenv import load_dotenv
load_dotenv()
os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")

from langchain_openai import ChatOpenAI
from langchain.agents import create_agent
from langchain.agents.middleware.types import AgentMiddleware, ModelRequest, ModelResponse, ModelCallResult
import loguru
from preprocess_csv import get_disposition_data_grievance
from typing import List, Dict, Any

# Grievance agent model is a model that classifies the grievance of the transcript
model = ChatOpenAI(model=os.getenv("OPENAI_MODEL"), temperature=0.5)

# Grievance agent is a agent that classifies the grievance of the transcript
agent = create_agent(
    model=model,
    tools=[]
)

# Grievance data is a list of grievances
disposition_data_grievance_formated, disposition_data_grievance = get_disposition_data_grievance()

# Grievance agent system prompt is a prompt that classifies the grievance of the transcript
system_prompt_grievance = f"""
You are an expert Grievance Subcategory Classification Assistant.

Your ONLY task:
Given a call transcript summary, classify the grievance into the MOST RELEVANT subcategory_code strictly using the provided table.

---------------------------------------------
GRIEVANCE SUBCATEGORY DATA (Ground Truth CSV)
{disposition_data_grievance_formated}
---------------------------------------------

### VERY IMPORTANT RULES

1. You MUST classify using ONLY the disposition_data_grievance_formated provided above.
2. NEVER create new categories, NEVER guess outside the table.
3. Choose the TOP most relevant subcategory_code based on semantic similarity.
   - 1 subcategory if the match is strong
4. If the transcript does **NOT** indicate a grievance → output:
   "Disposition_code": "Sub_Category_Code"

### STRICT OUTPUT FORMAT
Return ONLY a valid JSON object:

  "Disposition_code": "Disposition Code"    

Do NOT include explanation.
Do NOT add extra keys.
Do NOT output markdown.

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