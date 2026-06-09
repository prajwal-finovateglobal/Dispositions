import ast
import asyncio
import aiohttp
import json
import pandas as pd


INPUT_CSV = "/Users/apple/Downloads/test_dispo.csv"
OUTPUT_CSV = "/Users/apple/Downloads/updated_dispo.csv"

df = pd.read_csv(INPUT_CSV)
url = "http://localhost:8000/disposition"

df["transcript"] = df["transcript"].apply(lambda x: json.loads(x))

# Per-request cap so the script cannot hang forever on a stuck LLM / server call.
REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=240, sock_connect=30)


def parse_transcript_cell(val):
    """
    Parse transcript from a cell.
    - Returns value if it's already a dict.
    - Raises if missing/empty/None/"nan"/NaN.
    - Tries JSON decode, falls back to ast.literal_eval for Python dict-strings.
    """
    if isinstance(val, dict):
        return val
    if val is None or (isinstance(val, float) and val != val):
        raise ValueError("transcript is missing (NaN/None)")
    if isinstance(val, str):
        s = val.strip()
    else:
        s = str(val).strip()
    if not s or s.lower() == 'nan':
        raise ValueError("transcript is empty")
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        return ast.literal_eval(s)

async def fetch_and_update(session, idx, transcript, url):
    try:
        async with session.post(url, json=transcript) as response:
            if response.status >= 400:
                body = (await response.text())[:800]
                raise RuntimeError(f"HTTP {response.status}: {body}")
            result = await response.json()
        df.loc[idx, "new_disposition"] = result.get("Disposition_code")
        print(idx, "done", flush=True)
    except (TimeoutError, aiohttp.ClientError, RuntimeError, json.JSONDecodeError) as e:
        df.loc[idx, "new_disposition"] = None
        df.loc[idx, "disposition_error"] = repr(e)
        print(idx, "FAILED:", e, flush=True)

def run_async(coro):
    """
    Run ``coro`` from a normal script or from Jupyter.

    - CLI / ``python test_2.py``: uses ``asyncio.run`` (no nest_asyncio).
    - Jupyter with an active loop: requires ``pip install nest_asyncio``.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    try:
        import nest_asyncio
    except ModuleNotFoundError as e:
        raise RuntimeError(
            "Jupyter already has an event loop; install nest_asyncio: pip install nest_asyncio"
        ) from e
    nest_asyncio.apply()
    return asyncio.get_event_loop().run_until_complete(coro)


async def run_batches(df, url, batch_size=15):
    async with aiohttp.ClientSession(timeout=REQUEST_TIMEOUT) as session:
        indices = list(range(df.shape[0]))
        for batch_start in range(0, len(indices), batch_size):
            batch_indices = indices[batch_start : batch_start + batch_size]
            hi = batch_indices[-1]
            print(
                f"Batch rows {batch_indices[0]}–{hi} ({len(batch_indices)} concurrent) …",
                flush=True,
            )
            batch_tasks = [
                fetch_and_update(
                    session, i, parse_transcript_cell(df["transcript"][i]), url
                )
                for i in batch_indices
            ]
            await asyncio.gather(*batch_tasks)
            print(f"Finished batch ending at row {hi}", flush=True)

if __name__ == "__main__":
    run_async(run_batches(df, url, batch_size=10))
    df.to_csv(OUTPUT_CSV, index=False)
    print(f"Saved {OUTPUT_CSV}")
