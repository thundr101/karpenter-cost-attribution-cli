"""Per-instance-type hourly cost lookup.

Uses a local cache (~/.karpenter-cost-attribution/pricing_cache.json) and queries
the live AWS Pricing API (for On-Demand rates) and EC2 API (for Spot rates),
falling back to a static lookup or heuristic when offline or unauthorized.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
from typing import Any

import boto3

CACHE_DIR = Path.home() / ".karpenter-cost-attribution"
CACHE_FILE = CACHE_DIR / "pricing_cache.json"

# Fallback on-demand hourly rates (us-east-1, illustrative only).
_FALLBACK_RATES: dict[str, float] = {
    "m5.large": 0.096,
    "m5.xlarge": 0.192,
    "c6g.large": 0.068,
    "c6g.xlarge": 0.136,
    "r6g.large": 0.1008,
}

_REGION_TO_LOCATION = {
    "us-east-1": "US East (N. Virginia)",
    "us-east-2": "US East (Ohio)",
    "us-west-1": "US West (N. California)",
    "us-west-2": "US West (Oregon)",
    "eu-west-1": "EU (Ireland)",
    "eu-west-2": "EU (London)",
    "eu-central-1": "EU (Frankfurt)",
    "ap-southeast-1": "Asia Pacific (Singapore)",
    "ap-southeast-2": "Asia Pacific (Sydney)",
    "ap-northeast-1": "Asia Pacific (Tokyo)",
}

_CACHE: dict[str, Any] | None = None
_CACHE_MODIFIED = False


def load_cache() -> dict[str, Any]:
    """Load caching data from the user home directory."""
    if not CACHE_FILE.exists():
        return {"last_updated": "", "on_demand": {}, "spot": {}}
    try:
        with open(CACHE_FILE, "r") as f:
            data = json.load(f)
            if not isinstance(data, dict):
                return {"last_updated": "", "on_demand": {}, "spot": {}}
            return {
                "last_updated": data.get("last_updated", ""),
                "on_demand": data.get("on_demand", {}),
                "spot": data.get("spot", {}),
            }
    except Exception:
        return {"last_updated": "", "on_demand": {}, "spot": {}}


def save_cache(cache_data: dict[str, Any]) -> None:
    """Save caching data to the user home directory."""
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        with open(CACHE_FILE, "w") as f:
            json.dump(cache_data, f, indent=2)
    except Exception:
        pass


def is_cache_expired(last_updated_str: str) -> bool:
    """Check if the cache has expired (TTL is 24 hours)."""
    if not last_updated_str:
        return True
    try:
        last_updated = datetime.fromisoformat(last_updated_str)
        now = datetime.now(last_updated.tzinfo) if last_updated.tzinfo else datetime.now()
        return now - last_updated > timedelta(hours=24)
    except Exception:
        return True


def init_cache(refresh_cache: bool = False) -> None:
    """Initialize the global in-memory pricing cache."""
    global _CACHE, _CACHE_MODIFIED
    if _CACHE is not None and not refresh_cache:
        return

    _CACHE = load_cache()
    if refresh_cache or is_cache_expired(_CACHE.get("last_updated", "")):
        _CACHE["on_demand"] = {}
        _CACHE["spot"] = {}
        _CACHE["last_updated"] = datetime.now(timezone.utc).isoformat()
        _CACHE_MODIFIED = True



def flush_cache() -> None:
    """Flush the cache back to the disk if it has changed."""
    global _CACHE, _CACHE_MODIFIED
    if _CACHE_MODIFIED and _CACHE is not None:
        save_cache(_CACHE)
        _CACHE_MODIFIED = False


def get_hourly_rate(
    instance_type: str,
    capacity_type: str = "on-demand",
    region: str = "us-east-1",
    profile: str | None = None,
    refresh_cache: bool = False,
) -> float:
    """Return the hourly rate for an instance type / capacity type.

    Utilizes the cached results if fresh, otherwise fetches live pricing from AWS APIs.
    """
    global _CACHE, _CACHE_MODIFIED
    init_cache(refresh_cache=refresh_cache)

    key = f"{region}:{instance_type}"

    # Try Cache first
    if _CACHE is not None:
        if capacity_type == "spot" and key in _CACHE["spot"]:
            return float(_CACHE["spot"][key])
        elif capacity_type == "on-demand" and key in _CACHE["on_demand"]:
            return float(_CACHE["on_demand"][key])

    # Establish AWS Session
    try:
        session = boto3.Session(profile_name=profile, region_name=region)
    except Exception:
        session = boto3.Session(region_name=region)

    # Fetch On-Demand rate first if not in cache
    on_demand_rate = None
    if _CACHE is not None and key in _CACHE["on_demand"]:
        on_demand_rate = float(_CACHE["on_demand"][key])
    else:
        on_demand_rate = _fetch_from_pricing_api(instance_type, region, session)
        if on_demand_rate is not None and _CACHE is not None:
            _CACHE["on_demand"][key] = on_demand_rate
            _CACHE_MODIFIED = True

    # Ultimate fallback if pricing lookup fails entirely
    if on_demand_rate is None:
        on_demand_rate = _FALLBACK_RATES.get(instance_type, 0.10)

    # Handle Spot capacity type
    if capacity_type == "spot":
        spot_rate = _fetch_spot_price(instance_type, region, session)
        if spot_rate is not None:
            if _CACHE is not None:
                _CACHE["spot"][key] = spot_rate
                _CACHE_MODIFIED = True
            rate = spot_rate
        else:
            # Fall back to 70% off heuristic
            rate = round(on_demand_rate * 0.30, 4)
    else:
        rate = on_demand_rate

    return rate


def _fetch_from_pricing_api(instance_type: str, region: str, session: boto3.Session) -> float | None:
    """Live fallback for instance types. Fetches on-demand rate from AWS Pricing API."""
    try:
        # AWS Pricing API is only available in us-east-1 endpoint
        client = session.client("pricing", region_name="us-east-1")

        filters = [
            {"Type": "TERM_MATCH", "Field": "instanceType", "Value": instance_type},
            {"Type": "TERM_MATCH", "Field": "operatingSystem", "Value": "Linux"},
            {"Type": "TERM_MATCH", "Field": "tenancy", "Value": "Shared"},
            {"Type": "TERM_MATCH", "Field": "preInstalledSw", "Value": "NA"},
            {"Type": "TERM_MATCH", "Field": "capacitystatus", "Value": "Used"},
        ]

        # Use regionCode if standard, or try regionCode filter
        filters.append({"Type": "TERM_MATCH", "Field": "regionCode", "Value": region})

        response = client.get_products(
            ServiceCode="AmazonEC2",
            Filters=filters,
        )

        price_list = response.get("PriceList", [])
        if not price_list and region in _REGION_TO_LOCATION:
            # Fallback filter utilizing location name
            location_filters = [f for f in filters if f["Field"] != "regionCode"]
            location_filters.append(
                {"Type": "TERM_MATCH", "Field": "location", "Value": _REGION_TO_LOCATION[region]}
            )
            response = client.get_products(
                ServiceCode="AmazonEC2",
                Filters=location_filters,
            )
            price_list = response.get("PriceList", [])

        if not price_list:
            return None

        for price_str in price_list:
            price_json = json.loads(price_str)
            terms = price_json.get("terms", {})
            on_demand = terms.get("OnDemand", {})
            for offer in on_demand.values():
                price_dimensions = offer.get("priceDimensions", {})
                for dim in price_dimensions.values():
                    price_per_unit = dim.get("pricePerUnit", {})
                    if "USD" in price_per_unit:
                        return float(price_per_unit["USD"])
    except Exception:
        pass
    return None


def _fetch_spot_price(instance_type: str, region: str, session: boto3.Session) -> float | None:
    """Fetch current spot price from EC2 describe_spot_price_history API."""
    try:
        client = session.client("ec2", region_name=region)
        response = client.describe_spot_price_history(
            InstanceTypes=[instance_type],
            ProductDescriptions=["Linux/UNIX", "Linux/UNIX (Amazon VPC)"],
            MaxResults=1,
        )
        history = response.get("SpotPriceHistory", [])
        if history:
            return float(history[0]["SpotPrice"])
    except Exception:
        pass
    return None

