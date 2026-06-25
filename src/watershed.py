"""
Watershed Module
================
Catchment area lookup and delineation for hydrological stations.

Uses IMGW gauge station data and optionally the MERIT-based watershed
delineator for computing catchment areas at arbitrary points.

Data files:
- data/imgw_gauges.json -- IMGW station coordinates (auto-downloaded from API)
- data/catchment_areas.json -- cached catchment areas (computed by delineator)
"""

import json
import os
import sys
from pathlib import Path
from typing import Optional

import numpy as np
import requests

# Path to IMGW gauge station data
_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_GAUGES_FILE = _DATA_DIR / "imgw_gauges.json"
_CACHE_FILE = _DATA_DIR / "catchment_areas.json"

# Default path to the watershed delineator
DELINEATOR_PATH = r"d:\kod\watershed\delineator"

# IMGW API endpoint for current hydro data (includes station coordinates)
_IMGW_API_URL = "https://danepubliczne.imgw.pl/api/data/hydro"


def _download_gauges():
    """Download IMGW gauge station list from API and save to data/imgw_gauges.json."""
    print(f"Pobieranie listy wodowskazow IMGW z API...")
    resp = requests.get(_IMGW_API_URL, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    gauges = []
    seen_ids = set()
    for item in data:
        sid = item.get("id_stacji", "").strip()
        if not sid or sid in seen_ids:
            continue
        seen_ids.add(sid)
        lat = item.get("lat")
        lng = item.get("lon")
        if lat is None or lng is None:
            continue
        gauges.append({
            "id": sid,
            "name": item.get("stacja", "").strip(),
            "river": item.get("rzeka", "").strip(),
            "lat": float(lat),
            "lng": float(lng),
            "voivodeship": item.get("wojewodztwo", "").strip(),
        })

    os.makedirs(_DATA_DIR, exist_ok=True)
    with open(_GAUGES_FILE, "w", encoding="utf-8") as f:
        json.dump(gauges, f, indent=2, ensure_ascii=False)
    print(f"  Zapisano {len(gauges)} stacji do {_GAUGES_FILE}")
    return gauges


def load_gauges() -> list[dict]:
    """Load IMGW gauge station data (id, name, river, lat, lng).

    If data/imgw_gauges.json doesn't exist, downloads it from IMGW API.
    """
    if not _GAUGES_FILE.exists():
        _download_gauges()
    with open(_GAUGES_FILE, encoding="utf-8") as f:
        return json.load(f)


def find_gauge(station_id: str) -> Optional[dict]:
    """Find gauge station by IMGW station ID."""
    for g in load_gauges():
        if g["id"] == station_id:
            return g
    return None


def _load_cache() -> dict:
    """Load cached catchment areas."""
    if _CACHE_FILE.exists():
        with open(_CACHE_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_cache(cache: dict):
    """Save catchment areas cache."""
    os.makedirs(_DATA_DIR, exist_ok=True)
    with open(_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)


def get_catchment_area(
    lat: float,
    lng: float,
    label: str = "",
    delineator_path: str = DELINEATOR_PATH,
    use_cache: bool = True,
) -> float:
    """Get catchment area [km2] for a point.

    First checks cache (data/catchment_areas.json), then calls the
    watershed delineator if available.

    Args:
        lat, lng: coordinates (WGS84)
        label: optional label for caching
        delineator_path: path to the watershed delineator
        use_cache: if True, check/store results in cache

    Returns:
        Catchment area in km2

    Raises:
        FileNotFoundError: if area not in cache and delineator not available
    """
    cache_key = f"{lat:.4f},{lng:.4f}"

    # Check cache
    if use_cache:
        cache = _load_cache()
        if cache_key in cache:
            return cache[cache_key]["area_km2"]

    # Try to call the delineator
    area = _run_delineator(lat, lng, delineator_path)

    # Cache result
    if use_cache and area is not None:
        cache = _load_cache()
        cache[cache_key] = {
            "label": label,
            "lat": lat,
            "lng": lng,
            "area_km2": area,
        }
        _save_cache(cache)

    return area


def _run_delineator(lat: float, lng: float, delineator_path: str) -> Optional[float]:
    """Call the watershed delineator to compute catchment area."""
    delineator = Path(delineator_path)
    if not delineator.exists():
        raise FileNotFoundError(
            f"Powierzchnia zlewni nie znaleziona w cache (data/catchment_areas.json) "
            f"i delineator nie dostepny pod {delineator_path}.\n"
            f"Opcje:\n"
            f"  1. Dodaj wpis recznie do data/catchment_areas.json\n"
            f"  2. Zainstaluj delineator: git clone <repo> {delineator_path}\n"
            f"     i pobierz dane MERIT: python {delineator_path}/setup.py --basins 24"
        )

    # Save and change to delineator directory (it needs to run from its own dir)
    original_cwd = os.getcwd()
    original_path = sys.path.copy()
    str_path = str(delineator)

    try:
        os.chdir(str_path)
        if str_path not in sys.path:
            sys.path.insert(0, str_path)

        from server import delineate_point, load_megabasins
        import server as srv
        if srv.megabasins_gdf is None:
            load_megabasins()

        result = delineate_point(lat, lng)
        if "error" in result:
            raise RuntimeError(f"Delineation failed: {result['error']}")
        return result["area_km2"]
    finally:
        os.chdir(original_cwd)
        sys.path[:] = original_path


def get_station_area(
    station_id: str,
    delineator_path: str = DELINEATOR_PATH,
) -> float:
    """Get catchment area for an IMGW gauge station.

    Looks up station coordinates, then checks cache or runs delineator.

    Args:
        station_id: IMGW station ID (e.g. '151160150')
        delineator_path: path to the watershed delineator

    Returns:
        Catchment area in km2
    """
    gauge = find_gauge(station_id)
    if gauge is None:
        raise ValueError(f"Station {station_id} not found in IMGW gauge data")

    return get_catchment_area(
        gauge["lat"], gauge["lng"],
        label=f"{gauge['name']} ({gauge['river']})",
        delineator_path=delineator_path,
    )

