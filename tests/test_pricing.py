from unittest.mock import MagicMock, patch
from pathlib import Path
import json
import pytest
from karpenter_cost_attribution.pricing import (
    get_hourly_rate,
    load_cache,
    save_cache,
    is_cache_expired,
    init_cache,
    flush_cache,
    _CACHE,
    CACHE_FILE
)

@pytest.fixture(autouse=True)
def clean_cache_state():
    """Reset global cache state before and after each test."""
    import karpenter_cost_attribution.pricing as pricing
    pricing._CACHE = None
    pricing._CACHE_MODIFIED = False
    
    # Mock CACHE_FILE path to a temporary file if needed, or mock reading/writing
    with patch("karpenter_cost_attribution.pricing.CACHE_FILE") as mock_cache_file:
        yield mock_cache_file

def test_is_cache_expired():
    from datetime import datetime, timedelta, timezone
    
    # Not expired (e.g., 5 hours ago)
    recent_time = (datetime.now(timezone.utc) - timedelta(hours=5)).isoformat()
    assert is_cache_expired(recent_time) is False

    # Expired (e.g., 25 hours ago)
    old_time = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
    assert is_cache_expired(old_time) is True

    # Invalid string should be expired
    assert is_cache_expired("invalid-date-format") is True
    assert is_cache_expired("") is True

@patch("karpenter_cost_attribution.pricing.boto3.Session")
def test_get_hourly_rate_fallback_and_cache(mock_session_cls):
    # Mock AWS pricing/ec2 client calls to return None (trigger fallback)
    mock_session = MagicMock()
    mock_session_cls.return_value = mock_session
    mock_pricing_client = MagicMock()
    mock_ec2_client = MagicMock()
    
    def get_client(service, *args, **kwargs):
        if service == "pricing":
            return mock_pricing_client
        if service == "ec2":
            return mock_ec2_client
        return MagicMock()
    
    mock_session.client.side_effect = get_client
    mock_pricing_client.get_products.return_value = {"PriceList": []}
    mock_ec2_client.describe_spot_price_history.return_value = {"SpotPriceHistory": []}

    # First call with unknown instance type should use placeholder fallback (0.10)
    rate = get_hourly_rate("t3.medium", "on-demand", region="us-east-1")
    assert rate == 0.10

    # Call with a fallback instance type should return fallback rate
    rate = get_hourly_rate("m5.large", "on-demand", region="us-east-1")
    assert rate == 0.096

    # Call with spot on fallback instance type should apply 70% discount heuristic (0.096 * 0.30 = 0.0288)
    rate = get_hourly_rate("m5.large", "spot", region="us-east-1")
    assert rate == 0.0288

@patch("karpenter_cost_attribution.pricing.boto3.Session")
def test_get_hourly_rate_live_pricing_mock(mock_session_cls):
    mock_session = MagicMock()
    mock_session_cls.return_value = mock_session
    mock_pricing_client = MagicMock()
    mock_ec2_client = MagicMock()
    
    def get_client(service, *args, **kwargs):
        if service == "pricing":
            return mock_pricing_client
        if service == "ec2":
            return mock_ec2_client
        return MagicMock()
    
    mock_session.client.side_effect = get_client
    
    # Mock Pricing API output
    mock_pricing_client.get_products.return_value = {
        "PriceList": [
            json.dumps({
                "terms": {
                    "OnDemand": {
                        "some_offer_id": {
                            "priceDimensions": {
                                "some_dimension_id": {
                                    "pricePerUnit": {
                                        "USD": "0.15"
                                    }
                                }
                            }
                        }
                    }
                }
            })
        ]
    }
    
    # Mock EC2 Spot API output
    mock_ec2_client.describe_spot_price_history.return_value = {
        "SpotPriceHistory": [
            {"SpotPrice": "0.045"}
        ]
    }

    # Test live On-Demand lookup
    rate = get_hourly_rate("custom.large", "on-demand", region="us-east-1", refresh_cache=True)
    assert rate == 0.15
    
    # Test live Spot lookup
    rate = get_hourly_rate("custom.large", "spot", region="us-east-1")
    assert rate == 0.045
