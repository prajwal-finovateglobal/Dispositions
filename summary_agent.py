import os
from dotenv import load_dotenv
load_dotenv()
os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")

from langchain_openai import ChatOpenAI
from langchain.agents import create_agent
from langchain.agents.middleware.types import AgentMiddleware, ModelRequest, ModelResponse, ModelCallResult
import loguru
from T2T_agent import preprocess_transcript
from typing import List, Dict, Any

# Summary agent is a agent that summarizes the transcript into a text to text format
# model = ChatOpenAI(model=os.getenv("OPENAI_MODEL"), temperature=0.7)
model = ChatOpenAI(
    base_url=f"http://{os.getenv('IP_ADDRESS')}:8000/v1",
    api_key="not-needed",
    model="openai/gpt-oss-20b",
    temperature=0.7,
)
# model = ChatOpenAI(
#     base_url="https://api.euron.one/api/v1/euri",
#     api_key=os.getenv("EURON_API_KEY"),
#     model="openai/gpt-oss-20b",
#     temperature=0.7,
# )
# Summary agent is a agent that summarizes the transcript into a text to text format
summary_agent = create_agent(
    model=model,
    tools=[]
)

# Summary agent is a agent that summarizes the transcript into a text to text format
system_prompt= f"""
You are a Multilingual Call Transcript Summarizer.

Convert the RAW transcript to a CLEAR, NEUTRAL English summary (4-6 sentences).

## RULES (MANDATORY):
- English ONLY. Translate ALL languages accurately
- FACTS ONLY. NO analysis, NO disposition codes, NO status guesses
- Capture WHO spoke, WHAT was said, CONVERSATION FLOW
- Include key numbers (EMI amount, dates), customer responses
- NO assumptions

## REQUIRED ELEMENTS:
1. Who answered? (customer name verified / family / wrong number)
2. Main topics discussed (EMI / payment / complaint / callback)
3. Customer's key responses (promises / refusals / requests)
4. How call ended (hung up / callback requested / etc.)

## NO ANALYSIS:
BAD: "STATUS: CONNECTED → ANSWERED_BY_FAMILY_MEMBER"
GOOD: "Customer responded to EMI reminder with questions"

## EXAMPLE:
RAW: "Agent: EMI 3450 due. User: Will pay tomorrow."
SUMMARY: "Agent reminded customer of 3450 EMI due. Customer confirmed payment tomorrow."

Output PLAIN TEXT SUMMARY ONLY. No bullets. No markdown.

"""

# Summary agent is a agent that summarizes the transcript into a text to text format
async def get_summary(transcript: List[Dict[str, Any]]):
    # transcript_string = preprocess_transcript(transcript)
    transcript_string = str(transcript)
    result = await summary_agent.ainvoke({"messages": [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": transcript_string}]})
    res = result['messages'][-1].content
    tokens = result['messages'][-1].usage_metadata['total_tokens']
    return {"summary": res, "tokens": tokens}

