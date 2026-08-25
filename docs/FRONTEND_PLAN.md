# AquaWatch - Frontend Plan (Dashboard)

## Overview

A single-page vanilla HTML/JS/CSS dashboard with an interactive Leaflet map. No build tools, no npm, no framework. Opens by double-clicking `index.html` or serving via `python -m http.server`.

---

## Technology

| Library | Version | Source | Purpose |
|---------|---------|--------|---------|
| Leaflet.js | 1.9.4 | CDN | Interactive map |
| Chart.js | 4.4.0 | CDN (nice-to-have) | Trend line chart |
| No framework | - | - | Vanilla JS with fetch() |

---

## Page Layout

```
┌─────────────────────────────────────────────────────────────────┐
│  HEADER BAR                                                      │
│  [AquaWatch Logo]  Water Body Health Monitor    [Refresh] [Stats]│
├───────────────────────────────────────┬─────────────────────────┤
│                                       │                         │
│                                       │   DETAIL PANEL          │
│            LEAFLET MAP                │   (appears on click)    │
│            (full height)              │                         │
│                                       │   - Water body name     │
│    ● Green markers (Low)              │   - Risk badge          │
│    ● Yellow markers (Moderate)        │   - Score: 72.5/100     │
│    ● Red markers (High)              │   - Last report time    │
│                                       │   - Component scores    │
│                                       │   - Recent reports list │
│                                       │                         │
│                                       │   [View History]        │
│                                       │                         │
├───────────────────────────────────────┴─────────────────────────┤
│  FOOTER: 10 water bodies monitored | Last updated: 2 min ago    │
└─────────────────────────────────────────────────────────────────┘
```

---

## Files

### `index.html`
- Semantic HTML5
- CDN links for Leaflet CSS/JS and optionally Chart.js
- Container divs: `#map`, `#detail-panel`, `#header`, `#footer`
- No inline styles or scripts (separate files)

### `script.js`
- `initMap()` — Create Leaflet map centered on Bengaluru (12.97, 77.59), zoom 12
- `fetchWaterBodies()` — GET /api/v1/water-bodies, create markers
- `createMarker(waterBody)` — Circle marker with color based on risk_level
- `showDetail(waterBodyId)` — GET /api/v1/water-bodies/{id}, populate side panel
- `updateStats()` — Update footer stats (count, last refresh time)
- Auto-refresh every 30 seconds OR manual refresh button

### `style.css`
- CSS Grid layout (map 70% + panel 30% on desktop)
- Mobile responsive: panel slides up from bottom on small screens
- Risk color variables: `--risk-low`, `--risk-moderate`, `--risk-high`
- Clean, minimal design with good contrast

---

## Map Configuration

```javascript
const map = L.map('map').setView([12.97, 77.59], 12);

// OpenStreetMap tiles (free, no API key)
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; OpenStreetMap contributors',
    maxZoom: 18
}).addTo(map);
```

---

## Marker Styling

```javascript
function getMarkerStyle(riskLevel, riskScore) {
    const colors = {
        low: '#28a745',
        moderate: '#ffc107',
        high: '#dc3545'
    };
    
    return {
        radius: 12,              // Fixed size for demo
        fillColor: colors[riskLevel],
        color: '#333',           // Border
        weight: 2,
        opacity: 1,
        fillOpacity: 0.8
    };
}
```

Each marker shows a tooltip on hover: `"Bellandur Lake - HIGH RISK (72.5)"` and opens the detail panel on click.

---

## Detail Panel Content

When a marker is clicked:

```html
<div id="detail-panel" class="panel-open">
    <h2>Bellandur Lake</h2>
    <span class="risk-badge risk-high">HIGH RISK</span>
    <p class="score">Score: 72.5 / 100</p>
    
    <h3>Analysis Breakdown</h3>
    <div class="breakdown">
        <div class="component">
            <span class="label">Algae</span>
            <div class="bar" style="width: 45%"></div>
            <span class="value">45.8%</span>
        </div>
        <div class="component">
            <span class="label">Foam</span>
            <div class="bar" style="width: 32%"></div>
            <span class="value">32.1%</span>
        </div>
        <div class="component">
            <span class="label">Turbidity</span>
            <div class="bar" style="width: 85%"></div>
            <span class="value">High</span>
        </div>
    </div>
    
    <h3>Recent Reports</h3>
    <ul class="reports-list">
        <li>Industrial discharge - Rahul S - 2 hours ago</li>
        <li>Sewage - Priya M - 1 day ago</li>
    </ul>
    
    <p class="meta">8 reports in last 7 days | 23 total</p>
</div>
```

---

## Color Scheme

```css
:root {
    --risk-low: #28a745;
    --risk-moderate: #ffc107;
    --risk-high: #dc3545;
    --bg-primary: #f8f9fa;
    --bg-panel: #ffffff;
    --text-primary: #212529;
    --text-secondary: #6c757d;
    --border: #dee2e6;
}
```

---

## API Integration

```javascript
const API_BASE = 'http://localhost:8000/api/v1';

async function fetchWaterBodies() {
    const response = await fetch(`${API_BASE}/water-bodies`);
    const data = await response.json();
    return data.water_bodies;
}

async function fetchWaterBodyDetail(id) {
    const response = await fetch(`${API_BASE}/water-bodies/${id}`);
    return await response.json();
}

async function fetchHistory(id) {
    const response = await fetch(`${API_BASE}/water-bodies/${id}/history`);
    return await response.json();
}
```

---

## Responsive Behavior

| Breakpoint | Layout |
|-----------|--------|
| > 768px | Map (70%) + Side panel (30%) side by side |
| <= 768px | Full-width map, panel slides up from bottom (60% height) |

---

## Interactions

1. **Page load** → Fetch water bodies → Render markers → Fit map bounds
2. **Marker hover** → Show tooltip with name + risk
3. **Marker click** → Open detail panel, highlight marker
4. **Close panel** → Click X or click empty map area
5. **Refresh button** → Re-fetch all data, update markers
6. **Auto-refresh** → Every 30 seconds, silently update (no flicker)

---

## Nice-to-Have (If Time Permits)

- **Trend chart**: Small Chart.js line chart in detail panel showing risk over time
- **Filter buttons**: "Show only High Risk" / "Show All"
- **Legend**: Fixed legend in bottom-left corner of map
- **Loading state**: Spinner while fetching data
- **Error handling**: Banner if backend is unreachable
