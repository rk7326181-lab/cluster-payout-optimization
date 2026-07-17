"""
Map Renderer Module - OPTIMIZED
===================
Creates interactive Folium maps with cluster polygons and hub markers.
Uses a single batched GeoJSON FeatureCollection for performance (handles 12K+ polygons).
"""

import folium
from folium import plugins
from folium.plugins import MeasureControl
from branca.element import MacroElement
try:
    from jinja2 import Template as JinjaTemplate
except ImportError:
    JinjaTemplate = None
import pandas as pd
from shapely import wkt
from shapely.geometry import mapping
import json


class OsrmRouteDistanceTool(MacroElement):
    """Interactive road-distance tool — click two or more points on the map to
    measure the real driving distance via the OSRM public API.
    Works on polygons, markers, and empty map areas (clicks on any layer).
    Press ESC to clear. Click the ruler button again to deactivate.
    """
    _template = JinjaTemplate("""
    {% macro script(this, kwargs) %}
    (function(){
        var mapObj = {{ this._parent.get_name() }};
        var RouteDistControl = L.Control.extend({
            options: { position: 'topleft' },
            onAdd: function(map) {
                var container = L.DomUtil.create('div','leaflet-bar leaflet-control');
                var btn = L.DomUtil.create('a','',container);
                btn.innerHTML = '&#128207;';
                btn.title = 'Route Distance Tool  (click points → get road distance, ESC to clear)';
                btn.href = '#';
                btn.style.cssText = 'font-size:16px;line-height:30px;text-align:center;display:block;width:30px;height:30px;text-decoration:none;';
                L.DomEvent.disableClickPropagation(container);
                var active=false, points=[], layers=[], totalDist=0;
                function clearAll(){
                    layers.forEach(function(l){map.removeLayer(l);}); layers=[];
                    points=[]; totalDist=0; active=false;
                    btn.style.backgroundColor=''; btn.style.color='';
                    map.getContainer().style.cursor='';
                }
                function showInfo(){
                    if(points.length<2) return;
                    var last=points[points.length-1];
                    var lbl=L.marker(last,{icon:L.divIcon({className:'',
                        html:'<div style="background:#fff;border:2px solid #008A71;border-radius:5px;padding:4px 10px;font-size:12px;font-weight:700;white-space:nowrap;color:#008A71;box-shadow:0 2px 6px rgba(0,0,0,.2)">&#128739; '+totalDist.toFixed(2)+' km</div>',
                        iconAnchor:[-8,12]})}).addTo(map);
                    layers.push(lbl);
                }
                btn.onclick=function(e){
                    L.DomEvent.preventDefault(e);
                    if(active){clearAll();}else{
                        active=true;
                        btn.style.backgroundColor='#008A71'; btn.style.color='#fff';
                        map.getContainer().style.cursor='crosshair';
                    }
                };
                function addPoint(lat,lng){
                    if(!active) return;
                    var pt=[lat,lng]; points.push(pt);
                    var dot=L.circleMarker(pt,{radius:5,color:'#008A71',fillColor:'#008A71',fillOpacity:1,weight:2}).addTo(map);
                    layers.push(dot);
                    if(points.length>1){
                        var prev=points[points.length-2], curr=pt;
                        var url='https://router.project-osrm.org/route/v1/driving/'+prev[1]+','+prev[0]+';'+curr[1]+','+curr[0]+'?overview=full&geometries=geojson';
                        fetch(url,{signal:AbortSignal.timeout(8000)})
                            .then(function(r){return r.json();})
                            .then(function(d){
                                if(d.code==='Ok'&&d.routes&&d.routes.length){
                                    var coords=d.routes[0].geometry.coordinates.map(function(c){return[c[1],c[0]];});
                                    totalDist+=d.routes[0].distance/1000;
                                    layers.push(L.polyline(coords,{color:'#008A71',weight:3,opacity:0.85}).addTo(map));
                                } else {
                                    totalDist+=map.distance(L.latLng(prev),L.latLng(curr))/1000;
                                    layers.push(L.polyline([prev,curr],{color:'#ef4444',weight:2,dashArray:'6',opacity:0.7}).addTo(map));
                                }
                                showInfo();
                            })
                            .catch(function(){
                                totalDist+=map.distance(L.latLng(prev),L.latLng(curr))/1000;
                                layers.push(L.polyline([prev,curr],{color:'#ef4444',weight:2,dashArray:'6',opacity:0.7}).addTo(map));
                                showInfo();
                            });
                    }
                }
                window.osrmAddPoint=addPoint;
                var _osrmLastMs=0;
                function addPointOnce(lat,lng){
                    var now=Date.now(); if(now-_osrmLastMs<80) return; _osrmLastMs=now;
                    addPoint(lat,lng);
                }
                function addLayerListener(layer){
                    if(layer.eachLayer){
                        layer.eachLayer(addLayerListener);
                        layer.on('layeradd',function(ev){addLayerListener(ev.layer);});
                    } else if(layer.on){
                        layer.on('click',function(e){
                            if(!active) return;
                            addPointOnce(e.latlng.lat,e.latlng.lng);
                        });
                    }
                }
                map.eachLayer(addLayerListener);
                map.on('layeradd',function(ev){addLayerListener(ev.layer);});
                map.on('click',function(e){ addPointOnce(e.latlng.lat,e.latlng.lng); });
                document.addEventListener('keydown',function(e){if(e.key==='Escape')clearAll();});
                return container;
            }
        });
        new RouteDistControl().addTo(mapObj);
    })();
    {% endmacro %}
    """) if JinjaTemplate else None


