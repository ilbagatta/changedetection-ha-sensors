# Changelog

## 0.3.0

- Built-in notifications (Options → Notifications): recipients, kinds of change (price down / up, back in stock, any
  change), minimum drop in % and amount, cooldown per watch, quiet hours with deferred delivery.
- Per-watch `Notifications` switch and `Target price` number.
- `changedetection_ha_sensors.test_notification` action.
- Options are now a menu: General, Notifications.

## 0.2.0

- Card: new `exclude` option ("Watches to hide"), chosen by name in the visual editor.
- *Recent changes* now lists all watches (newest first); the number of rows is set only in the card.
  The integration option "Items in Recent changes" is removed (an old saved value is ignored).
- Card: spacing between the *Price* and *When* headers.

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
