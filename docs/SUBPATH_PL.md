# Frankenfly pod octra.pl/frankenfly

Aplikacja może działać pod `https://octra.pl/frankenfly/`, korzystając z
istniejącego serwera HTTPS. Backend pozostaje na `127.0.0.1:18080`.

HTML, grafika i zapytania API używają adresów względnych. Dzięki temu trafiają
do `/frankenfly/assets/...` i `/frankenfly/api/...`, a nie do głównych ścieżek
Octry. Wariant na osobnej domenie oraz lokalny podgląd nadal działają.

## Przygotowane pliki

- `update.py`: sprawdza sumy kontrolne istniejącego HTML i JavaScriptu,
  pobiera ich nową, przypiętą wersję i aktualizuje tylko te dwa pliki.
  Zachowuje kopie poprzednich plików i odmawia nadpisania własnych zmian.
  Nie wymaga restartu aplikacji ani przygotowywania modelu.
- `deploy/frankenfly-location.conf`: dwa bloki `location` przeznaczone do
  włączenia **wewnątrz istniejącego bloku HTTPS dla octra.pl**. Nie jest to
  samodzielny plik do wrzucenia w globalne `conf.d` w kontekście `http`.

Nginx przekierowuje `/frankenfly` na `/frankenfly/` i przekazuje żądania
z tego podkatalogu do backendu po usunięciu prefiksu. `^~` zapobiega
przechwyceniu zasobów Frankenfly przez istniejące reguły rozszerzeń plików.
Nie tworzymy reguł dla głównych `/api`, `/assets` ani `/` serwisu Octry.

## Kolejność wdrożenia

1. Odczytać aktywną konfigurację Nginxa i ustalić plik oraz dokładny blok
   HTTPS obsługujący `octra.pl`. Zweryfikować, że nie ma już reguły ani
   istniejącej zawartości pod `/frankenfly`. Sprawdzić `nginx -t` przed zmianą.
2. Zaktualizować tylko frontend Frankenfly z przypiętego commita:
   `python3 update.py --revision COMMIT_SHA --apply`.
3. Zachować kopię konfiguracji domeny i przygotować minimalne dodanie
   załączenia dwóch nowych bloków `location` w tym jednym bloku serwera.
   Istniejące reguły, certyfikaty, węzeł Octry i inne domeny pozostają bez zmian.
4. Wykonać `nginx -t`. Przy błędzie odtworzyć zapisany plik bez przeładowania.
   Po poprawnym wyniku przeładować konfigurację Nginxa, bez zatrzymywania
   procesu. Nie restartować węzła Octry ani aplikacji Frankenfly.
5. Sprawdzić po HTTPS stronę główną Octry, dotychczasowe podstrony i nowy
   podkatalog: przekierowanie, HTML, CSS, JavaScript, obrazek, `/healthz`,
   `/api/state` i odrzucanie nieuwierzytelnionych poleceń operatora.

Na etapie przygotowania kodu konfiguracja Nginxa na serwerze nie została
zmieniona. Docelowy fragment trzeba dopasować do odczytanego pliku domeny;
nie zakładamy jego nazwy ani struktury.

## Sprawdzenie

Testy `tests/test_subpath.py` rozwiązują odwołania z rzeczywistego HTML i JS
tak, jak robi to przeglądarka, zarówno pod `/`, jak i `/frankenfly/`. Sprawdzają,
że zasoby i API pozostają pod swoim prefiksem i wskazują istniejące endpointy.
Nie zastępuje to testu na docelowym Nginxie, którego nie ma w środowisku lokalnym.

Dokumentacja: [proxy_pass](https://nginx.org/en/docs/http/ngx_http_proxy_module.html#proxy_pass),
[wybór location](https://nginx.org/en/docs/http/ngx_http_core_module.html#location).
