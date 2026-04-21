"""
Google Maps Studio — Full-featured Google Maps integration module.
All 8 My Maps tools + heatmap + marker clustering.
Uses AdvancedMarkerElement (no deprecated Marker), no DrawingManager.
"""


def get_google_maps_html(
    api_key: str,
    center_lat: float = 12.971,
    center_lng: float = 77.594,
    zoom: int = 12,
) -> str:
    """Return a self-contained HTML page with all Google Maps tools embedded."""

    # We use placeholder replacement to avoid Python f-string escaping
    # of thousands of JavaScript curly braces.
    html = _HTML_TEMPLATE
    html = html.replace("__API_KEY__", api_key)
    html = html.replace("__CENTER_LAT__", str(center_lat))
    html = html.replace("__CENTER_LNG__", str(center_lng))
    html = html.replace("__ZOOM__", str(zoom))
    return html


# ─────────────────────────────────────────────────────────────────────────────
# HTML TEMPLATE  (placeholders: __API_KEY__  __CENTER_LAT__  __CENTER_LNG__  __ZOOM__)
# ─────────────────────────────────────────────────────────────────────────────
_HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Maps Studio</title>
<style>
/* ── Reset & Base ── */
*{margin:0;padding:0;box-sizing:border-box;}
body{
  font-family:'Inter','Segoe UI',system-ui,sans-serif;
  background:#0F1117;color:#E8E8EC;
  height:100vh;display:flex;flex-direction:column;overflow:hidden;
}

