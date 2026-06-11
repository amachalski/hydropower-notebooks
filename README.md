# hydropower-notebooks

**[PL]** Zestaw 13 notebooków Jupyter do analiz hydrologicznych, pełnego projektowania elektrowni wodnej (EW) i wielokryterialnej optymalizacji wariantów. **Materiały w opracowaniu.**

**[EN]** A set of 13 Jupyter notebooks for hydrological analysis, full hydropower plant design, and multi-criteria variant optimization. **Work in progress.**

---

## PL — Polski

Materiały dydaktyczne — kod wielokrotnego użytku w `src/`, analizy krok po kroku w `notebooks/`. Projekt prowadzi od surowych danych IMGW do pełnej, ekonomicznej optymalizacji punktu projektowego elektrowni.

**Cel zajęć:** Głównym celem jest nauka obliczeń związanych z projektowaniem elektrowni wodnych (hydrologia, potencjał energetyczny, dobór turbiny, koszty). Dodatkowym celem jest praktyczne wykorzystanie nowoczesnych narzędzi: agentów LLM do wspomagania programowania, Pythona z bibliotekami do analizy danych (pandas, numpy, plotly, scipy) oraz środowiska Jupyter do dokumentowania i prezentacji wyników.

> **Dla studentów:** Kod w tym repozytorium ma charakter informacyjny i poglądowy — służy jako podpowiedź i punkt wyjścia. Proszę tworzyć własne obliczenia samodzielnie, korzystając z tego kodu tylko gdy jest to konieczne. Korzystanie z pomocy LLM jest mile widziane, ale pamiętajcie — **to Wy odpowiadacie za poprawność wyników**.

### Plan kursu — 13 notebooków w czterech fazach

**Dane** (01-04) → **Modele składowe** (05-09) → **Integracja** (10) → **Analiza wariantów + optymalizacja** (11-12).

| # | Notebook | Krótki opis | Status |
|---|----------|-------------|--------|
| **00** | `llm_agents_for_coding` | Wprowadzenie, agenci LLM, konfiguracja środowiska, **spis treści projektu** | start |
| **01** | `data_acquisition` | Pobranie z archiwum IMGW (dwa formaty CSV), zapis do parquet | wymagany |
| **02** | `data_quality` | Uzupełnianie luk (krzywa konsumcyjna + korelacja stacji + interpolacja), outliers, **jedyne miejsce filtrowania lat** | wymagany |
| **03** | `hydro_statistics` | Interpolacja Q do lokalizacji EW; NNQ/SNQ/Q50/Q90/Q95, FDC, sezonowość | wymagany |
| **04** | `flow_duration_curve` | Średni rok uporządkowany — wygładzona FDC do projektowania | wymagany |
| **05** | `power_production` | Model uproszczony: stałe η, R-form turbiny, optymalizacja NPV/LCOE/payback | wymagany |
| **06** | `hydraulic_losses` | Kirschmer, Darcy-Weisbach, Manning, straty miejscowe | **opcjonalny** |
| **07** | `turbine_efficiency` | Katalog, krzywe η, prawa podobieństwa, macierz nsN, kawitacja, dispatch | wymagany |
| **08** | `generator_efficiency` | Model η_g(P/Pn): copper + iron + mechanical, skalowanie rozmiarem | **opcjonalny** |
| **09** | `cost_estimation` | Ogayar & Vidal + IRENA + NREL; NPV, LCOE, payback, IRR | wymagany |
| **10** | `integrated_production` | **Łączy wszystko**: pełna optymalizacja punktu projektowego z maksymalizacją NPV (sweep) | wymagany |
| **11** | `variants_comparison` | Cztery konfiguracje (Kaplan 1×, 2×, 4×, Crossflow) zestawione side-by-side | wymagany |
| **12** | `optimization_pareto` | Algorytm genetyczny NSGA-II, front Pareto (NPV vs LCOE), knee point | wymagany (final) |

**Notebooki 06 i 08** są dydaktycznie wartościowe, ale nb 10 ma własne, działające konfiguracje domyślne. Można je pominąć dla szybszego kursu — wynik nb 10 nadal będzie poprawny, choć bez głębszego zrozumienia modeli fizycznych.

**Ścieżka minimum**: 01 → 02 → 03 → 04 → 05 → 07 → 09 → 10 → 11 → 12
**Ścieżka pełna** (zalecana): 01 → 02 → 03 → 04 → 05 → 06 → 07 → 08 → 09 → 10 → 11 → 12

### Moduły (`src/`)

