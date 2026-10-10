import os
import requests
from typing import Dict, Any, List, Optional
from app.config import settings


class FAOSTATError(Exception):
    """Base exception for FAOSTAT data acquisition errors."""
    pass


class FAOSTATItemNotFoundError(FAOSTATError):
    """Raised when an unsupported or unknown crop/item is requested."""
    pass


class FAOSTATAPIError(FAOSTATError):
    """Raised when the live FAOSTAT API returns an HTTP error, times out, or fails."""
    pass


# Official FAO Item Code Mappings (Crops and Livestock Domain QCL)
FAO_ITEM_MAP: Dict[str, Dict[str, Any]] = {
    "tomato": {"code": "388", "fao_name": "Tomatoes"},
    "tomatoes": {"code": "388", "fao_name": "Tomatoes"},
    "onion": {"code": "403", "fao_name": "Onions, dry"},
    "onions": {"code": "403", "fao_name": "Onions, dry"},
    "onions, dry": {"code": "403", "fao_name": "Onions, dry"},
    "potato": {"code": "116", "fao_name": "Potatoes"},
    "potatoes": {"code": "116", "fao_name": "Potatoes"},
    "wheat": {"code": "15", "fao_name": "Wheat"},
    "rice": {"code": "27", "fao_name": "Rice, paddy"},
}

# Official FAO Element Code Mappings (QCL Domain)
FAO_ELEMENT_MAP: Dict[str, Dict[str, Any]] = {
    "production": {"code": "5510", "fao_name": "Production", "default_unit": "t"},
    "yield": {"code": "5412", "fao_name": "Yield", "default_unit": "hg/ha"},
    "area harvested": {"code": "5312", "fao_name": "Area harvested", "default_unit": "ha"},
    "area": {"code": "5312", "fao_name": "Area harvested", "default_unit": "ha"},
}

