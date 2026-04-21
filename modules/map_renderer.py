"""
Map Renderer Module - OPTIMIZED
===================
Creates interactive Folium maps with cluster polygons and hub markers.
Uses a single batched GeoJSON FeatureCollection for performance (handles 12K+ polygons).
"""

import folium
from folium import plugins
import pandas as pd
from shapely import wkt
from shapely.geometry import mapping
import json


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

        # Create base map
        m = folium.Map(
            location=center,
            zoom_start=zoom,
            tiles='OpenStreetMap',
            control_scale=True
        )

        # Build pincode-to-color mapping for pincode mode
        pincode_color_map = {}
        if color_mode == 'pincode':
            unique_pincodes = cluster_df['pincode'].dropna().unique()
            for i, pin in enumerate(sorted(unique_pincodes)):
                pincode_color_map[str(pin)] = self.PINCODE_COLORS[i % len(self.PINCODE_COLORS)]

        # ── Batch all polygons into a single GeoJSON FeatureCollection ──
        total_clusters = len(cluster_df)
        is_large = total_clusters > 500

        features = []
        for idx, row in cluster_df.iterrows():
            if pd.isna(row.get('geometry')):
                continue
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
                        "cluster_suffix": str(row.get('cluster_suffix', 'N/A')) if 'cluster_suffix' in row.index else 'N/A',
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
                    fields=['cluster_code', 'hub_name', 'pincode', 'surge_rate', 'rate_category', 'cluster_suffix'],
                    aliases=['Cluster Code', 'Hub', 'Pincode', 'Surge Rate', 'Category', 'Cluster ID'],
                    max_width=300,
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
        if show_rate_labels and total_clusters <= 300:
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
                    ).add_to(m)

        # ── Hub markers ──
        if show_hub_markers:
            relevant_hubs = hub_df[hub_df['id'].isin(cluster_df['hub_id'].unique())]
            for idx, hub in relevant_hubs.iterrows():
                self._add_hub_marker(m, hub)

        # ── Legend ──
        self._add_legend(m, pincode_color_map)

        # Fullscreen button
        plugins.Fullscreen(position='topright').add_to(m)

        return m

    def _add_hub_marker(self, map_obj, hub_row):
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

            popup_html = f"""
            <div style='width: 220px; font-family: Inter, Arial, sans-serif;'>
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
            ).add_to(map_obj)

        except Exception as e:
            print(f"Warning: Could not add hub marker for {hub_row.get('name', 'unknown')}: {e}")

    def _add_legend(self, map_obj, pincode_color_map=None):
        """Add color legend to the map"""
        if pincode_color_map and self._current_color_mode == 'pincode':
            # Build dynamic pincode legend
            pincode_items = ''
            for pin in sorted(pincode_color_map.keys()):
                color = pincode_color_map[pin]
                pincode_items += f'''
                <div style="display: flex; align-items: center;">
                    <div style="width: 20px; height: 14px; background-color: {color}; opacity: 0.7; margin-right: 6px; border: 1px solid #9CA3AF; border-radius: 2px;"></div>
                    <span style="font-size: 11px;">{pin}</span>
                </div>'''

            legend_html = f'''
            <div style="
                position: fixed;
                bottom: 50px;
                right: 50px;
                width: 200px;
                max-height: 500px;
                overflow-y: auto;
                background-color: white;
                border: 2px solid #d1d5db;
                border-radius: 8px;
                padding: 12px;
                font-family: Arial, sans-serif;
                font-size: 12px;
                z-index: 9999;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            ">
                <h4 style="margin: 0 0 8px 0; font-size: 13px; color: #1f2937; border-bottom: 2px solid #8B5CF6; padding-bottom: 5px;">
                    Pincode Legend
                </h4>
                <p style="margin: 0 0 8px 0; font-size: 10px; color: #6B7280;">Rate info in labels &amp; popups</p>
                <div style="display: flex; flex-direction: column; gap: 4px;">
                    {pincode_items}
                </div>
                <div style="margin-top: 8px; padding-top: 8px; border-top: 1px solid #e5e7eb;">
                    <div style="display: flex; align-items: center;">
                        <svg width="20" height="16" viewBox="0 0 30 30" style="margin-right: 6px;">
                            <polygon points="15,5 25,25 5,25" fill="#EF4444" stroke="#991B1B" stroke-width="2"/>
                        </svg>
                        <span style="font-weight: 500; font-size: 11px;">Hub Location</span>
                    </div>
                </div>
            </div>
            '''
        else:
            # Standard surge rate legend — all 20 actual rates
            rate_items = ''
            for rate, color in sorted(self.RATE_COLORS.items()):
                label = f"&#8377;{rate:g}"
                rate_items += f'''
                    <div style="display: flex; align-items: center;">
                        <div style="width: 22px; height: 13px; background-color: {color}; margin-right: 6px; border: 1px solid #9CA3AF; border-radius: 2px;"></div>
                        <span style="font-size: 11px;">{label}</span>
                    </div>'''

            legend_html = f'''
            <div style="
                position: fixed;
                bottom: 50px;
                right: 50px;
                width: 180px;
                max-height: 550px;
                overflow-y: auto;
                background-color: white;
                border: 2px solid #d1d5db;
                border-radius: 8px;
                padding: 12px;
                font-family: Arial, sans-serif;
                font-size: 12px;
                z-index: 9999;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            ">
                <h4 style="margin: 0 0 8px 0; font-size: 13px; color: #1f2937; border-bottom: 2px solid #3b82f6; padding-bottom: 5px;">
                    Surge Rate Legend
                </h4>
                <div style="display: flex; flex-direction: column; gap: 4px;">
                    {rate_items}
                </div>
                <div style="margin-top: 8px; padding-top: 8px; border-top: 1px solid #e5e7eb;">
                    <div style="display: flex; align-items: center;">
                        <svg width="22" height="16" viewBox="0 0 30 30" style="margin-right: 6px;">
                            <polygon points="15,5 25,25 5,25" fill="#EF4444" stroke="#991B1B" stroke-width="2"/>
                        </svg>
                        <span style="font-weight: 500; font-size: 11px;">Hub Location</span>
                    </div>
                </div>
            </div>
            '''

        map_obj.get_root().html.add_child(folium.Element(legend_html))

    def create_cpo_map(self, cluster_df, hub_df, show_rate_labels=True,
                      show_hub_markers=True, selected_hub=None):
        """Create map colored by CPO instead of surge rate"""
        center = [cluster_df['center_lat'].mean(), cluster_df['center_lon'].mean()] if len(cluster_df) > 0 else self.default_location
        zoom = 10 if len(cluster_df) > 0 else self.default_zoom

        m = folium.Map(location=center, zoom_start=zoom, tiles='OpenStreetMap')

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

                if show_rate_labels and pd.notna(row.get('center_lat')):
                    folium.Marker(
                        [row['center_lat'], row['center_lon']],
                        icon=folium.DivIcon(html=f'<div style="font-weight:bold;color:#1f2937;">\u20b9{row["cpo"]:.2f}</div>')
                    ).add_to(m)

        if show_hub_markers:
            for idx, hub in hub_df.iterrows():
                self._add_hub_marker(m, hub)

        return m
