import folium
import pandas as pd
import math
from datetime import datetime

# 🌟 ฟังก์ชันคำนวณหลักการกระจายตัว (Plume Physics) + ผลกระทบกลางคืน (Inversion)
def calculate_hazard_zones(hazard_type, wind_speed, is_night=False):
    base_zones = {
        "แอมโมเนีย (ก๊าซพิษ)": (500, 3000),
        "ไฟไหม้ / หม้อน้ำระเบิด": (100, 500),
        "ฝุ่นควัน / PM2.5": (200, 1500),
        "ค่าเริ่มต้น (ทั่วไป)": (300, 1000)
    }
    hot_m, warm_m = base_zones.get(hazard_type, (300, 1000))
    
    # Inversion Effect: สารเคมีลอยต่ำไปได้ไกลขึ้นในเวลากลางคืน (เฉพาะก๊าซและฝุ่น)
    if is_night and hazard_type in ["แอมโมเนีย (ก๊าซพิษ)", "ฝุ่นควัน / PM2.5"]:
        warm_m *= 1.5 
    
    if wind_speed <= 2:
        spread_angle = 360
        actual_warm_m = warm_m
    elif wind_speed <= 10:
        spread_angle = 90
        actual_warm_m = warm_m * 1.2
    elif wind_speed <= 25:
        spread_angle = 60
        actual_warm_m = warm_m * 1.5
    else:
        spread_angle = 30
        actual_warm_m = warm_m * 2.0
        
    return hot_m, actual_warm_m, spread_angle

def get_plume_polygon(lat, lon, distance_km, wind_dir_deg, spread_angle_deg=60):
    if spread_angle_deg >= 360: return None
    R = 6371.0
    angle_left = (wind_dir_deg - spread_angle_deg / 2) % 360
    angle_right = (wind_dir_deg + spread_angle_deg / 2) % 360
    lat_rad, lon_rad = math.radians(lat), math.radians(lon)
    polygon_coords = [[lat, lon]]
    steps = 20
    for i in range(steps + 1):
        angle_rad = math.radians(angle_left + (angle_right - angle_left) * (i / steps))
        lat_new = math.asin(math.sin(lat_rad)*math.cos(distance_km/R) + math.cos(lat_rad)*math.sin(distance_km/R)*math.cos(angle_rad))
        lon_new = lon_rad + math.atan2(math.sin(angle_rad)*math.sin(distance_km/R)*math.cos(lat_rad), math.cos(distance_km/R)-math.sin(lat_rad)*math.sin(lat_new))
        polygon_coords.append([math.degrees(lat_new), math.degrees(lon_new)])
    polygon_coords.append([lat, lon])
    return polygon_coords

