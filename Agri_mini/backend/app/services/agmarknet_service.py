import os
import requests
from typing import Dict, Any, List, Optional
from app.config import settings


class AgmarknetError(Exception):
    """Base exception for Agmarknet / data.gov.in acquisition errors."""
    pass


class AgmarknetApiKeyMissingError(AgmarknetError):
    """Raised when DATA_GOV_IN_API_KEY is not configured."""
    pass


class AgmarknetAPIError(AgmarknetError):
    """Raised when the external API returns a non-200 response or network error."""
    pass


class AgmarknetDataService:
    """Service to fetch and normalize daily agricultural market data from data.gov.in (Agmarknet)."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        resource_id: Optional[str] = None,
        timeout: int = 15,
    ):
        self.api_key = api_key or os.getenv("DATA_GOV_IN_API_KEY") or settings.DATA_GOV_IN_API_KEY
        self.base_url = base_url or settings.DATA_GOV_IN_BASE_URL
        self.resource_id = resource_id or settings.DATA_GOV_IN_RESOURCE_ID
        self.timeout = timeout

    def _get_api_key(self) -> str:
        """Validates that an API key is available."""
        key = self.api_key or os.getenv("DATA_GOV_IN_API_KEY") or settings.DATA_GOV_IN_API_KEY
        if not key or not key.strip():
            raise AgmarknetApiKeyMissingError(
                "DATA_GOV_IN_API_KEY is not configured.\n"
                "To obtain an API key:\n"
                "1. Register/Login at https://data.gov.in\n"
                "2. Go to 'My Account' -> 'API Key' to generate your key.\n"
                "3. Add DATA_GOV_IN_API_KEY=your_key_here to your .env file or environment."
            )
        return key.strip()

    @property
    def endpoint_url(self) -> str:
        """Constructs the full API endpoint URL for the resource."""
        return f"{self.base_url.rstrip('/')}/{self.resource_id}"

    def fetch_market_prices(
        self,
        commodity: Optional[str] = None,
        state: Optional[str] = None,
        district: Optional[str] = None,
        market: Optional[str] = None,
        limit: int = 10,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """
        Fetches and normalizes market price records from data.gov.in.

        Parameters:
            commodity: Filter by commodity name (e.g. 'Tomato', 'Onion', 'Potato')
            state: Filter by state name (e.g. 'Maharashtra', 'Karnataka')
            district: Filter by district name (e.g. 'Pune', 'Nashik')
            market: Filter by market/mandi name (e.g. 'Pune', 'Lasalgaon')
            limit: Number of records to return (default: 10)
            offset: Record offset for pagination (default: 0)

        Returns:
            Dict containing:
                - status: 'success'
                - total_records: int
                - returned_count: int
                - limit: int
                - offset: int
                - records: List[Dict] with normalized fields
        """
        api_key = self._get_api_key()

        params: Dict[str, Any] = {
            "api-key": api_key,
            "format": "json",
            "limit": limit,
            "offset": offset,
        }

        if commodity and commodity.strip():
            params["filters[commodity]"] = commodity.strip()
        if state and state.strip():
            params["filters[state]"] = state.strip()
        if district and district.strip():
            params["filters[district]"] = district.strip()
        if market and market.strip():
            params["filters[market]"] = market.strip()

        try:
            response = requests.get(
                self.endpoint_url,
                params=params,
                timeout=self.timeout,
                headers={"Accept": "application/json", "User-Agent": "AgriMiniProject/1.0"}
            )
        except requests.exceptions.Timeout:
            raise AgmarknetAPIError(f"Request to data.gov.in timed out after {self.timeout} seconds.")
        except requests.exceptions.ConnectionError as e:
            raise AgmarknetAPIError(f"Connection error connecting to data.gov.in: {e}")
        except requests.exceptions.RequestException as e:
            raise AgmarknetAPIError(f"Network error during data.gov.in request: {e}")

        # Check HTTP Status Code
        if response.status_code != 200:
            error_detail = response.text[:200] if response.text else "No response body"
            if response.status_code == 401 or response.status_code == 403:
                raise AgmarknetAPIError(
                    f"Authentication failed (HTTP {response.status_code}). "
                    f"Please verify that DATA_GOV_IN_API_KEY is valid. Server response: {error_detail}"
                )
            raise AgmarknetAPIError(
                f"data.gov.in API returned HTTP {response.status_code}: {error_detail}"
            )

        # Parse JSON response
        try:
            raw_data = response.json()
        except ValueError as e:
            raise AgmarknetAPIError(
                f"Failed to parse JSON response from data.gov.in: {e}. Raw content: {response.text[:200]}"
            )

        if not isinstance(raw_data, dict):
            raise AgmarknetAPIError(
                f"Unexpected response structure: expected JSON object, got {type(raw_data).__name__}"
            )

        # Extract records list
        raw_records = raw_data.get("records", [])
        if not isinstance(raw_records, list):
            raw_records = []

        total_count = raw_data.get("total", len(raw_records))
        try:
            total_count = int(total_count)
        except (ValueError, TypeError):
            total_count = len(raw_records)

        # Normalize records
        normalized_records = [self._normalize_record(rec) for rec in raw_records]

        return {
            "status": "success",
            "resource_id": self.resource_id,
            "total_records": total_count,
            "returned_count": len(normalized_records),
            "limit": limit,
            "offset": offset,
            "records": normalized_records,
        }

    def _normalize_record(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """Normalizes a raw data.gov.in record into standard typed fields."""
        def safe_float(val: Any) -> Optional[float]:
            if val is None:
                return None
            try:
                # Remove any stray commas or currency symbols if present
                clean_val = str(val).replace(",", "").strip()
                return float(clean_val)
            except (ValueError, TypeError):
                return None

        def safe_str(val: Any) -> str:
            return str(val).strip() if val is not None else ""

        return {
            "state": safe_str(raw.get("state")),
            "district": safe_str(raw.get("district")),
            "market": safe_str(raw.get("market")),
            "commodity": safe_str(raw.get("commodity")),
            "variety": safe_str(raw.get("variety")),
            "arrival_date": safe_str(raw.get("arrival_date")),
            "min_price": safe_float(raw.get("min_price")),
            "max_price": safe_float(raw.get("max_price")),
            "modal_price": safe_float(raw.get("modal_price")),
        }
