import pytest
from unittest.mock import patch, MagicMock
from app.services.faostat_service import (
    FAOSTATDataService,
    FAOSTATItemNotFoundError,
    FAOSTATAPIError,
    FAOSTATError,
    FAO_ITEM_MAP,
    FAO_ELEMENT_MAP,
)


def test_item_resolution():
    service = FAOSTATDataService()
    tomato = service.resolve_item("Tomato")
    assert tomato["code"] == "388"
    assert tomato["fao_name"] == "Tomatoes"

    onion = service.resolve_item("Onion")
    assert onion["code"] == "403"
    assert onion["fao_name"] == "Onions, dry"

    potato = service.resolve_item("Potato")
    assert potato["code"] == "116"
    assert potato["fao_name"] == "Potatoes"


def test_unsupported_item_raises_error():
    service = FAOSTATDataService()
    with pytest.raises(FAOSTATItemNotFoundError) as exc:
        service.resolve_item("DragonFruitNonExistentCrop123")
    assert "is not supported" in str(exc.value)


def test_element_resolution():
    service = FAOSTATDataService()
    prod = service.resolve_element("Production")
    assert prod["code"] == "5510"
    assert prod["fao_name"] == "Production"

    yld = service.resolve_element("Yield")
    assert yld["code"] == "5412"
    assert yld["fao_name"] == "Yield"


def test_successful_faostat_live_api_normalization():
    mock_payload = {
        "data": [
            {
                "Area": "India",
                "Area Code": 100,
                "Item": "Tomatoes",
                "Item Code": 388,
                "Element": "Production",
                "Element Code": 5510,
                "Year": 2022,
                "Unit": "t",
                "Value": 20694000.0,
                "Flag": "A",
                "Flag Description": "Official figure",
            }
        ]
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_payload

    service = FAOSTATDataService()

    with patch("requests.get", return_value=mock_resp):
        result = service.fetch_indicators(commodity="Tomato", year=2022, live_only=True)

        assert result["status"] == "success"
        assert result["domain"] == "QCL"
        assert result["total_records"] == 1
        assert result["is_fallback"] is False
        assert "LIVE API" in result["source"]

        rec = result["records"][0]
        assert rec["area"] == "India"
        assert rec["area_code"] == 100
        assert rec["item"] == "Tomatoes"
        assert rec["item_code"] == 388
        assert rec["indicator"] == "Production"
        assert rec["year"] == 2022
        assert rec["value"] == 20694000.0
        assert rec["unit"] == "t"
        assert rec["flag"] == "A"


def test_live_only_mode_raises_error_on_network_timeout():
    service = FAOSTATDataService()

    # When live_only=True, it must raise FAOSTATAPIError on network error
    with patch("requests.get", side_effect=Exception("Read timed out")):
        with pytest.raises(FAOSTATAPIError) as exc:
            service.fetch_indicators(commodity="Tomato", year=2022, live_only=True)
        assert "Live FAOSTAT API query failed" in str(exc.value)


def test_snapshot_fallback_when_live_only_is_false():
    service = FAOSTATDataService()

    # When live_only=False, it uses fallback snapshot on failure
    with patch("requests.get", side_effect=Exception("Read timed out")):
        result = service.fetch_indicators(commodity="Tomato", year=2022, element="Production", live_only=False)

        assert result["status"] == "success"
        assert result["total_records"] >= 1
        assert result["is_fallback"] is True
        assert "FALLBACK SNAPSHOT" in result["source"]
        assert "Read timed out" in result["live_error"]

        rec = result["records"][0]
        assert rec["area"] == "India"
        assert rec["item"] == "Tomatoes"
        assert rec["indicator"] == "Production"
        assert rec["year"] == 2022
        assert rec["value"] == 20694000.0
        assert rec["unit"] == "t"


def test_fetch_onion_indicators():
    service = FAOSTATDataService()
    result = service.fetch_indicators(commodity="Onion", limit=5, live_only=False)
    assert result["status"] == "success"
    assert result["total_records"] > 0
    items = set(r["item"] for r in result["records"])
    assert "Onions, dry" in items
