from datetime import date, datetime
from decimal import Decimal
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert as pg_insert
from app.models import MarketPrice, WeatherRecord, FAOSTATIndicator, RouteRecord


def parse_date_safe(date_val: Any) -> date:
    """Parses various date string formats into standard datetime.date."""
    if isinstance(date_val, datetime):
        return date_val.date()
    if isinstance(date_val, date):
        return date_val
    if not date_val:
        return datetime.now().date()

    date_str = str(date_val).strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Unable to parse arrival date: '{date_val}'")


def to_decimal_safe(val: Any) -> Optional[Decimal]:
    """Safely converts numeric values to Decimal."""
    if val is None or val == "":
        return None
    try:
        clean = str(val).replace(",", "").strip()
        return Decimal(clean)
    except Exception:
        return None


class DataIngestionService:
    """Service to persist normalized Phase 2 data streams into PostgreSQL tables."""

    @staticmethod
    def ingest_market_prices(records: List[Dict[str, Any]], db: Session) -> Dict[str, int]:
        """
        Stores normalized mandi market price records into the 'market_prices' table.
        Uses idempotent upsert based on (state, district, market, commodity, variety, arrival_date).
        """
        if not records:
            return {"inserted": 0, "updated": 0, "total": 0}

        inserted_count = 0
        updated_count = 0

        # Check if database dialect is PostgreSQL
        is_postgres = db.bind.dialect.name == "postgresql" if db.bind else False

        for r in records:
            arr_date = parse_date_safe(r.get("arrival_date"))
            min_p = to_decimal_safe(r.get("min_price"))
            max_p = to_decimal_safe(r.get("max_price"))
            modal_p = to_decimal_safe(r.get("modal_price"))
            variety = r.get("variety") or "Standard"
            source = r.get("source") or "data.gov.in (Agmarknet)"

            if is_postgres:
                stmt = pg_insert(MarketPrice).values(
                    state=r["state"],
                    district=r["district"],
                    market=r["market"],
                    commodity=r["commodity"],
                    variety=variety,
                    arrival_date=arr_date,
                    min_price=min_p,
                    max_price=max_p,
                    modal_price=modal_p,
                    source=source,
                ).on_conflict_do_update(
                    constraint="uq_market_prices_record",
                    set_={
                        "min_price": min_p,
                        "max_price": max_p,
                        "modal_price": modal_p,
                        "source": source,
                    },
                )
                db.execute(stmt)
                inserted_count += 1
            else:
                # Generic fallback for SQLite in-memory test environments
                existing = db.query(MarketPrice).filter_by(
                    state=r["state"],
                    district=r["district"],
                    market=r["market"],
                    commodity=r["commodity"],
                    variety=variety,
                    arrival_date=arr_date,
                ).first()

                if existing:
                    existing.min_price = min_p
                    existing.max_price = max_p
                    existing.modal_price = modal_p
                    existing.source = source
                    updated_count += 1
                else:
                    new_item = MarketPrice(
                        state=r["state"],
                        district=r["district"],
                        market=r["market"],
                        commodity=r["commodity"],
                        variety=variety,
                        arrival_date=arr_date,
                        min_price=min_p,
                        max_price=max_p,
                        modal_price=modal_p,
                        source=source,
                    )
                    db.add(new_item)
                    inserted_count += 1

        db.commit()
        return {
            "inserted": inserted_count,
            "updated": updated_count,
            "total": len(records),
        }

    @staticmethod
    def ingest_weather_data(weather_payload: Dict[str, Any], db: Session, location_name: Optional[str] = None) -> Dict[str, int]:
        """
        Stores normalized daily weather forecasts into the 'weather_records' table.
        Uses idempotent upsert based on (latitude, longitude, record_date).
        """
        forecasts = weather_payload.get("daily_forecasts", [])
        if not forecasts:
            return {"inserted": 0, "updated": 0, "total": 0}

        loc = weather_payload.get("location", {})
        lat = Decimal(str(round(float(loc.get("latitude", 0.0)), 5)))
        lon = Decimal(str(round(float(loc.get("longitude", 0.0)), 5)))
        source = weather_payload.get("source") or "Open-Meteo"

        inserted_count = 0
        updated_count = 0
        is_postgres = db.bind.dialect.name == "postgresql" if db.bind else False

        for f in forecasts:
            rec_date = parse_date_safe(f.get("date"))
            temp_mean = to_decimal_safe(f.get("temp_mean_celsius"))
            temp_min = to_decimal_safe(f.get("temp_min_celsius"))
            temp_max = to_decimal_safe(f.get("temp_max_celsius"))
            humidity = to_decimal_safe(f.get("humidity_mean_pct"))
            precip = to_decimal_safe(f.get("precipitation_mm"))
            rain = to_decimal_safe(f.get("rain_mm"))
            code = f.get("weather_code")
            condition = f.get("weather_condition")

            if is_postgres:
                stmt = pg_insert(WeatherRecord).values(
                    latitude=lat,
                    longitude=lon,
                    location_name=location_name,
                    record_date=rec_date,
                    temp_mean_celsius=temp_mean,
                    temp_min_celsius=temp_min,
                    temp_max_celsius=temp_max,
                    humidity_mean_pct=humidity,
                    precipitation_mm=precip,
                    rain_mm=rain,
                    weather_code=code,
                    weather_condition=condition,
                    source=source,
                ).on_conflict_do_update(
                    constraint="uq_weather_records_loc_date",
                    set_={
                        "temp_mean_celsius": temp_mean,
                        "temp_min_celsius": temp_min,
                        "temp_max_celsius": temp_max,
                        "humidity_mean_pct": humidity,
                        "precipitation_mm": precip,
                        "rain_mm": rain,
                        "weather_code": code,
                        "weather_condition": condition,
                        "source": source,
                    },
                )
                db.execute(stmt)
                inserted_count += 1
            else:
                existing = db.query(WeatherRecord).filter_by(
                    latitude=lat,
                    longitude=lon,
                    record_date=rec_date,
                ).first()

                if existing:
                    existing.temp_mean_celsius = temp_mean
                    existing.temp_min_celsius = temp_min
                    existing.temp_max_celsius = temp_max
                    existing.humidity_mean_pct = humidity
                    existing.precipitation_mm = precip
                    existing.rain_mm = rain
                    existing.weather_code = code
                    existing.weather_condition = condition
                    existing.source = source
                    if location_name:
                        existing.location_name = location_name
                    updated_count += 1
                else:
                    new_item = WeatherRecord(
                        latitude=lat,
                        longitude=lon,
                        location_name=location_name,
                        record_date=rec_date,
                        temp_mean_celsius=temp_mean,
                        temp_min_celsius=temp_min,
                        temp_max_celsius=temp_max,
                        humidity_mean_pct=humidity,
                        precipitation_mm=precip,
                        rain_mm=rain,
                        weather_code=code,
                        weather_condition=condition,
                        source=source,
                    )
                    db.add(new_item)
                    inserted_count += 1

        db.commit()
        return {
            "inserted": inserted_count,
            "updated": updated_count,
            "total": len(forecasts),
        }

    @staticmethod
    def ingest_faostat_indicators(faostat_payload: Dict[str, Any], db: Session) -> Dict[str, int]:
        """
        Stores macro agricultural statistics into the 'faostat_indicators' table.
        Uses idempotent upsert based on (area_code, item_code, indicator_code, year).
        """
        records = faostat_payload.get("records", [])
        if not records:
            return {"inserted": 0, "updated": 0, "total": 0}

        inserted_count = 0
        updated_count = 0
        is_postgres = db.bind.dialect.name == "postgresql" if db.bind else False

        for r in records:
            area = r["area"]
            area_code = int(r["area_code"])
            commodity = r["item"]
            item_code = int(r["item_code"])
            indicator = r["indicator"]
            indicator_code = int(r["indicator_code"])
            year = int(r["year"])
            val = to_decimal_safe(r["value"])
            unit = r["unit"]
            flag = r.get("flag")
            flag_desc = r.get("flag_description")
            source = r.get("source") or faostat_payload.get("source") or "FAOSTAT"

            if val is None:
                continue

            if is_postgres:
                stmt = pg_insert(FAOSTATIndicator).values(
                    area=area,
                    area_code=area_code,
                    commodity=commodity,
                    item_code=item_code,
                    indicator=indicator,
                    indicator_code=indicator_code,
                    year=year,
                    value=val,
                    unit=unit,
                    flag=flag,
                    flag_description=flag_desc,
                    source=source,
                ).on_conflict_do_update(
                    constraint="uq_faostat_indicators_metric",
                    set_={
                        "value": val,
                        "unit": unit,
                        "flag": flag,
                        "flag_description": flag_desc,
                        "source": source,
                    },
                )
                db.execute(stmt)
                inserted_count += 1
            else:
                existing = db.query(FAOSTATIndicator).filter_by(
                    area_code=area_code,
                    item_code=item_code,
                    indicator_code=indicator_code,
                    year=year,
                ).first()

                if existing:
                    existing.value = val
                    existing.unit = unit
                    existing.flag = flag
                    existing.flag_description = flag_desc
                    existing.source = source
                    updated_count += 1
                else:
                    new_item = FAOSTATIndicator(
                        area=area,
                        area_code=area_code,
                        commodity=commodity,
                        item_code=item_code,
                        indicator=indicator,
                        indicator_code=indicator_code,
                        year=year,
                        value=val,
                        unit=unit,
                        flag=flag,
                        flag_description=flag_desc,
                        source=source,
                    )
                    db.add(new_item)
                    inserted_count += 1

        db.commit()
        return {
            "inserted": inserted_count,
            "updated": updated_count,
            "total": len(records),
        }

    @staticmethod
    def ingest_route_data(route_payload: Dict[str, Any], db: Session, origin_name: Optional[str] = None, dest_name: Optional[str] = None) -> RouteRecord:
        """
        Stores road network route calculation records into the 'route_records' table.
        """
        orig = route_payload["origin"]
        dest = route_payload["destination"]

        orig_lat = Decimal(str(round(float(orig["latitude"]), 5)))
        orig_lon = Decimal(str(round(float(orig["longitude"]), 5)))
        dest_lat = Decimal(str(round(float(dest["latitude"]), 5)))
        dest_lon = Decimal(str(round(float(dest["longitude"]), 5)))

        dist_km = to_decimal_safe(route_payload.get("distance_km"))
        dur_min = to_decimal_safe(route_payload.get("duration_minutes"))
        dur_hr = to_decimal_safe(route_payload.get("duration_hours"))
        geometry = route_payload.get("geometry")
        provider = route_payload.get("provider") or "OSRM (OpenStreetMap)"

        # Check if identical route calculation exists
        existing = db.query(RouteRecord).filter_by(
            origin_lat=orig_lat,
            origin_lon=orig_lon,
            dest_lat=dest_lat,
            dest_lon=dest_lon,
        ).first()

        if existing:
            existing.distance_km = dist_km
            existing.duration_minutes = dur_min
            existing.duration_hours = dur_hr
            existing.geometry_geojson = geometry
            existing.routing_provider = provider
            if origin_name:
                existing.origin_name = origin_name
            if dest_name:
                existing.dest_name = dest_name
            db.commit()
            db.refresh(existing)
            return existing

        new_route = RouteRecord(
            origin_lat=orig_lat,
            origin_lon=orig_lon,
            origin_name=origin_name,
            dest_lat=dest_lat,
            dest_lon=dest_lon,
            dest_name=dest_name,
            distance_km=dist_km,
            duration_minutes=dur_min,
            duration_hours=dur_hr,
            geometry_geojson=geometry,
            routing_provider=provider,
        )
        db.add(new_route)
        db.commit()
        db.refresh(new_route)
        return new_route
