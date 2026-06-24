# ha-lightning

Home Assistant custom integration that fetches lightning strikes and triggers automations when strikes occur inside a configured zone.

Features
- Supports HTTP(S) JSON feeds or the lightningmaps.org websocket (wss://live2.lightningmaps.org/)
- Exposes recent strikes as a single sensor attribute
- Creates a binary sensor for a single configured zone (latitude, longitude, radius) that switches ON when a strike is detected in the zone
- Fires event `ha_lightning.zone_strike` with payload {"zone", "strike"}
- Includes a simple Leaflet-based Lovelace card (copy to your HA `www/` folder) to display strikes on a map and zoom/center the view

Note: The integration uses the websocket feed automatically when the configured `feed_url` starts with `ws://` or `wss://`. For websocket feeds the integration sends a subscription payload including a bounding box derived from your configured zone so the server returns strokes for the area of interest.

Installation

Option A — HACS (recommended)
1. In HACS go to Settings → Custom repositories and add this repository URL as a Custom Repository with category "Integration" (the hacs.json in this repo will let HACS detect the integration).
2. Install the integration from HACS. HACS copies the integration to `custom_components/` for you.
3. If the Lovelace card is not automatically added, add the resource `/local/ha-lightning-card.js` (JavaScript Module) or copy `custom_components/ha_lightning/www/ha-lightning-card.js` to `<config>/www/`.

Option B — Manual
1. Copy the `custom_components/ha_lightning` folder into your Home Assistant `config/custom_components/` directory.
2. If you want the Lovelace card, copy `custom_components/ha_lightning/www/ha-lightning-card.js` to `<config>/www/ha-lightning-card.js` (or add the resource directly from the file).

Configuration (UI)
- Install via HACS or manually and then add the integration in Configuration → Integrations → + Add Integration → "HA Lightning".
- In the UI setup you can set:
  - feed_url: either a HTTP(S) JSON feed or a websocket URL (e.g., `wss://live2.lightningmaps.org/`)
  - scan_interval: polling interval (seconds) for HTTP feeds
  - zone: configure a single zone with fields: zone_name, latitude, longitude, radius_km, cooldown_s

Legacy YAML example (optional)

```yaml
ha_lightning:
  feed_url: https://your-blitzortung-proxy.example/recent.json
  scan_interval: 15  # seconds
  zone:
    name: Home
    latitude: 48.1
    longitude: 11.6
    radius_km: 10
    cooldown_s: 300
```

Lovelace card

```yaml
type: 'custom:ha-lightning-card'
entity: sensor.ha_lightning_strikes
center: [48.1, 11.6]
zoom: 8
```

Notes on feeds
- If using an HTTP JSON feed, the integration expects either a JSON list of strike objects or an object with a `strikes` list. Each strike should contain `latitude`/`longitude` (or `lat`/`lon`) and `time` (unix timestamp or ISO string).
- For real-time data the integration supports the LightningMaps websocket feed. Use `wss://live2.lightningmaps.org/` as `feed_url` in the UI to receive live strokes. The integration sends a subscription payload including a bounding box derived from your configured zone so the server returns strokes for that area.
- If the feed you want to use is not directly accessible, consider deploying a small proxy that translates the source into the expected JSON or websocket format.

Avoiding recorder overload
- The integration keeps strike details in attributes of a single sensor to avoid creating a new entity per strike.
- The zone binary sensor only changes state when a new strike occurs in the zone and is subject to a configurable cooldown. This minimizes recorder churn.
- If you want to exclude these entities from the recorder, add the usual recorder exclude rules in `configuration.yaml`:

```yaml
recorder:
  exclude:
    entities:
      - sensor.ha_lightning_strikes
      - binary_sensor.ha_lightning_zone
```

Privacy & Usage
- This integration merely polls a feed or connects to a public websocket. Do not expose sensitive credentials in configuration.

License
MIT