def generate_map(boundary_geo, hospitals, gas_stations, df_factories, map_center, map_zoom, map_clicks, route_data, hazard_type="ค่าเริ่มต้น (ทั่วไป)", wind_speed=0, wind_dir=90):
    m = folium.Map(location=map_center, zoom_start=map_zoom)

    folium.TileLayer('http://{s}.google.com/vt/lyrs=m&x={x}&y={y}&z={z}', attr='Google', name='Google Maps (ถนน)', subdomains=['mt0', 'mt1', 'mt2', 'mt3']).add_to(m)
    folium.TileLayer('http://{s}.google.com/vt/lyrs=s,h&x={x}&y={y}&z={z}', attr='Google', name='Google Hybrid (ดาวเทียม)', subdomains=['mt0', 'mt1', 'mt2', 'mt3'], show=False).add_to(m)

    fg_boundary = folium.FeatureGroup(name="🟥 ขอบเขต อ.สันทราย")
    fg_hospital = folium.FeatureGroup(name="🏥 โรงพยาบาล")
    fg_gas = folium.FeatureGroup(name="⛽ ปั๊มน้ำมัน")
    fg_factory = folium.FeatureGroup(name="📍 โรงงาน (แยกสีตามความเสี่ยง)")
    fg_impact_zones = folium.FeatureGroup(name="🎯 รัศมีผลกระทบ")

    if boundary_geo:
        folium.GeoJson(boundary_geo, style_function=lambda x: {'color': 'red', 'weight': 4, 'fillColor': 'red', 'fillOpacity': 0.04}).add_to(fg_boundary)

    for h in hospitals:
        icon_html = "<div style='font-size:24px; filter: drop-shadow(2px 2px 2px rgba(0,0,0,0.4));'>🏥</div>"
        popup_html = f"""<div style="font-family: 'Sarabun', sans-serif; color: #333;"><b>🏥 {h['name']}</b></div>"""
        folium.Marker([h['lat'], h['lon']], icon=folium.DivIcon(html=icon_html, icon_size=(30,30), icon_anchor=(15,15)), popup=folium.Popup(popup_html, max_width=200)).add_to(fg_hospital)

    for el in gas_stations:
        lat = el.get('lat') or (el.get('center', {}).get('lat'))
        lon = el.get('lon') or (el.get('center', {}).get('lon'))
        if lat and lon:
            name = el.get('tags', {}).get('name', 'ปั๊มน้ำมันทั่วไป')
            brand = el.get('tags', {}).get('brand', '')
            icon_html = "<div style='font-size:24px; filter: drop-shadow(2px 2px 2px rgba(0,0,0,0.4));'>⛽</div>"
            popup_html = f"""<div style="font-family: 'Sarabun', sans-serif; color: #333;"><b>⛽ {name}</b><br><small>{brand}</small></div>"""
            folium.Marker([lat, lon], icon=folium.DivIcon(html=icon_html, icon_size=(30,30), icon_anchor=(15,15)), popup=folium.Popup(popup_html, max_width=250)).add_to(fg_gas)

    if not df_factories.empty:
        for idx, row in df_factories.iterrows():
            try:
                lat, lon = None, None
                for val in row.values:
                    val_str = str(val).strip().replace('"', '')
                    if ',' in val_str:
                        parts = val_str.split(',')
                        if len(parts) == 2:
                            try:
                                temp_lat, temp_lon = float(parts[0].strip()), float(parts[1].strip())
                                if 5 < temp_lat < 21 and 97 < temp_lon < 106: 
                                    lat, lon = temp_lat, temp_lon
                                    break
                            except ValueError:
                                pass
                
                if lat is not None and lon is not None:
                    full_name = str(row.iloc[1]).split('\n')[0].replace('"', '') if len(row) > 1 and pd.notna(row.iloc[1]) else 'ไม่มีชื่อ'
                    location = str(row.iloc[2]).replace('\n', '<br>') if len(row) > 2 and pd.notna(row.iloc[2]) else 'ไม่ระบุ'
                    activity = str(row.iloc[4]).replace('\n', '<br>') if len(row) > 4 and pd.notna(row.iloc[4]) else 'ไม่ระบุ'
                    risk_details = str(row.iloc[5]).replace('\n', '<br>') if len(row) > 5 and pd.notna(row.iloc[5]) else 'ไม่ระบุ'

                    # 🌟 จัดสีหมุดตามระดับความเสี่ยง (เพิ่มคำภาษาอังกฤษเพื่อความแม่นยำ)
                    text_for_color = f"{activity} {risk_details}".lower()
                    
                    if any(w in text_for_color for w in ['แอมโมเนีย', 'ammonia', 'เชื้อโรค', 'biohazard', 'ระเบิด', 'ไวไฟ', 'สารเคมีรุนแรง']):
                        marker_color, fill_color = '#b91c1c', '#ef4444' # แดง
                    elif any(w in text_for_color for w in ['หม้อน้ำ', 'boiler', 'อับอากาศ', 'confined', 'ตะกั่ว', 'lead']):
                        marker_color, fill_color = '#c2410c', '#f97316' # ส้ม
                    else:
                        marker_color, fill_color = '#b45309', '#fbbf24' # เหลือง

                    popup_html = f"""
                        <div style="min-width: 250px; font-family: 'Sarabun', sans-serif; color: #333;">
                            <h4 style="color: {marker_color}; border-bottom: 2px solid #eee; padding-bottom: 5px; margin-top: 0;">🏭 {full_name}</h4>
                            <div style="margin-bottom: 8px;"><strong>📍 สถานที่ตั้ง:</strong><br>{location}</div>
                            <div style="margin-bottom: 8px;"><strong>⚙️ การประกอบกิจการ:</strong><br>{activity}</div>
                            <div style="margin-bottom: 8px;"><strong>⚠️ ความเสี่ยง:</strong><br>{risk_details}</div>
                        </div>
                    """
                    folium.CircleMarker(location=[lat, lon], radius=8, color='white', weight=2, fill_color=fill_color, fill_opacity=0.9, popup=folium.Popup(popup_html, max_width=320)).add_to(fg_factory)
            except Exception:
                continue

    if len(map_clicks) >= 1:
        folium.Marker(map_clicks[0], icon=folium.Icon(color='darkred', icon='fire', prefix='fa'), tooltip="จุดเกิดเหตุ (Start)").add_to(m)

    if len(map_clicks) == 2 and route_data:
        rd = route_data
        start_point = rd['start']
        
        # 🌟 ตรวจสอบเวลาปัจจุบันเพื่อหากลางวัน/กลางคืน
        current_hour = datetime.now().hour
        is_night = current_hour < 6 or current_hour >= 18
        
        hot_radius, warm_radius, spread_angle = calculate_hazard_zones(hazard_type, wind_speed, is_night)
            
        folium.Circle(location=start_point, radius=max(5000, warm_radius * 2), color='#059669', weight=1, fill=True, fill_color='#059669', fill_opacity=0.05, interactive=False, tooltip="Cold Zone (พื้นที่ปลอดภัย)").add_to(fg_impact_zones)

        if spread_angle < 360:
            plume_coords = get_plume_polygon(start_point[0], start_point[1], warm_radius / 1000.0, wind_dir, spread_angle)
            if plume_coords:
                folium.Polygon(locations=plume_coords, color='#d97706', weight=2, fill=True, fill_color='#d97706', fill_opacity=0.3, interactive=False, tooltip=f"Warm Zone ({warm_radius:.0f}ม. มุม {spread_angle}°)").add_to(fg_impact_zones)
        else:
            folium.Circle(location=start_point, radius=warm_radius, color='#d97706', weight=2, fill=True, fill_color='#d97706', fill_opacity=0.3, interactive=False, tooltip=f"Warm Zone ({warm_radius:.0f}ม.)").add_to(fg_impact_zones)

        folium.Circle(location=start_point, radius=hot_radius, color='#dc2626', weight=3, fill=True, fill_color='#dc2626', fill_opacity=0.4, interactive=False, tooltip=f"Hot Zone ({hot_radius}ม.)").add_to(fg_impact_zones)

        # 🌟 วาดเส้นทางการเดินทางแบบปกติ
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
    
    compass_html = '''
    <div style="position: fixed; bottom: 50px; right: 50px; width: 75px; height: 75px; z-index: 9999; pointer-events: none;">
        <svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
            <circle cx="50" cy="50" r="45" fill="rgba(255,255,255,0.85)" stroke="#555" stroke-width="2"/>
            <path d="M50 50 L60 50 L50 90 L40 50 Z" fill="#cbd5e1"/>
            <path d="M50 10 L60 50 L40 50 Z" fill="#ef4444"/>
            <path d="M50 10 L60 50 L50 50 Z" fill="#dc2626"/>
            <path d="M50 50 L60 50 L50 90 Z" fill="#94a3b8"/>
            <text x="50" y="24" font-family="'Sarabun', sans-serif" font-size="14" font-weight="bold" fill="white" text-anchor="middle">N</text>
            <text x="50" y="86" font-family="'Sarabun', sans-serif" font-size="12" font-weight="bold" fill="#333" text-anchor="middle">S</text>
            <text x="84" y="54" font-family="'Sarabun', sans-serif" font-size="12" font-weight="bold" fill="#333" text-anchor="middle">E</text>
            <text x="16" y="54" font-family="'Sarabun', sans-serif" font-size="12" font-weight="bold" fill="#333" text-anchor="middle">W</text>
            <circle cx="50" cy="50" r="3" fill="#1e293b"/>
        </svg>
    </div>
    '''
    m.get_root().html.add_child(folium.Element(compass_html))
    
    folium.LayerControl(collapsed=False).add_to(m)
    
    return m
