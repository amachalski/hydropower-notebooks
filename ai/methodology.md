# Metodologia tworzenia projektu z agentem LLM

## Kontekst
Projekt EW (Energetyka Wodna) — notebooki Jupyter do analiz hydrologicznych i projektowania MEW.
Stworzony wspólnie z Claude Code (agent LLM) w sesji ~2h.

## Struktura projektu

```
projekt/
├── ai/              # Pliki dla agenta AI (CLAUDE.md, plan, metodologia)
├── data/
│   ├── raw/         # Surowe dane (gitignored)
│   └── processed/   # Przetworzone Parquet (gitignored)
├── src/             # Moduły Pythona wielokrotnego użytku
├── notebooks/       # Notebooki Jupyter (numerowane krokami)
├── environment.yml  # Conda env
├── requirements.txt # pip
└── .gitignore
```

## Zasady współpracy z agentem

### 1. Podział kodu: src/ vs notebooks/
- **src/** — moduły wielokrotnego użytku (download, parsing, statystyki)
- **notebooks/** — analiza krok po kroku, importuje z src/
- Agent ma tendencję do pisania wszystkiego w jednym pliku — trzeba przypominać o modularności

### 2. Notebooki dydaktyczne — struktura komórki
Każda komórka kodu powinna być poprzedzona komórką markdown z:
- **Prompt do LLM** — przykładowe zapytanie, które mogłoby wygenerować ten kod
- **Użyte moduły/funkcje** — co z src/ jest wykorzystywane
Na początku notebooka: prompt tworzący cały moduł src/ używany w danym notebooku.

### 3. Dane zewnętrzne
- Surowe dane (ZIP, CSV) w data/raw/ — gitignored, cache'owane lokalnie
- Przetworzone dane w Parquet (nie CSV!) — zachowuje typy, kompresja, bez problemów z kodowaniem
- Download uruchamiany raz — ponowne uruchomienie pomija istniejące pliki

### 4. Język
- Tekst w notebookach: **polski**
- Kod, zmienne, komentarze: **angielski**
- Polskie znaki w JSON (notebooki .ipynb) mogą powodować problemy — generować przez json.dumps()

### 5. Wykresy
- **Plotly** — interaktywne wykresy w notebooku
- Plotly nie działa w prezentacjach RISE bez dodatkowej konfiguracji

### 6. Prezentacje
- Jupyter notebook z metadanymi slideshow (`slide`, `subslide`, `fragment`, `skip`)
- **RISE / jupyterlab-rise** — prezentacja w przeglądarce z możliwością uruchamiania kodu
- VS Code NIE obsługuje trybu slideshow
- Alternatywa: **Marp** (VS Code) — ale bez interaktywnego kodu

### 7. Środowisko
- **Miniconda** — conda env z environment.yml
- Dodać **pyarrow** (Parquet), **statsmodels** (trendline OLS w plotly)
- `conda activate` nie działa w cmd bez `conda init` — użyj pełnej ścieżki

## Typowe problemy i rozwiązania

### JSON escape w notebookach
- Backslash w ścieżkach Windows (`C:\Users`) psuje JSON — używaj forward slash
- Polskie cudzysłowy „" mogą powodować problemy
- **Rozwiązanie:** Generuj notebooki przez skrypt Python z json.dumps()

### Kodowanie danych IMGW
- Pre-2023: CP-1250, separator przecinek, cudzysłowy wokół pól
- 2023+: UTF-8-sig, separator średnik, bez cudzysłowów
- Niektóre pliki 2023+ nadal w CP-1250!
- **Rozwiązanie:** Auto-detekcja kodowania (try/except) i separatora (sprawdź `;` w pierwszej linii)

### Wartości strażnikowe IMGW
- `9999` — brak danych stanu wody
- `99999.999` — brak danych przepływu
- `99.9` — brak danych temperatury (nie używamy)
- **Rozwiązanie:** Zamiana na NaN podczas parsowania

### Quoting w CSV
- Stare pliki mają `" 151160150"` (cudzysłów + spacja + ID)
- Z `quoting=QUOTE_NONE` pandas czyta cudzysłowy jako część wartości
- **Rozwiązanie:** Auto-detekcja: `;` → QUOTE_NONE, `,` → QUOTE_ALL

### Kernel Jupyter po zmianach w src/
- Po edycji pliku w src/ kernel ma starą wersję w pamięci
- **Rozwiązanie:** Restart kernel + Run All

## Workflow tworzenia nowego notebooka

1. Opisz agentowi cel notebooka i jakie moduły src/ są potrzebne
2. Poproś o stworzenie modułu src/ — z promptem do LLM na początku
3. Poproś o notebook z komórkami: markdown (prompt + opis) → kod → wynik
4. Przetestuj — napraw błędy (encoding, sentinel values, quoting)
5. Dodaj do environment.yml brakujące pakiety
6. Commituj

## Kolejne kroki projektu

- [ ] 04_power_potential.ipynb — P = ρgQH, energia roczna z FDC
- [ ] 05_turbine_selection.ipynb — dobór turbiny (H vs Q diagram)
- [ ] 06_kaplan_design.ipynb — projekt turbiny Kaplana
