# AGENTS.md — guida per chi sviluppa (persone e agenti AI)

Memoria di progetto: leggila prima di modificare il codice e aggiornala quando cambi architettura, decisioni o stato.
Lingua: codice commentato e log in **italiano**; README, CHANGELOG, `strings.json`/`en.json` e card in **inglese**
(repo pubblico), `it.json` in italiano.

- [README.md](README.md): documentazione per l'utente (inglese).
- [CHANGELOG.md](CHANGELOG.md).
- `docs/ENVIRONMENTS.local.md` (**non versionato**): host, IP e stato delle installazioni reali.

## Obiettivo

`custom_components/changedetection_ha_sensors` (nome "Changedetection HA sensors", repo GitHub pubblico
`ilbagatta/changedetection-ha-sensors`, installabile da HACS come repository personalizzato) porta in HA i watch di una
istanza **changedetection.io** (API REST v1): un sensore prezzo per watch con prezzo precedente, card Lovelace inclusa.
Sostituisce il vecchio `command_line` + script bash + card markdown dell'HA di casa.

## Struttura

```
custom_components/changedetection_ha_sensors/
  __init__.py     setup: registra la card (static path + add_extra_js_url), coordinator, piattaforme
  api.py          client aiohttp: /systeminfo, /watch, /watch/{uuid}/history[/{ts}], recheck, recheck_all
  parse.py        funzioni pure: extract_price, extract_stock, clean_text, trend
  coordinator.py  DataUpdateCoordinator[dict[uuid, Watch]]; storico riletto solo se last_changed cambia; evento
  entity.py       dispositivo "Changedetection.io" (server) + un dispositivo per watch (via_device)
  sensor.py       Price, Last changed (per watch); Recent changes, Watches (server)
  button.py       Recheck (per watch), Recheck all
  config_flow.py  user (url, api_key, verify_ssl), reauth, reconfigure, opzioni
  frontend/changedetection-card.js   card JS senza build (+ editor con ha-form)
  brand/icon.png, icon@2x.png        icona (richiesta dal validatore HACS), disegnata con Pillow
tests/            pytest con HA vero (pytest-homeassistant-custom-component), server finto in conftest.py
```

## Decisioni

- **Prezzo**: dal testo dell'ultima rilevazione. Prima `Price: x` (processore `restock_diff`), altrimenti il primo importo
  con due decimali (gestisce `1.299,00` e `1,299.50`). Con piu' importi si prende il primo (es. Amazon "€22.79 €11.40":
  il secondo e' il prezzo unitario).
- **Prezzo precedente**: si risale lo storico (max `history_depth`, default 10) fino al primo prezzo **diverso** da quello
  attuale: le rilevazioni in cui cambia solo la disponibilita' vengono saltate.
- **Carico sul server**: a ogni giro solo `GET /watch`; storico e snapshot solo per i watch con `last_changed` nuovo
  (cache nel coordinator, non persistita: al riavvio si rilegge tutto una volta). Max 4 richieste parallele.
- **Evento** `changedetection_ha_sensors_change` (dati = `Watch.as_dict()`): mai al primo caricamento ne' per watch nuovi.
- **Sensore Recent changes**: stato = ora dell'ultima modifica; attributo `watches` = **tutti** i watch dal piu'
  recente (max `MAX_LIST_ITEMS`), escluso dal recorder. Righe (`limit`) ed esclusioni (`exclude`, uuid) le decide la card;
  l'opzione `limit` dell'integrazione e' stata tolta nella 0.2.0; attributo `changedetection_card: true` usato dalla card per trovare l'entita' da sola.
- **Opzioni numeriche**: il `NumberSelector` restituisce float; si salvano come int e si leggono sempre con
  `const.int_option()` (bug della 0.1.1: `slice indices must be integers`).
- **Valuta**: opzione (default EUR), il prezzo e' `device_class: monetary` senza `state_class`.
- Watch nuovi: entita' aggiunte al volo; watch eliminati: entita' non disponibili, dispositivo rimovibile a mano.
- Card servita dall'integrazione (`/changedetection_ha_sensors/changedetection-card.js?v=VERSION`): niente risorsa Lovelace.

## Sviluppo

```
python3.13 -m venv .venv && .venv/bin/pip install -r requirements_test.txt
.venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/pytest -q
```

Nei test l'aggiornamento periodico del coordinator gira in background: usare
`hass.async_block_till_done(wait_background_tasks=True)` dopo `async_fire_time_changed`.

Versione: tenere allineate `manifest.json`, `const.VERSION`, `CARD_VERSION` nella card, `pyproject.toml`, CHANGELOG.

### Rilasci (regola dell'utente)

Ogni aggiornamento esce come **release GitHub** (`vX.Y.Z`, `--latest`) con **note brevi**: HACS le mostra nel popup di
aggiornamento di HA. Formato fisso, prima italiano poi inglese:

```
### 🇮🇹 Novità
- ✨ **Nuovo** …   /   🐛 **Corretto** …   /   🎨 **Card** …   (3-5 voci al massimo, linguaggio da utente)

**Dopo l'aggiornamento:** riavvia Home Assistant (e/o ricarica il browser per la card).

---

### 🇬🇧 What's new
- (stesse voci in inglese)

**After updating:** …
```

Niente dettagli tecnici interni nelle note (quelli vanno nel CHANGELOG). Ordine: test e ruff verdi → commit → push →
CI verde → `gh release create vX.Y.Z --latest --notes-file …`.

## Stato

- 0.2.0: esclusioni nella card. (0.1.2 fix opzioni float, 0.1.3 selettore entita' della card.) Installata sull'HA di casa via HACS dall'utente. Da installare sull'HA di casa e poi dismettere il vecchio command_line.
