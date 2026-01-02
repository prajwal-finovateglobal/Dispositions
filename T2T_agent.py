from typing import List, Dict, Any

# T2T agent is a agent that converts the transcript into a text to text format
def preprocess_transcript(transcript: List[Dict[str, Any]]):
    transcript_string = ""
    
    for msg in transcript:
        if msg['content'] is None:
            continue
        if msg['role'] == 'user':
            transcript_string += "borrower said: " + msg['content'] + ", "
        elif msg['role'] == 'assistant':
            transcript_string += "lender said: " + msg['content'] + ", "
    return transcript_string