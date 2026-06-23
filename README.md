# ha-lightning

Home Assistant custom integration that fetches lightning strikes (Blitzortung-style feeds) and triggers automations when strikes occur inside configured zones.

Features
- Polls a configurable JSON feed of recent strikes and exposes them as a sensor attribute
- Creates binary sensors for user-defined zones (latitude, longitude, radius) that switch ON when a strike is detected in the zone
- Fires event `ha_lightning.zone_strike` with payload {zone, strike}
- Includes a simple Leaflet-based Lovelace card (copy to your HA `www/` folder) to display strikes on a map and zoom/center the view

Installation
1. Copy the `custom_components/ha_lightning` folder into your Home Assistant `config/custom_components/` directory.
2. If you want the Lovelace card, copy `custom_components/ha_lightning/www/ha-lightning-card.js` to `<config>/www/ha-lightning-card.js` (or add the resource directly from the file).
3. In `configuration.yaml` add:

```yaml
ha_lightning:
  feed_url: https://your-blitzortung-proxy.example/recent.json
  scan_interval: 15  # seconds
  zones:
    - name: Home
      latitude: 48.1
      longitude: 11.6
      radius_km: 10
      cooldown_s: 300
```

4. Restart Home Assistant.
5. Add the Lovelace resource (UI -> Resources): `/local/ha-lightning-card.js` type: JavaScript Module
6. Use the card in Lovelace:

```yaml
type: 'custom:ha-lightning-card'
entity: sensor.ha_lightning_strikes
center: [48.1, 11.6]
zoom: 8
```

Notes on Blitzortung API
- Blitzortung's raw real-time feed may require a socket/proxy; the integration expects a JSON endpoint returning either a list of strike objects or an object with a `strikes` list. Each strike should contain `latitude`/`longitude` (or `lat`/`lon`) and `time` (unix timestamp or ISO string).
- If using Blitzortung, consider deploying a small proxy that translates the feed into the expected JSON format.

Avoiding recorder overload
- The integration keeps strike details in attributes of a single sensor to avoid creating a new entity per strike.
- Zone binary sensors only change state when a new strike occurs in the zone and are subject to a configurable cooldown. This minimizes recorder churn.
- If you want to exclude these entities from the recorder, add the usual recorder exclude rules in `configuration.yaml`:

```yaml
recorder:
  exclude:
    entities:
      - sensor.ha_lightning_strikes
      - binary_sensor.lightning_zone_home
```

Privacy & Usage
- This integration merely polls a feed. Do not expose sensitive credentials in configuration.

License
MIT
