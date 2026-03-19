"""
IMGW Data Download & Parsing Module
====================================
Downloads and parses hydrological data from IMGW public archive:
https://danepubliczne.imgw.pl/data/dane_pomiarowo_obserwacyjne/dane_hydrologiczne/

Handles two CSV format eras:
- Pre-2023: CP-1250 encoding, comma separator, quoted fields
- 2023+: UTF-8-sig encoding, semicolon separator, no quotes

Only water level [cm] and discharge [m3/s] are kept (no temperature).
Processed data saved as Parquet for speed and type preservation.
"""

import csv
import io
import os
import zipfile
from typing import Optional

import pandas as pd
import requests

# IMGW URLs
BASE_URL = "https://danepubliczne.imgw.pl/data/dane_pomiarowo_obserwacyjne/dane_hydrologiczne"
DAILY_URL = f"{BASE_URL}/dobowe"
STATION_LIST_URL = f"{BASE_URL}/lista_stacji_hydro.csv"
API_HYDRO_URL = "https://danepubliczne.imgw.pl/api/data/hydro"

# All 10 columns in source CSV (no header in file)
_RAW_COLUMNS = [
    "station_id",       # 9-digit string
    "station_name",     # e.g. "CHALUPKI"
    "river_name",       # e.g. "Odra (1)"
    "hydro_year",       # hydrological year
    "hydro_month",      # 01=November, 12=October
    "day",              # day of month
    "water_level_cm",   # water level [cm]
    "discharge_m3s",    # discharge [m3/s]
    "_water_temp_c",    # not used — dropped after parsing
    "calendar_month",   # calendar month number
]

# Columns kept in output
KEEP_COLUMNS = [
    "station_id", "station_name", "river_name",
    "water_level_cm", "discharge_m3s", "date",
]


def get_station_list() -> pd.DataFrame:
    """Download the list of all IMGW hydrological stations.

    Returns DataFrame with columns: station_id, station_name, river, route_number
    """
    resp = requests.get(STATION_LIST_URL, timeout=30)
    resp.raise_for_status()

    # Try different encodings
    for enc in ["utf-8-sig", "utf-8", "cp1250"]:
        try:
            text = resp.content.decode(enc)
            break
        except UnicodeDecodeError:
            continue

    df = pd.read_csv(
        io.StringIO(text),
        header=None,
        names=["station_id", "station_name", "river", "route_number"],
        dtype=str,
    )
    df["station_id"] = df["station_id"].str.strip()
    df["station_name"] = df["station_name"].str.strip()
    df["river"] = df["river"].str.strip()
    return df


def search_stations(query: str, by: str = "name") -> pd.DataFrame:
    """Search IMGW stations by name, river, or ID.

    Args:
        query: Search string (case-insensitive, partial match)
        by: Search field - 'name', 'river', or 'id'
    """
    stations = get_station_list()
    col = {"name": "station_name", "river": "river", "id": "station_id"}[by]
    mask = stations[col].str.contains(query, case=False, na=False)
    return stations[mask]


def get_current_hydro() -> pd.DataFrame:
    """Get current readings from all IMGW hydro stations via REST API.

    Useful for browsing available stations with coordinates.
    Returns DataFrame with station info, current water level, discharge, etc.
    """
    resp = requests.get(API_HYDRO_URL, timeout=30)
    resp.raise_for_status()
    return pd.DataFrame(resp.json())


def _detect_csv_format(year: int) -> dict:
    """Return CSV parsing parameters based on the year."""
    if year >= 2023:
        return {"encoding": "utf-8-sig", "sep": ";", "quoting": csv.QUOTE_NONE}
    else:
        return {"encoding": "cp1250", "sep": ",", "quoting": csv.QUOTE_ALL}


def _build_zip_urls(year: int) -> list[str]:
    """Build list of ZIP file URLs for a given hydrological year."""
    if year >= 2023:
        return [f"{DAILY_URL}/{year}/codz_{year}.zip"]
    else:
        return [f"{DAILY_URL}/{year}/codz_{year}_{m:02d}.zip" for m in range(1, 13)]


