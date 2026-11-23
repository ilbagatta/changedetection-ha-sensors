# Changelog

## 0.1.0

First release.

- UI setup (server URL + API key), reauthentication, reconfiguration and options.
- Per-watch sensors: **Price** (with previous price, trend, stock) and **Last changed** (with the detected text).
- **Recent changes** and **Watches** sensors for the server.
- **Recheck** button per watch and **Recheck all** button.
- `changedetection_ha_sensors_change` event when a watch changes.
- `custom:changedetection-card` Lovelace card, served by the integration, with visual editor.
