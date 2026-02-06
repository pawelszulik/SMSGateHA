# SMS Gate – integracja Home Assistant

Integracja **SMS Gate** ( [SMS Gateway for Android](https://docs.sms-gate.app/) ) dla Home Assistant w trybie **tylko Local**: telefon z aplikacją w sieci lokalnej, wysyłanie SMS przez notify i serwis, szablony wiadomości, nazwani odbiorcy oraz przeglądanie statusu i ostatnich wiadomości.

## Wymagania

- Home Assistant 2024.x lub nowszy (zalecane)
- Aplikacja [SMS Gateway for Android](https://github.com/capcom6/android-sms-gateway/releases) na telefonie w trybie **Local Server**
- Telefon i Home Assistant w tej samej sieci (LAN)

## Instalacja

### HACS (rekomendowane)

1. Zainstaluj [HACS](https://hacs.xyz/).
2. HACS → Integracje → Menu (⋮) → Custom repositories.
3. Dodaj repozytorium: `https://github.com/pawelszulik/SMSGateHA`
4. Kategoria: **Integration**.
5. Zainstaluj integrację **SMS Gate**.
6. Zrestartuj Home Assistant.

Uwaga: HACS jako „wersję” potrafi pokazać hash commita (np. `13db7b8`). Jeśli zobaczysz błąd typu:  
`The version 13db7b8 for this integration can not be used with HACS.`  
zainstaluj integrację **ręcznie** (poniżej) albo wybierz wersję z **GitHub Releases** (gdy jest dostępna).

### Ręczna instalacja

1. Sklonuj lub pobierz to repozytorium.
2. Skopiuj folder `custom_components/sms_gate` do katalogu `custom_components` w konfiguracji Home Assistant (docelowo: `/config/custom_components/sms_gate`).
3. Zrestartuj Home Assistant.

Po każdej aktualizacji plików w `custom_components/sms_gate` zrestartuj Home Assistant, aby zmiany zostały zastosowane.

## Konfiguracja

1. **Ustawienia** → **Urządzenia i usługi** → **Dodaj integrację**.
2. Wyszukaj **SMS Gate**.
3. Wpisz:
   - **Adres IP** – IP telefonu z aplikacją (np. 192.168.1.10),
   - **Port** – port Local Server (domyślnie 8080),
   - **Nazwa użytkownika** i **Hasło** – dane z zakładki Local Server w aplikacji.
4. Po połączeniu (test health) zatwierdź konfigurację.

Dane logowania znajdziesz w aplikacji SMS Gateway: **Home** → sekcja **Local Server** (po włączeniu serwera).

## Opcje integracji (numery i szablony)

W konfiguracji integracji wybierz **Opcje** (lub kliknij wpis SMS Gate → Opcje).

- **Odbiorcy** – jedna linia na wpis w formacie `nazwa: numer`, np.  
  `alarm: +48123456789`  
  `dom: +48987654321`
- **Szablony** – jedna linia na wpis w formacie `nazwa: treść`, z placeholderami Jinja2, np.  
  `alarm: Alarm: {{ message }} – {{ entity_id }}`  
  `awaria: Awaria: {{ friendly_name }}`

Placeholdery (w szablonach i automacjach): `{{ message }}`, `{{ entity_id }}`, `{{ friendly_name }}`, oraz dowolne zmienne przekazane w `data`.

## Wysyłanie SMS

### Notify

Usługa: `notify.send_message` (lub `notify.sms_gate` po nadaniu nazwy encji).

- **message** – treść wiadomości (lub bazowa przy szablonie).
- **data** (opcjonalnie):
  - **recipients** – lista numerów lub nazw z opcji (np. `["alarm", "+48111222333"]`),
  - **template** – nazwa szablonu z opcji,
  - **data** – słownik zmiennych do szablonu.

Przykład automacji (YAML):

```yaml
service: notify.send_message
data:
  message: "Wykryto dym w kuchni"
  target:
    - entity_id: notify.sms_gate
  data:
    recipients:
      - alarm
    template: alarm
    data:
      entity_id: sensor.smoke_kitchen
```

### Serwis sms_gate.send_sms

Usługa: `sms_gate.send_sms`.

- **message** (wymagane) – treść wiadomości.
- **recipients** (wymagane) – jeden numer lub lista (nazwy z opcji lub numery).
- **template** (opcjonalnie) – nazwa szablonu.
- **data** (opcjonalnie) – zmienne do szablonu.
- **entity_id** (opcjonalnie) – encja notify (np. `notify.sms_gate`), gdy masz **kilka bramek** – wybór, przez którą wysłać.
- **device_id** (opcjonalnie) – ID urządzenia bramki (alternatywa do entity_id). Bez podania używany jest pierwszy wpis integracji.

Przykład:

```yaml
service: sms_gate.send_sms
data:
  message: "Alarm: czujnik dymu"
  recipients:
    - alarm
```

## Encje (sensory)

- **Status** – `available` / `unavailable` (połączenie z bramką).
- **Ostatnie wiadomości** – liczba ostatnich wiadomości; atrybut **messages** z listą (id, odbiorca, status, device_id). Statusy: Pending, Processed, Sent, Delivered, Failed.
- **Liczba oczekujących** – liczba wiadomości w stanie Pending (w kolejce).

Dane odświeżane co 60 s z API SMS Gate (`GET /messages`).

## Przykłady automacji

- **Alarm (czujnik dymu)** – trigger: stan czujnika „wykryto dym” → akcja: `notify.send_message` z szablonem alarm i odbiorcą „alarm”.
- **Awaria pompy** – trigger: binary_sensor pompy „on” dłużej niż X minut → akcja: `sms_gate.send_sms` z message i odbiorcą „dom”.
- **Przypomnienie** – trigger: czas (np. 8:00) → akcja: notify z listą odbiorców i zwykłym message.

## Rozwiązywanie problemów

- **Nie można połączyć** – sprawdź IP i port (Local Server w aplikacji), czy HA i telefon są w tej samej sieci, czy serwer w aplikacji jest włączony (Online).
- **Nieprawidłowa nazwa użytkownika lub hasło** – skopiuj dokładnie z aplikacji (Local Server).
- **SMS nie wychodzi** – sprawdź sensory (status, ostatnie wiadomości); przy Failed zobacz atrybuty wiadomości. Sprawdź limit/opóźnienia w ustawieniach aplikacji SMS Gate.

## Testy

W katalogu projektu:

```bash
pip install -q pytest pytest-asyncio aiohttp
python -m pytest tests/ -v
```

Uwaga: pełna pula testów (w tym config_flow) może wymagać środowiska z zainstalowanym Home Assistant (np. Linux). Na Windows bez HA można uruchomić np. tylko `tests/test_api.py` po ustawieniu `PYTHONPATH=.`.

## Licencja

MIT (zgodnie z plikiem LICENSE w repozytorium).

## Autor / Codeowners

Integracja dla [SMS Gateway for Android](https://docs.sms-gate.app/) (tryb Local).  
