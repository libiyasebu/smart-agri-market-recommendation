import math
from datetime import date
from typing import Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.weather import WeatherRecord
from app.services.routing_service import RoutingDataService, RoutingError, InvalidCoordinatesError, NoRouteFoundError, RoutingAPIError
from app.services.weather_service import WeatherDataService, WeatherError, WeatherAPIError
from app.schemas.spoilage import (
    CommodityPerishabilityProfile,
    WeatherMetrics,
    RiskFactorsBreakdown,
    SpoilageEstimateRequest,
    SpoilageEstimateResponse,
)


# -----------------------------------------------------------------------------
# Configured Commodity Perishability Profiles
# -----------------------------------------------------------------------------
# Note: These values represent transparent baseline agro-logistics estimation
# parameters calibrated for non-refrigerated transit. They are project estimation
# heuristics, not laboratory-certified post-harvest standards.
DEFAULT_PERISHABILITY_PROFILES: Dict[str, CommodityPerishabilityProfile] = {
    "tomato": CommodityPerishabilityProfile(
        commodity="tomato",
        display_name="Tomato",
        base_perishability_score=55.0,
        preferred_temp_min_c=12.0,
        preferred_temp_max_c=22.0,
        heat_sensitivity=1.4,
        humidity_sensitivity=1.2,
        transit_time_sensitivity=1.4,
        max_loss_potential_pct=25.0,
    ),
    "onion": CommodityPerishabilityProfile(
        commodity="onion",
        display_name="Onion",
        base_perishability_score=15.0,
        preferred_temp_min_c=5.0,
        preferred_temp_max_c=28.0,
        heat_sensitivity=0.7,
        humidity_sensitivity=1.4,  # High humidity causes fungal rot and premature sprouting
        transit_time_sensitivity=0.5,
        max_loss_potential_pct=10.0,
    ),
    "potato": CommodityPerishabilityProfile(
        commodity="potato",
        display_name="Potato",
        base_perishability_score=12.0,
        preferred_temp_min_c=7.0,
        preferred_temp_max_c=22.0,
        heat_sensitivity=0.8,
        humidity_sensitivity=0.8,
        transit_time_sensitivity=0.5,
        max_loss_potential_pct=8.0,
    ),
    "banana": CommodityPerishabilityProfile(
        commodity="banana",
        display_name="Banana",
        base_perishability_score=50.0,
        preferred_temp_min_c=13.0,  # Below 13°C causes chilling injury
        preferred_temp_max_c=24.0,  # Above 24°C triggers rapid over-ripening & ethylene surge
        heat_sensitivity=1.5,
        humidity_sensitivity=1.3,
        transit_time_sensitivity=1.5,
        max_loss_potential_pct=25.0,
    ),
    "cabbage": CommodityPerishabilityProfile(
        commodity="cabbage",
        display_name="Cabbage",
        base_perishability_score=30.0,
        preferred_temp_min_c=0.0,
        preferred_temp_max_c=18.0,
        heat_sensitivity=1.1,
        humidity_sensitivity=1.0,
        transit_time_sensitivity=1.0,
        max_loss_potential_pct=15.0,
    ),
    "green chilli": CommodityPerishabilityProfile(
        commodity="green chilli",
        display_name="Green Chilli",
        base_perishability_score=40.0,
        preferred_temp_min_c=10.0,
        preferred_temp_max_c=22.0,
        heat_sensitivity=1.2,
        humidity_sensitivity=1.1,
        transit_time_sensitivity=1.2,
        max_loss_potential_pct=20.0,
    ),
}

# Alias mapping for alternate user inputs
COMMODITY_ALIASES: Dict[str, str] = {
    "tomatoes": "tomato",
    "onions": "onion",
    "potatoes": "potato",
    "bananas": "banana",
    "green_chilli": "green chilli",
    "chilli": "green chilli",
    "green chili": "green chilli",
    "chili": "green chilli",
}


