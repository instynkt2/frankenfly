# Instalacja obok innych projektów — bez Dockera

Ten wariant jest przeznaczony dla istniejącego serwera Ubuntu 24.04 z Pythonem
3.12 i systemd. Dodaje tylko Frankenfly. Nie instaluje pakietów systemowych,
nie aktualizuje systemu ani globalnego Pythona, nie zmienia Nginx/Caddy,
firewalla, SSH ani konfiguracji innych aplikacji. Nie restartuje serwera ani
pozostałych usług. `systemctl daemon-reload` wczytuje nowe definicje jednostek;
nie jest restartem działających usług.

## Zasoby i granice instalacji

| Element | Ustawienie |
| --- | --- |
| Kod | `/opt/frankenfly/app`, przypięty commit aplikacji |
| Instalator | `/opt/frankenfly/installer.py` |
| Pakiety Pythona | Osobne `/var/lib/frankenfly/venv` |
| Dane i stan | `/var/lib/frankenfly/data` i `/var/lib/frankenfly/state` |
| Usługi | Tylko `frankenfly-setup.service` i `frankenfly.service` |
| Użytkownik procesu | Nieuprzywilejowany, tworzony przez systemd DynamicUser |
| Port | `127.0.0.1:18080`; aplikacja początkowo dostępna tylko lokalnie |
| Przygotowanie | Maks. 1536 MiB RAM, bez swapu, maks. 50% jednego rdzenia |
| Działanie | Maks. 768 MiB RAM, bez swapu, maks. 50% jednego rdzenia, 2 obserwacje/s |
| Priorytet | Obniżony CPU i I/O; ograniczona liczba jednoczesnych zapytań |

Limity dotyczą procesów Frankenfly, nie innych projektów. Proces przygotowania
kończy się przed uruchomieniem aplikacji, więc nie sumują się ich maksymalne
limity. Wspólny host nadal dzieli CPU, dysk i RAM między procesami; ograniczenia
nie gwarantują zupełnego braku wpływu na opóźnienia innych aplikacji.

Instalator wymaga co najmniej 2560 MiB **dostępnego** RAM-u oraz 10 GiB wolnego
dysku i sprawdza, czy port 18080 jest wolny. Odmawia nadpisania istniejącego
katalogu, konta lub usługi Frankenfly. W razie konfliktu kończy pracę.

## Uruchomienie

Pobierz `scripts/install_native.py` z przejrzanego commita tego repozytorium.
Nie wklejaj do skryptu żadnych haseł. Samo sprawdzenie warunków jest tylko do
odczytu:

```bash
python3 install_native.py --check
```

Instalacja jako root:

```bash
python3 install_native.py
```

Instalator pobiera przypiętą wersję kodu, dodaje własne jednostki systemd i
uruchamia przygotowanie w tle. Zamknięcie konsoli nie przerywa przygotowania.
Przygotowanie tworzy własny venv bez wymagania pakietu `python3-venv`, instaluje
przypięte zależności z gotowych kół PyPI oraz buduje prawdziwy model z danych
FlyEM z weryfikacją sum kontrolnych. Zależności nie trafiają do systemowego
Pythona. Powodzenie uruchamia aplikację; błąd zatrzymuje tylko przygotowanie
Frankenfly. Nie podnosimy automatycznie limitów ani nie zwalniamy zasobów
przez zatrzymywanie innych procesów.

Postęp i wynik:

```bash
journalctl -u frankenfly-setup -n 25 --no-pager
systemctl status frankenfly --no-pager
curl -fsS http://127.0.0.1:18080/healthz
```

Oczekiwany wynik ostatniego polecenia: `{"ready":true,"status":"live"}`.
Po błędzie zachowaj logi. Instalator nie usuwa automatycznie częściowej
instalacji; po wyjaśnieniu przyczyny można powtórzyć tylko przygotowanie przez
`systemctl start frankenfly-setup`, o ile aplikacja nie jest już uruchomiona.
Nie uruchamiaj przygotowania równolegle z działającą aplikacją.

Pierwszy podgląd można otworzyć przez tunel SSH, używając faktycznego portu SSH
tego serwera. Publiczna domena i HTTPS wymagają osobnej konfiguracji po
potwierdzeniu poprawnego działania. Instalator nie zajmuje portów 80/443.

Klucz operatora jest generowany na serwerze i zapisany z prawami 0600 w
`/var/lib/frankenfly/operator.env`. Nie pojawia się w logach ani w repozytorium.
Odczytuj go tylko lokalnie na serwerze; nie przesyłaj go w rozmowie.

## Weryfikacja i ograniczenia

Lokalnie sprawdzono odmowę nadpisania istniejących plików, bezpieczne
rozpakowanie rzeczywistego archiwum GitHuba, składnię jednostek systemd 255,
bootstrap pip w pustym venv bez ensurepip i ponowne zbudowanie pełnego modelu.
Import osiągnął **1301,8 MiB szczytowego RSS** i odtworzył
identyczny SHA-256 grafu. RSS jednego procesu nie jest całkowitym zużyciem
pamięci cgroup. Limity, DynamicUser, instalacja pełnych zależności i uruchomienie
usług wymagają potwierdzenia na docelowym hoście; lokalne środowisko nie ma
działającego menedżera systemd.

Mechanizmy: [środowiska venv](https://docs.python.org/3.12/library/venv.html),
[limity systemd](https://www.freedesktop.org/software/systemd/man/latest/systemd.resource-control.html).