class MapRenderer:
    """Renders interactive maps using Folium"""

    # Pastel color palette for pincode-based coloring (30 distinct light colors)
    PINCODE_COLORS = [
        '#FFB3BA', '#BAFFC9', '#BAE1FF', '#FFFFBA', '#E8BAFF',
        '#FFB3E6', '#B3FFD9', '#B3D9FF', '#FFE6B3', '#D4BAFF',
        '#BAFFD4', '#FFD4BA', '#BAF2FF', '#FFB3CC', '#C9FFB3',
        '#B3FFEE', '#FFCCB3', '#CCB3FF', '#B3FFC9', '#FFE0CC',
        '#CCE0FF', '#E0FFD1', '#FFD1E0', '#D1FFE0', '#E0D1FF',
        '#FFE8D1', '#D1F0FF', '#F0FFD1', '#FFD1F0', '#FFDFBA',
    ]

    # Color scheme for the 20 actual surge rates
    RATE_COLORS = {
        0.0:  '#9CA3AF',   # 1  — Rs.0.00   Gray (Base)
        0.5:  '#BFDBFE',   # 2  — Rs.0.50   Very light blue
        1.0:  '#93C5FD',   # 3  — Rs.1.00   Light blue
        1.5:  '#60A5FA',   # 4  — Rs.1.50   Blue
        2.0:  '#3B82F6',   # 5  — Rs.2.00   Medium blue
        2.5:  '#2563EB',   # 6  — Rs.2.50   Bright blue
        3.0:  '#1D4ED8',   # 7  — Rs.3.00   Dark blue
        3.5:  '#6366F1',   # 8  — Rs.3.50   Indigo
        4.0:  '#8B5CF6',   # 9  — Rs.4.00   Purple
        4.5:  '#A78BFA',   # 10 — Rs.4.50   Light purple
        5.0:  '#FCD34D',   # 11 — Rs.5.00   Yellow
        6.0:  '#FBBF24',   # 12 — Rs.6.00   Amber
        7.0:  '#F59E0B',   # 13 — Rs.7.00   Orange-yellow
        8.0:  '#F97316',   # 14 — Rs.8.00   Orange
        9.0:  '#FB923C',   # 15 — Rs.9.00   Light orange
        10.0: '#EF4444',   # 16 — Rs.10.00  Red
        11.0: '#DC2626',   # 17 — Rs.11.00  Dark red
        12.0: '#B91C1C',   # 18 — Rs.12.00  Deeper red
        13.0: '#991B1B',   # 19 — Rs.13.00  Maroon
        15.0: '#7F1D1D',   # 20 — Rs.15.00  Dark maroon
    }

    def __init__(self):
        self.default_location = [20.5937, 78.9629]  # Center of India
        self.default_zoom = 5
        # Constrain panning + zoom to India only. Reduces tile fetches by
        # ~95% (no Africa / Americas / Asia-Pacific to render) and lowers
        # both browser memory and server-side HTML payload.
        # Bounds: south-west (Kanyakumari) to north-east (Arunachal Pradesh).
        self.INDIA_BOUNDS = [[5.5, 67.0], [37.6, 98.0]]
        self.MIN_ZOOM = 4
        self.MAX_ZOOM = 15

    def _get_rate_color(self, rate):
        """Get color for a given rate (handles decimal rates)"""
        rate = float(rate)
        closest_rate = min(self.RATE_COLORS.keys(), key=lambda x: abs(x - rate))
        return self.RATE_COLORS.get(closest_rate, '#9CA3AF')

    @staticmethod
    def _reduce_precision(geojson, decimals=4):
        """Round coordinates to fewer decimal places to shrink HTML payload."""
        def _round_coords(coords):
            if isinstance(coords[0], (list, tuple)):
                return [_round_coords(c) for c in coords]
            return [round(c, decimals) for c in coords]

        geo = dict(geojson)
        if 'coordinates' in geo:
            geo['coordinates'] = _round_coords(geo['coordinates'])
        return geo

    def create_cluster_map(self, cluster_df, hub_df, show_rate_labels=True,
                          show_hub_markers=True, selected_hub=None,
                          color_mode='rate'):
        """
        Create interactive map with cluster polygons and hub markers.
        Uses batched GeoJSON for performance with large datasets.
        """
        self._current_color_mode = color_mode

        # Determine map center
        if selected_hub and len(cluster_df[cluster_df['hub_name'] == selected_hub]) > 0:
            hub_data = hub_df[hub_df['name'] == selected_hub].iloc[0]
            center = [hub_data['latitude'], hub_data['longitude']]
            zoom = 11
        elif len(cluster_df) > 0 and 'center_lat' in cluster_df.columns:
            center = [
                cluster_df['center_lat'].mean(),
                cluster_df['center_lon'].mean()
            ]
            zoom = 10
        else:
            center = self.default_location
            zoom = self.default_zoom

        # Create base map clamped to India only — no panning outside, no
        # zoom levels that fetch global tiles. Big win on memory + tile
        # bandwidth on Streamlit Cloud.
        m = folium.Map(
            location=center,
            zoom_start=zoom,
            tiles='OpenStreetMap',
            control_scale=True,
            min_zoom=self.MIN_ZOOM,
            max_zoom=self.MAX_ZOOM,
            max_bounds=True,
        )
        m.fit_bounds(self.INDIA_BOUNDS)

        # Build pincode-to-color mapping for pincode mode
        pincode_color_map = {}
        if color_mode == 'pincode':
            unique_pincodes = cluster_df['pincode'].dropna().unique()
            for i, pin in enumerate(sorted(unique_pincodes)):
                pincode_color_map[str(pin)] = self.PINCODE_COLORS[i % len(self.PINCODE_COLORS)]

        # ── Batch all polygons into a single GeoJSON FeatureCollection ──
        total_clusters = len(cluster_df)
        is_large = total_clusters > 500

        # Pre-check optional columns once — avoids per-row index lookups
        _has_suffix   = 'cluster_suffix' in cluster_df.columns
        _has_created  = 'created' in cluster_df.columns
        _has_modified = 'modified' in cluster_df.columns

        # Helper defined outside loop — function objects are expensive inside iterrows
        def _fmt_dt(v):
            s = str(v) if v is not None else ''
            if s in ('', 'nan', 'NaT', 'None'):
                return ''
            # Trim microseconds: 2025-06-02T18:30:00.144754 → 2025-06-02 18:30:00
            return s.replace('T', ' ').split('.')[0]

        # Pre-filter rows with valid geometry — skips isna() check per iteration
        _render_df = cluster_df[cluster_df['geometry'].notna()]

        features = []
        for idx, row in _render_df.iterrows():
            try:
                geom = row['geometry']
                surge_amount = row.get('surge_amount', 0)
                pincode = str(row.get('pincode', ''))
                cluster_category = row.get('cluster_category', f'Rs.{surge_amount}')

                if color_mode == 'pincode' and pincode in pincode_color_map:
                    fill_color = pincode_color_map[pincode]
                    fill_opacity = 0.35
                else:
                    fill_color = self._get_rate_color(surge_amount)
                    fill_opacity = 0.5

                geo = mapping(geom)

                # Reduce coordinate precision for large datasets (shrinks HTML ~40%)
                if is_large:
                    geo = self._reduce_precision(geo, 4)

                feature = {
                    "type": "Feature",
                    "geometry": geo,
                    "properties": {
                        "fillColor": fill_color,
                        "fillOpacity": fill_opacity,
                        "cluster_code": str(row.get('cluster_code', 'N/A')),
                        "hub_name": str(row.get('hub_name', 'N/A')),
                        "pincode": pincode,
                        "surge_rate": str(cluster_category),
                        "rate_category": str(row.get('rate_category', 'N/A')),
                        "cluster_suffix": str(row.get('cluster_suffix', 'N/A')) if _has_suffix else 'N/A',
                        "created": _fmt_dt(row.get('created', '')) if _has_created else '',
                        "modified": _fmt_dt(row.get('modified', '')) if _has_modified else '',
                    }
                }
                features.append(feature)
            except Exception:
                continue

        if features:
            feature_collection = {"type": "FeatureCollection", "features": features}

            border_color = '#6B7280' if color_mode == 'pincode' else '#374151'
            border_weight = 1 if is_large else 1.5

            geojson_kwargs = dict(
                style_function=lambda feature, bc=border_color, bw=border_weight: {
                    'fillColor': feature['properties']['fillColor'],
                    'color': bc,
                    'weight': bw,
                    'fillOpacity': feature['properties']['fillOpacity'],
                },
                tooltip=folium.GeoJsonTooltip(
                    fields=['pincode', 'cluster_code', 'surge_rate'],
                    aliases=['Pincode:', 'Cluster:', 'Rate:'],
                    sticky=True,
                    style="font-size: 12px;"
                ),
                popup=folium.GeoJsonPopup(
                    fields=['cluster_code', 'hub_name', 'pincode', 'surge_rate',
                            'rate_category', 'cluster_suffix', 'created', 'modified'],
                    aliases=['Cluster Code', 'Hub', 'Pincode', 'Surge Rate',
                             'Category', 'Cluster ID', 'Created', 'Modified'],
                    max_width=320,
                    style="font-size: 12px;"
                ),
            )

            # Disable highlight for large datasets (saves JS overhead per feature)
            if not is_large:
                geojson_kwargs['highlight_function'] = lambda feature: {
                    'weight': 3,
                    'fillOpacity': 0.7,
                    'color': '#1f2937'
                }

            folium.GeoJson(feature_collection, **geojson_kwargs).add_to(m)

        # ── Rate labels — ONLY for small datasets (single hub view) ──
        # Each label = 1 DOM element. 12K labels = browser crash.
        # Hard cap at 300 clusters to keep the page responsive.
        rate_label_fg = folium.FeatureGroup(name="Rate Labels", show=show_rate_labels)
        if total_clusters <= 300:
            for idx, row in cluster_df.iterrows():
                if pd.notna(row.get('center_lat')) and pd.notna(row.get('center_lon')) and pd.notna(row.get('geometry')):
                    surge_amount = row.get('surge_amount', 0)
                    if surge_amount == int(surge_amount):
                        rate_text = f"\u20b9{int(surge_amount)}"
                    else:
                        rate_text = f"\u20b9{surge_amount:.1f}"

                    folium.Marker(
                        location=[row['center_lat'], row['center_lon']],
                        icon=folium.DivIcon(html=f"""
                            <div style='
                                font-size: 12px;
                                font-weight: bold;
                                color: #1f2937;
                                text-shadow:
                                    -1px -1px 0 white,
                                    1px -1px 0 white,
                                    -1px 1px 0 white,
                                    1px 1px 0 white;
                                background-color: rgba(255,255,255,0.8);
                                padding: 2px 6px;
                                border-radius: 3px;
                                border: 1px solid #6B7280;
                                white-space: nowrap;
                                transform: translate(-50%, -50%);
                            '>{rate_text}</div>
                        """)
                    ).add_to(rate_label_fg)
        rate_label_fg.add_to(m)

        # -- Hub markers -- grouped for clean LayerControl --
        # Skip hubs without coordinates - the raw hub_data may now contain
        # rows with NaN lat/long (BigQuery fetch keeps all rows).
        hub_fg = folium.FeatureGroup(name="Hub Markers", show=show_hub_markers)
        if show_hub_markers:
            relevant_hubs = hub_df[
                hub_df['id'].isin(cluster_df['hub_id'].unique())
                & hub_df['latitude'].notna()
                & hub_df['longitude'].notna()
            ]
            for idx, hub in relevant_hubs.iterrows():
                self._add_hub_marker(hub_fg, hub)
        hub_fg.add_to(m)

        # -- Legend --
        self._add_legend(m, pincode_color_map)

        # -- Map controls --
        plugins.Fullscreen(position='topright').add_to(m)
        # Haversine straight-line distance (ruler icon, top-left)
        MeasureControl(
            position='topleft',
            primary_length_unit='kilometers',
            secondary_length_unit='meters',
            primary_area_unit='sqkilometers',
        ).add_to(m)
        folium.LayerControl(position='topright', collapsed=True).add_to(m)
        # OSRM road-distance ruler (click any point on map/polygon/marker)
        if OsrmRouteDistanceTool._template is not None:
            OsrmRouteDistanceTool().add_to(m)

        return m

    def _add_hub_marker(self, map_obj_or_fg, hub_row):
        """Add a hub location marker to the map"""
        try:
            # Home-style hub marker (Precision Navigator green)
            icon_html = """
            <svg width="32" height="38" viewBox="0 0 32 38" xmlns="http://www.w3.org/2000/svg">
                <path d="M16 0C7.2 0 0 7.2 0 16c0 11 16 22 16 22s16-11 16-22C32 7.2 24.8 0 16 0z"
                      fill="#008A71" stroke="#005141" stroke-width="1.5"/>
                <path d="M16 8L8 15v8h5v-5h6v5h5v-8L16 8z" fill="white" opacity="0.95"/>
            </svg>
            """

            _created = str(hub_row.get('creation_date', '') or '').strip()
            if _created.lower() in ('nan', 'nat', 'none'):
                _created = ''
            _created_row = (
                f"""
                    <tr>
                        <td style='padding: 5px; font-weight: bold;'>Hub Created:</td>
                        <td style='padding: 5px;'>{_created}</td>
                    </tr>
                """ if _created else ""
            )

            popup_html = f"""
            <div style='width: 240px; font-family: Inter, Arial, sans-serif;'>
                <h4 style='margin: 0 0 10px 0; color: #1b1c1c; border-bottom: 2px solid #008A71; padding-bottom: 5px;
                    font-family: Montserrat, sans-serif; font-size: 13px;'>
                    {hub_row['name']}
                </h4>
                <table style='width: 100%; font-size: 12px; border-collapse: collapse;'>
                    <tr style='background-color: rgba(0,138,113,0.06);'>
                        <td style='padding: 5px; font-weight: bold;'>Hub ID:</td>
                        <td style='padding: 5px;'>{hub_row['id']}</td>
                    </tr>
                    <tr>
                        <td style='padding: 5px; font-weight: bold;'>Category:</td>
                        <td style='padding: 5px;'>{hub_row.get('hub_category', 'N/A')}</td>
                    </tr>
                    {_created_row}
                    <tr style='background-color: rgba(0,138,113,0.06);'>
                        <td style='padding: 5px; font-weight: bold;'>Latitude:</td>
                        <td style='padding: 5px;'>{hub_row['latitude']:.6f}</td>
                    </tr>
                    <tr>
                        <td style='padding: 5px; font-weight: bold;'>Longitude:</td>
                        <td style='padding: 5px;'>{hub_row['longitude']:.6f}</td>
                    </tr>
                </table>
            </div>
            """

            folium.Marker(
                location=[hub_row['latitude'], hub_row['longitude']],
                popup=folium.Popup(popup_html, max_width=260),
                tooltip=f"Hub: {hub_row['name']}",
                icon=folium.DivIcon(html=f'<div style="margin-left: -15px; margin-top: -15px;">{icon_html}</div>')
            ).add_to(map_obj_or_fg)

        except Exception as e:
            print(f"Warning: Could not add hub marker for {hub_row.get('name', 'unknown')}: {e}")

    def _add_legend(self, map_obj, pincode_color_map=None):
        """Add collapsible color legend to the map"""
        hub_entry = '''
                <div style="margin-top:8px;padding-top:8px;border-top:1px solid #e5e7eb;">
                    <div style="display:flex;align-items:center;">
                        <svg width="22" height="16" viewBox="0 0 32 38" style="margin-right:6px;">
                            <path d="M16 0C7.2 0 0 7.2 0 16c0 11 16 22 16 22s16-11 16-22C32 7.2 24.8 0 16 0z" fill="#008A71" stroke="#005141" stroke-width="1.5"/>
                            <path d="M16 8L8 15v8h5v-5h6v5h5v-8L16 8z" fill="white" opacity="0.95"/>
                        </svg>
                        <span style="font-weight:500;font-size:11px;">Hub Location</span>
                    </div>
                </div>'''

        if pincode_color_map and self._current_color_mode == 'pincode':
            # Build dynamic pincode legend
            pincode_items = ''
            for pin in sorted(pincode_color_map.keys()):
                color = pincode_color_map[pin]
                pincode_items += f'''
                <div style="display:flex;align-items:center;">
                    <div style="width:20px;height:14px;background-color:{color};opacity:0.7;margin-right:6px;border:1px solid #9CA3AF;border-radius:2px;"></div>
                    <span style="font-size:11px;">{pin}</span>
                </div>'''

            legend_html = f'''
            <div style="position:fixed;bottom:50px;right:50px;width:200px;
                background-color:white;border:2px solid #d1d5db;border-radius:8px;
                padding:10px 12px;font-family:Arial,sans-serif;font-size:12px;
                z-index:9999;box-shadow:0 4px 6px rgba(0,0,0,0.1);">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:5px">
                    <span style="font-size:13px;font-weight:700;color:#1f2937;border-bottom:2px solid #8B5CF6;padding-bottom:3px;flex:1">Pincode Legend</span>
                    <button onclick="var b=document.getElementById('_cpo_pin_body');var v=b.style.display!=='none';b.style.display=v?'none':'block';this.textContent=v?'+':'−'"
                        style="background:none;border:1px solid #9ca3af;border-radius:3px;padding:1px 6px;cursor:pointer;font-size:13px;font-weight:700;color:#6b7280;margin-left:6px;line-height:1.3">−</button>
                </div>
                <div id="_cpo_pin_body" style="max-height:300px;overflow-y:auto">
                    <p style="margin:0 0 6px 0;font-size:10px;color:#6B7280;">Rate info in labels &amp; popups</p>
                    <div style="display:flex;flex-direction:column;gap:4px;">
                        {pincode_items}
                    </div>
                    {hub_entry}
                </div>
            </div>
            '''
        else:
            # Standard surge rate legend — all 20 actual rates
            rate_items = ''
            for rate, color in sorted(self.RATE_COLORS.items()):
                label = f"&#8377;{rate:g}"
                rate_items += f'''
                    <div style="display:flex;align-items:center;">
                        <div style="width:22px;height:13px;background-color:{color};margin-right:6px;border:1px solid #9CA3AF;border-radius:2px;"></div>
                        <span style="font-size:11px;">{label}</span>
                    </div>'''

            legend_html = f'''
            <div style="position:fixed;bottom:50px;right:50px;width:180px;
                background-color:white;border:2px solid #d1d5db;border-radius:8px;
                padding:10px 12px;font-family:Arial,sans-serif;font-size:12px;
                z-index:9999;box-shadow:0 4px 6px rgba(0,0,0,0.1);">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:5px">
                    <span style="font-size:13px;font-weight:700;color:#1f2937;border-bottom:2px solid #3b82f6;padding-bottom:3px;flex:1">Surge Rate Legend</span>
                    <button onclick="var b=document.getElementById('_surge_rate_body');var v=b.style.display!=='none';b.style.display=v?'none':'block';this.textContent=v?'+':'−'"
                        style="background:none;border:1px solid #9ca3af;border-radius:3px;padding:1px 6px;cursor:pointer;font-size:13px;font-weight:700;color:#6b7280;margin-left:6px;line-height:1.3">−</button>
                </div>
                <div id="_surge_rate_body" style="max-height:400px;overflow-y:auto">
                    <div style="display:flex;flex-direction:column;gap:4px;">
                        {rate_items}
                    </div>
                    {hub_entry}
                </div>
            </div>
            '''

        map_obj.get_root().html.add_child(folium.Element(legend_html))

    def create_cpo_map(self, cluster_df, hub_df, show_rate_labels=True,
                      show_hub_markers=True, selected_hub=None):
        """Create map colored by CPO instead of surge rate"""
        center = [cluster_df['center_lat'].mean(), cluster_df['center_lon'].mean()] if len(cluster_df) > 0 else self.default_location
        zoom = 10 if len(cluster_df) > 0 else self.default_zoom

        m = folium.Map(
            location=center, zoom_start=zoom, tiles='OpenStreetMap',
            min_zoom=self.MIN_ZOOM, max_zoom=self.MAX_ZOOM, max_bounds=True,
        )
        m.fit_bounds(self.INDIA_BOUNDS)

        for idx, row in cluster_df.iterrows():
            if pd.notna(row.get('geometry')) and pd.notna(row.get('cpo')):
                from cpo_optimizer import get_cpo_color
                color = get_cpo_color(row['cpo'])

                geo_json = mapping(row['geometry'])

                popup_html = f"""
                <div style='width: 280px'>
                    <h4>{row.get('cluster_code', 'N/A')}</h4>
                    <p><b>Hub:</b> {row.get('hub_name', 'N/A')}</p>
                    <p><b>CPO:</b> \u20b9{row['cpo']:.2f}</p>
                    <p><b>Surge:</b> \u20b9{row.get('surge_amount', 0)}</p>
                    <p><b>Category:</b> {row.get('cpo_category', 'N/A')}</p>
                </div>
                """

                folium.GeoJson(
                    geo_json,
                    style_function=lambda x, color=color: {
                        'fillColor': color, 'color': '#374151', 'weight': 2, 'fillOpacity': 0.5
                    },
                    popup=folium.Popup(popup_html, max_width=320)
                ).add_to(m)

        # FeatureGroups for clean LayerControl
        cpo_label_fg = folium.FeatureGroup(name="CPO Labels", show=show_rate_labels)
        for idx, row in cluster_df.iterrows():
            if pd.notna(row.get('geometry')) and pd.notna(row.get('cpo')) and pd.notna(row.get('center_lat')):
                folium.Marker(
                    [row['center_lat'], row['center_lon']],
                    icon=folium.DivIcon(html=f'<div style="font-size:11px;font-weight:bold;background:rgba(255,255,255,0.85);padding:2px 5px;border-radius:3px;border:1px solid #6B7280;white-space:nowrap;color:#1f2937;">\u20b9{row["cpo"]:.2f}</div>')
                ).add_to(cpo_label_fg)
        cpo_label_fg.add_to(m)

        hub_fg = folium.FeatureGroup(name="Hub Markers", show=show_hub_markers)
        if show_hub_markers:
            for idx, hub in hub_df.iterrows():
                self._add_hub_marker(hub_fg, hub)
        hub_fg.add_to(m)

        plugins.Fullscreen(position='topright').add_to(m)
        MeasureControl(
            position='topleft',
            primary_length_unit='kilometers',
            secondary_length_unit='meters',
            primary_area_unit='sqkilometers',
        ).add_to(m)
        folium.LayerControl(position='topright', collapsed=True).add_to(m)
        if OsrmRouteDistanceTool._template is not None:
            OsrmRouteDistanceTool().add_to(m)

        return m