class SpoilageService:
    """
    Agricultural spoilage risk and transit loss estimation service.
    Combines commodity physiological perishability with live road transit duration (OSRM)
    and agro-meteorological stress factors (Open-Meteo).
    """

    def __init__(
        self,
        routing_service: Optional[RoutingDataService] = None,
        weather_service: Optional[WeatherDataService] = None,
        profiles: Optional[Dict[str, CommodityPerishabilityProfile]] = None,
    ):
        self.routing_service = routing_service or RoutingDataService()
        self.weather_service = weather_service or WeatherDataService()
        self.profiles = profiles or DEFAULT_PERISHABILITY_PROFILES

    def resolve_commodity_profile(self, commodity_name: str) -> CommodityPerishabilityProfile:
        """Resolves commodity string to a known perishability profile or raises ValueError."""
        cleaned = commodity_name.strip().lower()
        # Check alias
        canonical = COMMODITY_ALIASES.get(cleaned, cleaned)
        if canonical in self.profiles:
            return self.profiles[canonical]
        
        # Substring search
        for key, profile in self.profiles.items():
            if key in canonical or canonical in key:
                return profile

        supported = ", ".join([p.display_name for p in self.profiles.values()])
        raise ValueError(
            f"Unsupported commodity '{commodity_name}'. Supported commodities for spoilage risk estimation are: {supported}"
        )

    # -------------------------------------------------------------------------
    # 1. Pure Calculation Functions (Deterministic & Testable)
    # -------------------------------------------------------------------------

    def calculate_temperature_stress(
        self,
        temp_mean_c: float,
        temp_max_c: float,
        profile: CommodityPerishabilityProfile,
    ) -> float:
        """
        Calculates thermal stress index [0-100] based on deviation from commodity optimal range.
        Includes heat stress above preferred_temp_max_c and chilling stress below preferred_temp_min_c.
        """
        stress = 0.0
        # Heat stress
        if temp_mean_c > profile.preferred_temp_max_c:
            mean_excess = temp_mean_c - profile.preferred_temp_max_c
            max_excess = max(0.0, temp_max_c - profile.preferred_temp_max_c)
            combined_excess = mean_excess + (0.5 * max_excess)
            stress += combined_excess * 4.0 * profile.heat_sensitivity

        # Chilling injury stress (especially for tropical commodities like banana, tomato)
        if temp_mean_c < profile.preferred_temp_min_c:
            chill_defect = profile.preferred_temp_min_c - temp_mean_c
            stress += chill_defect * 3.0

        return round(min(100.0, max(0.0, stress)), 2)

    def calculate_humidity_stress(
        self,
        humidity_pct: float,
        profile: CommodityPerishabilityProfile,
    ) -> float:
        """
        Calculates moisture stress index [0-100].
        Excessive humidity (>80%) accelerates fungal rot/molds; severe dryness (<50%) causes wilting/weight loss.
        """
        stress = 0.0
        if humidity_pct > 80.0:
            excess = (humidity_pct - 80.0) / 20.0  # 0.0 to 1.0
            stress += excess * 100.0 * profile.humidity_sensitivity
        elif humidity_pct < 50.0:
            deficit = (50.0 - humidity_pct) / 50.0  # 0.0 to 1.0
            stress += deficit * 100.0 * profile.humidity_sensitivity

        return round(min(100.0, max(0.0, stress)), 2)

    def calculate_transit_time_stress(
        self,
        duration_minutes: float,
        profile: CommodityPerishabilityProfile,
    ) -> float:
        """
        Calculates duration exposure stress index [0-100].
        Prolonged road transit exponentially compounds physical vibration, respiration, and decay.
        """
        if duration_minutes <= 0.0:
            return 0.0
        transit_hours = duration_minutes / 60.0
        # 1 hour ≈ 12 baseline stress points, scaled by transit sensitivity
        stress = (transit_hours * 12.0) * profile.transit_time_sensitivity
        return round(min(100.0, max(0.0, stress)), 2)

    def calculate_rain_stress(self, precipitation_mm: float) -> float:
        """Calculates wet weather transport stress index [0-100]."""
        if precipitation_mm <= 0.0:
            return 0.0
        # Rain > 5mm adds transit moisture risk
        if precipitation_mm > 5.0:
            stress = min(100.0, ((precipitation_mm - 5.0) / 20.0) * 100.0)
            return round(stress, 2)
        return 0.0

    def classify_risk_level(self, risk_score: float) -> str:
        """Maps continuous risk score [0-100] to standardized categorical level."""
        if risk_score <= 25.0:
            return "LOW"
        elif risk_score <= 50.0:
            return "MODERATE"
        elif risk_score <= 75.0:
            return "HIGH"
        else:
            return "VERY HIGH"

    def estimate_loss_percentage(
        self,
        risk_score: float,
        profile: CommodityPerishabilityProfile,
    ) -> float:
        """
        Derives estimated transit crop loss percentage from risk score and commodity max loss potential.
        Uses a convex non-linear mapping (exponent 1.35) to model post-harvest decay kinetics.
        """
        clamped_score = max(0.0, min(100.0, risk_score))
        loss_fraction = math.pow(clamped_score / 100.0, 1.35)
        loss_pct = loss_fraction * profile.max_loss_potential_pct
        return round(min(100.0, max(0.0, loss_pct)), 2)

    def calculate_spoilage_risk(
        self,
        commodity: str,
        distance_km: float,
        duration_minutes: float,
        temp_mean_c: float,
        temp_max_c: float,
        humidity_pct: float,
        precipitation_mm: float = 0.0,
        origin_name: str = "Origin",
        destination_name: str = "Destination",
        weather_source: str = "database",
        weather_matched: bool = True,
        routing_provider: str = "OSRM (OpenStreetMap)",
    ) -> SpoilageEstimateResponse:
        """
        Pure calculation function producing transparent spoilage risk score, level, and loss percentage.
        """
        if distance_km < 0:
            raise ValueError(f"distance_km cannot be negative ({distance_km})")
        if duration_minutes < 0:
            raise ValueError(f"duration_minutes cannot be negative ({duration_minutes})")
        if not (0.0 <= humidity_pct <= 100.0):
            raise ValueError(f"humidity_pct must be between 0 and 100 ({humidity_pct})")

        profile = self.resolve_commodity_profile(commodity)

        # 1. Stress Factor Computations
        temp_stress = self.calculate_temperature_stress(temp_mean_c, temp_max_c, profile)
        hum_stress = self.calculate_humidity_stress(humidity_pct, profile)
        transit_stress = self.calculate_transit_time_stress(duration_minutes, profile)
        rain_stress = self.calculate_rain_stress(precipitation_mm)
        base_perish = round(profile.base_perishability_score, 2)

        # 2. Weighted Composite Risk Score [0 - 100]
        # Weights: Base Perishability (20%), Temperature (35%), Transit Time (30%), Humidity (10%), Rain (5%)
        raw_score = (
            (0.20 * base_perish)
            + (0.35 * temp_stress)
            + (0.30 * transit_stress)
            + (0.10 * hum_stress)
            + (0.05 * rain_stress)
        )
        risk_score = round(max(0.0, min(100.0, raw_score)), 1)

        # 3. Categorical Level
        risk_level = self.classify_risk_level(risk_score)

        # 4. Expected Loss Percentage
        estimated_spoilage_pct = self.estimate_loss_percentage(risk_score, profile)

        return SpoilageEstimateResponse(
            status="success",
            commodity=profile.display_name,
            origin=origin_name,
            destination=destination_name,
            distance_km=round(distance_km, 2),
            transit_duration_minutes=round(duration_minutes, 2),
            weather=WeatherMetrics(
                temperature_mean_c=round(temp_mean_c, 2),
                temperature_max_c=round(temp_max_c, 2),
                humidity_pct=round(humidity_pct, 2),
                precipitation_mm=round(precipitation_mm, 2),
                source=weather_source,
            ),
            risk_score=risk_score,
            risk_level=risk_level,
            estimated_spoilage_pct=estimated_spoilage_pct,
            risk_factors=RiskFactorsBreakdown(
                base_perishability=base_perish,
                temperature_stress=temp_stress,
                humidity_stress=hum_stress,
                transit_time_stress=transit_stress,
                rain_stress=rain_stress,
            ),
            weather_matched=weather_matched,
            weather_source=weather_source,
            routing_provider=routing_provider,
            estimation_type="weather-and-transit heuristic",
        )

    # -------------------------------------------------------------------------
    # 2. End-to-End Orchestration (Route + Weather + Spoilage)
    # -------------------------------------------------------------------------

    def resolve_weather_data(
        self,
        origin_lat: float,
        origin_lon: float,
        transport_date: date,
        origin_name: Optional[str] = None,
        db: Optional[Session] = None,
    ) -> Tuple[float, float, float, float, str, bool]:
        """
        Resolves agro-weather conditions for the origin location on transport_date.
        Preference order: 1) Stored PostgreSQL record -> 2) Live Open-Meteo API -> 3) Seasonal default fallback.
        """
        # 1. Check PostgreSQL Database if session is available
        if db is not None:
            try:
                # Query by matching location_name or exact coordinates
                query = db.query(WeatherRecord).filter(WeatherRecord.record_date == transport_date)
                if origin_name:
                    loc_keyword = origin_name.split(",")[0].strip().lower()
                    rec = query.filter(func.lower(WeatherRecord.location_name).like(f"%{loc_keyword}%")).first()
                else:
                    rec = None

                if not rec:
                    # Fallback to closest coordinate record on that date
                    rec = query.first()

                if not rec:
                    # Fallback to most recent record prior to transport_date
                    rec = db.query(WeatherRecord).filter(WeatherRecord.record_date <= transport_date).order_by(WeatherRecord.record_date.desc()).first()

                if rec and rec.temp_mean_celsius is not None:
                    t_mean = float(rec.temp_mean_celsius)
                    t_max = float(rec.temp_max_celsius or (t_mean + 4.0))
                    hum = float(rec.humidity_mean_pct or 80.0)
                    rain = float(rec.rain_mm or rec.precipitation_mm or 0.0)
                    return t_mean, t_max, hum, rain, "database", True
            except Exception:
                # Database lookup error; proceed to live API
                pass

        # 2. Check Live Open-Meteo API
        try:
            date_str = transport_date.isoformat()
            w_res = self.weather_service.fetch_weather(
                latitude=origin_lat,
                longitude=origin_lon,
                start_date=date_str,
                end_date=date_str,
            )
            if w_res and w_res.get("daily_forecasts"):
                day_data = w_res["daily_forecasts"][0]
                t_mean = float(day_data.get("temp_mean_celsius") or 28.5)
                t_max = float(day_data.get("temp_max_celsius") or (t_mean + 4.0))
                hum = float(day_data.get("humidity_mean_pct") or 80.0)
                rain = float(day_data.get("rain_mm") or day_data.get("precipitation_mm") or 0.0)
                return t_mean, t_max, hum, rain, "live_api", True
        except (WeatherAPIError, WeatherError, Exception):
            # Live API unavailable; proceed to fallback
            pass

        # 3. Configured Seasonal Default Fallback
        return 28.5, 32.5, 80.0, 0.0, "configured_fallback", False

    def estimate_spoilage_from_coordinates(
        self,
        request: SpoilageEstimateRequest,
        db: Optional[Session] = None,
    ) -> SpoilageEstimateResponse:
        """
        Retrieves actual road driving transit duration from OSRM and weather conditions,
        then executes the transparent spoilage risk calculation.
        """
        # 1. Fetch Driving Route Metrics from OSRM
        route_info = self.routing_service.get_route(
            origin_lat=request.origin_lat,
            origin_lon=request.origin_lon,
            dest_lat=request.destination_lat,
            dest_lon=request.destination_lon,
        )

        distance_km = float(route_info["distance_km"])
        duration_minutes = float(route_info["duration_minutes"])
        provider = str(route_info.get("provider", "OSRM (OpenStreetMap)"))

        # 2. Resolve Agro-Weather Conditions
        t_mean, t_max, hum, rain, w_source, w_matched = self.resolve_weather_data(
            origin_lat=request.origin_lat,
            origin_lon=request.origin_lon,
            transport_date=request.transport_date,
            origin_name=request.origin_name,
            db=db,
        )

        # 3. Apply Optional User Overrides if specified
        if request.temperature_override_c is not None:
            t_mean = float(request.temperature_override_c)
            t_max = t_mean + 4.0
            w_source = "user_override"

        if request.humidity_override_pct is not None:
            hum = float(request.humidity_override_pct)
            w_source = "user_override"

        # 4. Execute Calculation
        return self.calculate_spoilage_risk(
            commodity=request.commodity,
            distance_km=distance_km,
            duration_minutes=duration_minutes,
            temp_mean_c=t_mean,
            temp_max_c=t_max,
            humidity_pct=hum,
            precipitation_mm=rain,
            origin_name=request.origin_name,
            destination_name=request.destination_name,
            weather_source=w_source,
            weather_matched=w_matched,
            routing_provider=provider,
        )