# Verified official FAOSTAT macro indicators snapshot for India (Area: India, Code: 100)
# Published by FAO UN (Domain QCL - Crops & Livestock Products)
OFFICIAL_FAOSTAT_INDIA_SNAPSHOT: List[Dict[str, Any]] = [
    # Tomatoes (Item Code: 388)
    {"Area": "India", "Area Code": 100, "Item": "Tomatoes", "Item Code": 388, "Element": "Production", "Element Code": 5510, "Year": 2023, "Unit": "t", "Value": 21181000.0, "Flag": "E", "Flag Description": "Estimated value"},
    {"Area": "India", "Area Code": 100, "Item": "Tomatoes", "Item Code": 388, "Element": "Production", "Element Code": 5510, "Year": 2022, "Unit": "t", "Value": 20694000.0, "Flag": "A", "Flag Description": "Official figure"},
    {"Area": "India", "Area Code": 100, "Item": "Tomatoes", "Item Code": 388, "Element": "Yield", "Element Code": 5412, "Year": 2022, "Unit": "hg/ha", "Value": 246064.0, "Flag": "A", "Flag Description": "Official figure"},
    {"Area": "India", "Area Code": 100, "Item": "Tomatoes", "Item Code": 388, "Element": "Area harvested", "Element Code": 5312, "Year": 2022, "Unit": "ha", "Value": 841000.0, "Flag": "A", "Flag Description": "Official figure"},
    {"Area": "India", "Area Code": 100, "Item": "Tomatoes", "Item Code": 388, "Element": "Production", "Element Code": 5510, "Year": 2021, "Unit": "t", "Value": 21181000.0, "Flag": "A", "Flag Description": "Official figure"},
    {"Area": "India", "Area Code": 100, "Item": "Tomatoes", "Item Code": 388, "Element": "Production", "Element Code": 5510, "Year": 2020, "Unit": "t", "Value": 20573000.0, "Flag": "A", "Flag Description": "Official figure"},

    # Onions, dry (Item Code: 403)
    {"Area": "India", "Area Code": 100, "Item": "Onions, dry", "Item Code": 403, "Element": "Production", "Element Code": 5510, "Year": 2023, "Unit": "t", "Value": 31273000.0, "Flag": "E", "Flag Description": "Estimated value"},
    {"Area": "India", "Area Code": 100, "Item": "Onions, dry", "Item Code": 403, "Element": "Production", "Element Code": 5510, "Year": 2022, "Unit": "t", "Value": 31690000.0, "Flag": "A", "Flag Description": "Official figure"},
    {"Area": "India", "Area Code": 100, "Item": "Onions, dry", "Item Code": 403, "Element": "Yield", "Element Code": 5412, "Year": 2022, "Unit": "hg/ha", "Value": 166439.0, "Flag": "A", "Flag Description": "Official figure"},
    {"Area": "India", "Area Code": 100, "Item": "Onions, dry", "Item Code": 403, "Element": "Area harvested", "Element Code": 5312, "Year": 2022, "Unit": "ha", "Value": 1904000.0, "Flag": "A", "Flag Description": "Official figure"},
    {"Area": "India", "Area Code": 100, "Item": "Onions, dry", "Item Code": 403, "Element": "Production", "Element Code": 5510, "Year": 2021, "Unit": "t", "Value": 26641000.0, "Flag": "A", "Flag Description": "Official figure"},

    # Potatoes (Item Code: 116)
    {"Area": "India", "Area Code": 100, "Item": "Potatoes", "Item Code": 116, "Element": "Production", "Element Code": 5510, "Year": 2023, "Unit": "t", "Value": 56100000.0, "Flag": "E", "Flag Description": "Estimated value"},
    {"Area": "India", "Area Code": 100, "Item": "Potatoes", "Item Code": 116, "Element": "Production", "Element Code": 5510, "Year": 2022, "Unit": "t", "Value": 53576000.0, "Flag": "A", "Flag Description": "Official figure"},
    {"Area": "India", "Area Code": 100, "Item": "Potatoes", "Item Code": 116, "Element": "Yield", "Element Code": 5412, "Year": 2022, "Unit": "hg/ha", "Value": 243527.0, "Flag": "A", "Flag Description": "Official figure"},
    {"Area": "India", "Area Code": 100, "Item": "Potatoes", "Item Code": 116, "Element": "Area harvested", "Element Code": 5312, "Year": 2022, "Unit": "ha", "Value": 2200000.0, "Flag": "A", "Flag Description": "Official figure"},
    {"Area": "India", "Area Code": 100, "Item": "Potatoes", "Item Code": 116, "Element": "Production", "Element Code": 5510, "Year": 2021, "Unit": "t", "Value": 54230000.0, "Flag": "A", "Flag Description": "Official figure"},

    # Wheat (Item Code: 15)
    {"Area": "India", "Area Code": 100, "Item": "Wheat", "Item Code": 15, "Element": "Production", "Element Code": 5510, "Year": 2022, "Unit": "t", "Value": 107742000.0, "Flag": "A", "Flag Description": "Official figure"},
    {"Area": "India", "Area Code": 100, "Item": "Wheat", "Item Code": 15, "Element": "Yield", "Element Code": 5412, "Year": 2022, "Unit": "hg/ha", "Value": 35313.0, "Flag": "A", "Flag Description": "Official figure"},

    # Rice, paddy (Item Code: 27)
    {"Area": "India", "Area Code": 100, "Item": "Rice, paddy", "Item Code": 27, "Element": "Production", "Element Code": 5510, "Year": 2022, "Unit": "t", "Value": 196245000.0, "Flag": "A", "Flag Description": "Official figure"},
    {"Area": "India", "Area Code": 100, "Item": "Rice, paddy", "Item Code": 27, "Element": "Yield", "Element Code": 5412, "Year": 2022, "Unit": "hg/ha", "Value": 42300.0, "Flag": "A", "Flag Description": "Official figure"},
]


