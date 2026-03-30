import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import requests
import math

# ==========================================
# 1. การตั้งค่าหน้าเว็บ Streamlit และ ฟอนต์ Google Sans
# ==========================================
st.set_page_config(page_title="แผนที่โรงงาน อ.สันทราย", layout="wide", page_icon="📍")

# แทรก CSS เพื่อโหลดฟอนต์ โดยปรับให้ปลอดภัย ไม่ไปกระทบกับไอคอน (SVG) ของ Streamlit
st.markdown("""
    <style>
        @import url('https://fonts.cdnfonts.com/css/google-sans');
        @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+Thai:wght@300;400;500;600;700&display=swap');
        
        /* กำหนดฟอนต์ให้เฉพาะแท็กข้อความทั่วไป */
        html, body, p, h1, h2, h3, h4, h5, h6, span, label, div {
            font-family: 'Google Sans', 'Noto Sans Thai', sans-serif;
        }
        
        /* ป้องกันไม่ให้ฟอนต์ไปทับไอคอนลูกศร, เมนูย่อขยาย หรือกราฟิก SVG ต่างๆ */
        svg, svg *, i, .material-icons, [class*="icon"] {
            font-family: inherit !important;
        }
    </style>
""", unsafe_allow_html=True)

st.title("📍 แผนที่ความเสี่ยงโรงงาน อ.สันทราย จ.เชียงใหม่")
st.markdown("แสดงพิกัดโรงงานตามระดับความเสี่ยง พร้อมเลเยอร์ขอบเขต ปั๊มน้ำมัน และโรงพยาบาล")

# ==========================================
# 2. ฟังก์ชันดึงข้อมูล ระบบนำทาง และคำนวณระยะ
# ==========================================

@st.cache_data(ttl=3600)
def load_boundary():
    url = 'https://nominatim.openstreetmap.org/search?q=อำเภอสันทราย+จังหวัดเชียงใหม่&format=geojson&polygon_geojson=1&limit=1'
    try:
        headers = {'User-Agent': 'FactoryRiskMapApp/1.0 (Streamlit)'}
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code == 200:
            data = r.json()
            features = [f for f in data.get('features', []) if f.get('geometry', {}).get('type') in ['Polygon', 'MultiPolygon']]
            if features:
                return features[0]
            else:
                st.sidebar.warning("⚠️ ไม่พบข้อมูลรูปแปลงขอบเขต อ.สันทราย จากเซิร์ฟเวอร์")
        else:
             st.sidebar.error(f"โหลดขอบเขตไม่สำเร็จ (Status: {r.status_code})")
    except Exception as e:
        st.sidebar.error(f"โหลดขอบเขตไม่สำเร็จ: {e}")
    return None

@st.cache_data(ttl=3600)
def load_gas_stations():
    query = """[out:json][timeout:30];
    rel["name"~"สันทราย"]["admin_level"="6"];
    map_to_area -> .searchArea;
    (node["amenity"="fuel"](area.searchArea); way["amenity"="fuel"](area.searchArea););
    out center;"""
    url = 'https://overpass-api.de/api/interpreter'
    try:
        headers = {'User-Agent': 'FactoryRiskMapApp/1.0 (Streamlit)'}
        r = requests.post(url, data={'data': query}, headers=headers, timeout=30)
        if r.status_code == 200:
            return r.json().get('elements', [])
    except Exception as e:
        pass
    return []

@st.cache_data(ttl=300)
def load_factories():
    sheet_url = 'https://docs.google.com/spreadsheets/d/1qHJwpzbaFbn-ayQs4iAHodxAh1Lh5xiUuUHIL5t9v7k/export?format=csv&gid=0'
    try:
        return pd.read_csv(sheet_url)
    except Exception as e:
        return pd.DataFrame()

# ฟังก์ชันดึงข้อมูลเส้นทางขับรถจริง (OSRM API)
def get_driving_route(lat1, lon1, lat2, lon2):
    url = f"http://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}?overview=full&geometries=geojson"
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            data = r.json()
            if data['code'] == 'Ok':
                route = data['routes'][0]
                distance_km = route['distance'] / 1000.0  
                duration_min = route['duration'] / 60.0   
                geometry = route['geometry']['coordinates']
                route_coords = [[coord[1], coord[0]] for coord in geometry]
                return distance_km, duration_min, route_coords
    except Exception as e:
        pass
    return None, None, None

