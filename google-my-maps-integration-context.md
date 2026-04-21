# Context: Google My Maps Tools — Web App Integration Guide

> **How to use this file:**
> Place this file in your project root or any folder Claude Code can see.
> In a new conversation, say: _"Read `google-my-maps-integration-context.md` and help me implement the maps tools."_
> Claude will have full context of all tools, APIs, and code patterns.

---

## Project Goal

Integrate all Google My Maps tools into a web application using the **Google Maps JavaScript API**.
Every My Maps tool has a direct API equivalent. This file documents all 8 tools, their API classes,
integration code, and important deprecation warnings.

---

## Prerequisites

### 1. Get an API Key
- Go to [Google Cloud Console](https://console.cloud.google.com)
- Enable: **Maps JavaScript API**, **Places API**, **Directions API**, **Geocoding API**
- Create an API key and restrict it to your domain

### 2. Load the API in HTML

```html
<!-- Add to <head> — includes all required libraries -->
<script async
  src="https://maps.googleapis.com/maps/api/js
    ?key=YOUR_API_KEY
    &libraries=places,geometry,visualization
    &v=weekly
    &callback=initMap">
</script>

<!-- Map container -->
<div id="map" style="width:100%; height:600px;"></div>
```

> ⚠️ **Do NOT include `libraries=drawing`** — the DrawingManager UI widget was deprecated
> August 2025 and will be removed May 2026. Build your own toolbar instead (see Tool 2).

### 3. Initialize the Map

```javascript
let map;

async function initMap() {
  const { Map } = await google.maps.importLibrary("maps");

  map = new Map(document.getElementById("map"), {
    center: { lat: 12.971, lng: 77.594 }, // default center — change as needed
    zoom: 12,
    mapId: "YOUR_MAP_ID", // REQUIRED for AdvancedMarkerElement (get from Cloud Console)
  });
}
```

---

## Tool 1 — Add Marker / Drop Pin

**My Maps equivalent:** The pin tool — drop a marker, set a title, description, icon, and color.

**API class:** `google.maps.marker.AdvancedMarkerElement` ✅ (current standard)

> ⚠️ `google.maps.Marker` was **deprecated February 2024** — never use it in new code.
> `AdvancedMarkerElement` requires a `mapId` on map initialization.

### Operations
- Drop pin at coordinates or on click
- Custom icon (SVG, PNG, or HTML/CSS)
- Info window with title + description
- Draggable markers
- Remove marker

### Integration Code

```javascript
async function addMarker(map, lat, lng, title, htmlContent) {
  const { AdvancedMarkerElement } = await google.maps.importLibrary("marker");

  // Option A: Default red pin
  const marker = new AdvancedMarkerElement({
    map,
    position: { lat, lng },
    title,
    gmpDraggable: true,
  });

  // Option B: Custom HTML pin (full CSS control)
  const pin = document.createElement("div");
  pin.style.cssText = `
    background: #1a73e8;
    color: #fff;
    padding: 6px 12px;
    border-radius: 8px;
    font-size: 13px;
    font-weight: 500;
    box-shadow: 0 2px 6px rgba(0,0,0,0.3);
    white-space: nowrap;
  `;
  pin.textContent = title;

  const customMarker = new AdvancedMarkerElement({
    map,
    position: { lat, lng },
    title,
    content: pin,
    gmpDraggable: true,
  });

  // Info window on click
  const infoWindow = new google.maps.InfoWindow({
    content: `
      <div style="padding: 8px; max-width: 220px;">
        <strong>${title}</strong>
        <p style="margin-top: 4px; color: #555;">${htmlContent}</p>
      </div>
    `,
  });

  customMarker.addListener("gmp-click", () => {
    infoWindow.open({ anchor: customMarker, map });
  });

  // Drop pin on map click
  map.addListener("click", async (e) => {
    const clickedMarker = new AdvancedMarkerElement({
      map,
      position: e.latLng,
      gmpDraggable: true,
    });
  });

  // Remove marker
  // marker.map = null;

  return customMarker;
}
```

---

## Tool 2 — Draw a Line / Shape / Area

**My Maps equivalent:** The draw tool — polylines, polygons, rectangles, circles with editable handles.

**API classes:** `google.maps.Polyline`, `Polygon`, `Rectangle`, `Circle` ✅

> ⚠️ The `DrawingManager` UI toolbar was **deprecated August 2025**, removal **May 2026**.
> Build your own toolbar buttons that call the functions below.

### Operations
- Draw polyline (open path)
- Draw polygon (closed filled area)
- Draw rectangle (axis-aligned box)
- Draw circle (radius-based)
- Edit shapes with drag handles (`editable: true`)
- Delete shapes

### Integration Code

```javascript
// --- Polyline (open line between points) ---
function drawPolyline(map, points, color = "#1a73e8") {
  const polyline = new google.maps.Polyline({
    path: points, // [{ lat, lng }, ...]
    strokeColor: color,
    strokeOpacity: 0.9,
    strokeWeight: 3,
    editable: true,   // drag handles like My Maps
    geodesic: true,
    map,
  });

  polyline.addListener("click", () => {
    // Handle click on line
  });

  return polyline;
}

// --- Polygon (closed filled area) ---
function drawPolygon(map, points, color = "#0f9d58") {
  const polygon = new google.maps.Polygon({
    paths: points,
    strokeColor: color,
    strokeWeight: 2,
    fillColor: color,
    fillOpacity: 0.25,
    editable: true,
    map,
  });
  return polygon;
}

// --- Rectangle ---
function drawRectangle(map, north, south, east, west) {
  const rectangle = new google.maps.Rectangle({
    bounds: { north, south, east, west },
    strokeColor: "#ea4335",
    strokeWeight: 2,
    fillColor: "#ea4335",
    fillOpacity: 0.2,
    editable: true,
    map,
  });
  return rectangle;
}

// --- Circle ---
function drawCircle(map, lat, lng, radiusMetres = 5000, color = "#fbbc04") {
  const circle = new google.maps.Circle({
    center: { lat, lng },
    radius: radiusMetres,
    strokeColor: color,
    strokeWeight: 2,
    fillColor: color,
    fillOpacity: 0.2,
    editable: true,
    map,
  });
  return circle;
}

// --- Delete any overlay ---
function deleteOverlay(overlay) {
  overlay.setMap(null);
}

// --- Example: Custom toolbar button wiring ---
document.getElementById("btn-draw-line").addEventListener("click", () => {
  // Collect clicked points, then call drawPolyline
  const points = [];
  const clickListener = map.addListener("click", (e) => {
    points.push(e.latLng);
    if (points.length >= 2) {
      drawPolyline(map, points);
      google.maps.event.removeListener(clickListener);
    }
  });
});
```

---

## Tool 3 — Directions & Routes

**My Maps equivalent:** The directions tool — draw a driving/walking/cycling route between points.

**API class:** `google.maps.DirectionsService` + `DirectionsRenderer` ✅

### Operations
- Get route between origin and destination
- Add waypoints (up to 25 stops)
- Switch travel mode: DRIVING, WALKING, BICYCLING, TRANSIT
- Display route on map with polyline
- Show step-by-step turn instructions
- Optimize waypoint order

### Integration Code

```javascript
const directionsService = new google.maps.DirectionsService();
const directionsRenderer = new google.maps.DirectionsRenderer({
  map,
  suppressMarkers: false,
  polylineOptions: {
    strokeColor: "#1a73e8",
    strokeWeight: 4,
    strokeOpacity: 0.9,
  },
});

async function showRoute({
  origin,       // string address OR { lat, lng }
  destination,  // string address OR { lat, lng }
  waypoints = [],
  mode = "DRIVING", // DRIVING | WALKING | BICYCLING | TRANSIT
  optimizeWaypoints = false,
}) {
  try {
    const result = await directionsService.route({
      origin,
      destination,
      waypoints: waypoints.map((w) => ({ location: w, stopover: true })),
      travelMode: google.maps.TravelMode[mode],
      optimizeWaypoints,
    });

    directionsRenderer.setDirections(result);

    // Extract step-by-step instructions
    const legs = result.routes[0].legs;
    legs.forEach((leg, i) => {
      console.log(`Leg ${i + 1}: ${leg.start_address} → ${leg.end_address}`);
      console.log(`Distance: ${leg.distance.text}, Duration: ${leg.duration.text}`);
      leg.steps.forEach((step) => {
        console.log(`  - ${step.instructions} (${step.distance.text})`);
      });
    });

    return result;
  } catch (err) {
    console.error("Directions error:", err);
  }
}

// Usage examples:
// showRoute({ origin: "Bengaluru", destination: "Mysuru" });
// showRoute({ origin: { lat: 12.97, lng: 77.59 }, destination: { lat: 12.30, lng: 76.65 }, mode: "BICYCLING" });
// showRoute({ origin: "A", destination: "D", waypoints: ["B", "C"], optimizeWaypoints: true });
```

---

## Tool 4 — Measure Distance

**My Maps equivalent:** The ruler/measure tool — click points to measure distance.

**API library:** `google.maps.geometry.spherical` ✅ (add `&libraries=geometry` to API URL)

### Operations
- Straight-line distance between two points
- Total length of a multi-point path
- Area of a polygon
- Display live measurement while user clicks

### Integration Code

```javascript
// Load geometry (add &libraries=geometry to API script URL)
async function measureDistance(point1, point2) {
  const { spherical } = await google.maps.importLibrary("geometry");

  const p1 = new google.maps.LatLng(point1.lat, point1.lng);
  const p2 = new google.maps.LatLng(point2.lat, point2.lng);

  const metres = spherical.computeDistanceBetween(p1, p2);
  const km = (metres / 1000).toFixed(2);
  const miles = (metres / 1609.34).toFixed(2);

  return { metres, km, miles };
}

// Total path length
async function measurePath(points) {
  const { spherical } = await google.maps.importLibrary("geometry");
  const latLngs = points.map((p) => new google.maps.LatLng(p.lat, p.lng));
  const totalMetres = spherical.computeLength(latLngs);
  return { metres: totalMetres, km: (totalMetres / 1000).toFixed(2) };
}

// Area of a polygon
async function measureArea(points) {
  const { spherical } = await google.maps.importLibrary("geometry");
  const latLngs = points.map((p) => new google.maps.LatLng(p.lat, p.lng));
  const sqMetres = spherical.computeArea(latLngs);
  return { sqMetres, sqKm: (sqMetres / 1e6).toFixed(4) };
}

// Live measurement tool — click map to add points
function enableMeasureTool(map) {
  const measurePoints = [];
  let measureLine = null;
  let measureLabel = null;

  map.addListener("click", async (e) => {
    measurePoints.push(e.latLng);

    if (measureLine) measureLine.setMap(null);
    measureLine = new google.maps.Polyline({
      path: measurePoints,
      strokeColor: "#ff6d00",
      strokeWeight: 2,
      map,
    });

    if (measurePoints.length >= 2) {
      const { spherical } = await google.maps.importLibrary("geometry");
      const total = spherical.computeLength(measurePoints);
      console.log(`Total distance: ${(total / 1000).toFixed(2)} km`);
    }
  });
}
```

---

## Tool 5 — Search & Place Lookup

**My Maps equivalent:** The search bar — find a place and save it to the map.

**API library:** `google.maps.places` ✅ (add `&libraries=places` to API URL)

### Operations
- Autocomplete search input
- Get place details (name, address, phone, photos, rating)
- Nearby search by type
- Geocode an address to coordinates

### Integration Code

```javascript
// Autocomplete search input
function enablePlaceSearch(map, inputElementId) {
  const input = document.getElementById(inputElementId);

  const autocomplete = new google.maps.places.Autocomplete(input, {
    fields: ["geometry", "name", "formatted_address", "photos", "rating", "website"],
  });

  autocomplete.addListener("place_changed", async () => {
    const place = autocomplete.getPlace();
    if (!place.geometry) {
      console.warn("No geometry for this place");
      return;
    }

    // Pan map to result
    map.setCenter(place.geometry.location);
    map.setZoom(15);

    // Add marker
    await addMarker(
      map,
      place.geometry.location.lat(),
      place.geometry.location.lng(),
      place.name,
      place.formatted_address,
    );
  });
}

// Nearby search
function searchNearby(map, lat, lng, type = "restaurant", radius = 1000) {
  const service = new google.maps.places.PlacesService(map);

  service.nearbySearch(
    { location: { lat, lng }, radius, type },
    async (results, status) => {
      if (status !== google.maps.places.PlacesServiceStatus.OK) return;

      for (const place of results) {
        await addMarker(
          map,
          place.geometry.location.lat(),
          place.geometry.location.lng(),
          place.name,
          place.vicinity,
        );
      }
    },
  );
}

// Geocode address → coordinates
async function geocodeAddress(address) {
  const geocoder = new google.maps.Geocoder();
  const result = await geocoder.geocode({ address });
  if (result.results.length === 0) return null;
  const loc = result.results[0].geometry.location;
  return { lat: loc.lat(), lng: loc.lng() };
}
```

---

## Tool 6 — Layers (Group & Toggle Visibility)

**My Maps equivalent:** The layer panel — organize markers/shapes into named groups, toggle on/off.

**API:** No native layer API — use this custom `MapLayer` class pattern ✅

### Operations
- Create named layers
- Add any overlay (marker, polyline, polygon, circle) to a layer
- Show / hide entire layer
- Remove all items from a layer

### Integration Code

```javascript
class MapLayer {
  constructor(name, mapInstance) {
    this.name = name;
    this.map = mapInstance;
    this.visible = true;
    this.items = []; // markers, polylines, polygons, circles, etc.
  }

  add(overlay) {
    this.items.push(overlay);
    if (!this.visible) overlay.setMap(null); // respect current visibility
  }

  setVisible(visible) {
    this.visible = visible;
    this.items.forEach((item) => {
      // AdvancedMarkerElement uses .map property, others use .setMap()
      if ("setMap" in item) {
        item.setMap(visible ? this.map : null);
      } else {
        item.map = visible ? this.map : null;
      }
    });
  }

  clear() {
    this.setVisible(false);
    this.items = [];
  }
}

// --- Usage ---
const layers = {
  restaurants: new MapLayer("Restaurants", map),
  hotels: new MapLayer("Hotels", map),
  routes: new MapLayer("Routes", map),
};

// Add a marker to the restaurants layer
const m = await addMarker(map, 12.97, 77.59, "Eat Street", "Great food");
layers.restaurants.add(m);

// Wire up toggle checkboxes
document.querySelectorAll(".layer-toggle").forEach((checkbox) => {
  checkbox.addEventListener("change", (e) => {
    const layerName = e.target.dataset.layer;
    layers[layerName].setVisible(e.target.checked);
  });
});
```

```html
<!-- Example layer toggle UI -->
<div id="layer-panel">
  <label><input type="checkbox" class="layer-toggle" data-layer="restaurants" checked> Restaurants</label>
  <label><input type="checkbox" class="layer-toggle" data-layer="hotels" checked> Hotels</label>
  <label><input type="checkbox" class="layer-toggle" data-layer="routes" checked> Routes</label>
</div>
```

---

## Tool 7 — Import Data (KML / GeoJSON / CSV)

**My Maps equivalent:** The import button — upload a spreadsheet or file to bulk-add locations.

**API classes:** `google.maps.KmlLayer`, `map.data` (GeoJSON) ✅

### Operations
- Load KML file onto the map
- Load GeoJSON (recommended for programmatic use)
- Parse CSV and plot markers
- Style imported features
- Listen for clicks on imported data

### Integration Code

```javascript
// --- Option A: GeoJSON (recommended for programmatic use) ---
function loadGeoJson(map, url) {
  map.data.loadGeoJson(url);

  map.data.setStyle((feature) => ({
    fillColor: "#1a73e8",
    fillOpacity: 0.3,
    strokeColor: "#1a73e8",
    strokeWeight: 1.5,
    icon: {
      path: google.maps.SymbolPath.CIRCLE,
      scale: 6,
      fillColor: "#1a73e8",
      fillOpacity: 1,
      strokeWeight: 0,
    },
  }));

  map.data.addListener("click", (event) => {
    const name = event.feature.getProperty("name");
    const description = event.feature.getProperty("description");
    console.log("Clicked feature:", name, description);
  });
}

// Load GeoJSON from a local object (no server needed)
function loadGeoJsonObject(map, geojson) {
  map.data.addGeoJson(geojson);
}

// --- Option B: KML layer (file must be publicly hosted) ---
function loadKml(map, kmlUrl) {
  const kmlLayer = new google.maps.KmlLayer({
    url: kmlUrl, // must be a public HTTPS URL, not localhost
    map,
    preserveViewport: false, // auto-zoom to KML bounds
    suppressInfoWindows: false,
  });

  kmlLayer.addListener("click", (event) => {
    console.log("KML feature clicked:", event.featureData.name);
  });

  return kmlLayer;
}

// --- Option C: CSV import (requires PapaParse) ---
// Add to HTML: <script src="https://cdnjs.cloudflare.com/ajax/libs/PapaParse/5.4.1/papaparse.min.js"></script>

async function loadCsv(map, csvText) {
  const { data } = Papa.parse(csvText, { header: true, skipEmptyLines: true });

  for (const row of data) {
    const lat = parseFloat(row.lat || row.latitude);
    const lng = parseFloat(row.lng || row.longitude || row.lon);
    if (isNaN(lat) || isNaN(lng)) continue;

    await addMarker(map, lat, lng, row.name || "Pin", row.description || "");
  }
}

// File input handler
document.getElementById("file-input").addEventListener("change", (e) => {
  const file = e.target.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = (ev) => loadCsv(map, ev.target.result);
  reader.readAsText(file);
});
```

---

## Tool 8 — Base Map Style

**My Maps equivalent:** The base map selector — road, satellite, terrain, minimal, etc.

**API classes:** `map.setMapTypeId()`, `google.maps.StyledMapType` ✅

### Operations
- Switch between built-in map types
- Apply custom JSON style (colors, labels, roads)
- Use Cloud-hosted styles (set in Cloud Console, no JSON needed)

### Built-in Map Types

```javascript
// Road map (default)
map.setMapTypeId(google.maps.MapTypeId.ROADMAP);

// Satellite imagery
map.setMapTypeId(google.maps.MapTypeId.SATELLITE);

// Satellite + labels
map.setMapTypeId(google.maps.MapTypeId.HYBRID);

// Terrain / topographic
map.setMapTypeId(google.maps.MapTypeId.TERRAIN);
```

### Custom Style (JSON)

```javascript
const minimalStyle = [
  { elementType: "geometry", stylers: [{ color: "#f5f5f5" }] },
  { elementType: "labels.text.fill", stylers: [{ color: "#616161" }] },
  { featureType: "water", elementType: "geometry", stylers: [{ color: "#c9c9c9" }] },
  { featureType: "road", elementType: "geometry", stylers: [{ color: "#ffffff" }] },
  { featureType: "poi", stylers: [{ visibility: "off" }] },
];

const styledMap = new google.maps.StyledMapType(minimalStyle, { name: "Minimal" });
map.mapTypes.set("minimal_style", styledMap);
map.setMapTypeId("minimal_style");
```

### Cloud-Hosted Styles (Recommended)

Set styles in Google Cloud Console → Maps Platform → Map Styles.
Then reference the generated `mapId` in your map initialization — no JSON required in code.

```javascript
const map = new google.maps.Map(document.getElementById("map"), {
  mapId: "YOUR_CLOUD_MAP_ID",  // from Cloud Console
  center: { lat: 12.97, lng: 77.59 },
  zoom: 12,
});
```

---

## Bonus — Heatmap & Marker Clustering

These aren't in My Maps but are commonly needed alongside these tools.

### Heatmap

```javascript
// Add &libraries=visualization to API URL

function showHeatmap(map, points) {
  // points = [{ lat, lng, weight? }, ...]
  const heatmapData = points.map((p) => ({
    location: new google.maps.LatLng(p.lat, p.lng),
    weight: p.weight || 1,
  }));

  const heatmap = new google.maps.visualization.HeatmapLayer({
    data: heatmapData,
    radius: 40,
    opacity: 0.7,
    map,
  });

  return heatmap;
}
```

### Marker Clustering

```bash
npm install @googlemaps/markerclusterer
```

```javascript
import { MarkerClusterer } from "@googlemaps/markerclusterer";

// markers = array of AdvancedMarkerElement
const clusterer = new MarkerClusterer({ map, markers });
```

---

## Quick Reference Table

| My Maps Tool       | Maps JS API Class                        | Library Param              | Status      |
|--------------------|------------------------------------------|----------------------------|-------------|
| Add marker / pin   | `AdvancedMarkerElement`                  | `libraries=marker`         | ✅ Current  |
| Draw line          | `google.maps.Polyline`                   | built-in                   | ✅ Current  |
| Draw polygon       | `google.maps.Polygon`                    | built-in                   | ✅ Current  |
| Draw rectangle     | `google.maps.Rectangle`                  | built-in                   | ✅ Current  |
| Draw circle        | `google.maps.Circle`                     | built-in                   | ✅ Current  |
| Directions         | `DirectionsService` + `DirectionsRenderer` | built-in                 | ✅ Current  |
| Measure distance   | `geometry.spherical`                     | `libraries=geometry`       | ✅ Current  |
| Search places      | `places.Autocomplete`                    | `libraries=places`         | ✅ Current  |
| Layers             | Custom `MapLayer` class                  | built-in                   | ✅ Pattern  |
| Import KML         | `google.maps.KmlLayer`                   | built-in                   | ✅ Current  |
| Import GeoJSON     | `map.data.loadGeoJson()`                 | built-in                   | ✅ Current  |
| Import CSV         | PapaParse + `addMarker()`                | external lib               | ✅ Pattern  |
| Base map type      | `map.setMapTypeId()`                     | built-in                   | ✅ Current  |
| Custom style       | `StyledMapType` or Cloud `mapId`         | built-in                   | ✅ Current  |
| Heatmap            | `visualization.HeatmapLayer`             | `libraries=visualization`  | ✅ Current  |
| Clustering         | `@googlemaps/markerclusterer`            | npm package                | ✅ Current  |

---

## Deprecation Warnings Summary

| Deprecated Item             | Deprecated Since  | Removal     | Replacement                   |
|-----------------------------|-------------------|-------------|-------------------------------|
| `google.maps.Marker`        | February 2024     | TBD         | `AdvancedMarkerElement`       |
| `DrawingManager` UI widget  | August 2025       | May 2026    | Custom toolbar + overlay APIs |

---

## Common Patterns

### Remove / delete any overlay
```javascript
overlay.setMap(null);       // for Polyline, Polygon, Circle, Rectangle, KmlLayer
marker.map = null;          // for AdvancedMarkerElement
```

### Get coordinates from a click
```javascript
map.addListener("click", (e) => {
  const lat = e.latLng.lat();
  const lng = e.latLng.lng();
});
```

### Fit map to show all markers
```javascript
const bounds = new google.maps.LatLngBounds();
markers.forEach((m) => bounds.extend(m.position));
map.fitBounds(bounds);
```

### Convert address to coordinates
```javascript
const geocoder = new google.maps.Geocoder();
const { results } = await geocoder.geocode({ address: "Bengaluru, India" });
const { lat, lng } = results[0].geometry.location;
```