class FAOSTATDataService:
    """Service to fetch, normalize, and inspect macro-level agricultural indicators from FAOSTAT."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        default_domain: str = "QCL",
        default_area_code: str = "100",  # 100 = India
        token: Optional[str] = None,
        timeout: int = 15,
    ):
        self.base_url = base_url or settings.FAOSTAT_BASE_URL
        self.default_domain = default_domain or settings.FAOSTAT_DEFAULT_DOMAIN
        self.default_area_code = default_area_code or settings.FAOSTAT_DEFAULT_AREA_CODE
        self.token = token or os.getenv("FAOSTAT_API_KEY") or os.getenv("FAOSTAT_TOKEN") or ""
        self.timeout = timeout

    @property
    def endpoint_url(self) -> str:
        """Returns the official FAOSTAT API endpoint for the default domain."""
        return f"{self.base_url.rstrip('/')}/{self.default_domain}"

    def resolve_item(self, item_name_or_code: str) -> Dict[str, str]:
        """Resolves user commodity input into standard FAO item code and name."""
        key = item_name_or_code.strip().lower()
        if key in FAO_ITEM_MAP:
            return FAO_ITEM_MAP[key]
        for meta in FAO_ITEM_MAP.values():
            if meta["code"] == item_name_or_code.strip():
                return meta
        raise FAOSTATItemNotFoundError(
            f"Commodity/Item '{item_name_or_code}' is not supported in the FAOSTAT mapper. "
            f"Supported items: {', '.join(sorted(set(v['fao_name'] for v in FAO_ITEM_MAP.values())))}"
        )

    def resolve_element(self, element_name_or_code: str) -> Dict[str, str]:
        """Resolves indicator name into standard FAO element code."""
        key = element_name_or_code.strip().lower()
        if key in FAO_ELEMENT_MAP:
            return FAO_ELEMENT_MAP[key]
        for meta in FAO_ELEMENT_MAP.values():
            if meta["code"] == element_name_or_code.strip():
                return meta
        raise FAOSTATError(
            f"Indicator/Element '{element_name_or_code}' is not supported. "
            f"Supported elements: {', '.join(sorted(set(v['fao_name'] for v in FAO_ELEMENT_MAP.values())))}"
        )

    def fetch_indicators(
        self,
        commodity: Optional[str] = None,
        area_code: Optional[str] = None,
        year: Optional[int] = None,
        element: Optional[str] = None,
        limit: int = 10,
        live_only: bool = False,
    ) -> Dict[str, Any]:
        """
        Fetches macro agricultural indicators for a given commodity and country from FAOSTAT.

        Parameters:
            commodity: Commodity name (e.g. 'Tomato', 'Onion', 'Potato', 'Wheat', 'Rice')
            area_code: FAO area code (default '100' for India)
            year: Specific year filter (e.g. 2022)
            element: Specific indicator filter (e.g. 'Production', 'Yield')
            limit: Maximum records to return
            live_only: If True, disables fallback snapshot and raises an error if live API fails.

        Returns:
            Dict containing:
                - status: 'success'
                - domain: 'QCL'
                - geographic_level: 'National (Country Level - India)'
                - source: str (Exact source name with LIVE / FALLBACK prefix)
                - is_fallback: bool
                - live_error: Optional[str] (error detail if live call failed during fallback)
                - total_records: int
                - records: List[Dict] of normalized records
        """
        target_area = str(area_code or self.default_area_code).strip()
        item_meta = self.resolve_item(commodity) if commodity else None
        element_meta = self.resolve_element(element) if element else None

        # Build official query parameters
        params: Dict[str, Any] = {
            "area": target_area,
            "show_unit": "1",
            "show_flags": "1",
            "output_type": "objects",
            "limit": limit,
        }
        if item_meta:
            params["item"] = item_meta["code"]
        if element_meta:
            params["element"] = element_meta["code"]
        if year:
            params["year"] = str(year)

        headers: Dict[str, str] = {
            "Accept": "application/json",
            "User-Agent": "AgriMiniProject/1.0",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token.strip()}"

        raw_records = []
        source_label = "LIVE API: FAOSTAT (Live API - QCL)"
        is_fallback = False
        live_error_msg: Optional[str] = None

        try:
            response = requests.get(
                self.endpoint_url,
                params=params,
                headers=headers,
                timeout=self.timeout,
            )
            if response.status_code == 200:
                json_data = response.json()
                if isinstance(json_data, dict) and "data" in json_data:
                    raw_records = json_data["data"]
                else:
                    live_error_msg = f"Unexpected JSON response structure (missing 'data' key): {response.text[:200]}"
            else:
                live_error_msg = f"HTTP {response.status_code}: {response.text[:200] if response.text else 'No response body'}"
        except requests.exceptions.Timeout:
            live_error_msg = f"Request to '{self.endpoint_url}' timed out after {self.timeout} seconds."
        except requests.exceptions.ConnectionError as e:
            live_error_msg = f"Connection error reaching '{self.endpoint_url}': {e}"
        except requests.exceptions.RequestException as e:
            live_error_msg = f"Network request error: {e}"
        except Exception as e:
            live_error_msg = f"Unexpected error during live FAOSTAT query: {e}"

        # If live request failed
        if live_error_msg or not raw_records:
            if live_only:
                raise FAOSTATAPIError(
                    f"Live FAOSTAT API query failed against '{self.endpoint_url}'.\n"
                    f"Parameters: {params}\n"
                    f"Error Details: {live_error_msg or 'No records returned from live API.'}"
                )
            
            # Use official benchmark snapshot as fallback
            source_label = "FALLBACK SNAPSHOT: FAOSTAT (Official Benchmark Snapshot - QCL)"
            is_fallback = True
            raw_records = self._query_snapshot(
                target_area_code=target_area,
                item_code=item_meta["code"] if item_meta else None,
                element_code=element_meta["code"] if element_meta else None,
                year=year,
                limit=limit,
            )

        # Normalize records
        normalized = [self._normalize_record(r, source_label) for r in raw_records]

        return {
            "status": "success",
            "domain": self.default_domain,
            "endpoint_tested": self.endpoint_url,
            "request_parameters": params,
            "geographic_level": "National (Country Level - India)",
            "source": source_label,
            "is_fallback": is_fallback,
            "live_error": live_error_msg if is_fallback else None,
            "total_records": len(normalized),
            "records": normalized,
        }

    def _query_snapshot(
        self,
        target_area_code: str,
        item_code: Optional[str],
        element_code: Optional[str],
        year: Optional[int],
        limit: int,
    ) -> List[Dict[str, Any]]:
        """Filters the official FAOSTAT snapshot dataset matching the request parameters."""
        results = []
        for row in OFFICIAL_FAOSTAT_INDIA_SNAPSHOT:
            if target_area_code and str(row.get("Area Code")) != str(target_area_code):
                continue
            if item_code and str(row.get("Item Code")) != str(item_code):
                continue
            if element_code and str(row.get("Element Code")) != str(element_code):
                continue
            if year and row.get("Year") != int(year):
                continue
            results.append(row)
            if len(results) >= limit:
                break
        return results

    def _normalize_record(self, raw: Dict[str, Any], source: str) -> Dict[str, Any]:
        """Normalizes a raw FAOSTAT record dictionary into standardized fields."""
        def safe_float(val: Any) -> Optional[float]:
            if val is None:
                return None
            try:
                return float(str(val).replace(",", "").strip())
            except (ValueError, TypeError):
                return None

        def safe_int(val: Any) -> Optional[int]:
            if val is None:
                return None
            try:
                return int(val)
            except (ValueError, TypeError):
                return None

        def safe_str(val: Any) -> str:
            return str(val).strip() if val is not None else ""

        return {
            "area": safe_str(raw.get("Area") or raw.get("area")),
            "area_code": safe_int(raw.get("Area Code") or raw.get("area_code")),
            "item": safe_str(raw.get("Item") or raw.get("item")),
            "item_code": safe_int(raw.get("Item Code") or raw.get("item_code")),
            "indicator": safe_str(raw.get("Element") or raw.get("element")),
            "indicator_code": safe_int(raw.get("Element Code") or raw.get("element_code")),
            "year": safe_int(raw.get("Year") or raw.get("year")),
            "value": safe_float(raw.get("Value") or raw.get("value")),
            "unit": safe_str(raw.get("Unit") or raw.get("unit")),
            "flag": safe_str(raw.get("Flag") or raw.get("flag")),
            "flag_description": safe_str(raw.get("Flag Description") or raw.get("flag_description")),
            "source": source,
        }
