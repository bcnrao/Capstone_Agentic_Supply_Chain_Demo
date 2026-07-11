from __future__ import annotations

from typing import Any

from agentic_scd.agents.schema import DailyWeatherDay

# Daily variables requested from Open-Meteo.
DAILY = "weather_code,wind_speed_10m_max,precipitation_sum"

# WMO weather interpretation codes → (human phrase, severity hint).
WMO: dict[int, tuple[str, str]] = {
    0: ("clear sky", "none"),
    1: ("mainly clear", "none"),
    2: ("partly cloudy", "none"),
    3: ("overcast", "none"),
    45: ("fog", "low"),
    61: ("rain", "low"),
    63: ("heavy rain causing flood risk", "moderate"),
    65: ("heavy rain and flooding disruption", "severe"),
    71: ("snowfall", "moderate"),
    75: ("heavy snow storm", "severe"),
    82: ("violent storm with flooding", "severe"),
    95: ("thunderstorm", "severe"),
    99: ("severe thunderstorm with gale-force wind", "severe"),
}

# Severity hint → numeric score on the shared 1-10 scale.
SEVERITY_SCORE = {"none": 1.0, "low": 3.0, "moderate": 6.0, "severe": 9.0}

# Raw wind (km/h) and precipitation (mm) that lift a day's risk even when its WMO
# code alone reads mild.
WIND_DISRUPTION_KMH = 60.0
PRECIP_DISRUPTION_MM = 40.0


def describe_code(code: int) -> tuple[str, str]:
    """Map a WMO weather code to its (phrase, severity hint)."""
    return WMO.get(code, ("unsettled weather", "low"))


def _series_value(daily: dict[str, Any], key: str, idx: int) -> float | None:
    series = daily.get(key) or []
    if idx < len(series) and series[idx] is not None:
        return float(series[idx])
    return None


def parse_daily_series(hub: dict[str, Any], response: dict[str, Any]) -> list[DailyWeatherDay]:
    """Turn an Open-Meteo ``daily`` block into one ``DailyWeatherDay`` per day."""
    daily = response.get("daily", {}) or {}
    times = daily.get("time") or []
    codes = daily.get("weather_code") or []
    days: list[DailyWeatherDay] = []
    for idx, day in enumerate(times):
        code = int(codes[idx]) if idx < len(codes) and codes[idx] is not None else 0
        phrase, hint = describe_code(code)
        wind = _series_value(daily, "wind_speed_10m_max", idx)
        precip = _series_value(daily, "precipitation_sum", idx)
        if hint in {"none", "low"} and ((wind or 0.0) >= WIND_DISRUPTION_KMH or (precip or 0.0) >= PRECIP_DISRUPTION_MM):
            hint = "moderate"
        days.append(
            DailyWeatherDay(
                date=str(day),
                weather_code=code,
                phrase=phrase,
                wind_kmh_max=wind,
                precipitation_mm=precip,
                severity_hint=hint,
            )
        )
    return days


def day_severity(day: DailyWeatherDay) -> float:
    """Numeric 1-10 severity for a single day, floored by wind/precip thresholds."""
    score = SEVERITY_SCORE.get(day.severity_hint, 1.0)
    if (day.wind_kmh_max or 0.0) >= WIND_DISRUPTION_KMH:
        score = max(score, 6.0)
    if (day.precipitation_mm or 0.0) >= PRECIP_DISRUPTION_MM:
        score = max(score, 6.0)
    return score


def peak_day(days: list[DailyWeatherDay]) -> DailyWeatherDay | None:
    """The most severe day in the horizon (ties resolved by earliest)."""
    return max(days, key=day_severity, default=None)


def score_hub_risk(days: list[DailyWeatherDay]) -> float:
    """Aggregate 1-10 risk: peak day plus a small bump for sustained disruption."""
    if not days:
        return 1.0
    peak = max(day_severity(day) for day in days)
    disruptive = sum(1 for day in days if day_severity(day) >= 6.0)
    persistence_bonus = min(1.0, 0.2 * max(0, disruptive - 1))
    return round(min(10.0, peak + persistence_bonus), 2)


def operations_at_risk(days: list[DailyWeatherDay], hub: dict[str, Any]) -> list[str]:
    """Supply-chain operations likely disrupted across the horizon."""
    if not days:
        return []
    max_wind = max((day.wind_kmh_max or 0.0) for day in days)
    max_precip = max((day.precipitation_mm or 0.0) for day in days)
    severe = any(day.severity_hint == "severe" for day in days)
    ops: list[str] = []
    if severe or max_wind >= WIND_DISRUPTION_KMH:
        ops.extend(["port_ops", "container_handling"])
    if severe or max_precip >= PRECIP_DISRUPTION_MM:
        ops.append("inland_freight")
    return list(dict.fromkeys(ops))


def summarize_hub_forecast(hub: dict[str, Any], days: list[DailyWeatherDay]) -> str:
    """One-line, human-readable summary of the horizon's peak risk."""
    place = hub.get("hub_port") or hub.get("region") or "configured hub"
    if not days:
        return f"No forecast data available for {place}."
    peak = peak_day(days)
    return (
        f"{len(days)}-day forecast for {place}: peak {peak.phrase} on {peak.date} "
        f"(max wind {peak.wind_kmh_max} km/h, precipitation {peak.precipitation_mm} mm)."
    )
