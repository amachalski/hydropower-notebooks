# EW - Water Power Engineering (Energetyka Wodna)

## Project Overview
Jupyter notebook series for Water Power Plant (WPP) design workflow.
Teaching material for EW course, 2025/2026 academic year.

## Tech Stack
- Python 3.11+, conda environment `ew` (see `environment.yml`)
- Jupyter notebooks in `notebooks/`
- Reusable modules in `src/`
- Plotly for interactive plots
- Data from IMGW (Polish Institute of Meteorology and Water Management)
- Watershed delineator (optional, for computing catchment areas)

## Project Structure
```
ai/                    - AI assistant files (CLAUDE.md, reviewers)
data/                  - Shared data files (tracked in git)
  imgw_gauges.json     - IMGW station coordinates (auto-downloaded)
  catchment_areas.json - Cached catchment areas (computed by delineator)
data/raw/              - Downloaded IMGW ZIP/CSV files (gitignored)
data/processed/        - Cleaned/merged data (gitignored)
other/                 - Reference files (gitignored)
src/                   - Reusable Python modules
  imgw_data.py         - IMGW download, parsing, Parquet I/O
  hydrology.py         - Data quality, statistics, interpolation
  watershed.py         - Catchment areas, gauge lookup
notebooks/             - Jupyter notebooks (numbered by step)
```

## Data Source: IMGW
- Archive: https://danepubliczne.imgw.pl/data/dane_pomiarowo_obserwacyjne/dane_hydrologiczne/dobowe/
- API (current only): https://danepubliczne.imgw.pl/api/data/hydro
- Station list: https://danepubliczne.imgw.pl/data/dane_pomiarowo_obserwacyjne/dane_hydrologiczne/lista_stacji_hydro.csv
- Historical data in ZIP files: `codz_{YEAR}_{MONTH}.zip` (pre-2023), `codz_{YEAR}.zip` (2023+)
- CSV format changed in 2023: old=CP1250/comma, new=UTF-8-sig/semicolon
- Hydrological year: Nov 1 → Oct 31 (month 01 = November)

## Reviewers

Two AI reviewers are available for notebook quality assurance:
- `ai/code_reviewer.md` -- Code quality, architecture, performance, robustness
- `ai/engineering_reviewer.md` -- Engineering calculations, physical correctness, design methodology

Use both reviewers after completing a notebook. Apply their review criteria to check the work.

## Conventions
- Notebooks: numbered `01_`, `02_`, etc. Each has markdown descriptions, code, results.
- Modules in `src/` should be importable from notebooks.
- Plotly for all plots (interactive in notebook).
- Data download runs once, results cached in `data/`. Station IDs provided by user.
- Polish river/station names preserved in data, English for code/comments.
- Keep notebooks GENERIC -- not specific to MEW or any single project type.
- For non-obvious concepts, add **educational markdown cells** with:
  - What the concept is and why it matters
  - Equations (LaTeX) where applicable
  - Example: log-normal distribution, rating curve physics, Manning equation
- Use time% (exceedance percentage) instead of day numbers for FDC/sorted data.
- All sorted flow analyses should include exceedance_pct column.

## Notebook Plan

### Data pipeline (each notebook saves output for the next):
```
01 → data/processed/daily_hydro.parquet
02 → data/processed/daily_hydro_clean.parquet
03 → (analysis only, no file output)
04 → (analysis only, uses clean data)
05 → (analysis only, uses clean data + catchment cache)
```

### Notebooks:
0. LLM Agents for Coding (introduction)
1. Data Acquisition (station selection, IMGW download, parsing)
2. Data Quality (gap detection, filling, validation)
3. Hydrological Statistics (flow duration curves, characteristic flows)
4. Flow Duration Curve (year filtering, average sorted year)
5. Power Production Potential (interpolation, head model, energy, economics)
6. Turbine Selection (planned)
7. Kaplan Turbine Design (planned)