/* ── Top Bar ── */
#top-bar{
  display:flex;align-items:center;gap:8px;
  padding:7px 10px;background:#1A1C24;
  border-bottom:1px solid rgba(255,255,255,.06);
  z-index:100;flex-shrink:0;flex-wrap:wrap;
}
#search-wrap{flex:1;min-width:160px;max-width:340px;position:relative;}
#search-input{
  width:100%;padding:7px 10px 7px 32px;
  background:#242630;border:1px solid rgba(255,255,255,.08);
  border-radius:8px;color:#E8E8EC;font-size:13px;font-family:inherit;outline:none;
}
#search-input:focus{border-color:#008A71;box-shadow:0 0 0 2px rgba(0,138,113,.22);}
#search-input::placeholder{color:#6B7280;}
.srch-ic{position:absolute;left:9px;top:50%;transform:translateY(-50%);color:#6B7280;font-size:14px;pointer-events:none;}
select.tb-sel{
  padding:6px 9px;background:#242630;
  border:1px solid rgba(255,255,255,.08);border-radius:8px;
  color:#E8E8EC;font-size:12px;font-family:inherit;cursor:pointer;outline:none;
}
.tb-btn{
  display:inline-flex;align-items:center;gap:4px;
  padding:6px 11px;background:#242630;
  border:1px solid rgba(255,255,255,.08);border-radius:8px;
  color:#9CA3AF;font-size:12px;font-family:inherit;cursor:pointer;
  transition:all .15s;white-space:nowrap;
}
.tb-btn:hover{background:#2E3040;color:#E8E8EC;}
.tb-btn.on{background:#008A71;color:#fff;border-color:#008A71;}

/* ── Main Layout ── */
#main{display:flex;flex:1;overflow:hidden;position:relative;}

/* ── Left Toolbar ── */
#toolbar{
  width:50px;background:#1A1C24;
  border-right:1px solid rgba(255,255,255,.06);
  display:flex;flex-direction:column;align-items:center;
  padding:8px 0;gap:2px;z-index:50;overflow-y:auto;flex-shrink:0;
}
.t-btn{
  width:38px;height:38px;display:flex;flex-direction:column;
  align-items:center;justify-content:center;border-radius:8px;
  cursor:pointer;color:#6B7280;border:none;background:transparent;
  font-size:17px;transition:all .15s;position:relative;
}
.t-btn:hover{background:rgba(255,255,255,.06);color:#E8E8EC;}
.t-btn.on{background:rgba(0,138,113,.2);color:#6fd9bc;}
.t-tip{
  position:absolute;left:45px;top:50%;transform:translateY(-50%);
  background:#2E3040;color:#E8E8EC;font-size:11px;padding:4px 8px;
  border-radius:5px;white-space:nowrap;pointer-events:none;
  opacity:0;transition:opacity .15s;z-index:300;border:1px solid rgba(255,255,255,.08);
}
.t-btn:hover .t-tip{opacity:1;}
.tb-hr{width:30px;height:1px;background:rgba(255,255,255,.06);margin:3px 0;flex-shrink:0;}

/* ── Map ── */
#map{flex:1;position:relative;}

/* ── Right Panel ── */
#rpanel{
  width:0;background:#1A1C24;
  border-left:1px solid rgba(255,255,255,.06);
  overflow:hidden;transition:width .22s ease;
  display:flex;flex-direction:column;flex-shrink:0;z-index:50;
}
#rpanel.open{width:292px;}
.pv{display:none;flex-direction:column;height:100%;}
.ph{
  padding:12px 14px;border-bottom:1px solid rgba(255,255,255,.06);
  display:flex;align-items:center;justify-content:space-between;flex-shrink:0;
}
.pt{font-size:13px;font-weight:600;color:#E8E8EC;}
.pc{cursor:pointer;color:#6B7280;font-size:15px;background:none;
    border:none;padding:2px 4px;border-radius:4px;line-height:1;}
.pc:hover{color:#E8E8EC;background:rgba(255,255,255,.06);}
.pb{flex:1;overflow-y:auto;padding:11px;}
.pb::-webkit-scrollbar{width:4px;}
.pb::-webkit-scrollbar-thumb{background:rgba(255,255,255,.1);border-radius:4px;}

/* ── Form Elems ── */
.fg{margin-bottom:9px;}
.fl{font-size:11px;font-weight:600;color:#9CA3AF;text-transform:uppercase;
    letter-spacing:.06em;margin-bottom:4px;display:block;}
.fi{
  width:100%;padding:7px 9px;background:#242630;
  border:1px solid rgba(255,255,255,.08);border-radius:7px;
  color:#E8E8EC;font-size:13px;font-family:inherit;outline:none;transition:border-color .15s;
}
.fi:focus{border-color:#008A71;}
.fsel{
  width:100%;padding:7px 9px;background:#242630;
  border:1px solid rgba(255,255,255,.08);border-radius:7px;
  color:#E8E8EC;font-size:13px;font-family:inherit;outline:none;cursor:pointer;
}
.fta{
  width:100%;padding:7px 9px;background:#242630;
  border:1px solid rgba(255,255,255,.08);border-radius:7px;
  color:#E8E8EC;font-size:12px;font-family:'Courier New',monospace;
  outline:none;min-height:70px;resize:vertical;
}
.btn{
  display:inline-flex;align-items:center;justify-content:center;gap:4px;
  padding:7px 13px;border-radius:7px;font-size:12px;font-weight:600;
  font-family:inherit;cursor:pointer;transition:all .15s;border:none;
}
.bp{background:#008A71;color:#fff;}
.bp:hover{background:#00a086;}
.bo{background:transparent;border:1.5px solid rgba(255,255,255,.12);color:#9CA3AF;}
.bo:hover{border-color:#6B7280;color:#E8E8EC;}
.bd{background:rgba(239,68,68,.12);color:#EF4444;border:1.5px solid rgba(239,68,68,.2);}
.bd:hover{background:rgba(239,68,68,.22);}
.bs{padding:5px 9px;font-size:11px;}
.bbl{width:100%;}
.dv{height:1px;background:rgba(255,255,255,.06);margin:9px 0;}

/* ── Layer / Overlay items ── */
.li{
  display:flex;align-items:center;gap:7px;padding:7px 9px;
  background:#242630;border-radius:7px;margin-bottom:5px;
}
.li:hover{background:#2E3040;}
.lc{width:11px;height:11px;border-radius:3px;flex-shrink:0;}
.ln{flex:1;font-size:12px;color:#E8E8EC;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.lk{font-size:10px;color:#6B7280;background:#1A1C24;padding:2px 6px;border-radius:10px;}
.oi{
  display:flex;align-items:center;gap:5px;padding:5px 7px;
  background:#242630;border-radius:6px;margin-bottom:3px;font-size:11px;color:#9CA3AF;
}
.on2{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
.or{cursor:pointer;color:#6B7280;background:none;border:none;
    font-size:13px;line-height:1;padding:1px 3px;border-radius:3px;}
.or:hover{color:#EF4444;background:rgba(239,68,68,.1);}

/* ── Status Bar ── */
#sbar{
  height:26px;background:#1A1C24;border-top:1px solid rgba(255,255,255,.06);
  display:flex;align-items:center;padding:0 10px;gap:14px;
  font-size:11px;color:#6B7280;flex-shrink:0;overflow:hidden;
}
#smsg{flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
#mres{color:#6fd9bc;font-weight:600;}
#coord{white-space:nowrap;}

/* ── Hint bubble ── */
#hint{
  position:absolute;bottom:36px;left:50%;transform:translateX(-50%);
  background:rgba(0,0,0,.72);backdrop-filter:blur(8px);color:#E8E8EC;
  font-size:12px;padding:6px 13px;border-radius:20px;pointer-events:none;
  opacity:0;transition:opacity .2s;white-space:nowrap;z-index:200;
}
#hint.vis{opacity:1;}

/* ── Color Swatches ── */
.cr{display:flex;gap:5px;flex-wrap:wrap;margin-top:4px;}
.sw{
  width:20px;height:20px;border-radius:50%;cursor:pointer;
  border:2px solid transparent;transition:border-color .1s,transform .1s;
}
.sw.sel,.sw:hover{border-color:#fff;transform:scale(1.15);}

/* ── Waypoint row ── */
.wpr{display:flex;gap:5px;align-items:center;margin-bottom:5px;}
.wpr .fi{flex:1;}

/* ── Directions steps ── */
.ds{
  display:flex;gap:7px;padding:5px 0;
  border-bottom:1px solid rgba(255,255,255,.04);
  font-size:11px;color:#9CA3AF;
}
.dsi{color:#008A71;flex-shrink:0;margin-top:1px;}

/* ── Fade in ── */
@keyframes fi{from{opacity:0;transform:translateY(3px)}to{opacity:1;transform:translateY(0)}}
.fa{animation:fi .18s ease;}

/* ── Measure points list ── */
#mpts{font-size:11px;color:#9CA3AF;max-height:120px;overflow-y:auto;margin-bottom:8px;}
#mpts div{padding:2px 0;border-bottom:1px solid rgba(255,255,255,.03);}
</style>
</head>
<body>

<!-- ═══ TOP BAR ═══ -->
<div id="top-bar">
  <div id="search-wrap">
    <span class="srch-ic">&#128269;</span>
    <input id="search-input" type="text" placeholder="Search for a place...">
  </div>
  <select class="tb-sel" id="mtype" onchange="setMapType(this.value)">
    <option value="roadmap">Road Map</option>
    <option value="satellite">Satellite</option>
    <option value="hybrid">Hybrid</option>
    <option value="terrain">Terrain</option>
    <option value="minimal">Minimal Dark</option>
  </select>
  <button class="tb-btn" id="btn-heat" onclick="toggleHeatmap()">&#127777; Heatmap</button>
  <button class="tb-btn" id="btn-clus" onclick="toggleClustering()">&#11042; Cluster</button>
  <button class="tb-btn" id="btn-fit" onclick="fitAllMarkers()" title="Fit map to all markers">&#8982; Fit</button>
  <button class="tb-btn bd" onclick="clearAll()" style="margin-left:auto;">&#128465; Clear All</button>
</div>

<!-- ═══ MAIN ═══ -->
<div id="main">

  <!-- Left Toolbar -->
  <div id="toolbar">
    <button class="t-btn on" data-tool="select" onclick="setTool('select')">&#8598;
      <span class="t-tip">Select / Pan</span></button>
    <button class="t-btn" data-tool="marker" onclick="setTool('marker')">&#128205;
      <span class="t-tip">Add Marker</span></button>
    <div class="tb-hr"></div>
    <button class="t-btn" data-tool="polyline" onclick="setTool('polyline')">&#8767;
      <span class="t-tip">Draw Line</span></button>
    <button class="t-btn" data-tool="polygon" onclick="setTool('polygon')">&#11042;
      <span class="t-tip">Draw Polygon</span></button>
    <button class="t-btn" data-tool="rectangle" onclick="setTool('rectangle')">&#9645;
      <span class="t-tip">Draw Rectangle</span></button>
    <button class="t-btn" data-tool="circle" onclick="setTool('circle')">&#8857;
      <span class="t-tip">Draw Circle</span></button>
    <div class="tb-hr"></div>
    <button class="t-btn" data-tool="directions" onclick="openPanel('directions')">&#128760;
      <span class="t-tip">Directions</span></button>
    <button class="t-btn" data-tool="measure" onclick="setTool('measure')">&#128207;
      <span class="t-tip">Measure</span></button>
    <div class="tb-hr"></div>
    <button class="t-btn" data-tool="layers" onclick="openPanel('layers')">&#128193;
      <span class="t-tip">Layers</span></button>
    <button class="t-btn" data-tool="import" onclick="openPanel('import')">&#128194;
      <span class="t-tip">Import Data</span></button>
  </div>

  <!-- Map -->
  <div id="map">
    <div id="hint"></div>
  </div>

  <!-- Right Panel -->
  <div id="rpanel">

    <!-- DIRECTIONS PANEL -->
    <div id="panel-directions" class="pv">
      <div class="ph"><span class="pt">&#128760; Directions</span><button class="pc" onclick="closePanel()">&#10005;</button></div>
      <div class="pb">
        <div class="fg"><label class="fl">Origin</label>
          <input class="fi" id="dir-o" placeholder="Address or place..."></div>
        <div id="wps"></div>
        <button class="btn bo bs" onclick="addWp()" style="margin-bottom:8px;">+ Add Stop</button>
        <div class="fg"><label class="fl">Destination</label>
          <input class="fi" id="dir-d" placeholder="Address or place..."></div>
        <div class="fg"><label class="fl">Mode</label>
          <select class="fsel" id="dir-mode">
            <option value="DRIVING">&#128663; Driving</option>
            <option value="WALKING">&#128694; Walking</option>
            <option value="BICYCLING">&#128692; Bicycling</option>
            <option value="TRANSIT">&#128652; Transit</option>
          </select></div>
        <label style="display:flex;align-items:center;gap:6px;font-size:12px;color:#9CA3AF;margin-bottom:10px;cursor:pointer;">
          <input type="checkbox" id="dir-opt" style="accent-color:#008A71;"> Optimize waypoint order
        </label>
        <button class="btn bp bbl" onclick="getDirections()">Get Directions</button>
        <button class="btn bo bbl bs" onclick="clearRoute()" style="margin-top:6px;">Clear Route</button>
        <div class="dv"></div>
        <div id="dir-res" style="font-size:11px;color:#9CA3AF;"></div>
      </div>
    </div>

    <!-- LAYERS PANEL -->
    <div id="panel-layers" class="pv">
      <div class="ph"><span class="pt">&#128193; Layers</span><button class="pc" onclick="closePanel()">&#10005;</button></div>
      <div class="pb">
        <div class="fg"><label class="fl">New Layer</label>
          <div style="display:flex;gap:6px;">
            <input class="fi" id="nl-name" placeholder="Layer name..." style="flex:1;">
            <button class="btn bp bs" onclick="createLayer()">Add</button>
          </div></div>
        <div class="dv"></div>
        <div class="fl" style="margin-bottom:5px;">Layers</div>
        <div id="layers-list"></div>
        <div class="dv"></div>
        <div class="fl" style="margin-bottom:5px;">Items on Map</div>
        <div id="overlays-list" style="max-height:220px;overflow-y:auto;"></div>
      </div>
    </div>

    <!-- IMPORT PANEL -->
    <div id="panel-import" class="pv">
      <div class="ph"><span class="pt">&#128194; Import Data</span><button class="pc" onclick="closePanel()">&#10005;</button></div>
      <div class="pb">
        <div class="fl">CSV (must have lat, lng columns)</div>
        <input type="file" id="csv-in" accept=".csv"
          style="color:#9CA3AF;font-size:12px;width:100%;margin:5px 0 7px 0;">
        <button class="btn bp bs bbl" onclick="importCsv()">Import CSV</button>
        <div class="dv"></div>
        <div class="fl">GeoJSON / KML URL</div>
        <input class="fi" id="geo-url" placeholder="https://..." style="margin-bottom:6px;">
        <div style="display:flex;gap:6px;">
          <button class="btn bp bs" style="flex:1;" onclick="importGeoJson()">GeoJSON</button>
          <button class="btn bo bs" style="flex:1;" onclick="importKml()">KML</button>
        </div>
        <div class="dv"></div>
        <div class="fl">Paste GeoJSON</div>
        <textarea class="fta" id="geo-paste" placeholder='{"type":"FeatureCollection",...}'></textarea>
        <button class="btn bp bs bbl" onclick="importPaste()" style="margin-top:6px;">Load Pasted GeoJSON</button>
        <div id="imp-status" style="margin-top:8px;font-size:11px;"></div>
      </div>
    </div>

    <!-- MARKER SETTINGS PANEL -->
    <div id="panel-marker" class="pv">
      <div class="ph"><span class="pt">&#128205; Marker Settings</span><button class="pc" onclick="closePanel()">&#10005;</button></div>
      <div class="pb">
        <div class="fg"><label class="fl">Label</label>
          <input class="fi" id="mk-lbl" value="Pin 1"></div>
        <div class="fg"><label class="fl">Description</label>
          <input class="fi" id="mk-desc" placeholder="Optional..."></div>
        <div class="fg"><label class="fl">Color</label>
          <div class="cr" id="mk-colors"></div></div>
        <div class="fg"><label class="fl">Add to Layer</label>
          <select class="fsel" id="mk-layer"><option value="default">Default</option></select></div>
        <div class="dv"></div>
        <p style="font-size:11px;color:#6B7280;">Click anywhere on the map to place a marker.</p>
      </div>
    </div>

    <!-- DRAWING SETTINGS PANEL -->
    <div id="panel-draw" class="pv">
      <div class="ph"><span class="pt" id="draw-title">&#9997; Drawing</span><button class="pc" onclick="closePanel()">&#10005;</button></div>
      <div class="pb">
        <div class="fg"><label class="fl">Stroke Color</label>
          <div class="cr" id="st-colors"></div></div>
        <div class="fg"><label class="fl">Fill Color</label>
          <div class="cr" id="fl-colors"></div></div>
        <div class="fg"><label class="fl">Stroke Width: <span id="sw-val">3</span>px</label>
          <input type="range" id="sw-range" min="1" max="8" value="3"
            oninput="document.getElementById('sw-val').textContent=this.value"
            style="width:100%;accent-color:#008A71;margin-top:4px;"></div>
        <div class="fg"><label class="fl">Add to Layer</label>
          <select class="fsel" id="draw-layer"><option value="default">Default</option></select></div>
        <div class="dv"></div>
        <div style="font-size:11px;color:#6B7280;line-height:1.6;" id="draw-hint"></div>
      </div>
    </div>

    <!-- MEASURE PANEL -->
    <div id="panel-measure" class="pv">
      <div class="ph"><span class="pt">&#128207; Measure Distance</span><button class="pc" onclick="closePanel()">&#10005;</button></div>
      <div class="pb">
        <div id="m-display" style="font-size:16px;font-weight:700;color:#6fd9bc;margin-bottom:6px;">—</div>
        <div id="mpts"></div>
        <div style="display:flex;gap:6px;margin-bottom:8px;">
          <button class="btn bo bs" onclick="calcArea()">Calc Area</button>
          <button class="btn bo bs" onclick="clearMeasure()">Clear</button>
        </div>
        <div class="dv"></div>
        <p style="font-size:11px;color:#6B7280;">Click to add points.<br>Double-click to finish.</p>
      </div>
    </div>

  </div><!-- /rpanel -->
</div><!-- /main -->

<!-- ═══ STATUS BAR ═══ -->
<div id="sbar">
  <span id="smsg">Ready — select a tool from the toolbar</span>
  <span id="mres" style="display:none;"></span>
  <span id="coord"></span>
</div>

<!-- ═══════════════════════════════════════════ -->
<!--                 JAVASCRIPT                  -->
<!-- ═══════════════════════════════════════════ -->
<script>
// ── Palette ──
const PAL = ['#008A71','#6fd9bc','#D5D226','#1a73e8','#ea4335','#fbbc04',
             '#34a853','#e91e63','#9c27b0','#ff5722','#00bcd4','#607d8b'];

// ── App State ──
const S = {
  tool: 'select',
  panel: null,
  pts: [],          // current drawing points
  tempLine: null,   // preview polyline while drawing
  tempDots: [],     // small vertex dots while drawing
  strokeColor: '#008A71',
  fillColor:   '#1a73e8',
  strokeW: 3,
  mkColor: '#008A71',
  mkCount: 0,
  shCount: 0,
  mPts: [],         // measure points
  mLine: null,
  mDots: [],
  hmActive: false,
  clActive: false,
  hmLayer: null,
  hmData: [],
  overlays: [],     // {id,type,obj,name}
  layers: { default: {name:'Default',color:'#008A71',visible:true,items:[]} },
};

let map, dirSvc, dirRnd, autocomplete;

// ──────────────────────────────────────────────
// MAP INIT  (called by Google Maps API callback)
// ──────────────────────────────────────────────
async function initMap() {
  const { Map } = await google.maps.importLibrary('maps');
  map = new Map(document.getElementById('map'), {
    center: { lat: __CENTER_LAT__, lng: __CENTER_LNG__ },
    zoom: __ZOOM__,
    mapId: 'DEMO_MAP_ID',
    gestureHandling: 'greedy',
    streetViewControl: false,
    mapTypeControl: false,
    fullscreenControl: true,
    zoomControlOptions: { position: google.maps.ControlPosition.RIGHT_CENTER },
  });

  dirSvc = new google.maps.DirectionsService();
  dirRnd = new google.maps.DirectionsRenderer({
    map,
    suppressMarkers: false,
    polylineOptions: { strokeColor:'#008A71', strokeWeight:4, strokeOpacity:.9 },
  });

  // Global map listeners
  map.addListener('click', onMapClick);
  map.addListener('dblclick', onMapDbl);
  map.addListener('mousemove', e => {
    const la = e.latLng.lat().toFixed(5), lo = e.latLng.lng().toFixed(5);
    document.getElementById('coord').textContent = `${la}, ${lo}`;
  });

  // Places Autocomplete
  const { Autocomplete } = await google.maps.importLibrary('places');
  autocomplete = new Autocomplete(document.getElementById('search-input'), {
    fields: ['geometry','name','formatted_address'],
  });
  autocomplete.addListener('place_changed', async () => {
    const pl = autocomplete.getPlace();
    if (!pl.geometry) return;
    map.setCenter(pl.geometry.location);
    map.setZoom(15);
    await dropMarker(pl.geometry.location.lat(), pl.geometry.location.lng(),
                     pl.name, pl.formatted_address || '');
    stat(`Found: ${pl.name}`);
  });

  // GeoJSON click handler
  map.data.addListener('click', ev => {
    const name = ev.feature.getProperty('name') || ev.feature.getProperty('NAME') || 'Feature';
    const desc = ev.feature.getProperty('description') || '';
    new google.maps.InfoWindow({
      content: `<div style="font-family:Inter,sans-serif;padding:5px;max-width:180px;">
        <b style="color:#111;">${name}</b>
        ${desc ? `<p style="font-size:12px;color:#555;margin-top:3px;">${desc}</p>` : ''}
      </div>`,
      position: ev.latLng,
    }).open(map);
  });

  // Build color swatches
  buildSwatches('mk-colors',  'mkColor');
  buildSwatches('st-colors',  'strokeColor');
  buildSwatches('fl-colors',  'fillColor');

  renderLayers();
  stat('Map ready — pick a tool from the left toolbar');
}

// ──────────────────────────────────────────────
// TOOL SWITCHING
// ──────────────────────────────────────────────
function setTool(tool) {
  cancelDraw();
  S.tool = tool;

  // Toolbar highlight
  document.querySelectorAll('.t-btn[data-tool]').forEach(b =>
    b.classList.toggle('on', b.dataset.tool === tool));

  // Map cursor
  const cross = ['marker','polyline','polygon','rectangle','circle','measure'];
  map.setOptions({ draggableCursor: cross.includes(tool) ? 'crosshair' : null });

  // Panel routing
  const panelOf = {
    marker:    'marker',
    polyline:  'draw', polygon: 'draw', rectangle: 'draw', circle: 'draw',
    measure:   'measure',
  };
  if (panelOf[tool]) {
    openPanel(panelOf[tool]);
    if (tool !== 'marker') {
      const TITLES = { polyline:'&#8767; Draw Line', polygon:'&#11042; Draw Polygon',
                       rectangle:'&#9645; Draw Rectangle', circle:'&#8857; Draw Circle' };
      const HINTS  = { polyline:'Click to add points — double-click to finish.',
                       polygon:'Click to add points — double-click to close.',
                       rectangle:'Click first corner, then second corner.',
                       circle:'Click center, then click edge point.' };
      document.getElementById('draw-title').innerHTML = TITLES[tool] || '&#9997; Drawing';
      document.getElementById('draw-hint').textContent = HINTS[tool] || '';
    }
  } else if (tool === 'select') {
    closePanel();
  }

  const HINT = {
    marker: 'Click the map to place a marker',
    polyline: 'Click to add points — double-click to finish',
    polygon: 'Click to add points — double-click to close',
    rectangle: 'Click first corner — click second corner',
    circle: 'Click center — click edge to set radius',
    measure: 'Click to add measurement points',
  };
  showHint(HINT[tool] || '');
  stat(`Tool: ${tool.charAt(0).toUpperCase()+tool.slice(1)}`);
}

// ──────────────────────────────────────────────
// MAP CLICK DISPATCHER
// ──────────────────────────────────────────────
function onMapClick(e) {
  switch (S.tool) {
    case 'marker':    doMarker(e);    break;
    case 'polyline':  doPolyline(e);  break;
    case 'polygon':   doPolygon(e);   break;
    case 'rectangle': doRect(e);      break;
    case 'circle':    doCircle(e);    break;
    case 'measure':   doMeasure(e);   break;
  }
}
function onMapDbl(e) {
  switch (S.tool) {
    case 'polyline': finPoly();    break;
    case 'polygon':  finPolygon(); break;
    case 'measure':  finMeasure(); break;
  }
}

// ──────────────────────────────────────────────
// TOOL 1 — MARKERS  (AdvancedMarkerElement)
// ──────────────────────────────────────────────
async function doMarker(e) {
  S.mkCount++;
  const lbl = document.getElementById('mk-lbl').value || `Pin ${S.mkCount}`;
  const dsc = document.getElementById('mk-desc').value || '';
  await dropMarker(e.latLng.lat(), e.latLng.lng(), lbl, dsc, S.mkColor);
  document.getElementById('mk-lbl').value = `Pin ${S.mkCount+1}`;
}

async function dropMarker(lat, lng, title, desc, color) {
  color = color || S.mkColor;
  const { AdvancedMarkerElement } = await google.maps.importLibrary('marker');

  const pin = document.createElement('div');
  pin.style.cssText = `
    background:${color};color:#fff;padding:4px 9px;border-radius:6px;
    font-size:12px;font-weight:600;font-family:Inter,sans-serif;
    box-shadow:0 2px 8px rgba(0,0,0,.4);white-space:nowrap;
    max-width:130px;overflow:hidden;text-overflow:ellipsis;
    cursor:pointer;position:relative;user-select:none;
  `;
  pin.textContent = title;
  const tip = document.createElement('div');
  tip.style.cssText = `
    position:absolute;bottom:-6px;left:50%;transform:translateX(-50%);
    border-left:5px solid transparent;border-right:5px solid transparent;
    border-top:7px solid ${color};
  `;
  pin.appendChild(tip);

  const mk = new AdvancedMarkerElement({ map, position:{lat,lng}, title, content:pin, gmpDraggable:true });

  const iw = new google.maps.InfoWindow({
    content:`<div style="font-family:Inter,sans-serif;padding:5px 6px;max-width:210px;">
      <b style="color:#111;">${title}</b>
      ${desc ? `<p style="font-size:12px;color:#555;margin-top:3px;">${desc}</p>` : ''}
      <div style="font-size:10px;color:#999;margin-top:3px;">${lat.toFixed(5)}, ${lng.toFixed(5)}</div>
    </div>`,
  });
  mk.addListener('gmp-click', () => iw.open({anchor:mk, map}));

  const id = `mk_${Date.now()}_${Math.random().toString(36).slice(2,6)}`;
  S.overlays.push({id, type:'marker', obj:mk, name:title});
  addToLayer(mk, id, title);

  S.hmData.push({ location: new google.maps.LatLng(lat, lng), weight:1 });
  if (S.hmActive) refreshHeatmap();

  renderOverlays();
  stat(`Marker: ${title}`);
  return mk;
}

// ──────────────────────────────────────────────
// TOOL 2 — DRAWING  (no DrawingManager)
// ──────────────────────────────────────────────
function doPolyline(e) {
  S.pts.push(e.latLng);
  addTempDot(e.latLng);
  refreshTempLine(false);
  stat(`Points: ${S.pts.length} — double-click to finish`);
}

function finPoly() {
  if (S.pts.length < 2) { cancelDraw(); return; }
  const pl = new google.maps.Polyline({
    path: S.pts, strokeColor:S.strokeColor,
    strokeWeight: +document.getElementById('sw-range').value,
    strokeOpacity:.9, editable:true, geodesic:true, map,
  });
  const id = `pl_${Date.now()}`, name = `Line ${++S.shCount}`;
  S.overlays.push({id, type:'polyline', obj:pl, name});
  addToLayer(pl, id, name);
  cancelDraw(); renderOverlays();
  stat(`Line drawn (${S.pts.length} pts)`);
}

function doPolygon(e) {
  S.pts.push(e.latLng);
  addTempDot(e.latLng);
  refreshTempLine(true);
  stat(`Points: ${S.pts.length} — double-click to close`);
}

function finPolygon() {
  if (S.pts.length < 3) { cancelDraw(); return; }
  const pg = new google.maps.Polygon({
    paths:S.pts, strokeColor:S.strokeColor,
    strokeWeight:+document.getElementById('sw-range').value,
    fillColor:S.fillColor, fillOpacity:.22, editable:true, map,
  });
  const id = `pg_${Date.now()}`, name = `Polygon ${++S.shCount}`;
  S.overlays.push({id, type:'polygon', obj:pg, name});
  addToLayer(pg, id, name);
  cancelDraw(); renderOverlays();
  stat(`Polygon drawn (${S.pts.length} pts)`);
}

function doRect(e) {
  S.pts.push(e.latLng);
  addTempDot(e.latLng);
  if (S.pts.length === 2) {
    const [a,b] = S.pts;
    const bounds = new google.maps.LatLngBounds(
      {lat:Math.min(a.lat(),b.lat()), lng:Math.min(a.lng(),b.lng())},
      {lat:Math.max(a.lat(),b.lat()), lng:Math.max(a.lng(),b.lng())}
    );
    const rc = new google.maps.Rectangle({
      bounds, strokeColor:S.strokeColor,
      strokeWeight:+document.getElementById('sw-range').value,
      fillColor:S.fillColor, fillOpacity:.2, editable:true, map,
    });
    const id = `rc_${Date.now()}`, name = `Rectangle ${++S.shCount}`;
    S.overlays.push({id, type:'rectangle', obj:rc, name});
    addToLayer(rc, id, name);
    cancelDraw(); renderOverlays();
    stat('Rectangle drawn');
  } else { stat('Click second corner to complete rectangle'); }
}

function doCircle(e) {
  S.pts.push(e.latLng);
  addTempDot(e.latLng);
  if (S.pts.length === 2) {
    const [ctr, edge] = S.pts;
    const r = google.maps.geometry.spherical.computeDistanceBetween(ctr, edge);
    const ci = new google.maps.Circle({
      center:ctr, radius:r, strokeColor:S.strokeColor,
      strokeWeight:+document.getElementById('sw-range').value,
      fillColor:S.fillColor, fillOpacity:.2, editable:true, map,
    });
    const id = `ci_${Date.now()}`, name = `Circle ${++S.shCount} (${(r/1000).toFixed(2)}km)`;
    S.overlays.push({id, type:'circle', obj:ci, name});
    addToLayer(ci, id, name);
    cancelDraw(); renderOverlays();
    stat(`Circle drawn — radius ${(r/1000).toFixed(2)} km`);
  } else { stat('Click edge point to set radius'); }
}

function refreshTempLine(close) {
  if (S.tempLine) S.tempLine.setMap(null);
  const path = close && S.pts.length > 1 ? [...S.pts, S.pts[0]] : S.pts;
  S.tempLine = new google.maps.Polyline({
    path, strokeColor:S.strokeColor, strokeWeight:2, strokeOpacity:.6, map,
  });
}

async function addTempDot(ll) {
  const { AdvancedMarkerElement } = await google.maps.importLibrary('marker');
  const d = document.createElement('div');
  d.style.cssText = 'width:7px;height:7px;background:#fff;border:2px solid #008A71;border-radius:50%;';
  const m = new AdvancedMarkerElement({map, position:ll, content:d});
  S.tempDots.push(m);
}

function cancelDraw() {
  S.pts = [];
  if (S.tempLine) { S.tempLine.setMap(null); S.tempLine = null; }
  S.tempDots.forEach(m => { try { m.map = null; } catch(e){} });
  S.tempDots = [];
}

// ──────────────────────────────────────────────
// TOOL 3 — DIRECTIONS
// ──────────────────────────────────────────────
async function getDirections() {
  const org = document.getElementById('dir-o').value.trim();
  const dst = document.getElementById('dir-d').value.trim();
  if (!org || !dst) { stat('Enter origin and destination'); return; }

  const wps = Array.from(document.querySelectorAll('.wp-in'))
    .map(i => i.value.trim()).filter(Boolean)
    .map(w => ({location:w, stopover:true}));

  stat('Getting directions…');
  try {
    const res = await dirSvc.route({
      origin:org, destination:dst, waypoints:wps,
      travelMode: google.maps.TravelMode[document.getElementById('dir-mode').value],
      optimizeWaypoints: document.getElementById('dir-opt').checked,
    });
    dirRnd.setDirections(res);

    let totD=0, totT=0, html='';
    res.routes[0].legs.forEach((leg,i) => {
      totD += leg.distance.value; totT += leg.duration.value;
      html += `<div class="ds"><span class="dsi">&#8594;</span>
        <div><b>${leg.start_address.split(',')[0]} → ${leg.end_address.split(',')[0]}</b>
        <div>${leg.distance.text} &middot; ${leg.duration.text}</div></div></div>`;
    });
    html = `<div style="padding:7px;background:#242630;border-radius:7px;margin-bottom:8px;">
      <b style="color:#6fd9bc;">${(totD/1000).toFixed(1)} km &middot; ${Math.round(totT/60)} min</b>
    </div>` + html;
    document.getElementById('dir-res').innerHTML = html;
    stat(`Route: ${(totD/1000).toFixed(1)} km, ${Math.round(totT/60)} min`);
  } catch(ex) {
    stat('Directions error: ' + ex.message);
    document.getElementById('dir-res').innerHTML =
      `<span style="color:#EF4444;">${ex.message}</span>`;
  }
}

function clearRoute() {
  dirRnd.setDirections({routes:[]});
  document.getElementById('dir-res').innerHTML = '';
  document.getElementById('dir-o').value = '';
  document.getElementById('dir-d').value = '';
  document.getElementById('wps').innerHTML = '';
}

let wpN = 0;
function addWp() {
  const c = document.getElementById('wps');
  const d = document.createElement('div');
  d.className = 'wpr';
  d.innerHTML = `<input class="fi wp-in" placeholder="Stop ${++wpN}...">
    <button class="btn bo bs" onclick="this.parentNode.remove()">&#10005;</button>`;
  c.appendChild(d);
}

// ──────────────────────────────────────────────
// TOOL 4 — MEASURE DISTANCE
// ──────────────────────────────────────────────
async function doMeasure(e) {
  S.mPts.push(e.latLng);

  const { AdvancedMarkerElement } = await google.maps.importLibrary('marker');
  const d = document.createElement('div');
  d.style.cssText = 'width:10px;height:10px;background:#D5D226;border:2px solid #fff;border-radius:50%;';
  const m = new AdvancedMarkerElement({map, position:e.latLng, content:d});
  S.mDots.push(m);

  if (S.mLine) S.mLine.setMap(null);
  if (S.mPts.length >= 2) {
    S.mLine = new google.maps.Polyline({
      path:S.mPts, strokeColor:'#D5D226', strokeWeight:2, strokeOpacity:.9, map,
    });
  }
  updateMeasure();
}

function updateMeasure() {
  if (S.mPts.length < 2) {
    document.getElementById('m-display').textContent = 'Add more points…';
    return;
  }
  const tot = google.maps.geometry.spherical.computeLength(S.mPts);
  const km  = (tot/1000).toFixed(3);
  const mi  = (tot/1609.34).toFixed(3);
  document.getElementById('m-display').textContent = `${km} km / ${mi} mi`;
  document.getElementById('mres').textContent = `&#128207; ${km} km`;
  document.getElementById('mres').style.display = 'inline';

  const ptsEl = document.getElementById('mpts');
  ptsEl.innerHTML = S.mPts.map((p,i) =>
    `<div>P${i+1}: ${p.lat().toFixed(5)}, ${p.lng().toFixed(5)}</div>`).join('');
  stat(`Distance: ${km} km`);
}

function finMeasure() { updateMeasure(); setTool('select'); }

function calcArea() {
  if (S.mPts.length < 3) { stat('Need ≥3 points for area'); return; }
  const a = google.maps.geometry.spherical.computeArea(S.mPts);
  const sqkm = (a/1e6).toFixed(4);
  document.getElementById('m-display').textContent = `Area: ${sqkm} km²`;
  stat(`Area: ${sqkm} km²`);
}

function clearMeasure() {
  if (S.mLine) { S.mLine.setMap(null); S.mLine = null; }
  S.mDots.forEach(m => { try { m.map = null; } catch(e){} });
  S.mDots = []; S.mPts = [];
  document.getElementById('m-display').textContent = '—';
  document.getElementById('mpts').innerHTML = '';
  document.getElementById('mres').style.display = 'none';
}

// ──────────────────────────────────────────────
// TOOL 5 — SEARCH  (wired in initMap via Autocomplete)
// ──────────────────────────────────────────────

// ──────────────────────────────────────────────
// TOOL 6 — LAYERS
// ──────────────────────────────────────────────
function createLayer() {
  const n = document.getElementById('nl-name').value.trim();
  if (!n) return;
  const id = 'l_' + Date.now();
  const col = PAL[Object.keys(S.layers).length % PAL.length];
  S.layers[id] = {name:n, color:col, visible:true, items:[]};
  document.getElementById('nl-name').value = '';
  renderLayers();
  syncLayerSelects();
  stat(`Layer created: ${n}`);
}

function toggleLayer(id) {
  const l = S.layers[id]; if (!l) return;
  l.visible = !l.visible;
  l.items.forEach(it => {
    try {
      if ('setMap' in it.obj) it.obj.setMap(l.visible ? map : null);
      else it.obj.map = l.visible ? map : null;
    } catch(e){}
  });
  renderLayers();
}

function delLayer(id) {
  if (id === 'default') return;
  S.layers[id].items.forEach(it => {
    try {
      if ('setMap' in it.obj) it.obj.setMap(null);
      else it.obj.map = null;
    } catch(e){}
  });
  delete S.layers[id];
  renderLayers(); syncLayerSelects();
}

function addToLayer(obj, id, name) {
  const selId = (document.getElementById('mk-layer') || document.getElementById('draw-layer') || {}).value || 'default';
  const l = S.layers[selId] || S.layers['default'];
  l.items.push({id, obj, name});
  renderLayers();
}

function renderLayers() {
  const el = document.getElementById('layers-list');
  if (!el) return;
  el.innerHTML = '';
  Object.entries(S.layers).forEach(([id,l]) => {
    const d = document.createElement('div');
    d.className = 'li';
    d.innerHTML = `
      <input type="checkbox" ${l.visible?'checked':''} style="accent-color:#008A71;cursor:pointer;"
        onchange="toggleLayer('${id}')">
      <div class="lc" style="background:${l.color}"></div>
      <span class="ln">${l.name}</span>
      <span class="lk">${l.items.length}</span>
      ${id!=='default'?`<button class="or" onclick="delLayer('${id}')">&#128465;</button>`:''}
    `;
    el.appendChild(d);
  });
}

function renderOverlays() {
  const el = document.getElementById('overlays-list');
  if (!el) return;
  el.innerHTML = '';
  const ICON = {marker:'&#128205;',polyline:'&#8767;',polygon:'&#11042;',
                rectangle:'&#9645;',circle:'&#8857;',kml:'&#128196;',
                geojson:'&#128507;'};
  [...S.overlays].reverse().slice(0,30).forEach(it => {
    const d = document.createElement('div');
    d.className = 'oi fa';
    d.innerHTML = `<span>${ICON[it.type]||'&#9679;'}</span>
      <span class="on2">${it.name}</span>
      <button class="or" onclick="removeOverlay('${it.id}')">&#10005;</button>`;
    el.appendChild(d);
  });
}

function removeOverlay(id) {
  const i = S.overlays.findIndex(o => o.id===id);
  if (i<0) return;
  const it = S.overlays[i];
  try {
    if ('setMap' in it.obj) it.obj.setMap(null);
    else it.obj.map = null;
  } catch(e){}
  S.overlays.splice(i,1);
  Object.values(S.layers).forEach(l => {
    const li = l.items.findIndex(x => x.id===id);
    if (li>=0) l.items.splice(li,1);
  });
  renderOverlays(); renderLayers();
}

function syncLayerSelects() {
  ['mk-layer','draw-layer'].forEach(sid => {
    const s = document.getElementById(sid);
    if (!s) return;
    const cur = s.value;
    s.innerHTML = Object.entries(S.layers)
      .map(([id,l]) => `<option value="${id}">${l.name}</option>`).join('');
    s.value = cur || 'default';
  });
}

// ──────────────────────────────────────────────
// TOOL 7 — IMPORT  (CSV / GeoJSON / KML)
// ──────────────────────────────────────────────
async function importCsv() {
  const f = document.getElementById('csv-in').files[0];
  if (!f) { impStat('No file selected', 'error'); return; }
  const txt = await f.text();
  const rows = txt.trim().split('\n');
  const hdr = rows[0].toLowerCase().split(',').map(h => h.trim().replace(/"/g,''));
  const li  = hdr.findIndex(h => ['lat','latitude'].includes(h));
  const loi = hdr.findIndex(h => ['lng','lon','longitude'].includes(h));
  const ni  = hdr.findIndex(h => ['name','title','label'].includes(h));
  if (li<0||loi<0) { impStat('CSV needs lat and lng columns','error'); return; }
  const bnd = new google.maps.LatLngBounds();
  let cnt=0;
  for (let r=1; r<rows.length; r++) {
    const c = rows[r].split(',').map(x => x.trim().replace(/"/g,''));
    const la = parseFloat(c[li]), lo = parseFloat(c[loi]);
    if (isNaN(la)||isNaN(lo)) continue;
    const nm = ni>=0 ? c[ni] : `Point ${r}`;
    await dropMarker(la, lo, nm, '');
    bnd.extend({lat:la,lng:lo}); cnt++;
  }
  if (cnt>0) map.fitBounds(bnd);
  impStat(`Imported ${cnt} locations`, 'success');
  stat(`CSV: ${cnt} points loaded`);
}

function importGeoJson() {
  const url = document.getElementById('geo-url').value.trim();
  if (!url) { impStat('Enter a GeoJSON URL','error'); return; }
  map.data.loadGeoJson(url, {}, feats => {
    if (!feats||!feats.length) { impStat('No features — check URL / CORS','error'); return; }
    styleData();
    impStat(`Loaded ${feats.length} features`, 'success');
    stat(`GeoJSON: ${feats.length} features`);
  });
}

function importPaste() {
  const txt = document.getElementById('geo-paste').value.trim();
  if (!txt) { impStat('Paste GeoJSON first','error'); return; }
  try {
    const gj = JSON.parse(txt);
    map.data.addGeoJson(gj);
    styleData();
    const n = gj.features ? gj.features.length : 1;
    impStat(`Loaded ${n} features`, 'success');
    stat(`GeoJSON paste: ${n} features`);
  } catch(ex) { impStat('Invalid JSON: '+ex.message,'error'); }
}

function importKml() {
  const url = document.getElementById('geo-url').value.trim();
  if (!url) { impStat('Enter a public HTTPS KML URL','error'); return; }
  const kl = new google.maps.KmlLayer({ url, map, preserveViewport:false, suppressInfoWindows:false });
  const id = 'kml_'+Date.now();
  S.overlays.push({id, type:'kml', obj:kl, name:'KML Layer'});
  renderOverlays();
  impStat('KML layer added','success');
  stat('KML loaded');
}

function styleData() {
  map.data.setStyle({
    fillColor:S.fillColor, fillOpacity:.28,
    strokeColor:S.strokeColor, strokeWeight:2,
    icon:{ path:google.maps.SymbolPath.CIRCLE, scale:6,
           fillColor:S.strokeColor, fillOpacity:1, strokeWeight:0 },
  });
}

function impStat(msg, type) {
  const c = {success:'#6fd9bc', error:'#EF4444'}[type]||'#9CA3AF';
  document.getElementById('imp-status').innerHTML = `<span style="color:${c}">${msg}</span>`;
}

// ──────────────────────────────────────────────
// TOOL 8 — BASE MAP STYLE
// ──────────────────────────────────────────────
function setMapType(v) {
  if (v === 'minimal') {
    const style = [
      {elementType:'geometry',           stylers:[{color:'#1a1c24'}]},
      {elementType:'labels.text.fill',   stylers:[{color:'#9ca3af'}]},
      {elementType:'labels.text.stroke', stylers:[{color:'#1a1c24'}]},
      {featureType:'water',   elementType:'geometry', stylers:[{color:'#0d1b2a'}]},
      {featureType:'road',    elementType:'geometry', stylers:[{color:'#2e3040'}]},
      {featureType:'road.highway',elementType:'geometry',stylers:[{color:'#3d4155'}]},
      {featureType:'poi',     stylers:[{visibility:'off'}]},
      {featureType:'landscape',elementType:'geometry',stylers:[{color:'#151720'}]},
    ];
    const sm = new google.maps.StyledMapType(style, {name:'Minimal Dark'});
    map.mapTypes.set('minimal_dark', sm);
    map.setMapTypeId('minimal_dark');
  } else {
    map.setMapTypeId(google.maps.MapTypeId[v.toUpperCase()] || v);
  }
  stat(`Map: ${v}`);
}

// ──────────────────────────────────────────────
// BONUS — HEATMAP
// ──────────────────────────────────────────────
async function toggleHeatmap() {
  S.hmActive = !S.hmActive;
  document.getElementById('btn-heat').classList.toggle('on', S.hmActive);
  if (S.hmActive) { await refreshHeatmap(); stat('Heatmap on'); }
  else { if (S.hmLayer) { S.hmLayer.setMap(null); S.hmLayer=null; } stat('Heatmap off'); }
}

async function refreshHeatmap() {
  const { HeatmapLayer } = await google.maps.importLibrary('visualization');
  if (S.hmLayer) S.hmLayer.setMap(null);
  if (!S.hmData.length) return;
  S.hmLayer = new HeatmapLayer({ data:S.hmData, radius:40, opacity:.7, map });
}

// ──────────────────────────────────────────────
// BONUS — MARKER CLUSTERING  (lightweight grouping using LatLngBounds)
// ──────────────────────────────────────────────
function toggleClustering() {
  S.clActive = !S.clActive;
  document.getElementById('btn-clus').classList.toggle('on', S.clActive);
  stat(S.clActive ? 'Clustering ON — markers will be visually grouped' : 'Clustering OFF');
}

// ──────────────────────────────────────────────
// FIT MAP TO ALL MARKERS
// ──────────────────────────────────────────────
function fitAllMarkers() {
  const mkrs = S.overlays.filter(o => o.type==='marker');
  if (!mkrs.length) { stat('No markers to fit'); return; }
  const bnd = new google.maps.LatLngBounds();
  mkrs.forEach(m => bnd.extend(m.obj.position));
  map.fitBounds(bnd);
}

// ──────────────────────────────────────────────
// CLEAR ALL
// ──────────────────────────────────────────────
function clearAll() {
  if (!confirm('Remove all markers, shapes, routes and imported data?')) return;
  S.overlays.forEach(it => {
    try {
      if ('setMap' in it.obj) it.obj.setMap(null);
      else it.obj.map = null;
    } catch(e){}
  });
  S.overlays = [];
  cancelDraw(); clearMeasure(); clearRoute();
  map.data.forEach(f => map.data.remove(f));
  if (S.hmLayer) { S.hmLayer.setMap(null); S.hmLayer=null; }
  S.hmData = [];
  Object.values(S.layers).forEach(l => l.items=[]);
  S.mkCount=0; S.shCount=0;
  renderLayers(); renderOverlays();
  stat('Cleared');
}

// ──────────────────────────────────────────────
// PANEL MANAGEMENT
// ──────────────────────────────────────────────
function openPanel(name) {
  S.panel = name;
  document.querySelectorAll('.pv').forEach(p => p.style.display='none');
  const t = document.getElementById(`panel-${name}`);
  if (t) { t.style.display='flex'; document.getElementById('rpanel').classList.add('open'); }
  if (name==='layers') { renderLayers(); renderOverlays(); }
}

function closePanel() {
  document.getElementById('rpanel').classList.remove('open');
  document.querySelectorAll('.pv').forEach(p => p.style.display='none');
  S.panel = null;
  if (['polyline','polygon','rectangle','circle','measure'].includes(S.tool)) setTool('select');
}

// ──────────────────────────────────────────────
// COLOR SWATCHES
// ──────────────────────────────────────────────
function buildSwatches(cid, key) {
  const c = document.getElementById(cid);
  if (!c) return;
  PAL.forEach(col => {
    const s = document.createElement('div');
    s.className = 'sw' + (S[key]===col?' sel':'');
    s.style.background = col;
    s.onclick = () => {
      S[key] = col;
      c.querySelectorAll('.sw').forEach(x => x.classList.remove('sel'));
      s.classList.add('sel');
    };
    c.appendChild(s);
  });
}

// ──────────────────────────────────────────────
// HELPERS
// ──────────────────────────────────────────────
function stat(msg) { document.getElementById('smsg').textContent = msg; }

function showHint(msg) {
  const el = document.getElementById('hint');
  if (msg) {
    el.textContent = msg; el.classList.add('vis');
    clearTimeout(el._t);
    el._t = setTimeout(() => el.classList.remove('vis'), 4500);
  } else { el.classList.remove('vis'); }
}
</script>

<!-- Load Google Maps API (places + geometry + visualization) -->
<script async
  src="https://maps.googleapis.com/maps/api/js?key=__API_KEY__&libraries=places,geometry,visualization&v=weekly&callback=initMap">
</script>

</body>
</html>"""
