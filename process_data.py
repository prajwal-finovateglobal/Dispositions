import pandas as pd
import ast
from pydantic.networks import import_email_validator
import requests
import json
from typing import List, Dict, Any
from database.dependencies import DB_DEPENDENCY
from sqlalchemy import text
import numpy as np
from datetime import datetime
import loguru
db = DB_DEPENDENCY
import asyncio
from asyncio import Semaphore
import httpx

def _sanitize_for_csv(s: Any) -> str:
    """Replace newlines/carriage returns with space so CSV rows stay on one line."""
    if s is None or (isinstance(s, float) and np.isnan(s)):
        return ""
    return str(s).replace("\r\n", " ").replace("\n", " ").replace("\r", " ").strip()


def normalize_to_list_of_dicts(data: Any) -> List[Dict[str, Any]]:
    """Delegate to shared transcript normalizer (handles turns/chat wrappers)."""
    from transcript_utils import normalize_transcript

    return normalize_transcript(data)




def query_sql(query:str):
    from database.session import SessionLocal
    # To list tables in PostgreSQL, use the information_schema.tables view:
    with SessionLocal() as db:
        result = db.execute(text(query))
        return result.fetchall()
loguru.logger.info(f"query_sql function loaded")

# data =query_sql('''
# SELECT chat,contact_to,duration,direction,recording,uid  FROM spandana_sphoorty_data where campaign_id in (289);
# ''')


#acepipe
# data =query_sql('''select 
# 	mt.transcript_json->>'chat' as chat, 
# 	mcl.customer_phone as contact_to,
# 	mcl.answered_sec as duration,
# 	mcl.call_description as direction,
# 	mcl.recording_url_acefone as recording,
# 	mcl.customer_id as uid
# from mvp_call_log mcl 
# 	join mvp_transcript mt  on mcl.transcript_id = mt.id 
# where mcl.campaign_id in (321);
# ''')


# data =query_sql('''

# '''
# )
#221 still pending






# data =query_sql('''select 
# 	mt.transcript_json->>'chat' as chat, 
# 	mcl.customer_phone as contact_to,
# 	mcl.answered_sec as duration,
# 	mcl.call_description as direction,
# 	mcl.recording_url_acefone as recording,
# 	mcl.customer_id as uid
# from mvp_call_log mcl 
# 	join mvp_transcript mt  on mcl.transcript_id = mt.id 
# where mcl.recording_url_acefone in 
# (


# )
# ''')


# data =query_sql('''
# SELECT chat,contact_to,duration,direction,recording,uid  FROM spandana_sphoorty_data where recording in 
# (


# )
# ''')

df = pd.read_csv('extractcsv/243_data.csv')
df['chat'] = df['transcript']
df['contact_to'] = df['contact_to']
df['duration'] = df['duration']
df['recording'] = df['recording']
df['uid'] = df['fincode']
df[['chat','contact_to','duration','recording','uid']].replace(np.nan, 'Blank', regex=True)


# df = pd.DataFrame(data, columns=['chat', 'contact_to', 'duration', 'direction','recording','uid']).replace(np.nan, 'Blank', regex=True)
df = df[df['duration']!='inbound']
loguru.logger.info(f"df loaded")

# con_df = df[df['recording']!='Blank']
con_df = df
loguru.logger.info(f"len(con_df): {len(con_df)}")


con_df.to_csv('df_processed_final_raw.csv', index=False)


url =  'http://localhost:8001/disposition'
i = 0
import datetime
start_time = datetime.datetime.now()
loguru.logger.info(f"*"*50 , "Processing data not async" , "*"*50)
loguru.logger.info(f"start_time: {start_time}")
# for idx, row in con_df[['chat', 'contact_to', 'duration']].iterrows():
#     loguru.logger.info(f"processing row {idx}")
#     transcript = row['chat']
#     contact_to = row['contact_to']
#     duration = row['duration']
#     loguru.logger.info(f"contact_to: {contact_to}, duration: {duration}")
#     # Normalize to ensure it's List[Dict[str, Any]]
#     # If already in correct format, it will pass through unchanged
#     transcript_list = normalize_to_list_of_dicts(transcript)
    
#     # hit above url
#     try:
#         response = requests.post(url, json=transcript_list)
    
