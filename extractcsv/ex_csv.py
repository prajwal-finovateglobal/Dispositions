import os
from dotenv import load_dotenv
import psycopg2
import pandas as pd

# Load environment variables
load_dotenv()

# Read DB credentials
DB_HOST="postgres-db-proxy.proxy-c5e8c8k6gr3n.ap-south-1.rds.amazonaws.com"
DB_PORT="5432"
DB_NAME="avio"
DB_USER="app_proxy"  
DB_PASSWORD="FGPL@6766"
# Connect to PostgreSQL
conn = psycopg2.connect(
    host=DB_HOST,
    port=DB_PORT,
    dbname=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD
)
camps = [233,237,242,243,245,246,247,248]
for i in camps:
    # Your SQL query
    query = f"""
SELECT
  ccd.id              AS ccd_id,
  ccd.campaign_id     AS ccd_campaign_id,
  ccd.customer_id     AS ccd_customer_id,
  ccd.current_wave_id,
  ccd.attempts_made,
  ccd.last_attempt_at,
  ccd.scheduled_at,
  ccd.status          AS ccd_status,
  ccd.created_at      AS ccd_created_at,
  ccd.updated_at      AS ccd_updated_at,

  c.id                AS campaign_id,
  c.client_id,
  c.name              AS campaign_name,
  c.status            AS campaign_status,
  c.bot_id            AS campaign_bot_id,

  cl.id               AS call_log_id,
  cl.payload_id,
  cl.campaign_id      AS cl_campaign_id,
  cl.customer_id      AS cl_customer_id,
  cl.wave_id,
  cl.attempts,
  cl.call_status,
  cl.transcript,
  cl.duration,
  cl.fincode,
  cl.contact_to,
  cl.recording,
  cl.started_at       AS call_started_at,
  cl.ended_at         AS call_ended_at,
  cl.connected_on_attempt,
  cl.media_connected_at,
  cl.scheduler_status,
  cl.bot_id           AS call_bot_id
FROM ivo_campaign_call_data ccd
JOIN ivo_campaign c ON c.id = ccd.campaign_id
JOIN ivo_call_log cl
  ON cl.campaign_id = ccd.campaign_id
 AND cl.customer_id = ccd.customer_id
 AND (
       cl.connected_on_attempt IS TRUE
    OR LOWER(COALESCE(cl.call_status, '')) IN ('answered', 'connected')
    OR cl.media_connected_at IS NOT NULL
 )
WHERE c.client_id = 5
  AND c.deleted_at IS NULL
  AND ccd.status = 'completed_connected'
  AND cl.campaign_id = {i};
"""

    # Execute query and load result into a DataFrame
    df = pd.read_sql_query(query, conn)

    # Export to CSV
    output_file_csv = f"{i}_data.csv"
    output_file_json = f"{i}_data.json"
    df.to_csv(output_file_csv, index=False)
    df.to_json(output_file_json, index=False)
    print(f"Successfully exported {len(df)} rows to {i}data.csv")

# Close connection
conn.close()
