# hydropower-notebooks

Zestaw notebooków Jupyter do analiz hydrologicznych i projektowania Małych Elektrowni Wodnych (MEW).

Materiały dydaktyczne — kod wielokrotnego użytku w `src/`, analizy krok po kroku w `notebooks/`.

## Zawartość

| Notebook | Temat |
|----------|-------|
| `00_llm_agents_for_coding` | Prezentacja: agenci LLM w tworzeniu kodu, konfiguracja środowiska |
| `01_data_acquisition` | Pobieranie danych hydrologicznych z archiwum IMGW |
| `02_data_quality` | Kontrola jakości danych, uzupełnianie luk |
| `03_hydro_statistics` | Statystyka hydrologiczna: FDC, przepływy charakterystyczne |

### Moduły (`src/`)

| Moduł | Opis |
|-------|------|
| `imgw.py` | Pobieranie i parsowanie danych IMGW (2 formaty CSV, Parquet) |
| `data_quality.py` | Detekcja luk, interpolacja, korelacja stacji, outliers |
| `hydro_stats.py` | Krzywa sum czasów przepływu, NNQ/SNQ/SSQ/SWQ/WWQ |

## Źródło danych

Dane hydrologiczne z publicznego archiwum [IMGW](https://danepubliczne.imgw.pl/data/dane_pomiarowo_obserwacyjne/dane_hydrologiczne/dobowe/) — dobowe stany wody i przepływy.

## Wymagania

- Python 3.11+
- Miniconda (zalecane) lub pip

### Instalacja

```bash
# Miniconda
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

## Struktura projektu

```
├── ai/                  # Dokumentacja projektu, plan, metodologia
├── data/
│   ├── raw/             # Pobrane ZIP z IMGW (nie w repo)
│   └── processed/       # Przetworzone Parquet (nie w repo)
├── src/                 # Moduły Pythona
├── notebooks/           # Notebooki Jupyter
├── environment.yml      # Środowisko conda
├── requirements.txt     # Zależności pip
└── .gitignore
```

## Jak to powstało

Projekt został stworzony wspólnie z agentem LLM (Claude Code). Każdy notebook zawiera przykładowe prompty, które mogłyby wygenerować dany kod — jako materiał dydaktyczny o pracy z AI.

Szczegóły metodologii: [`ai/methodology.md`](ai/methodology.md)

## Licencja

MIT — patrz [LICENSE](LICENSE)
