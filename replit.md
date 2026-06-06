# Typer MŚ 2026

Aplikacja do typowania wyników meczów Mistrzostw Świata 2026, napisana w Pythonie z użyciem Streamlit. UI w języku polskim.

## Run & Operate

- `streamlit run app.py --server.port 5000` — uruchom aplikację
- Required: Python 3.11, Streamlit

## Stack

- Python 3.11
- Streamlit (UI framework)
- JSON files for data storage (data/)

## Where things live

- `app.py` — cała logika aplikacji (logowanie, taby, scoring, admin)
- `data/users.json` — użytkownicy i ich PINy
- `data/matches.json` — lista meczów (z wynikami po wpisaniu przez admina)
- `data/bets.json` — typy użytkowników
- `data/extra_bets.json` — typy dodatkowe (król strzelców, MVP, etc.)
- `.streamlit/config.toml` — konfiguracja serwera Streamlit

## Product

Aplikacja do typowania wyników meczów MŚ 2026:
- Logowanie bez e-mail: wybór imienia z dropdownu + PIN 4-cyfrowy
- Tab 1 (Obstawianie): typowanie wyników meczów
- Tab 2 (Typy Dodatkowe): król strzelców, MVP, najlepszy bramkarz, najlepszy U21
- Tab 3 (Ranking): tabela punktowa posortowana malejąco
- Tab 4 (Panel Administratora): chroniony PINem admina, wprowadzanie rzeczywistych wyników

## Scoring

- 5 pkt — dokładny wynik (np. przewidziano 2:1, wynik 2:1)
- 2 pkt — dobry wynik meczu (wygrana/remis/przegrana), ale zły dokładny wynik
- 0 pkt — zły wynik meczu

## User preferences

- UI w języku polskim
- Prosty system logowania bez e-mail

## Gotchas

- Admin PIN: `9999` (można zmienić w app.py, zmienna `ADMIN_PIN`)
- Domyślni użytkownicy i ich PINy są w `data/users.json`
- Po dodaniu nowych użytkowników przez panel admina, plik JSON jest aktualizowany natychmiast
- `st.rerun()` zamiast `experimental_rerun` (wymaganie środowiska)
