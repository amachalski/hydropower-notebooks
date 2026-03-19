# hydropower-notebooks

**[PL]** Zestaw notebooków Jupyter do analiz hydrologicznych i projektowania elektrowni wodnych. **Materiały w opracowaniu.**

**[EN]** A set of Jupyter notebooks for hydrological analysis and hydropower plant design. **Work in progress.**

---

## PL — Polski

Materiały dydaktyczne — kod wielokrotnego użytku w `src/`, analizy krok po kroku w `notebooks/`.

**Cel zajęć:** Głównym celem jest nauka obliczeń związanych z projektowaniem elektrowni wodnych (hydrologia, potencjał energetyczny, dobór turbiny). Dodatkowym celem jest praktyczne wykorzystanie nowoczesnych narzędzi: agentów LLM do wspomagania programowania, Pythona z bibliotekami do analizy danych (pandas, numpy, plotly, scipy) oraz środowiska Jupyter do dokumentowania i prezentacji wyników.

> **Dla studentów:** Kod w tym repozytorium ma charakter informacyjny i poglądowy — służy jako podpowiedź i punkt wyjścia. Proszę tworzyć własne obliczenia samodzielnie, korzystając z tego kodu tylko gdy jest to konieczne. Korzystanie z pomocy LLM jest mile widziane, ale pamiętajcie — **to Wy odpowiadacie za poprawność wyników**.

### Zawartość

| Notebook | Temat |
|----------|-------|
| `00_llm_agents_for_coding` | Prezentacja: agenci LLM w tworzeniu kodu, konfiguracja środowiska |
| `01_data_acquisition` | Pobieranie danych hydrologicznych z archiwum IMGW |
| `02_data_quality` | Kontrola jakości danych, uzupełnianie luk |
| `03_hydro_statistics` | Statystyka hydrologiczna: FDC, przepływy charakterystyczne |

#### Moduły (`src/`)

| Moduł | Opis |
|-------|------|
| `imgw_data.py` | Pobieranie i parsowanie danych IMGW (2 formaty CSV, Parquet) |
| `hydrology.py` | Detekcja luk, interpolacja, korelacja stacji, outliers |
| `hydrology.py` | Krzywa uporządkowana przepływu, NNQ/SNQ/SSQ/SWQ/WWQ |

### Źródło danych

Dane hydrologiczne z publicznego archiwum [IMGW](https://danepubliczne.imgw.pl/data/dane_pomiarowo_obserwacyjne/dane_hydrologiczne/dobowe/) — dobowe stany wody i przepływy.

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
cd notebooks
jupyter lab 01_data_acquisition.ipynb
```

Lub otwórz notebooki w VS Code (rozszerzenie Jupyter).

### Jak to powstało

Projekt został stworzony wspólnie z agentem LLM (Claude Code). Każdy notebook zawiera przykładowe prompty, które mogłyby wygenerować dany kod — jako materiał dydaktyczny o pracy z AI.

Szczegóły metodologii: [`ai/methodology.md`](ai/methodology.md)

---

## EN — English

Teaching materials — reusable modules in `src/`, step-by-step analyses in `notebooks/`.

**Course objectives:** The primary goal is learning hydropower plant design calculations (hydrology, energy potential, turbine selection). An additional goal is hands-on experience with modern tools: LLM agents for programming assistance, Python data analysis libraries (pandas, numpy, plotly, scipy), and the Jupyter environment for documenting and presenting results.

> **For students:** The code in this repository is provided for reference and as a starting point. Please create your own calculations independently, reusing this code only when necessary. LLM assistance is encouraged, but remember — **you are responsible for the correctness of your results**.

### Contents

| Notebook | Topic |
|----------|-------|
| `00_llm_agents_for_coding` | Presentation: LLM agents for coding, environment setup |
| `01_data_acquisition` | Downloading hydrological data from IMGW archive |
| `02_data_quality` | Data quality control, gap filling |
| `03_hydro_statistics` | Hydrological statistics: FDC, characteristic flows |

#### Modules (`src/`)

| Module | Description |
|--------|-------------|
| `imgw_data.py` | IMGW data download & parsing (2 CSV format eras, Parquet output) |
| `hydrology.py` | Gap detection, interpolation, station correlation, outliers |
| `hydrology.py` | Flow duration curve, NNQ/SNQ/SSQ/SWQ/WWQ characteristic flows |

### Data source

Hydrological data from the public [IMGW](https://danepubliczne.imgw.pl/data/dane_pomiarowo_obserwacyjne/dane_hydrologiczne/dobowe/) archive — daily water levels and discharge (Polish Institute of Meteorology and Water Management).

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
cd notebooks
jupyter lab 01_data_acquisition.ipynb
```

Or open notebooks in VS Code (Jupyter extension).

### How it was built

This project was built collaboratively with an LLM agent (Claude Code). Each notebook contains example prompts that could generate the code — serving as teaching material about working with AI.

Methodology details: [`ai/methodology.md`](ai/methodology.md)

---

## Project structure

```
├── ai/                  # Project docs, plan, methodology
├── data/
│   ├── raw/             # Downloaded IMGW ZIPs (not in repo)
│   └── processed/       # Processed Parquet files (not in repo)
├── src/                 # Reusable Python modules
├── notebooks/           # Jupyter notebooks
├── environment.yml      # Conda environment
├── requirements.txt     # pip dependencies
└── .gitignore
```

## License / Licencja

MIT — see [LICENSE](LICENSE)
