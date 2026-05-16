from __future__ import annotations

import json
import sqlite3
from typing import Any

MULTI_VALUE_FIELDS = {
    "products_used": "product",
    "technical_area": "technical_area",
    "use_case_category": "use_case_category",
    "outcome_category": "outcome_category",
    "metrics": "metric",
    "architecture_clues": "architecture_clue",
    "evidence_quotes": "evidence_quote",
}


def initialize_database(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        create table if not exists case_studies (
            id text primary key,
            slug text not null unique,
            vendor text not null,
            customer_name text not null,
            industry text not null,
            region text not null,
            company_size text not null,
            business_problem text not null,
            solution_summary text not null,
            business_outcome text not null,
            source_url text not null,
            published_date text not null,
            confidence_score real not null,
            maturity_score integer not null,
            is_sample integer not null default 0,
            raw_json text not null,
            updated_at text not null default current_timestamp
        );

        create table if not exists case_study_values (
            case_study_id text not null,
            kind text not null,
            value text not null,
            foreign key (case_study_id) references case_studies(id) on delete cascade
        );

        create index if not exists idx_case_studies_vendor on case_studies(vendor);
        create index if not exists idx_case_studies_industry on case_studies(industry);
        create index if not exists idx_case_values_kind_value on case_study_values(kind, value);
        """
    )


def upsert_records(connection: sqlite3.Connection, records: list[dict[str, Any]]) -> None:
    for record in records:
        connection.execute(
            """
            insert into case_studies (
                id, slug, vendor, customer_name, industry, region, company_size,
                business_problem, solution_summary, business_outcome, source_url,
                published_date, confidence_score, maturity_score, is_sample, raw_json, updated_at
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, current_timestamp)
            on conflict(id) do update set
                slug = excluded.slug,
                vendor = excluded.vendor,
                customer_name = excluded.customer_name,
                industry = excluded.industry,
                region = excluded.region,
                company_size = excluded.company_size,
                business_problem = excluded.business_problem,
                solution_summary = excluded.solution_summary,
                business_outcome = excluded.business_outcome,
                source_url = excluded.source_url,
                published_date = excluded.published_date,
                confidence_score = excluded.confidence_score,
                maturity_score = excluded.maturity_score,
                is_sample = excluded.is_sample,
                raw_json = excluded.raw_json,
                updated_at = current_timestamp
            """,
            (
                record["id"],
                record["slug"],
                record["vendor"],
                record["customer_name"],
                record["industry"],
                record["region"],
                record["company_size"],
                record["business_problem"],
                record["solution_summary"],
                record["business_outcome"],
                record["source_url"],
                record["published_date"],
                record["confidence_score"],
                record["maturity_score"],
                int(record.get("is_sample", False)),
                json.dumps(record, ensure_ascii=False, sort_keys=True),
            ),
        )

        connection.execute("delete from case_study_values where case_study_id = ?", (record["id"],))
        for field, kind in MULTI_VALUE_FIELDS.items():
            for value in record.get(field, []):
                connection.execute(
                    "insert into case_study_values (case_study_id, kind, value) values (?, ?, ?)",
                    (record["id"], kind, value),
                )

    connection.commit()