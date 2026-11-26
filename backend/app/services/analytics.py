"""Optional export of each cycle's risk snapshot to BigQuery (works in the free BigQuery sandbox,
no billing needed). Looker Studio connects to the table for the regional analytics dashboard."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings

log = logging.getLogger(__name__)
SCHEMA = [
    ("ts", "TIMESTAMP"), ("facility_id", "INTEGER"), ("abo_rh", "STRING"), ("component", "STRING"),
    ("usable_units", "INTEGER"), ("p_stockout_24", "FLOAT"), ("p_stockout_72", "FLOAT"), ("tts_p50", "FLOAT"),
    ("days_cover", "FLOAT"), ("expected_wastage", "FLOAT"), ("severity", "STRING"), ("confidence", "FLOAT"),
]


def _export(rows: list[dict]) -> str:
    from google.cloud import bigquery

    s = get_settings()
    client = bigquery.Client(project=s.google_cloud_project)
    table_id = f"{client.project}.{s.bigquery_dataset}.risk_snapshots"
    try:
        client.get_table(table_id)
    except Exception:  # noqa: BLE001 - create on first use
        client.create_dataset(s.bigquery_dataset, exists_ok=True)
        table = bigquery.Table(table_id, schema=[bigquery.SchemaField(n, t) for n, t in SCHEMA])
        table.time_partitioning = bigquery.TimePartitioning(field="ts")
        client.create_table(table, exists_ok=True)
    ts = datetime.now(UTC).isoformat()
    payload = [{k: r.get(k) for k, _ in SCHEMA if k != "ts"} | {"ts": ts} for r in rows]
    # Sandbox tables do not allow streaming inserts; a load job works on the free tier.
    job = client.load_table_from_json(payload, table_id)
    job.result(timeout=60)
    return f"exported {len(payload)} rows"


async def export_snapshot(session: AsyncSession, rows: list[dict]) -> str:
    if not get_settings().bigquery_dataset:
        return "disabled"
    return await asyncio.to_thread(_export, rows)
