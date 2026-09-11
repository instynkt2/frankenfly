# Frankenfly na Hetznerze

Potrzebny jest serwer, na którym można uruchamiać programy: Hetzner Cloud VPS
albo serwer dedykowany. Sam Storage Box jest magazynem plików i nie zastąpi VPS.
Nie potrzeba osobnego dysku ani GPU, jeśli serwer ma odpowiedni zapas zasobów.

## Konfiguracja na początek

| Element | Propozycja |
| --- | --- |
| CPU | 2 vCPU na pierwszą próbę; 4 vCPU daje zapas dla aplikacji i ruchu HTTP |
| RAM | 4 GB na start; 8 GB komfortowo do budowania i obsługi dodatkowych procesów |
| Dysk | Co najmniej 10 GB wolnego miejsca; 20 GB daje wygodny zapas |
| System | Ubuntu 24.04 LTS lub kompatybilny Linux z Dockerem |
| GPU | Niepotrzebne w tej wersji |
| Domena | Potrzebna do wygodnego publicznego adresu HTTPS |

To budżet startowy, a nie pomiar konkretnego planu Hetznera. Jeden model
wykonuje się głównie na jednym rdzeniu. Lepsza wydajność pojedynczego rdzenia
może pomóc bardziej niż sama liczba vCPU. Widzowie odczytują wspólną symulację;
nie uruchamiają oddzielnych mózgów. Publiczny ruch trzeba zmierzyć po wdrożeniu.

## Przygotowanie

1. Zaloguj się przez SSH do serwera. Jeśli stoi tam już inna aplikacja, sprawdź
   wolne zasoby oraz zajętość portów 80 i 443 przed włączeniem Caddy.
2. Zainstaluj Docker Engine i plugin Docker Compose zgodnie z
   [oficjalną instrukcją dla Ubuntu](https://docs.docker.com/engine/install/ubuntu/).
3. Pobierz repozytorium albo rozpakuj paczkę Frankenfly na serwerze. Przejdź do
   katalogu, w którym znajdują się `compose.yaml` i `Dockerfile`.
4. Wykonaj:

```bash
python3 scripts/make_env.py
docker compose build
docker compose --profile setup run --rm prepare
docker compose up -d app
docker compose logs -f app
```

Skrypt `make_env.py` zapisuje losowy klucz operatora w `.env` z ograniczonym
dostępem. Nie nadpisuje istniejącego pliku. Nie wysyłaj klucza w czacie ani na
GitHub. Klucz aplikacji nie ma nic wspólnego z portfelem kryptowalutowym.

Przygotowanie pobiera około 566 MB danych naukowych i tworzy lokalny model.
Późniejsze restarty korzystają z tego samego woluminu. Brak danych lub błąd
sumy kontrolnej powoduje komunikat o nieaktywnym mózgu; aplikacja nie udaje
wtedy działającej symulacji.

## Pierwsze otwarcie bez publikacji

Na swoim komputerze uruchom tunel:

```bash
ssh -L 8000:127.0.0.1:8000 user@ADRES_IP_SERWERA
```

Otwórz `http://localhost:8000`. Przycisk **Take controls** przyjmuje klucz
operatora zapisany na Twoim serwerze w `.env`. Przez tunel można sprawdzić
działanie, zanim podłączysz domenę.

## Publiczna strona

Ustaw rekord DNS A domeny na adres IPv4 serwera. Rekord AAAA dodaj tylko przy
działającym IPv6. W `.env` ustaw `FRANKENFLY_DOMAIN=twoja-domena.example`
(wpisz swoją rzeczywistą domenę, bez `https://` i bez ścieżki). Otwórz TCP 80 i
443; UDP 443 jest opcjonalny dla HTTP/3. Następnie:

```bash
docker compose --profile public up -d
docker compose ps
docker compose logs --tail=100 caddy
```

Caddy obsługuje HTTPS. Jeżeli Twój serwer ma już reverse proxy, podłącz je do
aplikacji zamiast uruchamiać drugą usługę na tych samych portach.

## Aktualizacja i dane

```bash
git pull --ff-only
docker compose build app
docker compose up -d app
```

Dane modelu są w woluminie `connectome`, a stan sesji w `brain-state`.
Zwykłe `docker compose down` zachowuje dane. **Nie dodawaj `-v`, jeśli chcesz
zachować woluminy.** Przed większą aktualizacją zrób snapshot serwera lub kopię
woluminu ze stanem. Logi mają ograniczony rozmiar, żeby nie rosły bez końca.

Serwer uruchamia dokładnie jeden proces symulacji. Nie zwiększaj liczby
workerów Uvicorna: stworzyłoby to osobne, niespójne sesje tego samego kota.

## Co potrzebne do kolejnego kroku

Nazwa/model serwera lub informacja o CPU, RAM i wolnym dysku; system
operacyjny; informacja, czy inne aplikacje używają portów 80/443; docelowa
domena. Do wyboru konfiguracji nie trzeba podawać haseł ani prywatnych kluczy.

Źródła: [serwery Hetzner Cloud](https://docs.hetzner.com/cloud/servers/overview/),
[Docker Compose](https://docs.docker.com/compose/).
