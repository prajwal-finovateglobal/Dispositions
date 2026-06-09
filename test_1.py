import asyncio
import requests
from datetime import datetime

start_time = datetime.now()
def make_request(input_text):
    url = "http://localhost:1234/api/v1/chat"
    headers = {
        "Authorization": "Bearer sk-lm-COIGf9Y3:mSMCpR1zsaXD8wrPs45P",
        "Content-Type": "application/json",
    }
    data = {
        "model": "mistralai/ministral-3-3b",
        "input": input_text
    }
    response = requests.post(url, headers=headers, json=data)
    return response.json()

def main():
    inputs = [
        "My favorite color is blue.",
        "What is the capital of France?",
        "Tell me a joke."
    ]
    for i in inputs:
        print("*"*100)
        response = make_request(i)
        print(response)
        print("*"*100)

# To run the async main function
main()
end_time = datetime.now()
print(f"Time taken: {end_time - start_time}")
