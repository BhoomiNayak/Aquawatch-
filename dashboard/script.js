/**
 * AquaWatch Dashboard
 * Leaflet map + side panel for water body health monitoring.
 */

const API_BASE = 'http://localhost:8001/api/v1';
const MAP_CENTER = [12.97, 77.59]; // Bengaluru
const MAP_ZOOM = 12;
const REFRESH_INTERVAL = 30000;
const RISK_COLORS = { low: '#28a745', moderate: '#ffc107', high: '#dc3545' };

let map;
let markersLayer;
let selectedId = null;
let refreshTimer = null;
let isLoading = false;

// ===== INIT =====
document.addEventListener('DOMContentLoaded', function () {
    initMap();
    fetchWaterBodies();
    document.getElementById('btn-refresh').addEventListener('click', function () {
        fetchWaterBodies();
    });
    document.getElementById('panel-close').addEventListener('click', closePanel);
    map.on('click', closePanel);
    refreshTimer = setInterval(fetchWaterBodies, REFRESH_INTERVAL);
});

function initMap() {
    map = L.map('map').setView(MAP_CENTER, MAP_ZOOM);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; OpenStreetMap contributors',
        maxZoom: 18
    }).addTo(map);
    markersLayer = L.layerGroup().addTo(map);
}

// ===== FETCH DATA =====
function fetchWaterBodies() {
    if (isLoading) return;
    isLoading = true;
    showLoading(true);
    hideError();

    fetch(API_BASE + '/water-bodies')
        .then(function (res) {
            if (!res.ok) throw new Error('Server returned ' + res.status);
            return res.json();
        })
        .then(function (data) {
            isLoading = false;
            showLoading(false);
            if (data.water_bodies && data.water_bodies.length > 0) {
                renderMarkers(data.water_bodies);
                updateStats(data.count, data.water_bodies);
                hideEmpty();
            } else {
                showEmpty();
            }
        })
        .catch(function (err) {
            isLoading = false;
            showLoading(false);
            showError('Cannot connect to backend. Is the server running on port 8000?');
            console.error('Fetch failed:', err);
        });
}

function fetchDetail(id) {
    fetch(API_BASE + '/water-bodies/' + id)
        .then(function (res) { return res.json(); })
        .then(function (data) { showDetail(data); })
        .catch(function (err) { console.error('Detail fetch failed:', err); });
}

function fetchReports(id) {
    fetch(API_BASE + '/water-bodies/' + id + '/reports?limit=5')
        .then(function (res) { return res.json(); })
        .then(function (data) { renderReports(data.reports); })
        .catch(function (err) { console.error('Reports fetch failed:', err); });
}

// ===== RENDER MAP =====
function renderMarkers(waterBodies) {
    markersLayer.clearLayers();

    waterBodies.forEach(function (wb) {
        var color = RISK_COLORS[wb.risk_level] || '#999';
        var marker = L.circleMarker([wb.latitude, wb.longitude], {
            radius: 12,
            fillColor: color,
            color: '#333',
            weight: 2,
            opacity: 1,
            fillOpacity: 0.8
        });

        marker.bindTooltip(
            '<strong>' + wb.name + '</strong><br>' +
            wb.risk_level.toUpperCase() + ' (' + wb.risk_score.toFixed(1) + ')',
            { direction: 'top' }
        );

        marker.on('click', function (e) {
            L.DomEvent.stopPropagation(e);
            selectedId = wb.id;
            fetchDetail(wb.id);
            fetchReports(wb.id);
        });

        markersLayer.addLayer(marker);
    });

    // Fit map to markers
    if (waterBodies.length > 0) {
        var bounds = L.latLngBounds(waterBodies.map(function (wb) {
            return [wb.latitude, wb.longitude];
        }));
        map.fitBounds(bounds, { padding: [50, 50] });
    }
}

