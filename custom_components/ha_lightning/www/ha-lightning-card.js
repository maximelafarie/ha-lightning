class HaLightningCard extends HTMLElement {
  setConfig(config) {
    this._config = Object.assign({entity: 'sensor.ha_lightning_strikes', center: [0,0], zoom: 2}, config);
  }

  connectedCallback() {
    if (!this.shadowRoot) this.attachShadow({mode: 'open'});
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css';
    this.shadowRoot.appendChild(link);

    const container = document.createElement('div');
    container.style.width = '100%';
    container.style.height = '400px';
    container.id = 'map';
    this.shadowRoot.appendChild(container);

    const script = document.createElement('script');
    script.src = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js';
    script.onload = () => this._initMap(container);
    this.shadowRoot.appendChild(script);
  }

  _initMap(container) {
    const center = this._config.center || [0,0];
    const zoom = this._config.zoom || 2;
    this._map = L.map(container).setView(center, zoom);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '© OpenStreetMap contributors'
    }).addTo(this._map);

    this._markers = {};
    this._updateFromState();

    // listen to state changes
    const hass = this._hass || window.hass;
    if (hass) {
      this._hass = hass;
      hass.connection.subscribeEvents((e) => this._updateFromState(), 'state_changed');
    }
  }

  set hass(hass) {
    this._hass = hass;
    this._updateFromState();
  }

  _updateFromState() {
    if (!this._hass) return;
    const entityId = this._config.entity;
    const stateObj = this._hass.states[entityId];
    if (!stateObj) return;
    const strikes = (stateObj.attributes && stateObj.attributes.strikes) || [];

    // remove old markers
    Object.values(this._markers).forEach(m => this._map.removeLayer(m));
    this._markers = {};

    strikes.forEach((s, idx) => {
      const lat = parseFloat(s.latitude);
      const lon = parseFloat(s.longitude);
      const marker = L.circleMarker([lat, lon], {radius: 6, color: 'orange'}).addTo(this._map);
      marker.bindPopup(`Strike ${idx+1}<br>${s.time}`);
      this._markers[idx] = marker;
    });
  }
}

customElements.define('ha-lightning-card', HaLightningCard);
