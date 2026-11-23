<p align="center"><img src="custom_components/changedetection_ha_sensors/brand/icon.png" width="112" alt="icon"></p>

# Changedetection HA sensors

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/docs/faq/custom_repositories)
[![Validate](https://github.com/ilbagatta/changedetection-ha-sensors/actions/workflows/validate.yml/badge.svg)](https://github.com/ilbagatta/changedetection-ha-sensors/actions/workflows/validate.yml)
[![GitHub release](https://img.shields.io/github/v/release/ilbagatta/changedetection-ha-sensors)](https://github.com/ilbagatta/changedetection-ha-sensors/releases)
[![License](https://img.shields.io/github/license/ilbagatta/changedetection-ha-sensors)](LICENSE)

Bring your [changedetection.io](https://github.com/dgtlmoon/changedetection.io) watches into Home Assistant:
**one price sensor per watch**, the **previous price** and the trend, a **change event** for your automations and a
small, clean **Lovelace card**, plus **built-in notifications** with price-drop thresholds, target prices and quiet
hours, all from a UI setup.

```
PRODUCT                                  PRICE          WHEN
• Simpson Venom White           €229.95  €319.95   today 15:18
  Meross smart plug (2 pack)     €23.99   €22.79   yesterday 06:30
  Lexin B4FM intercom            €93.99   €74.28         19/11
  MagSafe power bank 10000       €55.99   €49.99         19/11
  News page        New article published…     —          17/11
```

*Old price struck through, new price green when it drops and red when it rises; the dot marks changes you have not
viewed yet in changedetection.io.*

## Features

- **UI configuration**: server URL and API key, with connection check, reauthentication and reconfiguration.
- **Per-watch device** with:
  - `Price` sensor (monetary, with history graphs), with attributes `previous_price`, `trend` (`up` / `down`),
    `in_stock`, `url`;
  - `Last changed` timestamp sensor, with the detected `text`, `error`, `viewed`, `paused`;
  - `Recheck` button;
  - `Notifications` switch and `Target price` number (configuration entities).
- **Server device** with `Recent changes` (feeds the card), `Watches` (count, errors, unviewed) and `Recheck all`.
- **Previous price** found by walking the snapshot history back to the first *different* price, so snapshots where only
  the stock status changed are skipped.
- **Light on your server**: only `GET /watch` on every poll; history is read only for watches that actually changed.
- **Notifications** to your phone on price drops (or rises, back in stock, any change), with minimum drop, target
  price per watch, cooldown and quiet hours.
- **Event** `changedetection_ha_sensors_change` on every change, for your own automations.
- **Lovelace card** served by the integration itself: nothing else to install, with a visual editor.
- New watches show up automatically; watches can be excluded from the options.
- English and Italian translations.

## Requirements

- Home Assistant 2025.6 or newer.
- A changedetection.io instance reachable from Home Assistant, with the API enabled
  (changedetection.io → **Settings → API**, copy the API key).

## Installation

### HACS (recommended)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=ilbagatta&repository=changedetection-ha-sensors&category=integration)

1. HACS → ⋮ → **Custom repositories** → add `https://github.com/ilbagatta/changedetection-ha-sensors`, type
   **Integration**.
2. Search for **Changedetection HA sensors** and download it.
3. Restart Home Assistant.

### Manual

Copy `custom_components/changedetection_ha_sensors` into your `config/custom_components/` folder and restart.

## Configuration

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=changedetection_ha_sensors)

**Settings → Devices & services → Add integration → Changedetection HA sensors**, then enter:

| Field | Example | Notes |
|---|---|---|
| Server URL | `http://192.168.1.10:5000` | With or without `/api/v1`. |
| API key | `••••••••` | From changedetection.io → Settings → API. Stored in the config entry, not in YAML. |
| Verify SSL certificate | on | Turn off for self-signed HTTPS. |

### Options

The options have two pages: **General** and **Notifications**.

**General**

| Option | Default | |
|---|---|---|
| Update interval | 5 min | How often the watch list is read. |
| Snapshots to scan for the previous price | 10 | How far back to look for a different price. |
| Price currency | `EUR` | ISO code used as the unit of the price sensors and by the card. |
| Watches to exclude | — | No entities, not shown in the card. |

## Notifications

Set them in **Options → Notifications**:

| Option | Default | |
|---|---|---|
| Send to | — | One or more `notify` services (e.g. `notify.mobile_app_my_phone`). Empty: no notifications. |
| Notify when | price dropped, back in stock | Also: price increased, any other change (pages without a price). |
| Minimum drop (%) / (amount) | 0 | Smaller drops are ignored. |
| Wait between notifications of the same watch | 6 h | Skipped when the price drops further. |
| Quiet hours | — | Notifications in the window (e.g. 23:00–08:00) are held and sent when it ends (the latest one per watch). |

Per watch, on the device page:

- **Notifications** switch: silence a single watch without excluding it.
- **Target price**: notify only when the price is at or below this value (0 = no target).

A notification looks like this, and tapping it opens the product page (Companion app, iOS and Android):

> **📉 Simpson Venom White**
> €319.95 → €229.95 (-28%)

Use the **Send test notification** action (`changedetection_ha_sensors.test_notification`) to check the recipients.
Nothing is sent when Home Assistant starts or for newly added watches.

## Lovelace card

The card is loaded automatically. Add it from the card picker (**Changedetection**) or in YAML:

```yaml
type: custom:changedetection-card
```

| Option | Default | |
|---|---|---|
| `entity` | auto | The `Recent changes` sensor (not a per-watch sensor); found automatically if omitted. |
| `title` | `Changedetection` | `""` hides the header. |
| `limit` | `10` | Rows to show. |
| `exclude` | — | Watches to hide in this card (list of watch UUIDs; pick them by name in the visual editor). |
| `show_text` | `true` | For watches without a price, show the detected text under the name. |

The card uses your theme colours (`--success-color`, `--error-color`, `--accent-color`, `--divider-color`) and works in
light and dark mode.

## Price detection

The price is read from the latest snapshot text:

1. `Price: 319.95`, as written by the **Re-stock & Price detection** processor (which also gives `In Stock: True/False`);
2. otherwise the **first** amount with two decimals, such as `€22.79`, `49,99 €`, `1.299,00` or `$1,299.50`.

Tip: in changedetection.io, use a CSS/XPath filter that keeps only the price element (for example
`#corePrice_feature_div .a-offscreen` on Amazon) so the snapshot is short and the first amount is the right one.
Watches without any amount still get the `Last changed` sensor; their price sensor is `unknown`.

## Automations

For anything the built-in notifications do not cover, every change fires `changedetection_ha_sensors_change` with `uuid`, `title`, `url`, `price`, `old_price`, `trend`,
`in_stock`, `text`, `last_changed`, `viewed`, `error`, `tags`.

Notify when a price drops:

```yaml
alias: Price drop
triggers:
  - trigger: event
    event_type: changedetection_ha_sensors_change
    event_data:
      trend: down
actions:
  - action: notify.mobile_app_my_phone
    data:
      title: "📉 {{ trigger.event.data.title }}"
      message: >-
        {{ trigger.event.data.old_price }} → {{ trigger.event.data.price }}
      data:
        url: "{{ trigger.event.data.url }}"
```

Or use the sensors directly, e.g. a `numeric_state` trigger below a target price:

```yaml
triggers:
  - trigger: numeric_state
    entity_id: sensor.simpson_venom_white_price
    below: 250
```

## Troubleshooting

- **Cannot reach the server**: the URL must be reachable *from Home Assistant* (container/VM network), port included.
- **Invalid API key**: Home Assistant opens a reauthentication flow; paste the new key.
- **Card not found** after updating: refresh the browser (the card URL carries the version, so a reload is enough).
- Debug logs:

  ```yaml
  logger:
    logs:
      custom_components.changedetection_ha_sensors: debug
  ```

## Development

```bash
python3.13 -m venv .venv
.venv/bin/pip install -r requirements_test.txt
.venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/pytest -q
```

The tests run against a real Home Assistant core (`pytest-homeassistant-custom-component`) with a fake changedetection.io
server. CI runs hassfest, the HACS validator and the test suite.

## Credits

Not affiliated with changedetection.io. Thanks to [dgtlmoon](https://github.com/dgtlmoon) for changedetection.io and its
API.

## License

[GPL-3.0](LICENSE)