| Moduł | Opis |
|-------|------|
| `imgw_data.py` | Pobieranie i parsowanie danych IMGW (2 formaty CSV, Parquet I/O) |
| `hydrology.py` | Detekcja luk, krzywa konsumcyjna (z H₀), korelacja stacji, outliers, FDC, NNQ/SNQ/SSQ/SWQ/WWQ, średni rok uporządkowany, interpolacja Q do lokalizacji EW, przepływ nienaruszalny |
| `watershed.py` | Powierzchnie zlewni IMGW + delineator MERIT z cache |
| `losses.py` | Strata na kracie (Kirschmer), tarcie w rurociągu (Darcy-Weisbach + Swamee-Jain z gałęzią laminarną), straty miejscowe, składanie i spad netto |
| `turbine.py` | Katalog turbin (Kaplan/Francis/Propeller/Crossflow/PL10/PL20), krzywa η_t, wymiarowanie z praw podobieństwa, nsN (kW i metryczny KM), filtr po H, rozdział wieloturbinowy, **kawitacja Thomy** |
| `generator.py` | η_g(P/Pn), współczynniki zależne od rozmiaru maszyny (50 kW–5 MW) |
| `costs.py` | Ogayar & Vidal (EM) + IRENA (civil) + NREL (grid) + inżynieria; ekonomia: NPV, LCOE, payback z annuitetem |
| `production.py` | `compute_power()` — integrator łączący straty + sprawności + dispatch + Q_env |

### Źródło danych

