"""Per-instance-type hourly cost lookup.

Uses a small static fallback table for common instance types so the tool
is usable offline/in tests; falls back to the live Pricing API otherwise.
"""
from __future__ import annotations

import json

import boto3

# Fallback on-demand hourly rates (us-east-1, illustrative only).
# TODO: replace with a live pull from the Pricing API index on first run
# and cache it locally instead of hardcoding.
_FALLBACK_RATES: dict[str, float] = {
    "m5.large": 0.096,
    "m5.xlarge": 0.192,
    "c6g.large": 0.068,
    "c6g.xlarge": 0.136,
    "r6g.large": 0.1008,
}


def get_hourly_rate(instance_type: str, capacity_type: str = "on-demand", region: str = "us-east-1") -> float:
    """Return the hourly rate for an instance type / capacity type.

    Spot pricing is approximated as a flat 70% discount off on-demand when
    live spot pricing isn't fetched — this is intentionally rough for v0.1.
    """
    base_rate = _FALLBACK_RATES.get(instance_type)

    if base_rate is None:
        base_rate = _fetch_from_pricing_api(instance_type, region)

    if capacity_type == "spot":
        return round(base_rate * 0.30, 4)
    return base_rate


def _fetch_from_pricing_api(instance_type: str, region: str) -> float:
    """Live fallback for instance types not in the static table.

    TODO: this is a stub — the AWS Pricing API's filter/response shape is
    verbose; wire up the full `get_products` call with proper filters
    (operatingSystem=Linux, tenancy=Shared, preInstalledSw=NA, etc.)
    before relying on this in production.
    """
    client = boto3.client("pricing", region_name="us-east-1")  # Pricing API is us-east-1 only
    _ = client  # placeholder until full filter logic is implemented
    return 0.10  # conservative placeholder rate
