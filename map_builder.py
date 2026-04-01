import folium
import pandas as pd
import streamlit as st

def generate_map(boundary_geo, hospitals, gas_stations, df_factories, map_center, map_zoom, map_clicks, route_data):
    m = folium.Map(location=map_center, zoom_start=map_zoom)

    folium.TileLayer('http://{s}.google.com/vt/lyrs=m&x={x}&y={y}&z={z}', attr='Google', name='Google Maps (ถนน)', subdomains=['mt0', 'mt1', 'mt2', 'mt3']).add_to(m)
    folium.TileLayer('http://{s}.google.com/vt/lyrs=s,h&x={x}&y={y}&z={z}', attr='Google', name='Google Hybrid (ดาวเทียม)', subdomains=['mt0', 'mt1', 'mt2', 'mt3'], show=False).add_to(m)

    fg_boundary = folium.FeatureGroup(name="🟥 ขอบเขต อ.สันทราย")
    fg_hospital = folium.FeatureGroup(name="🏥 โรงพยาบาล")
    fg_gas = folium.FeatureGroup(name="⛽ ปั๊มน้ำมัน")
    fg_factory = folium.FeatureGroup(name="📍 โรงงาน") # เอาคำว่า (ตามความเสี่ยง) ออก
    fg_impact_zones = folium.FeatureGroup(name="🎯 รัศมีผลกระทบ (คำนวณอัตโนมัติ)")

    if boundary_geo:
        folium.GeoJson(boundary_geo, style_function=lambda x: {'color': 'red', 'weight': 4, 'fillColor': 'red', 'fillOpacity': 0.04}).add_to(fg_boundary)

    for h in hospitals:
        icon_html = "<div style='font-size:24px; filter: drop-shadow(2px 2px 2px rgba(0,0,0,0.4));'>🏥</div>"
        popup_html = f"""<div style="font-family: 'Google Sans', 'Noto Sans Thai', sans-serif; color: #333;"><b>🏥 {h['name']}</b></div>"""
        folium.Marker([h['lat'], h['lon']], icon=folium.DivIcon(html=icon_html, icon_size=(30,30), icon_anchor=(15,15)), popup=folium.Popup(popup_html, max_width=200)).add_to(fg_hospital)

    for el in gas_stations:
        lat = el.get('lat') or (el.get('center', {}).get('lat'))
        lon = el.get('lon') or (el.get('center', {}).get('lon'))
        if lat and lon:
            name = el.get('tags', {}).get('name', 'ปั๊มน้ำมันทั่วไป')
            brand = el.get('tags', {}).get('brand', '')
            icon_html = "<div style='font-size:24px; filter: drop-shadow(2px 2px 2px rgba(0,0,0,0.4));'>⛽</div>"
            popup_html = f"""<div style="font-family: 'Google Sans', 'Noto Sans Thai', sans-serif; color: #333;"><b>⛽ {name}</b><br><small>{brand}</small></div>"""
            folium.Marker([lat, lon], icon=folium.DivIcon(html=icon_html, icon_size=(30,30), icon_anchor=(15,15)), popup=folium.Popup(popup_html, max_width=250)).add_to(fg_gas)

    if not df_factories.empty:
        for idx, row in df_factories.iterrows():
            try:
                if len(row) >= 8 and pd.notna(row.iloc[7]):
                    coords_str = str(row.iloc[7]).strip()
                    if ',' in coords_str:
                        lat_str, lon_str = coords_str.replace('"', '').split(',')
                        lat, lon = float(lat_str.strip()), float(lon_str.strip())
                        
                        full_name = str(row.iloc[1]).split('\n')[0].replace('"', '') if pd.notna(row.iloc[1]) else 'ไม่มีชื่อ'
                        location = str(row.iloc[2]).replace('\n', '<br>') if pd.notna(row.iloc[2]) else 'ไม่ระบุ'
                        activity = str(row.iloc[4]).replace('\n', '<br>') if pd.notna(row.iloc[4]) else 'ไม่ระบุ'
                        risk_details = str(row.iloc[5]).replace('\n', '<br>') if pd.notna(row.iloc[5]) else 'ไม่ระบุ'

                        # ปรับให้เป็นสีเทาทั้งหมดโดยไม่มีเงื่อนไขความเสี่ยง
                        marker_color, fill_color = '#7f8c8d', '#bdc3c7'

                        # เอาข้อมูลความเสี่ยงออกจาก Popup ด้วย
                        popup_html = f"""
                            <div style="min-width: 250px; font-family: 'Google Sans', 'Noto Sans Thai', sans-serif; color: #333;">
                                <h4 style="color: {marker_color}; border-bottom: 2px solid #eee; padding-bottom: 5px; margin-top: 0;">🏭 {full_name}</h4>
                                <div style="margin-bottom: 8px;"><strong>📍 สถานที่ตั้ง:</strong><br>{location}</div>
                                <div style="margin-bottom: 8px;"><strong>⚙️ การประกอบกิจการ:</strong><br>{activity}</div>
                                <div style="margin-bottom: 8px;"><strong>🔥 ความเสี่ยง:</strong><br>{risk_details}</div>
                            </div>
                        """
                        folium.CircleMarker(location=[lat, lon], radius=8, color='white', weight=2, fill_color=fill_color, fill_opacity=0.95, popup=folium.Popup(popup_html, max_width=320)).add_to(fg_factory)
            except Exception:
                continue

    if len(map_clicks) >= 1:
        folium.Marker(map_clicks[0], icon=folium.Icon(color='darkred', icon='fire', prefix='fa'), tooltip="จุดเกิดเหตุ (Start)").add_to(m)

    if len(map_clicks) == 2 and route_data:
        rd = route_data
        start_point = rd['start']
        
        folium.Circle(location=start_point, radius=5000, color='#059669', weight=1, fill=True, fill_color='#059669', fill_opacity=0.05, interactive=False).add_to(fg_impact_zones)
        folium.Circle(location=start_point, radius=2000, color='#d97706', weight=2, fill=True, fill_color='#d97706', fill_opacity=0.1, interactive=False).add_to(fg_impact_zones)
        folium.Circle(location=start_point, radius=500, color='#dc2626', weight=3, fill=True, fill_color='#dc2626', fill_opacity=0.2, interactive=False).add_to(fg_impact_zones)

        folium.PolyLine(rd['coords'], color="#3388ff", weight=5, opacity=0.8, tooltip=f"ระยะทางขับรถ {rd['dist']:.1f} กม.").add_to(m)
        folium.Marker(rd['end'], icon=folium.Icon(color='green', icon='flag', prefix='fa'), tooltip="จุดปลายทาง (End)").add_to(m)
        
        min_lat, max_lat = min(start_point[0], rd['end'][0]) - 0.045, max(start_point[0], rd['end'][0]) + 0.045
        min_lon, max_lon = min(start_point[1], rd['end'][1]) - 0.045, max(start_point[1], rd['end'][1]) + 0.045
        m.fit_bounds([[min_lat, min_lon], [max_lat, max_lon]])

    fg_boundary.add_to(m)
    fg_hospital.add_to(m)
    fg_gas.add_to(m)
    fg_factory.add_to(m)
    fg_impact_zones.add_to(m) 
    folium.LayerControl(collapsed=False).add_to(m)
    
    return m