#         result = response.json()
#         # Convert dict to object-like access if necessary
#         class Result: pass
#         r = Result()
#         for k, v in result.items():
#             setattr(r, k, v)
#         result = r
#         loguru.logger.info(f"result: {result}")
#         disposition = result.Disposition_code
#         confidence = result.confidence
#         explanation = result.explanation
#         summary = result.summary
#         key_points = result.key_points
#         loguru.logger.info(f"idx:{i}, disposition:{disposition}, confidence:{confidence}")
#         con_df.loc[idx, 'Disposition_code'] = disposition
#         con_df.loc[idx, 'confidence'] = confidence
#         con_df.loc[idx, 'explanation'] = explanation
#         con_df.loc[idx, 'summary'] = summary
#         # When setting a cell in pandas, convert list to string to avoid ValueError for non-scalar values
#         con_df.loc[idx, 'key_points'] = str(key_points) if not isinstance(key_points, str) else key_points
#         con_df.loc[idx, 'duration'] = duration
#     except Exception as e:
#         loguru.logger.error(f"error: {e}")
#         loguru.logger.error(f"idx: {idx}")
#         loguru.logger.error(f"transcript_list: {transcript_list}")
#         continue
#     if i == 10:
#         # con_df.to_csv('df_processed_final.csv', index=False)
#         loguru.logger.info(f"processed {idx} rows")
#         loguru.logger.info(f"*"*50)
#         break
#     i += 1
con_df.to_csv('df_processed_final.csv', index=False)
loguru.logger.info(f"processed {len(con_df)} rows not async", "*"*50)
end_time = datetime.datetime.now()
loguru.logger.info(f"end_time: {end_time}")
loguru.logger.info(f"time taken: {end_time - start_time}")
loguru.logger.info(f"*"*50 , "Processing data async" , "*"*50)

async def make_request(client: httpx.AsyncClient, url: str, transcript_list: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Make an async HTTP POST request"""
    try:
        response = await client.post(url, json=transcript_list, timeout=None)
        response.raise_for_status()  # Raise an exception for bad status codes
        result = response.json()
        if result is None:
            raise ValueError("Response JSON is None")
        return result
    except httpx.HTTPStatusError as e:
        loguru.logger.error(f"HTTP error: {e.response.status_code} - {e.response.text}")
        raise
    except httpx.RequestError as e:
        loguru.logger.error(f"Request error: {e}")
        raise
    except Exception as e:
        loguru.logger.error(f"Unexpected error in make_request: {type(e).__name__}: {e}")
        raise

async def main():
    """Main async function: process all records with Semaphore(30) + asyncio.gather."""
    sem = Semaphore(14)

    idx_row_pairs = [(idx, row) for idx, row in con_df[['chat', 'contact_to', 'duration']].iterrows() if idx >= 0]
    total = len(idx_row_pairs)
    print(f"********** Processing (semaphore=30, gather) **********\nTotal to process: {total}\n****************************")

    async def process_one(client: httpx.AsyncClient, idx: int, row) -> tuple:
        async with sem:
            transcript_list = normalize_to_list_of_dicts(row['chat'])
            loguru.logger.info(f"contact_to: {row['contact_to']}, duration: {row['duration']}, idx: {idx}")
            try:
                result = await make_request(client, url, transcript_list)
                return (idx, result)
            except Exception as e:
                return (idx, e)

    async with httpx.AsyncClient(timeout=None) as client:
        tasks = [process_one(client, idx, row) for idx, row in idx_row_pairs]
        results = await asyncio.gather(*tasks)

    kount = 0
    for outcome in results:
        idx, result = outcome
        if isinstance(result, Exception):
            loguru.logger.error(f"idx {idx} request error: {type(result).__name__}: {result}")
            continue
        if result is None:
            loguru.logger.error(f"Result is None for idx {idx}")
            continue
        try:
            if not isinstance(result, dict):
                loguru.logger.error(f"Result is not a dict for idx {idx}, got {type(result)}")
                continue
            class Result:
                pass
            r = Result()
            for k, v in result.items():
                setattr(r, k, v)
            loguru.logger.info(f"result: {r}")
            disposition = r.Disposition_code
            confidence = r.confidence
            loguru.logger.info(f"idx:{idx}, disposition:{disposition}, confidence:{confidence}")
            explanation = r.explanation
            summary = r.summary
            key_points = r.key_points
            con_df.loc[idx, 'Disposition_code'] = disposition
            con_df.loc[idx, 'confidence'] = confidence
            con_df.loc[idx, 'explanation'] = _sanitize_for_csv(explanation)
            con_df.loc[idx, 'summary'] = _sanitize_for_csv(summary)
            con_df.loc[idx, 'key_points'] = json.dumps(key_points, ensure_ascii=False) if isinstance(key_points, list) else _sanitize_for_csv(key_points)
            kount += 1
            if kount % 100 == 0:
                loguru.logger.info(f"*" * 50)
                loguru.logger.info(f"Saving checkpoint at {kount} records")
                con_df.to_csv('df_processed_final_async.csv', index=False)
                loguru.logger.info(f"Checkpoint: saved {kount} records to df_processed_final_async.csv")
                loguru.logger.info(f"*" * 50)
        except Exception as e:
            loguru.logger.error(f"error processing result for idx {idx}: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            kount += 1
            continue

asyncio.run(main())
loguru.logger.info(f"processed {len(con_df)} rows async {'*'*50}")
a_end_time = datetime.datetime.now()
# Sanitize text columns so each CSV row is one line (no embedded newlines)
for col in ['explanation', 'summary', 'key_points']:
    if col in con_df.columns:
        con_df[col] = con_df[col].fillna("").astype(str).apply(lambda s: s.replace("\n", " ").replace("\r", " ").strip())
con_df.to_csv('df_processed_final_async.csv', index=False)
loguru.logger.info(f"a_end_time: {a_end_time}")
loguru.logger.info(f"time taken: {a_end_time - end_time}")
