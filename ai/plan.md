# WPP Design Notebook - Implementation Plan

## Phase 1: Data Infrastructure
- [x] Project structure, git, conda env, requirements
- [x] `src/imgw.py` — IMGW data download & parsing (2 format eras, sentinel values, Parquet)
- [x] `01_data_acquisition.ipynb` — Station discovery, download, first look
- [x] `src/data_quality.py` — Gap detection, filling, validation
- [x] `02_data_quality.ipynb` — Data QC notebook
- [x] `00_llm_agents_for_coding.ipynb` — Presentation: LLM agents, setup, tools

## Phase 2: Hydrological Analysis
- [x] `src/hydro_stats.py` — Flow duration curves, characteristic flows
- [x] `03_hydro_statistics.ipynb` — Statistical analysis notebook

## Phase 3: Power & Turbine Design
- [ ] `src/power.py` — Power/energy calculations
- [ ] `04_power_potential.ipynb` — Power production potential
- [ ] `src/turbine.py` — Turbine selection logic
- [ ] `05_turbine_selection.ipynb` — Turbine selection notebook
- [ ] `06_kaplan_design.ipynb` — Kaplan turbine design

## Key Design Decisions
- Plotly for interactive plots in notebooks
- Parquet for processed data (not CSV)
- Data download is a one-time operation (cached in data/)
- Station IDs provided by user (not auto-discovered)
- Modules in src/ reusable across notebooks and potential future app
- Auto-detect CSV encoding (CP1250/UTF8) and separator (comma/semicolon)
- IMGW sentinel values (9999, 99999) replaced with NaN during parsing
- Polish text in notebooks, English code/variables
- LLM prompts before each code cell + module creation prompts
- RISE/jupyterlab-rise for interactive presentations