def _parse_csv_from_zip(
    zip_bytes: bytes, year: int, station_ids: Optional[set[str]] = None
) -> pd.DataFrame:
    """Parse CSV files inside a ZIP archive."""
    fmt = _detect_csv_format(year)
    frames = []

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        for name in zf.namelist():
            if not name.lower().endswith(".csv"):
                continue
            with zf.open(name) as f:
                raw = f.read()
                # Try expected encoding first, fall back to alternative
                try:
                    text = raw.decode(fmt["encoding"])
                except UnicodeDecodeError:
                    fallback = "cp1250" if fmt["encoding"] != "cp1250" else "utf-8-sig"
                    text = raw.decode(fallback)
                # Auto-detect separator and quoting from first line
                first_line = text.split("\n")[0]
                if ";" in first_line:
                    sep, quoting = ";", csv.QUOTE_NONE
                else:
                    sep, quoting = ",", csv.QUOTE_ALL
                df = pd.read_csv(
                    io.StringIO(text),
                    header=None,
                    names=_RAW_COLUMNS,
                    sep=sep,
                    quoting=quoting,
                    dtype={"station_id": str, "hydro_year": str,
                           "hydro_month": str, "day": str, "calendar_month": str},
                    na_values=["", " "],
                )
                df["station_id"] = df["station_id"].str.strip()
                # Replace IMGW sentinel values with NaN
                df.loc[df["water_level_cm"] >= 9999, "water_level_cm"] = pd.NA
                df.loc[df["discharge_m3s"] >= 99999, "discharge_m3s"] = pd.NA
                if station_ids:
                    df = df[df["station_id"].isin(station_ids)]
                if not df.empty:
                    frames.append(df)

    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=_RAW_COLUMNS)


def download_daily_data(
    station_ids: list[str],
    year_from: int,
    year_to: int,
    data_dir: str = "data/raw",
    force: bool = False,
) -> pd.DataFrame:
    """Download daily hydrological data for given stations and year range.

    Downloads ZIP files from IMGW archive, caches them locally, parses CSV.
    Runs only once per file unless force=True.

    Args:
        station_ids: List of 9-digit IMGW station IDs
        year_from: Start hydrological year (inclusive)
        year_to: End hydrological year (inclusive)
        data_dir: Directory to cache downloaded ZIPs
        force: Re-download even if cached

    Returns:
        DataFrame with columns: station_id, station_name, river_name,
        water_level_cm, discharge_m3s, date
    """
    os.makedirs(data_dir, exist_ok=True)
    station_set = set(s.strip() for s in station_ids)
    all_frames = []

    for year in range(year_from, year_to + 1):
        urls = _build_zip_urls(year)
        for url in urls:
            filename = url.split("/")[-1]
            local_path = os.path.join(data_dir, filename)

            # Download if not cached
            if not os.path.exists(local_path) or force:
                print(f"  Downloading {filename}...")
                try:
                    resp = requests.get(url, timeout=60)
                    resp.raise_for_status()
                    with open(local_path, "wb") as f:
                        f.write(resp.content)
                except requests.HTTPError as e:
                    print(f"  Warning: {filename} not available ({e})")
                    continue
            else:
                print(f"  Using cached {filename}")

            # Parse
            with open(local_path, "rb") as f:
                zip_bytes = f.read()
            df = _parse_csv_from_zip(zip_bytes, year, station_set)
            if not df.empty:
                all_frames.append(df)

    if not all_frames:
        print("No data found for the given stations/years.")
        return pd.DataFrame(columns=KEEP_COLUMNS)

    result = pd.concat(all_frames, ignore_index=True)
    result = _add_date_column(result)

    # Drop temp and intermediate columns, keep only what we need
    result = result.drop(columns=["_water_temp_c", "hydro_year", "hydro_month",
                                   "day", "calendar_month"], errors="ignore")
    result = result.sort_values(["station_id", "date"]).reset_index(drop=True)
    return result


def _add_date_column(df: pd.DataFrame) -> pd.DataFrame:
    """Add a proper datetime 'date' column from hydro_year + calendar_month + day."""
    df = df.copy()
    df["calendar_month"] = pd.to_numeric(df["calendar_month"], errors="coerce")
    df["day"] = pd.to_numeric(df["day"], errors="coerce")
    df["hydro_year"] = pd.to_numeric(df["hydro_year"], errors="coerce")

    # Determine calendar year: months 11,12 belong to hydro_year-1
    df["calendar_year"] = df["hydro_year"].astype("Int64")
    mask_prev = df["calendar_month"].isin([11, 12])
    df.loc[mask_prev, "calendar_year"] = df.loc[mask_prev, "hydro_year"] - 1

    df["date"] = pd.to_datetime(
        df[["calendar_year", "calendar_month", "day"]].rename(
            columns={"calendar_year": "year", "calendar_month": "month"}
        ),
        errors="coerce",
    )
    df = df.drop(columns=["calendar_year"])
    return df


def save_processed(df: pd.DataFrame, path: str = "data/processed/daily_hydro.parquet"):
    """Save processed DataFrame to Parquet."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    df.to_parquet(path, index=False)
    print(f"Saved {len(df)} rows to {path}")


def load_processed(path: str = "data/processed/daily_hydro.parquet") -> pd.DataFrame:
    """Load previously saved processed data from Parquet."""
    df = pd.read_parquet(path)
    return df
