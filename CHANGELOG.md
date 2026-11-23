# Changelog

## 0.1.3

- Card editor: the entity picker lists only the *Recent changes* sensor.
- Card: a wrong `entity` (e.g. a watch price sensor) falls back to the *Recent changes* sensor instead of an empty card.

## 0.1.2

- Fix: setup failed with `slice indices must be integers` after saving the options (numbers were stored as `10.0`).
  Options already saved that way now work too.

## 0.1.1

- Integration icon (`brand/`), shown by Home Assistant and HACS.
- CI: newer GitHub Actions.

## 0.1.0

First release.

- UI setup (server URL + API key), reauthentication, reconfiguration and options.
- Per-watch sensors: **Price** (with previous price, trend, stock) and **Last changed** (with the detected text).
- **Recent changes** and **Watches** sensors for the server.
- **Recheck** button per watch and **Recheck all** button.
- `changedetection_ha_sensors_change` event when a watch changes.
- `custom:changedetection-card` Lovelace card, served by the integration, with visual editor.
