import asyncio
import aiohttp
from datetime import datetime
start_time = datetime.now()
async def make_request(input_text):
    url = "http://localhost:1234/api/v1/chat"
    headers = {
        "Authorization": "Bearer sk-lm-COIGf9Y3:mSMCpR1zsaXD8wrPs45P",
        "Content-Type": "application/json",
    }
    data = {
        "model": "mistralai/ministral-3-3b",
        "input": input_text
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=data) as resp:
            return await resp.json()

async def main():
    inputs = [
        "My favorite color is blue.",
        "What is the capital of France?",
        "Tell me a joke."
    ]
    tasks = [make_request(i) for i in inputs]
    responses = await asyncio.gather(*tasks)
    for r in responses:
        print(r)

# To run the async main function
asyncio.run(main())
end_time = datetime.now()
print(f"Time taken: {end_time - start_time}")
