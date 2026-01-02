import os
from dotenv import load_dotenv
load_dotenv()
os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")

from langchain_openai import ChatOpenAI
from T2T_agent import preprocess_transcript
from typing import List, Dict, Any

import loguru

# Connection status agent is a agent that detects the connection status of the transcript
def detect_connection_status(transcript: List[Dict[str, Any]]) -> str:
    """First pass: Detect if call was CONNECTED using raw transcript patterns"""
    transcript_text = preprocess_transcript(transcript).lower()
    
    # Rule-based + LLM hybrid for reliability on short transcripts
    connected_indicators = [
        "hello", "hi", "namaste", "yes", "no", "pay", "emi", "due", 
        "family", "voicemail", "wrong", "deceased", "complaint"
    ]
    not_connected_indicators = ["ringing", "busy", "switched off", "unreachable", "no answer"]
    
    has_speech = any(word in transcript_text for word in connected_indicators)
    if len(transcript_text.strip()) < 20 or not has_speech:
        return "Not Connected"  # Default for minimal interaction
    
    # LLM confirmation for edge cases
    status_model = ChatOpenAI(model=os.getenv("OPENAI_MODEL"), temperature=0)
    status_prompt = """
    CLASSIFY ONLY: Was this call CONNECTED (conversation happened) or NOT CONNECTED?
    
    CONNECTED if: ANY human response beyond ringing/busy/unreachable
    NOT CONNECTED if: ringing, busy tone, switched off, no answer, network error
    
    Transcript: {transcript}
    
    Respond ONLY: "CONNECTED" or "NOT CONNECTED"
    """
    
    result = status_model.invoke([{"role": "system", "content": status_prompt.format(transcript=transcript_text)}])
    res = result.content.strip()
    loguru.logger.info(f"Connection Status: {res}")
    return res