Dane hydrologiczne z publicznego archiwum [IMGW](https://danepubliczne.imgw.pl/data/dane_pomiarowo_obserwacyjne/dane_hydrologiczne/dobowe/) — dobowe stany wody i przepływy.

Punkt referencyjny: rzeka **Odra** koło Malczyc. Dwa wodowskazy ograniczające lokalizację EW: **Brzeg Dolny** (upstream, A=26 495 km²) i **Malczyce** (downstream, A=26 860 km²).

### Instalacja

```bash
# Miniconda (zalecane)
conda env create -f environment.yml
conda activate ew

# Alternatywnie: pip
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
pip install -r requirements.txt
```

### Uruchomienie

```bash
conda activate ew
jupyter lab notebooks
```

Lub otwórz notebooki w VS Code (rozszerzenie Jupyter). Zalecana kolejność: **00 → 01 → 02 → … → 10**.

### Jak to powstało

Projekt został stworzony wspólnie z agentem LLM (Claude Code). Każdy notebook zawiera przykładowe prompty, które mogłyby wygenerować dany kod — jako materiał dydaktyczny o pracy z AI.

Szczegóły metodologii: [`ai/methodology.md`](ai/methodology.md)

### Referencja

Projekt odtwarza i rozszerza metodologię z arkusza `other/WPE_2.xlsm` — historycznego narzędzia projektowego EW (8 arkuszy: dane hydrologiczne, sortowanie, statystyki, parametry instalacyjne, dobór turbiny). Liczby z modelu Python powinny zgadzać się z arkuszem w tych samych punktach projektowych; różnice (np. labelowanie kolumn) są opisane w komentarzach w kodzie.

---

## EN — English

Teaching materials — reusable modules in `src/`, step-by-step analyses in `notebooks/`. The project walks from raw IMGW data to a full economic optimization of the design operating point.

**Course objectives:** The primary goal is learning hydropower plant design calculations (hydrology, energy potential, turbine selection, costs). An additional goal is hands-on experience with modern tools: LLM agents for programming assistance, Python data analysis libraries (pandas, numpy, plotly, scipy), and the Jupyter environment for documenting and presenting results.

> **For students:** The code in this repository is provided for reference and as a starting point. Please create your own calculations independently, reusing this code only when necessary. LLM assistance is encouraged, but remember — **you are responsible for the correctness of your results**.

### Course plan — 13 notebooks in four phases

**Data** (01-04) → **Component models** (05-09) → **Integration** (10) → **Variant analysis + optimization** (11-12).

| # | Notebook | Short description | Status |
|---|----------|-------------------|--------|
| **00** | `llm_agents_for_coding` | Intro, LLM agents, environment setup, **project table of contents** | start |
| **01** | `data_acquisition` | Download from IMGW archive (two CSV eras), save to parquet | required |
| **02** | `data_quality` | Gap filling (rating curve + station correlation + interpolation), outliers, **single source for year filtering** | required |
| **03** | `hydro_statistics` | Interpolate Q to plant location; NNQ/SNQ/Q50/Q90/Q95, FDC, seasonality | required |
| **04** | `flow_duration_curve` | Average sorted year — smoothed FDC for design | required |
| **05** | `power_production` | Simplified model: constant η, R-form turbine, NPV/LCOE/payback optimization | required |
| **06** | `hydraulic_losses` | Kirschmer, Darcy-Weisbach, Manning, minor losses | **optional** |
| **07** | `turbine_efficiency` | Catalog, η curves, similarity laws, nsN matrix, cavitation, multi-unit dispatch | required |
| **08** | `generator_efficiency` | η_g(P/Pn) model: copper + iron + mechanical, size scaling | **optional** |
| **09** | `cost_estimation` | Ogayar & Vidal + IRENA + NREL; NPV, LCOE, payback, IRR | required |
| **10** | `integrated_production` | **Combines everything**: full design-point optimization (max NPV, 1D sweep) | required |
| **11** | `variants_comparison` | Four configurations (Kaplan 1×, 2×, 4×, Crossflow) compared side-by-side | required |
| **12** | `optimization_pareto` | Genetic algorithm NSGA-II, Pareto front (NPV vs LCOE), knee point | required (final) |

Notebooks **06 and 08** are pedagogically valuable but not strictly required — nb 10 has working default configurations. They can be skipped for a shorter course; the nb 10 result will still be valid, just without deeper understanding of the underlying physics.

**Minimal path**: 01 → 02 → 03 → 04 → 05 → 07 → 09 → 10 → 11 → 12
**Full path** (recommended): 01 → 02 → 03 → 04 → 05 → 06 → 07 → 08 → 09 → 10 → 11 → 12

### Modules (`src/`)

| Module | Description |
|--------|-------------|
| `imgw_data.py` | IMGW data download & parsing (2 CSV format eras, Parquet I/O) |
| `hydrology.py` | Gap detection, rating curve with H₀ offset, station correlation, outliers, FDC, NNQ/SNQ/SSQ/SWQ/WWQ, average sorted year, Q-to-location interpolation, environmental flow |
| `watershed.py` | IMGW catchment areas + MERIT delineator with cache |
| `losses.py` | Trash rack (Kirschmer), pipe friction (Darcy-Weisbach + Swamee-Jain with laminar branch), minor losses, composition, net head |
| `turbine.py` | Turbine catalog (Kaplan/Francis/Propeller/Crossflow/PL10/PL20), η_t curve, similarity-law dimensioning, nsN (kW + metric HP forms), H-fit filter, multi-turbine dispatch, **Thoma cavitation** |
| `generator.py` | η_g(P/Pn), size-dependent loss coefficients (50 kW–5 MW) |
| `costs.py` | Ogayar & Vidal (EM) + IRENA (civil) + NREL (grid) + engineering; economics: NPV, LCOE, payback with annuity |
| `production.py` | `compute_power()` — integrator chaining losses + efficiencies + dispatch + Q_env |

### Data source

Hydrological data from the public [IMGW](https://danepubliczne.imgw.pl/data/dane_pomiarowo_obserwacyjne/dane_hydrologiczne/dobowe/) archive — daily water levels and discharge (Polish Institute of Meteorology and Water Management).

Reference site: Odra river near Malczyce. Two bounding gauges: **Brzeg Dolny** (upstream, A=26,495 km²) and **Malczyce** (downstream, A=26,860 km²).

### Installation

```bash
# Miniconda (recommended)
conda env create -f environment.yml
conda activate ew

# Alternative: pip
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
pip install -r requirements.txt
```

### Usage

```bash
conda activate ew
jupyter lab notebooks
```

Or open notebooks in VS Code (Jupyter extension). Recommended order: **00 → 01 → 02 → … → 10**.

### How it was built

This project was built collaboratively with an LLM agent (Claude Code). Each notebook contains example prompts that could generate the code — serving as teaching material about working with AI.

Methodology details: [`ai/methodology.md`](ai/methodology.md)

### Reference

The project replicates and extends the methodology from `other/WPE_2.xlsm` — a legacy hydropower design spreadsheet (8 sheets: hydrological data, sorted flow, statistics, installation parameters, turbine selection). Python output should match the spreadsheet at equivalent design points; deviations (e.g., column labelling fixes like "Number of poles" → "Number of pole pairs", "ROI" → "Payback years") are documented in code comments.

---

## Project structure

```
├── ai/                  # AI assistant config (CLAUDE.md, methodology, reviewers)
├── data/
│   ├── raw/             # Downloaded IMGW ZIPs (not in repo, generated by nb 01)
│   ├── processed/       # Processed Parquet files (not in repo)
│   ├── imgw_gauges.json # 599 IMGW stations (tracked)
│   └── catchment_areas.json  # cached MERIT areas (tracked)
├── src/                 # Reusable Python modules (8 modules, see table above)
├── notebooks/           # Jupyter notebooks (11 notebooks, 00–10)
├── other/               # Reference files (e.g., WPE_2.xlsm; gitignored)
├── environment.yml      # Conda environment
├── requirements.txt     # pip dependencies
└── .gitignore
```

## License / Licencja

MIT — see [LICENSE](LICENSE)
