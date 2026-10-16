"""Workflow-integrated multi-dimensional analytics and official vendor logo sync.

Invoked automatically as part of `npm run data:build` so every new ingestion or
enrichment run recomputes granular cross-dimensional intelligence and ensures
every active vendor has an official logo asset in `public/logos/vendors/`.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
from itertools import combinations
import json
from pathlib import Path
import re
from statistics import median
from typing import Any
import urllib.request

from .settings import (
    GENERATED_ANALYTICS_PATH as DEFAULT_ANALYTICS_PATH,
    GENERATED_CASE_STUDIES_PATH as DEFAULT_EXPORT_PATH,
    REPO_ROOT as ROOT_DIR,
    TAXONOMY_PATH,
)

VENDOR_LOGOS_DIR = ROOT_DIR / "public" / "logos" / "vendors"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

VENDOR_CATEGORY_MAP: dict[str, tuple[str, str]] = {
    "Microsoft": ("Cloud & Hyperscaler", "microsoft.com"),
    "Google Cloud": ("Cloud & Hyperscaler", "cloud.google.com"),
    "AWS": ("Cloud & Hyperscaler", "aws.amazon.com"),
    "Oracle": ("Cloud & Hyperscaler", "oracle.com"),
    "IBM": ("Enterprise & Cloud", "ibm.com"),
    "Alibaba Cloud": ("China Cloud & AI", "alibabacloud.com"),
    "Baidu AI Cloud": ("China Cloud & AI", "cloud.baidu.com"),
    "Huawei Cloud": ("China Cloud & AI", "huaweicloud.com"),
    "Tencent Cloud": ("China Cloud & AI", "tencentcloud.com"),
    "BytePlus": ("China Cloud & AI", "byteplus.com"),
    "OpenAI": ("Foundation Models & AI", "openai.com"),
    "Anthropic": ("Foundation Models & AI", "anthropic.com"),
    "Mistral": ("Foundation Models & AI", "mistral.ai"),
    "Cohere": ("Foundation Models & AI", "cohere.com"),
    "LangChain": ("Foundation Models & AI", "langchain.com"),
    "Databricks": ("Data & AI Platform", "databricks.com"),
    "Snowflake": ("Data & AI Platform", "snowflake.com"),
    "MongoDB": ("Data & AI Platform", "mongodb.com"),
    "Confluent": ("Data & AI Platform", "confluent.io"),
    "NVIDIA": ("AI Compute & Silicon", "nvidia.com"),
    "Intel": ("AI Compute & Silicon", "intel.com"),
    "Salesforce": ("Enterprise Software", "salesforce.com"),
    "ServiceNow": ("Enterprise Software", "servicenow.com"),
    "SAP": ("Enterprise Software", "sap.com"),
    "Adobe": ("Enterprise Software", "adobe.com"),
    "Sprinklr": ("Enterprise Software", "sprinklr.com"),
    "Windward": ("Enterprise Software", "windward.ai"),
    "Wolters Kluwer": ("Enterprise Software", "wolterskluwer.com"),
    "7AI": ("Enterprise Software", "7ai.com"),
    "Accenture": ("Global Consulting", "accenture.com"),
    "Capgemini": ("Global Consulting", "capgemini.com"),
    "EY": ("Global Consulting", "ey.com"),
    "PwC": ("Global Consulting", "pwc.com"),
    "Bain": ("Global Consulting", "bain.com"),
    "TCS": ("Global Consulting", "tcs.com"),
    "DXC": ("Global Consulting", "dxc.com"),
    "BCG": ("Global Consulting", "bcg.com"),
    "Cognizant": ("Global Consulting", "cognizant.com"),
    "Atos": ("Global Consulting", "atos.net"),
    "Infosys": ("Global Consulting", "infosys.com"),
    "KPMG": ("Global Consulting", "kpmg.com"),
    "Wipro": ("Global Consulting", "wipro.com"),
    "Deloitte": ("Global Consulting", "deloitte.com"),
    "Eviden": ("Global Consulting", "eviden.com"),
    "SLB": ("Enterprise & Industry", "slb.com"),
    "Deutsche Telekom": ("Enterprise & Industry", "telekom.com"),
    "Mastercard": ("Enterprise & Industry", "mastercard.com"),
    "Medtronic": ("Enterprise & Industry", "medtronic.com"),
    "Halliburton": ("Enterprise & Industry", "halliburton.com"),
    "Rockwell Automation": ("Enterprise & Industry", "rockwellautomation.com"),
    "Telefónica": ("Enterprise & Industry", "telefonica.com"),
    "In-house": ("Internal Engineering", "internal"),
}

ROI_CATEGORIES: list[tuple[str, str, re.Pattern[str]]] = [
    (
        "Cycle Time & Latency Reduction",
        "Faster response, processing, turnaround, or deployment times.",
        re.compile(
            r"\b(latency|response time|turnaround|faster|speed|minutes|seconds|hours to|days to|weeks to|cycle time|wait time|processing time|real-time|time to market)\b",
            re.I,
        ),
    ),
    (
        "Productivity & Time Saved",
        "Engineering, analyst, or frontline staff hours saved and output gains.",
        re.compile(
            r"\b(productivity|hours saved|time saved|efficiency|manual effort|workload|staff|engineer|developer|analyst|saved per|hours per|workweek)\b",
            re.I,
        ),
    ),
    (
        "Automation & Resolution Rate",
        "Self-service containment, automated handling, and model precision/accuracy.",
        re.compile(
            r"\b(automat\w+|deflect\w+|containment|resolution|self-service|accuracy|precision|recall|f1|error rate|false positive|straight-through)\b",
            re.I,
        ),
    ),
    (
        "Cost & Infrastructure Efficiency",
        "Direct operating cost, compute/storage TCO, and financial savings.",
        re.compile(
            r"\b(cost|tco|savings|saved \$|\$[0-9]|million|billion|budget|opex|compute cost|infrastructure cost|roi|payback)\b",
            re.I,
        ),
    ),
    (
        "Revenue, Conversion & Experience Lift",
        "Top-line growth, conversion rate, retention, CSAT, and NPS improvements.",
        re.compile(
            r"\b(revenue|sales|conversion|retention|churn|csat|nps|satisfaction|engagement|click-through|ctr|upsell|order value|growth)\b",
            re.I,
        ),
    ),
    (
        "Scale & Throughput Capacity",
        "Volume of documents, transactions, queries, or users handled at scale.",
        re.compile(
            r"\b(throughput|scale|queries|requests|documents|transactions|users|customers|calls|tickets|tokens|terabytes|petabytes|concurrent)\b",
            re.I,
        ),
    ),
]

PERCENT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*%")
MULTIPLIER_RE = re.compile(r"\b(\d+(?:\.\d+)?)\s*x\b", re.I)


def slugify(value: str) -> str:
    normalized = (
        value.lower()
        .replace("é", "e")
        .replace("ó", "o")
        .replace("í", "i")
        .replace("á", "a")
        .replace("ú", "u")
        .replace("ñ", "n")
    )
    return re.sub(r"[^a-z0-9]+", "-", normalized).strip("-")


def normalize_country_and_macro_region(raw_region: str) -> tuple[str, str]:
    text = (raw_region or "").strip()
    if not text or text.lower() in {"unknown", "n/a", "unspecified"}:
        return ("Unknown", "Unspecified")

    low = text.lower()
    if any(k in low for k in ["global", "worldwide", "multi-region", "international", "multiple"]):
        return ("Global", "Global / Multi-region")
    if any(k in low for k in ["china", "beijing", "shanghai", "shenzhen", "guangdong", "hangzhou", "hong kong", "taiwan", "macau"]):
        country = "China"
        if "hong kong" in low:
            country = "Hong Kong"
        elif "taiwan" in low:
            country = "Taiwan"
        return (country, "Greater China")
    if any(k in low for k in ["united states", "usa", "u.s.", "us", "california", "new york", "texas", "north america", "canada"]):
        country = "Canada" if "canada" in low else ("North America" if "north america" in low else "United States")
        return (country, "North America")
    if any(
        k in low
        for k in [
            "united kingdom",
            "uk",
            "england",
            "london",
            "germany",
            "france",
            "spain",
            "italy",
            "netherlands",
            "switzerland",
            "sweden",
            "norway",
            "denmark",
            "finland",
            "poland",
            "ireland",
            "belgium",
            "austria",
            "portugal",
            "europe",
            "eu",
            "emea",
            "czech",
            "romania",
            "greece",
            "turkey",
            "ukraine",
        ]
    ):
        for name, token in [
            ("United Kingdom", "united kingdom"),
            ("United Kingdom", "uk"),
            ("Germany", "germany"),
            ("France", "france"),
            ("Spain", "spain"),
            ("Italy", "italy"),
            ("Netherlands", "netherlands"),
            ("Switzerland", "switzerland"),
            ("Sweden", "sweden"),
            ("Norway", "norway"),
            ("Denmark", "denmark"),
            ("Finland", "finland"),
            ("Ireland", "ireland"),
            ("Poland", "poland"),
            ("Belgium", "belgium"),
            ("Austria", "austria"),
        ]:
            if token in low:
                return (name, "Europe")
        return ("Europe (Regional)", "Europe")
    if any(
        k in low
        for k in [
            "japan",
            "india",
            "singapore",
            "australia",
            "south korea",
            "korea",
            "indonesia",
            "malaysia",
            "thailand",
            "vietnam",
            "philippines",
            "new zealand",
            "apac",
            "asia",
        ]
    ):
        for name, token in [
            ("Japan", "japan"),
            ("India", "india"),
            ("Singapore", "singapore"),
            ("Australia", "australia"),
            ("South Korea", "korea"),
            ("Indonesia", "indonesia"),
            ("Malaysia", "malaysia"),
            ("Thailand", "thailand"),
            ("Philippines", "philippines"),
            ("Vietnam", "vietnam"),
            ("New Zealand", "new zealand"),
        ]:
            if token in low:
                return (name, "Asia-Pacific")
        return ("Asia-Pacific (Regional)", "Asia-Pacific")
    if any(k in low for k in ["brazil", "mexico", "colombia", "chile", "argentina", "peru", "latin america", "latam"]):
        for name, token in [
            ("Brazil", "brazil"),
            ("Mexico", "mexico"),
            ("Colombia", "colombia"),
            ("Chile", "chile"),
            ("Argentina", "argentina"),
            ("Peru", "peru"),
        ]:
            if token in low:
                return (name, "Latin America")
        return ("Latin America (Regional)", "Latin America")
    if any(
        k in low
        for k in [
            "united arab emirates",
            "uae",
            "dubai",
            "saudi",
            "israel",
            "qatar",
            "south africa",
            "nigeria",
            "kenya",
            "egypt",
            "middle east",
            "africa",
        ]
    ):
        for name, token in [
            ("United Arab Emirates", "united arab emirates"),
            ("United Arab Emirates", "uae"),
            ("Saudi Arabia", "saudi"),
            ("Israel", "israel"),
            ("South Africa", "south africa"),
            ("Qatar", "qatar"),
        ]:
            if token in low:
                return (name, "Middle East & Africa")
        return ("MEA (Regional)", "Middle East & Africa")

    return (text, "Global / Multi-region")


def has_quantified_impact(record: dict[str, Any]) -> bool:
    for item in record.get("value_breakdown") or []:
        if item.get("criterion") == "Quantified impact" and (item.get("score") or 0) > 0:
            return True
    return any(bool(re.search(r"\d", str(m))) for m in (record.get("metrics") or []))


def clean_metric_text(raw: str) -> str:
    txt = str(raw or "").strip().strip('"\'“”‘’')
    txt = re.sub(r"\s+", " ", txt).strip()
    if len(txt) <= 105:
        return txt
    return txt[:102].rsplit(" ", 1)[0] + "…"


def headline_metric(record: dict[str, Any]) -> str:
    metrics = [clean_metric_text(m) for m in (record.get("metrics") or []) if str(m).strip()]
    concise = [
        m
        for m in metrics
        if 8 <= len(m) <= 95
        and re.search(r"(\d+(?:\.\d+)?\s*%|\d+(?:\.\d+)?x\b|\$|\bhours?\b|\bdays?\b|\bminutes?\b|\bseconds?\b|\bmillion\b|\bbillion\b)", m, re.I)
        and not m.startswith("(")
    ]
    if concise:
        return concise[0]
    chosen = next((m for m in metrics if re.search(r"\d", m)), metrics[0] if metrics else "")
    return chosen


def sync_vendor_logos(vendors: list[str], logos_dir: Path = VENDOR_LOGOS_DIR) -> dict[str, str]:
    """Ensure every active vendor has an official logo asset in public/logos/vendors/."""
    logos_dir.mkdir(parents=True, exist_ok=True)
    existing_by_slug: dict[str, str] = {}
    for file_path in sorted(logos_dir.iterdir()):
        if file_path.is_file():
            existing_by_slug[file_path.stem] = file_path.name

    resolved: dict[str, str] = {}
    for vendor in vendors:
        slug = slugify(vendor)
        if slug in existing_by_slug:
            resolved[vendor] = existing_by_slug[slug]
            continue
        # Automatic fallback for newly discovered vendors in future CI runs:
        _, domain = VENDOR_CATEGORY_MAP.get(vendor, ("Enterprise & Industry", f"{slug}.com"))
        target_name = f"{slug}.png"
        target_path = logos_dir / target_name
        if domain != "internal":
            try:
                url = f"https://www.google.com/s2/favicons?domain={domain}&sz=128"
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                data = urllib.request.urlopen(req, timeout=8).read()
                if len(data) > 100:
                    target_path.write_bytes(data)
                    resolved[vendor] = target_name
                    existing_by_slug[slug] = target_name
                    continue
            except Exception:
                pass
        resolved[vendor] = existing_by_slug.get("in-house", "in-house.svg")
    return resolved


def _top_counter(counter: Counter[str], total: int, limit: int = 8) -> list[dict[str, Any]]:
    denom = max(total, 1)
    return [
        {"label": label, "count": count, "share": round(count / denom, 4)}
        for label, count in sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))[:limit]
        if label
    ]


def _build_group_dossier(
    key_name: str,
    label: str,
    group_records: list[dict[str, Any]],
    total_corpus: int,
    component_layers: list[str],
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    count = len(group_records)
    denom = max(count, 1)
    quantified_records = [r for r in group_records if has_quantified_impact(r)]
    with_arch = [r for r in group_records if r.get("solution_components")]
    with_flow = [r for r in group_records if r.get("data_flow")]

    products_counter: Counter[str] = Counter()
    pairs_counter: Counter[tuple[str, str]] = Counter()
    layer_counter: Counter[str] = Counter()
    layer_comp_counter: Counter[str] = Counter()
    layer_prod_counter: dict[str, Counter[str]] = defaultdict(Counter)
    vendor_counter: Counter[str] = Counter()
    use_case_counter: Counter[str] = Counter()
    industry_counter: Counter[str] = Counter()
    outcome_counter: Counter[str] = Counter()
    area_counter: Counter[str] = Counter()
    macro_region_counter: Counter[str] = Counter()
    company_size_counter: Counter[str] = Counter()
    percent_gains: list[float] = []
    sample_metrics: list[dict[str, str]] = []

    for r in group_records:
        v = r.get("vendor") or ""
        if v:
            vendor_counter[v] += 1
        ind = r.get("industry") or ""
        if ind and ind != "unknown":
            industry_counter[ind] += 1
        for uc in set(r.get("use_case_category") or []):
            if uc and uc != "unknown":
                use_case_counter[uc] += 1
        for oc in set(r.get("outcome_category") or []):
            if oc and oc != "unknown":
                outcome_counter[oc] += 1
        for ta in set(r.get("technical_area") or []):
            if ta and ta != "unknown":
                area_counter[ta] += 1

        prods = sorted({str(p).strip() for p in (r.get("products_used") or []) if str(p).strip()})
        for p in prods:
            products_counter[p] += 1
        if len(prods) >= 2:
            for a, b in combinations(prods[:10], 2):
                pairs_counter[(a, b)] += 1

        seen_layers: set[str] = set()
        for comp in r.get("solution_components") or []:
            layer = (comp.get("layer") or "").strip()
            cname = (comp.get("name") or "").strip()
            if layer in component_layers:
                seen_layers.add(layer)
                layer_comp_counter[layer] += 1
                if cname:
                    layer_prod_counter[layer][cname] += 1
        for layer in seen_layers:
            layer_counter[layer] += 1

        _, macro_reg = normalize_country_and_macro_region(str(r.get("region") or ""))
        if macro_reg != "Unspecified":
            macro_region_counter[macro_reg] += 1

        csize = str(r.get("company_size") or "Unknown").strip() or "Unknown"
        if csize.lower() != "unknown":
            company_size_counter[csize] += 1

        for m in r.get("metrics") or []:
            m_str = str(m).strip()
            for match in PERCENT_RE.findall(m_str):
                val = float(match)
                if 1.0 <= val <= 500.0:
                    percent_gains.append(val)
            if len(sample_metrics) < 6 and re.search(r"(\d+(?:\.\d+)?\s*%|\d+(?:\.\d+)?x\b|\$|\bhours?\b|\bdays?\b|\bminutes?\b)", m_str, re.I):
                cleaned = clean_metric_text(m_str)
                if 10 <= len(cleaned) <= 95 and not cleaned.startswith("("):
                    sample_metrics.append(
                        {
                            "metric": cleaned,
                            "customer_name": str(r.get("customer_name") or ""),
                            "vendor": str(r.get("vendor") or ""),
                            "slug": str(r.get("slug") or ""),
                        }
                    )

    ranked_cases = sorted(
        group_records,
        key=lambda r: (
            -(r.get("value_score") or 0),
            -(r.get("confidence_score") or 0.0),
            -(r.get("maturity_score") or 0),
            str(r.get("customer_name") or ""),
        ),
    )[:4]

    flagship_cases = [
        {
            "slug": str(r.get("slug") or ""),
            "customer_name": str(r.get("customer_name") or ""),
            "vendor": str(r.get("vendor") or ""),
            "industry": str(r.get("industry") or ""),
            "use_case": (r.get("use_case_category") or [""])[0],
            "headline_metric": headline_metric(r),
            "value_score": int(r.get("value_score") or 0),
        }
        for r in ranked_cases
    ]

    layer_distribution = [
        {
            "layer": layer,
            "count": layer_counter.get(layer, 0),
            "story_count": layer_counter.get(layer, 0),
            "component_count": layer_comp_counter.get(layer, 0),
            "share": round(layer_counter.get(layer, 0) / denom, 4),
            "story_share": round(layer_counter.get(layer, 0) / denom, 4),
            "top_products": _top_counter(layer_prod_counter[layer], max(layer_comp_counter.get(layer, 0), 1), 4),
        }
        for layer in component_layers
        if layer_comp_counter.get(layer, 0) > 0
    ]
    layer_distribution.sort(key=lambda item: (-item["component_count"], item["layer"]))

    top_pairs = [
        {"pair": f"{a} + {b}", "product_a": a, "product_b": b, "count": c, "share": round(c / denom, 4)}
        for (a, b), c in sorted(pairs_counter.items(), key=lambda kv: (-kv[1], kv[0]))[:5]
        if c >= 2
    ]

    for r in ranked_cases:
        hm = headline_metric(r)
        if hm and len(sample_metrics) < 6 and not any(s["customer_name"] == r.get("customer_name") for s in sample_metrics):
            sample_metrics.append(
                {
                    "metric": hm,
                    "customer_name": str(r.get("customer_name") or ""),
                    "vendor": str(r.get("vendor") or ""),
                    "slug": str(r.get("slug") or ""),
                }
            )

    result: dict[str, Any] = {
        "name": label,
        key_name: label,
        "slug": slugify(label),
        "count": count,
        "share": round(count / max(total_corpus, 1), 4),
        "avg_value_score": round(sum(float(r.get("value_score") or 0) for r in group_records) / denom, 1),
        "avg_confidence_score": round(sum(float(r.get("confidence_score") or 0) for r in group_records) / denom, 2),
        "quantified_count": len(quantified_records),
        "quantified_rate": round(len(quantified_records) / denom, 4),
        "architecture_count": len(with_arch),
        "architecture_rate": round(len(with_arch) / denom, 4),
        "architecture_coverage_rate": round(len(with_arch) / denom, 4),
        "data_flow_rate": round(len(with_flow) / denom, 4),
        "data_flow_coverage_rate": round(len(with_flow) / denom, 4),
        "distinct_products_count": len(products_counter),
        "median_percent_gain": round(median(percent_gains), 1) if percent_gains else None,
        "top_products": _top_counter(products_counter, count, 8),
        "product_pairs": top_pairs,
        "co_occurring_pairs": top_pairs,
        "layer_distribution": layer_distribution,
        "architecture_layers": layer_distribution,
        "top_vendors": _top_counter(vendor_counter, count, 6),
        "top_use_cases": _top_counter(use_case_counter, count, 6),
        "top_industries": _top_counter(industry_counter, count, 6),
        "top_outcomes": _top_counter(outcome_counter, count, 5),
        "top_technical_areas": _top_counter(area_counter, count, 5),
        "macro_regions": _top_counter(macro_region_counter, count, 5),
        "company_sizes": _top_counter(company_size_counter, count, 4),
        "sample_metrics": sample_metrics[:4],
        "flagship_cases": flagship_cases,
        "top_cases": flagship_cases,
    }
    if extra:
        result.update(extra)
    return result


def build_analytics(
    records: list[dict[str, Any]],
    taxonomy: dict[str, Any],
    sync_logos: bool = True,
) -> dict[str, Any]:
    live_records = [r for r in records if not r.get("is_sample")]
    total = len(live_records)
    denom = max(total, 1)
    component_layers: list[str] = list(
        taxonomy.get("component_layers")
        or ["Ingest", "Compute", "Storage", "Serving", "Orchestration", "Governance"]
    )

    vendors = sorted({str(r.get("vendor") or "") for r in live_records if r.get("vendor")})
    logo_map = sync_vendor_logos(vendors) if sync_logos else {}

    # 1. Architecture layers breakdown
    layer_stories: dict[str, list[dict[str, Any]]] = defaultdict(list)
    layer_components_count: Counter[str] = Counter()
    layer_products: dict[str, Counter[str]] = defaultdict(Counter)
    layer_vendors: dict[str, Counter[str]] = defaultdict(Counter)
    layer_use_cases: dict[str, Counter[str]] = defaultdict(Counter)
    layer_roles: dict[str, list[str]] = defaultdict(list)

    # 2. Product ecosystem & co-occurrence
    product_counter: Counter[str] = Counter()
    product_vendors: dict[str, Counter[str]] = defaultdict(Counter)
    product_layers: dict[str, Counter[str]] = defaultdict(Counter)
    product_use_cases: dict[str, Counter[str]] = defaultdict(Counter)
    product_value_scores: dict[str, list[float]] = defaultdict(list)
    product_quantified: Counter[str] = Counter()

    pair_counter: Counter[tuple[str, str]] = Counter()
    pair_vendors: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    pair_use_cases: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    integration_counter: Counter[str] = Counter()

    # 3. Geography & Company Size
    macro_region_records: dict[str, list[dict[str, Any]]] = defaultdict(list)
    country_counter: Counter[str] = Counter()
    country_macro: dict[str, str] = {}
    country_vendors: dict[str, Counter[str]] = defaultdict(Counter)
    country_industries: dict[str, Counter[str]] = defaultdict(Counter)
    company_size_records: dict[str, list[dict[str, Any]]] = defaultdict(list)

    # 4. Facet groups
    by_vendor: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_use_case: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_industry: dict[str, list[dict[str, Any]]] = defaultdict(list)

    total_components = 0
    total_metrics = 0

    for r in live_records:
        v = str(r.get("vendor") or "")
        ind = str(r.get("industry") or "")
        ucs = [u for u in (r.get("use_case_category") or []) if u and u != "unknown"]
        is_quant = has_quantified_impact(r)
        val_score = float(r.get("value_score") or 0)

        if v:
            by_vendor[v].append(r)
        if ind and ind != "unknown":
            by_industry[ind].append(r)
        for uc in set(ucs):
            by_use_case[uc].append(r)

        # Components & layers
        comps = r.get("solution_components") or []
        total_components += len(comps)
        seen_layers: set[str] = set()
        for comp in comps:
            c_name = str(comp.get("name") or "").strip()
            c_layer = str(comp.get("layer") or "").strip()
            c_role = str(comp.get("role") or "").strip()
            if c_layer in component_layers:
                seen_layers.add(c_layer)
                layer_components_count[c_layer] += 1
                if c_name:
                    layer_products[c_layer][c_name] += 1
                    product_layers[c_name][c_layer] += 1
                if c_role and len(layer_roles[c_layer]) < 5:
                    layer_roles[c_layer].append(c_role)
        for layer in seen_layers:
            layer_stories[layer].append(r)
            if v:
                layer_vendors[layer][v] += 1
            for uc in set(ucs):
                layer_use_cases[layer][uc] += 1

        # Products & pairs
        prods = sorted({str(p).strip() for p in (r.get("products_used") or []) if str(p).strip()})
        for p in prods:
            product_counter[p] += 1
            if v:
                product_vendors[p][v] += 1
            for uc in set(ucs):
                product_use_cases[p][uc] += 1
            product_value_scores[p].append(val_score)
            if is_quant:
                product_quantified[p] += 1

        if len(prods) >= 2:
            for a, b in combinations(prods[:10], 2):
                pair_counter[(a, b)] += 1
                if v:
                    pair_vendors[(a, b)][v] += 1
                for uc in set(ucs):
                    pair_use_cases[(a, b)][uc] += 1

        for ip in set(r.get("integration_points") or []):
            ip_str = str(ip).strip()
            if ip_str:
                integration_counter[ip_str] += 1

        # Geography & size
        country, macro_reg = normalize_country_and_macro_region(str(r.get("region") or ""))
        macro_region_records[macro_reg].append(r)
        if country not in {"Unknown", "Global"} and not country.endswith("(Regional)"):
            country_counter[country] += 1
            country_macro[country] = macro_reg
            if v:
                country_vendors[country][v] += 1
            if ind and ind != "unknown":
                country_industries[country][ind] += 1

        csize = str(r.get("company_size") or "Unknown").strip() or "Unknown"
        company_size_records[csize].append(r)

        total_metrics += len(r.get("metrics") or [])

    # Build architecture_layers array
    architecture_layers = []
    for layer in component_layers:
        stories = layer_stories[layer]
        s_count = len(stories)
        architecture_layers.append(
            {
                "layer": layer,
                "story_count": s_count,
                "story_share": round(s_count / denom, 4),
                "component_count": layer_components_count[layer],
                "top_products": _top_counter(layer_products[layer], s_count, 8),
                "top_vendors": _top_counter(layer_vendors[layer], s_count, 5),
                "top_use_cases": _top_counter(layer_use_cases[layer], s_count, 5),
                "sample_roles": layer_roles[layer][:3],
            }
        )

    # Build product_ecosystem
    top_products = []
    for prod, count in sorted(product_counter.items(), key=lambda kv: (-kv[1], kv[0]))[:30]:
        primary_vendor = product_vendors[prod].most_common(1)[0][0] if product_vendors[prod] else ""
        primary_layer = product_layers[prod].most_common(1)[0][0] if product_layers[prod] else "Serving"
        scores = product_value_scores[prod]
        top_products.append(
            {
                "name": prod,
                "count": count,
                "share": round(count / denom, 4),
                "primary_vendor": primary_vendor,
                "primary_layer": primary_layer,
                "top_use_cases": [lbl for lbl, _ in product_use_cases[prod].most_common(3)],
                "avg_value_score": round(sum(scores) / max(len(scores), 1), 1),
                "quantified_rate": round(product_quantified[prod] / max(count, 1), 4),
            }
        )

    co_occurring_pairs = []
    for (a, b), count in sorted(pair_counter.items(), key=lambda kv: (-kv[1], kv[0]))[:24]:
        co_occurring_pairs.append(
            {
                "pair": f"{a} + {b}",
                "product_a": a,
                "product_b": b,
                "count": count,
                "share": round(count / denom, 4),
                "top_vendor": pair_vendors[(a, b)].most_common(1)[0][0] if pair_vendors[(a, b)] else "",
                "top_use_case": pair_use_cases[(a, b)].most_common(1)[0][0] if pair_use_cases[(a, b)] else "",
            }
        )

    # Build quantified_roi_benchmarks
    roi_benchmarks = []
    for cat_label, cat_desc, pattern in ROI_CATEGORIES:
        matched_stories: list[dict[str, Any]] = []
        matched_metrics_count = 0
        pct_values: list[float] = []
        mult_count = 0
        uc_counter: Counter[str] = Counter()
        samples: list[dict[str, str]] = []

        for r in live_records:
            metrics = [str(m).strip() for m in (r.get("metrics") or []) if str(m).strip()]
            cat_hits = [m for m in metrics if pattern.search(m)]
            if not cat_hits:
                continue
            matched_stories.append(r)
            matched_metrics_count += len(cat_hits)
            for uc in set(r.get("use_case_category") or []):
                if uc and uc != "unknown":
                    uc_counter[uc] += 1
            for m in cat_hits:
                for p_match in PERCENT_RE.findall(m):
                    val = float(p_match)
                    if 1.0 <= val <= 500.0:
                        pct_values.append(val)
                if MULTIPLIER_RE.search(m):
                    mult_count += 1
                if len(samples) < 5 and re.search(r"\d", m):
                    samples.append(
                        {
                            "metric": headline_metric({"metrics": [m]}),
                            "customer_name": str(r.get("customer_name") or ""),
                            "vendor": str(r.get("vendor") or ""),
                            "slug": str(r.get("slug") or ""),
                        }
                    )

        sorted_pcts = sorted(pct_values)
        p75 = sorted_pcts[int(len(sorted_pcts) * 0.75)] if sorted_pcts else None
        roi_benchmarks.append(
            {
                "category": cat_label,
                "description": cat_desc,
                "story_count": len(matched_stories),
                "story_share": round(len(matched_stories) / denom, 4),
                "metric_count": matched_metrics_count,
                "median_percent_gain": round(median(sorted_pcts), 1) if sorted_pcts else None,
                "p75_percent_gain": round(p75, 1) if p75 is not None else None,
                "multiplier_count": mult_count,
                "top_use_cases": _top_counter(uc_counter, len(matched_stories), 4),
                "sample_metrics": samples[:4],
            }
        )

    # Build geography_and_scale
    macro_regions = []
    for reg_label, reg_records in sorted(macro_region_records.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        if reg_label == "Unspecified":
            continue
        r_count = len(reg_records)
        v_cnt = Counter(str(r.get("vendor") or "") for r in reg_records if r.get("vendor"))
        uc_cnt = Counter(
            uc
            for r in reg_records
            for uc in set(r.get("use_case_category") or [])
            if uc and uc != "unknown"
        )
        q_cnt = sum(1 for r in reg_records if has_quantified_impact(r))
        macro_regions.append(
            {
                "region": reg_label,
                "count": r_count,
                "share": round(r_count / denom, 4),
                "quantified_rate": round(q_cnt / max(r_count, 1), 4),
                "top_vendors": _top_counter(v_cnt, r_count, 4),
                "top_use_cases": _top_counter(uc_cnt, r_count, 4),
            }
        )

    top_countries = [
        {
            "country": c_label,
            "macro_region": country_macro.get(c_label, ""),
            "count": c_count,
            "share": round(c_count / denom, 4),
            "top_vendor": country_vendors[c_label].most_common(1)[0][0] if country_vendors[c_label] else "",
            "top_industry": country_industries[c_label].most_common(1)[0][0] if country_industries[c_label] else "",
        }
        for c_label, c_count in sorted(country_counter.items(), key=lambda kv: (-kv[1], kv[0]))[:20]
    ]

    company_sizes = []
    for size_label in ["Enterprise", "Mid-market", "Public sector", "SMB", "Unknown"]:
        s_records = company_size_records.get(size_label, [])
        if not s_records:
            continue
        s_count = len(s_records)
        q_cnt = sum(1 for r in s_records if has_quantified_impact(r))
        uc_cnt = Counter(
            uc
            for r in s_records
            for uc in set(r.get("use_case_category") or [])
            if uc and uc != "unknown"
        )
        v_cnt = Counter(str(r.get("vendor") or "") for r in s_records if r.get("vendor"))
        company_sizes.append(
            {
                "company_size": size_label,
                "count": s_count,
                "share": round(s_count / denom, 4),
                "avg_value_score": round(sum(float(r.get("value_score") or 0) for r in s_records) / s_count, 1),
                "quantified_rate": round(q_cnt / s_count, 4),
                "top_use_cases": _top_counter(uc_cnt, s_count, 4),
                "top_vendors": _top_counter(v_cnt, s_count, 4),
            }
        )

    # Dossiers per vendor, use case, and industry
    vendor_dossiers = {
        v: _build_group_dossier(
            "vendor",
            v,
            group,
            total,
            component_layers,
            extra={
                "category": VENDOR_CATEGORY_MAP.get(v, ("Enterprise & Industry", ""))[0],
                "domain": VENDOR_CATEGORY_MAP.get(v, ("Enterprise & Industry", ""))[1],
                "logo": logo_map.get(v, f"{slugify(v)}.png"),
            },
        )
        for v, group in sorted(by_vendor.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    }

    use_case_dossiers = {
        uc: _build_group_dossier("use_case", uc, group, total, component_layers)
        for uc, group in sorted(by_use_case.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    }

    industry_dossiers = {
        ind: _build_group_dossier("industry", ind, group, total, component_layers)
        for ind, group in sorted(by_industry.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    }

    quantified_total = sum(1 for r in live_records if has_quantified_impact(r))
    arch_total = sum(1 for r in live_records if r.get("solution_components"))
    flow_total = sum(1 for r in live_records if r.get("data_flow"))
    integ_total = sum(1 for r in live_records if r.get("integration_points"))

    return {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "summary": {
            "total_records": total,
            "total_vendors": len(by_vendor),
            "total_industries": len(by_industry),
            "total_use_cases": len(by_use_case),
            "total_unique_products": len(product_counter),
            "total_solution_components": total_components,
            "total_quantified_metrics": total_metrics,
            "quantified_impact_count": quantified_total,
            "quantified_impact_rate": round(quantified_total / denom, 4),
            "architecture_coverage_count": arch_total,
            "architecture_coverage_rate": round(arch_total / denom, 4),
            "data_flow_coverage_count": flow_total,
            "data_flow_coverage_rate": round(flow_total / denom, 4),
            "integration_coverage_count": integ_total,
            "integration_coverage_rate": round(integ_total / denom, 4),
            "avg_value_score": round(sum(float(r.get("value_score") or 0) for r in live_records) / denom, 1),
            "avg_confidence_score": round(sum(float(r.get("confidence_score") or 0) for r in live_records) / denom, 2),
        },
        "architecture_layers": architecture_layers,
        "product_ecosystem": {
            "top_products": top_products,
            "co_occurring_pairs": co_occurring_pairs,
            "top_integrations": _top_counter(integration_counter, total, 20),
        },
        "quantified_roi_benchmarks": roi_benchmarks,
        "geography_and_scale": {
            "macro_regions": macro_regions,
            "top_countries": top_countries,
            "company_sizes": company_sizes,
        },
        "vendor_dossiers": vendor_dossiers,
        "use_case_dossiers": use_case_dossiers,
        "industry_dossiers": industry_dossiers,
    }


def generate_analytics_file(
    input_path: Path = DEFAULT_EXPORT_PATH,
    output_path: Path = DEFAULT_ANALYTICS_PATH,
    taxonomy_path: Path = TAXONOMY_PATH,
    sync_logos: bool = True,
) -> dict[str, Any]:
    records = read_json(input_path)
    taxonomy = read_json(taxonomy_path)
    payload = build_analytics(records, taxonomy, sync_logos=sync_logos)
    write_json(output_path, payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Build granular multi-dimensional use-case analytics.")
    parser.add_argument("--input", type=Path, default=DEFAULT_EXPORT_PATH, help="Exported case-studies JSON path.")
    parser.add_argument("--output", type=Path, default=DEFAULT_ANALYTICS_PATH, help="Output analytics JSON path.")
    parser.add_argument("--no-logo-sync", action="store_true", help="Skip vendor logo check/download.")
    args = parser.parse_args()
    payload = generate_analytics_file(
        input_path=args.input,
        output_path=args.output,
        sync_logos=not args.no_logo_sync,
    )
    summary = payload["summary"]
    print(
        f"Built granular analytics for {summary['total_records']} records "
        f"({summary['total_vendors']} vendors, {summary['total_unique_products']} products, "
        f"{summary['total_solution_components']} components) -> {args.output}"
    )


if __name__ == "__main__":
    main()