# ฟังก์ชันคำนวณระยะกระจัด (เส้นตรง) เพื่อประเมินรัศมีผลกระทบ
def calculate_straight_distance(lat1, lon1, lat2, lon2):
    R = 6371.0 # รัศมีโลก (กม.)
    lat1_rad, lon1_rad = math.radians(lat1), math.radians(lon1)
    lat2_rad, lon2_rad = math.radians(lat2), math.radians(lon2)
    dlon = lon2_rad - lon1_rad
    dlat = lat2_rad - lat1_rad
    a = math.sin(dlat / 2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

# ==========================================
# 3. จัดการ State สำหรับระบบคลิกแผนที่และการจดจำมุมมอง
# ==========================================
if "map_center" not in st.session_state:
    st.session_state.map_center = [18.9135, 99.0279]
if "map_zoom" not in st.session_state:
    st.session_state.map_zoom = 11

if "map_clicks" not in st.session_state:
    st.session_state.map_clicks = [] 
if "last_processed_click" not in st.session_state:
    st.session_state.last_processed_click = None 
if "route_data" not in st.session_state:
    st.session_state.route_data = None 

# หากผู้ใช้คลิกครบ 2 จุด ให้คำนวณเส้นทางอัตโนมัติก่อนที่จะนำไปวาดบนแผนที่
if len(st.session_state.map_clicks) == 2 and st.session_state.route_data is None:
    with st.spinner('กำลังประมวลผลเส้นทาง...'):
        lat1, lon1 = st.session_state.map_clicks[0]
        lat2, lon2 = st.session_state.map_clicks[1]
        
        dist_km, dur_min, coords = get_driving_route(lat1, lon1, lat2, lon2)
        straight_dist = calculate_straight_distance(lat1, lon1, lat2, lon2)
        
        if dist_km is not None:
            st.session_state.route_data = {
                'dist': dist_km,
                'dur': dur_min,
                'coords': coords,
                'start': (lat1, lon1),
                'end': (lat2, lon2),
                'straight_dist': straight_dist
            }
        else:
            st.sidebar.error("❌ ไม่สามารถคำนวณเส้นทางได้ (จุดที่คลิกอาจอยู่ห่างไกลถนนเกินไป)")
            # ลบจุดที่ 2 ออกเพื่อให้คลิกใหม่ได้
            st.session_state.map_clicks.pop()

# ==========================================
# 4. ส่วนแถบเมนูด้านข้าง (Sidebar)
# ==========================================
st.sidebar.header("⚙️ การจัดการข้อมูล")

if st.sidebar.button("🔄 รีโหลดข้อมูลโรงงานล่าสุด", use_container_width=True):
    load_factories.clear()
    st.sidebar.success("อัปเดตข้อมูลจากชีตแล้ว!")

st.sidebar.markdown("---")
st.sidebar.markdown("### 📌 คำนิยามระดับความเสี่ยง")

st.sidebar.error("**🔴 เสี่ยงสูง (High Risk)**\n\nกิจการอันตราย (เช่น น้ำแข็ง, สารเคมี, พลาสติก, แช่แข็ง, อบพืช) หรือ เครื่องจักร > 500 HP หรือ คนงาน > 100 คน")
st.sidebar.warning("**🟡 เสี่ยงปานกลาง (Medium)**\n\nกิจการโรงกลึง, โลหะ, ซักรีด, เฟอร์นิเจอร์, กระจก หรือ เครื่องจักร > 100 HP หรือ คนงาน > 30 คน")
st.sidebar.success("**🟢 เสี่ยงต่ำ (Low Risk)**\n\nกิจการขนาดเล็กทั่วไปที่ไม่ได้อยู่ในหมวดอันตราย และเครื่องจักร < 100 HP")

st.sidebar.markdown("---")
st.sidebar.markdown("### 🎯 ประเมินอุบัติภัยและนำทาง")

# เพิ่มสวิตช์ Toggle สำหรับเลือกโหมด
enable_routing_click = st.sidebar.toggle("🖱️ เปิดโหมดคลิกเพื่อนำทาง", value=False)

if enable_routing_click:
    st.sidebar.info("💡 **สถานะ: เปิดโหมดนำทาง** \n- คลิก 1 ครั้ง: จุดเกิดเหตุ\n- คลิก 2 ครั้ง: จุดปลายทาง")
else:
    st.sidebar.info("💡 **สถานะ: โหมดดูข้อมูลปกติ** \n- คุณสามารถคลิกดูรายละเอียดโรงงานบนแผนที่ได้โดยที่พิกัดจะไม่ถูกนำไปคำนวณ")

# แสดงพิกัดที่คลิก
c1_txt = f"{st.session_state.map_clicks[0][0]:.4f}, {st.session_state.map_clicks[0][1]:.4f}" if len(st.session_state.map_clicks) > 0 else "รอคลิกแผนที่..."
c2_txt = f"{st.session_state.map_clicks[1][0]:.4f}, {st.session_state.map_clicks[1][1]:.4f}" if len(st.session_state.map_clicks) > 1 else "รอคลิกแผนที่..."

st.sidebar.markdown(f"🔥 **จุดเกิดเหตุ:** {c1_txt}")
st.sidebar.markdown(f"🏁 **จุดปลายทาง:** {c2_txt}")

if st.sidebar.button("🗑️ ล้างเส้นทาง (เริ่มใหม่)", use_container_width=True):
    st.session_state.map_clicks = []
    st.session_state.route_data = None
    st.session_state.last_processed_click = None
    st.rerun()

# แสดงผลการประเมิน (เมื่อได้เส้นทางแล้ว)
if st.session_state.route_data:
    rd = st.session_state.route_data
    s_dist = rd['straight_dist']
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("#### 🚗 สรุปการเดินทาง")
    col1, col2 = st.sidebar.columns(2)
    col1.metric("ระยะทางขับรถ", f"{rd['dist']:.2f} กม.")
    col2.metric("เวลาเดินทาง", f"~ {rd['dur']:.0f} นาที")
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("#### 🎯 รัศมีผลกระทบ")
    st.sidebar.caption(f"ระยะกระจัด (เส้นตรง): {s_dist:.2f} กม.")
    
    if s_dist <= 0.5:
        st.sidebar.error("**🔴 โซนอันตราย (Hot Zone) < 500ม.**\n\nอันตรายถึงชีวิต ต้องสวม PPE ระดับสูงสุดและอพยพทันที")
    elif s_dist <= 2.0:
        st.sidebar.warning("**🟡 โซนเฝ้าระวัง (Warm Zone) < 2กม.**\n\nอาจได้รับผลกระทบจากกลุ่มควัน/ก๊าซพิษ เตรียมพร้อมอพยพหรือหลบในอาคาร (Shelter-in-place)")
    else:
        st.sidebar.success("**🟢 โซนปลอดภัย (Cold Zone) > 2กม.**\n\nอยู่นอกรัศมีผลกระทบรุนแรง เหมาะสำหรับตั้งศูนย์บัญชาการ (Incident Command) หรือจุดปฐมพยาบาล")


# ==========================================
# 5. โหลดข้อมูลแผนที่หลัก
# ==========================================
boundary_geo = load_boundary()
gas_stations = load_gas_stations()
df_factories = load_factories()

hospitals = [
    {"name": "รพ. สันทราย", "lat": 18.921246, "lon": 98.994203},
    {"name": "รพ. นครพิงค์", "lat": 18.852547, "lon": 98.968389}
]

# ดึงตำแหน่งล่าสุดของแผนที่มาจาก Session State
m = folium.Map(location=st.session_state.map_center, zoom_start=st.session_state.map_zoom)

folium.TileLayer('http://{s}.google.com/vt/lyrs=m&x={x}&y={y}&z={z}', attr='Google', name='Google Maps (ถนน)', subdomains=['mt0', 'mt1', 'mt2', 'mt3']).add_to(m)
folium.TileLayer('http://{s}.google.com/vt/lyrs=s,h&x={x}&y={y}&z={z}', attr='Google', name='Google Hybrid (ดาวเทียม)', subdomains=['mt0', 'mt1', 'mt2', 'mt3'], show=False).add_to(m)

fg_boundary = folium.FeatureGroup(name="🟥 ขอบเขต อ.สันทราย")
fg_hospital = folium.FeatureGroup(name="🏥 โรงพยาบาล")
fg_gas = folium.FeatureGroup(name="⛽ ปั๊มน้ำมัน")
fg_factory = folium.FeatureGroup(name="📍 โรงงาน (ตามความเสี่ยง)")
fg_impact_zones = folium.FeatureGroup(name="🎯 รัศมีผลกระทบ (คำนวณอัตโนมัติ)")

if boundary_geo:
    folium.GeoJson(boundary_geo, style_function=lambda x: {'color': 'red', 'weight': 4, 'fillColor': 'red', 'fillOpacity': 0.04}).add_to(fg_boundary)

for h in hospitals:
    icon_html = "<div style='font-size:24px; filter: drop-shadow(2px 2px 2px rgba(0,0,0,0.4));'>🏥</div>"
    popup_html = f"""<div style="font-family: 'Google Sans', 'Noto Sans Thai', sans-serif;"><b>🏥 {h['name']}</b></div>"""
    folium.Marker([h['lat'], h['lon']], icon=folium.DivIcon(html=icon_html, icon_size=(30,30), icon_anchor=(15,15)), popup=folium.Popup(popup_html, max_width=200)).add_to(fg_hospital)

for el in gas_stations:
    lat = el.get('lat') or (el.get('center', {}).get('lat'))
    lon = el.get('lon') or (el.get('center', {}).get('lon'))
    if lat and lon:
        name = el.get('tags', {}).get('name', 'ปั๊มน้ำมันทั่วไป')
        brand = el.get('tags', {}).get('brand', '')
        icon_html = "<div style='font-size:24px; filter: drop-shadow(2px 2px 2px rgba(0,0,0,0.4));'>⛽</div>"
        popup_html = f"""<div style="font-family: 'Google Sans', 'Noto Sans Thai', sans-serif;"><b>⛽ {name}</b><br><small>{brand}</small></div>"""
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
                    risk_level = str(row.iloc[6]) if pd.notna(row.iloc[6]) else 'ไม่ระบุ'

                    marker_color, fill_color = '#95a5a6', '#bdc3c7'
                    if '🔴' in risk_level or 'เสี่ยงสูง' in risk_level:
                        marker_color, fill_color = '#c0392b', '#e74c3c'
                    elif '🟡' in risk_level or 'ปานกลาง' in risk_level:
                        marker_color, fill_color = '#d35400', '#f1c40f'
                    elif '🟢' in risk_level or 'เสี่ยงต่ำ' in risk_level:
                        marker_color, fill_color = '#27ae60', '#2ecc71'

                    popup_html = f"""
                        <div style="min-width: 250px; font-family: 'Google Sans', 'Noto Sans Thai', sans-serif;">
                            <h4 style="color: {marker_color}; border-bottom: 2px solid #eee; padding-bottom: 5px; margin-top: 0;">🏭 {full_name}</h4>
                            <div style="margin-bottom: 8px;"><strong>⚠️ ระดับความเสี่ยง:</strong><br>{risk_level}</div>
                            <div style="margin-bottom: 8px;"><strong>📍 สถานที่ตั้ง:</strong><br>{location}</div>
                            <div style="margin-bottom: 8px;"><strong>⚙️ การประกอบกิจการ:</strong><br>{activity}</div>
                            <div style="margin-bottom: 8px;"><strong>🔥 ความเสี่ยง:</strong><br>{risk_details}</div>
                        </div>
                    """
                    folium.CircleMarker(location=[lat, lon], radius=8, color='white', weight=2, fill_color=fill_color, fill_opacity=0.95, popup=folium.Popup(popup_html, max_width=320)).add_to(fg_factory)
        except Exception:
            continue

# ==========================================
# 6. วาดเส้นทางและวงกลมบนแผนที่ (Folium)
# ==========================================
if len(st.session_state.map_clicks) >= 1:
    folium.Marker(st.session_state.map_clicks[0], icon=folium.Icon(color='darkred', icon='fire', prefix='fa'), tooltip="จุดเกิดเหตุ (Start)").add_to(m)

if len(st.session_state.map_clicks) == 2 and st.session_state.route_data:
    rd = st.session_state.route_data
    start_point = rd['start']
    
    # วาดวงกลมรัศมีอาชีวเวชกรรม
    folium.Circle(location=start_point, radius=5000, color='#059669', weight=1, fill=True, fill_color='#059669', fill_opacity=0.05, interactive=False).add_to(fg_impact_zones)
    folium.Circle(location=start_point, radius=2000, color='#d97706', weight=2, fill=True, fill_color='#d97706', fill_opacity=0.1, interactive=False).add_to(fg_impact_zones)
    folium.Circle(location=start_point, radius=500, color='#dc2626', weight=3, fill=True, fill_color='#dc2626', fill_opacity=0.2, interactive=False).add_to(fg_impact_zones)

    folium.PolyLine(rd['coords'], color="#3388ff", weight=5, opacity=0.8, tooltip=f"ระยะทางขับรถ {rd['dist']:.1f} กม.").add_to(m)
    folium.Marker(rd['end'], icon=folium.Icon(color='green', icon='flag', prefix='fa'), tooltip="จุดปลายทาง (End)").add_to(m)
    
    # ซูมให้พอดีกับเส้นทางเฉพาะตอนที่มีการคำนวณเส้นทางเสร็จใหม่ๆ
    min_lat, max_lat = min(start_point[0], rd['end'][0]) - 0.045, max(start_point[0], rd['end'][0]) + 0.045
    min_lon, max_lon = min(start_point[1], rd['end'][1]) - 0.045, max(start_point[1], rd['end'][1]) + 0.045
    m.fit_bounds([[min_lat, min_lon], [max_lat, max_lon]])

fg_boundary.add_to(m)
fg_hospital.add_to(m)
fg_gas.add_to(m)
fg_factory.add_to(m)
fg_impact_zones.add_to(m) 
folium.LayerControl(collapsed=False).add_to(m)

# ==========================================
# 7. Render แผนที่และดักจับ Event การคลิกเมาส์
# ==========================================
# แก้ไข returned_objects: ลบ center และ zoom ออก เพื่อป้องกันไม่ให้ Streamlit รีเฟรชแอปทุกครั้งที่เลื่อนหรือซูมแผนที่
map_data = st_folium(m, width="100%", height=700, returned_objects=["last_object_clicked", "last_clicked"])

# ดักจับพิกัดจากการคลิกของแผนที่
clicked_point = None
if map_data:
    if map_data.get("last_object_clicked"):
        clicked_point = map_data["last_object_clicked"]
    elif map_data.get("last_clicked"):
        clicked_point = map_data["last_clicked"]

# ประมวลผลเมื่อเกิดการคลิกใหม่
if clicked_point and clicked_point != st.session_state.last_processed_click:
    st.session_state.last_processed_click = clicked_point
    
    # อัปเดตจุดกึ่งกลางแผนที่เป็นพิกัดที่เพิ่งคลิก เพื่อป้องกันไม่ให้แผนที่เด้งกลับไปที่หน้าแรก
    st.session_state.map_center = [clicked_point['lat'], clicked_point['lng']]
    
    # ถ้าเปิดสวิตช์ "โหมดคลิกเพื่อนำทาง" ค่อยเอาพิกัดไปคำนวณ
    if enable_routing_click:
        if len(st.session_state.map_clicks) >= 2:
            st.session_state.map_clicks = [(clicked_point['lat'], clicked_point['lng'])]
            st.session_state.route_data = None
        else:
            st.session_state.map_clicks.append((clicked_point['lat'], clicked_point['lng']))
        
        st.rerun() # รีเฟรชแผนที่เมื่ออยู่ในโหมดนำทาง