// ===== DETAIL PANEL =====
function showDetail(data) {
    var panel = document.getElementById('detail-panel');
    panel.classList.add('open');

    document.getElementById('panel-title').textContent = data.name;

    var badge = document.getElementById('panel-risk-badge');
    badge.textContent = data.risk_level.toUpperCase();
    badge.className = 'risk-badge ' + data.risk_level;

    var scoreEl = document.getElementById('panel-score');
    scoreEl.textContent = data.risk_score.toFixed(1);
    scoreEl.style.color = RISK_COLORS[data.risk_level] || '#333';

    // Breakdown
    var breakdownEl = document.getElementById('panel-breakdown');
    breakdownEl.innerHTML = '';

    if (data.latest_analysis) {
        var items = [
            { label: 'Algae', value: data.latest_analysis.algae_percentage || 0, color: '#28a745' },
            { label: 'Foam', value: data.latest_analysis.foam_coverage_percentage || 0, color: '#6c757d' },
            { label: 'Clarity', value: data.latest_analysis.turbidity_score || 0, color: '#17a2b8' },
        ];

        items.forEach(function (item) {
            var pct = Math.min(100, item.value);
            breakdownEl.innerHTML +=
                '<div class="breakdown-item">' +
                '<span class="breakdown-label">' + item.label + '</span>' +
                '<div class="breakdown-bar-bg"><div class="breakdown-bar" style="width:' + pct + '%;background:' + item.color + '"></div></div>' +
                '<span class="breakdown-value">' + item.value.toFixed(1) + '%</span>' +
                '</div>';
        });
    } else {
        breakdownEl.innerHTML = '<p style="font-size:0.8rem;color:#999">No analysis data yet</p>';
    }

    // Meta
    var meta = document.getElementById('panel-meta');
    meta.textContent = data.total_reports + ' total reports | ' + (data.reports_last_7_days || 0) + ' in last 7 days';
}

function renderReports(reports) {
    var list = document.getElementById('panel-reports');
    list.innerHTML = '';

    if (!reports || reports.length === 0) {
        list.innerHTML = '<li style="color:#999">No reports yet</li>';
        return;
    }

    reports.forEach(function (r) {
        var timeAgo = getTimeAgo(r.created_at);
        var name = r.reporter_name || 'Anonymous';
        var type = r.contamination_type.replace(/_/g, ' ');
        type = type.charAt(0).toUpperCase() + type.slice(1);
        var li = document.createElement('li');
        li.innerHTML =
            '<span class="report-type">' + type + '</span>' +
            '<br><span class="report-meta">' + name + ' &middot; ' + timeAgo + ' &middot; Score: ' + r.composite_score.toFixed(1) + '</span>';
        list.appendChild(li);
    });
}

function closePanel() {
    document.getElementById('detail-panel').classList.remove('open');
    selectedId = null;
}

// ===== UI STATE =====
function showLoading(show) {
    var btn = document.getElementById('btn-refresh');
    btn.textContent = show ? 'Loading...' : 'Refresh';
    btn.disabled = show;
}

function showError(message) {
    document.getElementById('stats-text').textContent = message;
    document.getElementById('stats-text').style.color = '#dc3545';
}

function hideError() {
    document.getElementById('stats-text').style.color = '#8899aa';
}

function showEmpty() {
    document.getElementById('stats-text').textContent = 'No water bodies found. Run seed.py to add demo data.';
}

function hideEmpty() {
    // handled by updateStats
}

function updateStats(count, waterBodies) {
    // Count by risk level
    var high = 0, moderate = 0, low = 0;
    if (waterBodies) {
        waterBodies.forEach(function (wb) {
            if (wb.risk_level === 'high') high++;
            else if (wb.risk_level === 'moderate') moderate++;
            else low++;
        });
    }

    document.getElementById('stats-text').textContent =
        count + ' water bodies | ' + high + ' high | ' + moderate + ' moderate | ' + low + ' low';
    document.getElementById('footer-count').textContent = count + ' water bodies monitored';
    document.getElementById('footer-updated').textContent = 'Last updated: ' + new Date().toLocaleTimeString();
}

// ===== HELPERS =====
function getTimeAgo(isoString) {
    if (!isoString) return 'Unknown';
    var now = new Date();
    var then = new Date(isoString);
    var diff = Math.floor((now - then) / 1000);
    if (diff < 60) return diff + 's ago';
    if (diff < 3600) return Math.floor(diff / 60) + 'm ago';
    if (diff < 86400) return Math.floor(diff / 3600) + 'h ago';
    return Math.floor(diff / 86400) + 'd ago';
}
