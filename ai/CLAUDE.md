# EW - Water Power Engineering (Energetyka Wodna)

## Project Overview
Jupyter notebook series for Water Power Plant (WPP) design workflow.
Teaching material for EW course, 2025/2026 academic year.

## Tech Stack
- Python 3.11+, virtual env in `venv/`
- Jupyter notebooks in `notebooks/`
- Reusable modules in `src/`
- Plotly for interactive plots
- Data from IMGW (Polish Institute of Meteorology and Water Management)

## Project Structure
```
ai/          - AI assistant files (this file, plans)
data/raw/    - Downloaded IMGW ZIP/CSV files (gitignored)
data/processed/ - Cleaned/merged data (gitignored)
src/         - Reusable Python modules
notebooks/   - Jupyter notebooks (numbered by step)
```

## Data Source: IMGW
- Archive: https://danepubliczne.imgw.pl/data/dane_pomiarowo_obserwacyjne/dane_hydrologiczne/dobowe/
- API (current only): https://danepubliczne.imgw.pl/api/data/hydro
- Station list: https://danepubliczne.imgw.pl/data/dane_pomiarowo_obserwacyjne/dane_hydrologiczne/lista_stacji_hydro.csv
- Historical data in ZIP files: `codz_{YEAR}_{MONTH}.zip` (pre-2023), `codz_{YEAR}.zip` (2023+)
- CSV format changed in 2023: old=CP1250/comma, new=UTF-8-sig/semicolon
- Hydrological year: Nov 1 → Oct 31 (month 01 = November)

## Conventions
- Notebooks: numbered `01_`, `02_`, etc. Each has markdown descriptions, code, results.
- Modules in `src/` should be importable from notebooks.
- Plotly for all plots (interactive in notebook).
- Data download runs once, results cached in `data/`. Station IDs provided by user.
- Polish river/station names preserved in data, English for code/comments.

## Notebook Plan
1. Data Acquisition (station selection, IMGW download, parsing)
2. Data Quality (gap detection, filling, validation)
3. Hydrological Statistics (flow duration curves, characteristic flows)
4. Power Production Potential
5. Turbine Selection
6. Kaplan Turbine Design
