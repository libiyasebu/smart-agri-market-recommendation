import pytest
from unittest.mock import patch, MagicMock
from app.services.agmarknet_service import (
    AgmarknetDataService,
    AgmarknetApiKeyMissingError,
    AgmarknetAPIError,
)


def test_missing_api_key_raises_error():
    service = AgmarknetDataService(api_key="")
    with patch("os.getenv", return_value=""), patch("app.services.agmarknet_service.settings.DATA_GOV_IN_API_KEY", ""):
        with pytest.raises(AgmarknetApiKeyMissingError) as exc_info:
            service.fetch_market_prices(commodity="Tomato")
        assert "DATA_GOV_IN_API_KEY is not configured" in str(exc_info.value)


def test_successful_data_fetch_and_normalization():
    mock_response_data = {
        "status": "ok",
        "total": 1500,
        "count": 2,
        "records": [
            {
                "state": "Maharashtra",
                "district": "Pune",
                "market": "Pune",
                "commodity": "Tomato",
                "variety": "Local",
                "arrival_date": "24/08/2026",
                "min_price": "1800",
                "max_price": "2600",
                "modal_price": "2200",
            },
            {
                "state": "Maharashtra",
                "district": "Nashik",
                "market": "Lasalgaon",
                "commodity": "Onion",
                "variety": "Red",
                "arrival_date": "24/08/2026",
                "min_price": "1,500.5",
                "max_price": "2,100.0",
                "modal_price": "1,850.0",
            }
        ]
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_response_data

    service = AgmarknetDataService(api_key="test_dummy_key_12345")

    with patch("requests.get", return_value=mock_resp) as mock_get:
        result = service.fetch_market_prices(
            commodity="Tomato",
            state="Maharashtra",
            limit=2
        )

        assert result["status"] == "success"
        assert result["total_records"] == 1500
        assert result["returned_count"] == 2
        assert len(result["records"]) == 2

        # Verify Record 1
        rec1 = result["records"][0]
        assert rec1["state"] == "Maharashtra"
        assert rec1["district"] == "Pune"
        assert rec1["market"] == "Pune"
        assert rec1["commodity"] == "Tomato"
        assert rec1["variety"] == "Local"
        assert rec1["arrival_date"] == "24/08/2026"
        assert rec1["min_price"] == 1800.0
        assert rec1["max_price"] == 2600.0
        assert rec1["modal_price"] == 2200.0

        # Verify Record 2 (comma handling)
        rec2 = result["records"][1]
        assert rec2["min_price"] == 1500.5
        assert rec2["max_price"] == 2100.0
        assert rec2["modal_price"] == 1850.0

        # Check call arguments
        mock_get.assert_called_once()
        args, kwargs = mock_get.call_args
        assert kwargs["params"]["api-key"] == "test_dummy_key_12345"
        assert kwargs["params"]["filters[commodity]"] == "Tomato"
        assert kwargs["params"]["filters[state]"] == "Maharashtra"


def test_http_401_unauthorized_error():
    mock_resp = MagicMock()
    mock_resp.status_code = 401
    mock_resp.text = "Invalid API Key"

    service = AgmarknetDataService(api_key="invalid_key")

    with patch("requests.get", return_value=mock_resp):
        with pytest.raises(AgmarknetAPIError) as exc_info:
            service.fetch_market_prices()
        assert "Authentication failed" in str(exc_info.value)


def test_safe_normalization_with_none_and_missing_fields():
    service = AgmarknetDataService(api_key="test_dummy_key")
    raw_record = {
        "state": "Karnataka",
        "commodity": "Potato",
        "min_price": None,
        "modal_price": "invalid_number",
    }
    normalized = service._normalize_record(raw_record)
    assert normalized["state"] == "Karnataka"
    assert normalized["district"] == ""
    assert normalized["market"] == ""
    assert normalized["commodity"] == "Potato"
    assert normalized["min_price"] is None
    assert normalized["max_price"] is None
    assert normalized["modal_price"] is None
