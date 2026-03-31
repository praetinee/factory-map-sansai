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

# แทรก CSS เพื่อโหลดฟอนต์ แก้ปัญหาไม้เอกหาย และปรับให้ยืดหยุ่น (Responsive)
st.markdown("""
    <style>
        @import url('https://fonts.cdnfonts.com/css/google-sans');
        @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+Thai:wght@300;400;500;600;700&display=swap');
        
        /* กำหนดฟอนต์หลัก และบังคับความสูงบรรทัดเพื่อป้องกันไม้เอก/สระบนโดนตัด */
        html, body, [class*="st-"], p, h1, h2, h3, h4, h5, h6, span, label, div {
            font-family: 'Google Sans', 'Noto Sans Thai', sans-serif !important;
            line-height: 1.6 !important; 
        }
        
        /* เพิ่มพื้นที่ด้านบนให้หัวข้อโดยเฉพาะ */
        h1, h2, h3 {
            padding-top: 12px !important;
            padding-bottom: 8px !important;
        }
        
        /* ป้องกันไม่ให้ฟอนต์ไปทับไอคอนต่างๆ ของระบบ */
        svg, svg *, i, .material-icons, [class*="icon"] {
            font-family: inherit !important;
        }
        
        /* ปรับโครงสร้างหน้าเว็บให้ยืดหยุ่น รองรับทั้งมือถือและคอมพิวเตอร์ */
        .block-container {
            padding-top: 1.5rem !important;
            padding-bottom: 1.5rem !important;
            padding-left: 3% !important; /* ใช้เปอร์เซ็นต์เพื่อให้ยืดหยุ่นตามขนาดจอ */
            padding-right: 3% !important;
            max-width: 100% !important; 
        }
    </style>
""", unsafe_allow_html=True)

st.title("📍 แผนที่โรงงานแยกตามประเภทความเสี่ยง อ.สันทราย")
st.markdown("แสดงพิกัดโรงงานแบ่งตามกลุ่มความเสี่ยง พร้อมระบบกรองข้อมูลและคำนวณระยะรัศมี")

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
    except Exception:
        pass
    return None

@st.cache_data(ttl=3600)
def load_gas_stations():
    query = """[out:json][timeout:30];
    area["name"~"สันทราย"]["admin_level"="6"]->.searchArea;
    (
      node["amenity"="fuel"](area.searchArea);
      way["amenity"="fuel"](area.searchArea);
      relation["amenity"="fuel"](area.searchArea);
    );
    out center;"""
    url = 'https://overpass-api.de/api/interpreter'
    try:
        headers = {'User-Agent': 'FactoryRiskMapApp/1.0'}
        r = requests.post(url, data=query.encode('utf-8'), headers=headers, timeout=30)
        if r.status_code == 200:
            data = r.json()
            return data.get('elements', [])
    except Exception:
        pass
    return []

@st.cache_data(ttl=300)
def load_factories():
    sheet_url = 'https://docs.google.com/spreadsheets/d/1qHJwpzbaFbn-ayQs4iAHodxAh1Lh5xiUuUHIL5t9v7k/export?format=csv&gid=0'
    try:
        df = pd.read_csv(sheet_url)
        return df
    except Exception:
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
    except Exception:
        pass
    return None, None, None

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

# ประมวลผลเส้นทางถ้ามี 2 จุด
if len(st.session_state.map_clicks) == 2 and st.session_state.route_data is None:
    lat1, lon1 = st.session_state.map_clicks[0]
    lat2, lon2 = st.session_state.map_clicks[1]
    dist_km, dur_min, coords = get_driving_route(lat1, lon1, lat2, lon2)
    straight_dist = calculate_straight_distance(lat1, lon1, lat2, lon2)
    if dist_km is not None:
        st.session_state.route_data = {
            'dist': dist_km, 'dur': dur_min, 'coords': coords,
            'start': (lat1, lon1), 'end': (lat2, lon2), 'straight_dist': straight_dist
        }
    else:
        st.session_state.map_clicks.pop()

# ==========================================
# 4. เตรียมข้อมูลพิกัดสถานที่
# ==========================================
boundary_geo = load_boundary()
gas_stations = load_gas_stations()
df_factories = load_factories()

# --- จัดการกลุ่มความเสี่ยงและสี (คอลัมน์ F) ---
risk_categories = []
if not df_factories.empty:
    # คอลัมน์ F คือ index 5 (เริ่มจาก 0)
    df_factories['risk_group'] = df_factories.iloc[:, 5].fillna('ไม่ระบุประเภทความเสี่ยง').astype(str)
    risk_categories = sorted(df_factories['risk_group'].unique().tolist())

# กำหนด Palette สีคงที่สำหรับประเภทความเสี่ยงหลักๆ
color_map = {
    "อัคคีภัย": "#e74c3c", 
    "สารเคมีรั่วไหล": "#9b59b6",
    "แอมโมเนีย": "#3498db",
    "ฝุ่นละออง": "#95a5a6",
    "เสียงดัง": "#f1c40f",
    "น้ำเสีย": "#2980b9",
    "ก๊าซหุงต้ม": "#e67e22"
}

def get_color(risk_text):
    for key, color in color_map.items():
        if key in risk_text: return color
    # ถ้าไม่ตรงกับสีที่กำหนดไว้ ให้สุ่มสีจาก hash ของข้อความ
    colors = ["#16a085", "#27ae60", "#2980b9", "#8e44ad", "#2c3e50", "#f39c12", "#d35400"]
    return colors[hash(risk_text) % len(colors)]

# ==========================================
# 5. ส่วนแถบเมนูด้านข้าง (Sidebar)
# ==========================================
st.sidebar.header("⚙️ การจัดการข้อมูล")

if st.sidebar.button("🔄 รีโหลดข้อมูลใหม่ทั้งหมด", use_container_width=True):
    load_factories.clear()
    load_gas_stations.clear()
    load_boundary.clear()
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.markdown("### 📊 ตัวกรองประเภทความเสี่ยง")
selected_risks = st.sidebar.multiselect(
    "เลือกแสดงกลุ่มความเสี่ยง (คอลัมน์ F):",
    options=risk_categories,
    default=risk_categories
)

# กรองข้อมูลตามที่เลือก
df_filtered = df_factories[df_factories['risk_group'].isin(selected_risks)] if not df_factories.empty else df_factories

st.sidebar.markdown("---")
st.sidebar.markdown("### 🎯 ประเมินอุบัติภัยและนำทาง")
mode = st.sidebar.radio("โหมดการใช้งานแผนที่", ["🔍 ดูข้อมูลปกติ", "🖱️ คลิกบนแผนที่", "📋 เลือกจากรายชื่อ"])

enable_routing_click = False
locations_dict = {}

# เตรียมรายชื่อสำหรับ Dropdown (อิงตามข้อมูลที่กรองแล้ว)
hospitals = [
    {"name": "รพ. สันทราย", "lat": 18.921246, "lon": 98.994203},
    {"name": "รพ. นครพิงค์", "lat": 18.852547, "lon": 98.968389}
]
for h in hospitals: locations_dict[f"🏥 {h['name']}"] = (h['lat'], h['lon'])
for el in gas_stations:
    lat = el.get('lat') or (el.get('center', {}).get('lat'))
    lon = el.get('lon') or (el.get('center', {}).get('lon'))
    if lat and lon:
        name = el.get('tags', {}).get('name', 'ปั๊มน้ำมันทั่วไป')
        locations_dict[f"⛽ {name}"] = (lat, lon)

if not df_filtered.empty:
    for idx, row in df_filtered.iterrows():
        try:
            if pd.notna(row.iloc[7]):
                coords_str = str(row.iloc[7]).strip()
                if ',' in coords_str:
                    lat_str, lon_str = coords_str.replace('"', '').split(',')
                    lat, lon = float(lat_str.strip()), float(lon_str.strip())
                    name = str(row.iloc[1]).split('\n')[0].replace('"', '')
                    locations_dict[f"🏭 {name}"] = (lat, lon)
        except Exception: pass

if mode == "🖱️ คลิกบนแผนที่":
    enable_routing_click = True
    st.sidebar.info("💡 คลิกบนแผนที่เพื่อระบุจุดเกิดเหตุและปลายทาง")
elif mode == "📋 เลือกจากรายชื่อ":
    if locations_dict:
        point1 = st.sidebar.selectbox("จุดเริ่มต้น (เช่น จุดเกิดเหตุ)", options=list(locations_dict.keys()), index=0)
        point2 = st.sidebar.selectbox("จุดปลายทาง (เช่น รพ./ศูนย์อพยพ)", options=list(locations_dict.keys()), index=1 if len(locations_dict) > 1 else 0)
        if st.sidebar.button("🚀 คำนวณเส้นทาง", type="primary", use_container_width=True):
            st.session_state.map_clicks = [locations_dict[point1], locations_dict[point2]]
            st.session_state.route_data = None
            st.session_state.map_center = locations_dict[point1]
            st.rerun()

if len(st.session_state.map_clicks) > 0:
    if st.sidebar.button("🗑️ ล้างเส้นทาง (เริ่มใหม่)", use_container_width=True):
        st.session_state.map_clicks = []; st.session_state.route_data = None; st.session_state.last_processed_click = None
        st.rerun()

if st.session_state.route_data:
    rd = st.session_state.route_data
    st.sidebar.markdown("---")
    st.sidebar.markdown("#### 🚗 สรุปการเดินทาง")
    col1, col2 = st.sidebar.columns(2)
    col1.metric("ระยะขับรถ", f"{rd['dist']:.2f} กม.")
    col2.metric("เวลาเดินทาง", f"~{rd['dur']:.0f} น.")
    
    s_dist = rd['straight_dist']
    st.sidebar.caption(f"ระยะกระจัด: {s_dist:.2f} กม.")
    if s_dist <= 0.5: st.sidebar.error("**🔴 โซนอันตราย (Hot Zone)**")
    elif s_dist <= 2.0: st.sidebar.warning("**🟡 โซนเฝ้าระวัง (Warm Zone)**")
    else: st.sidebar.success("**🟢 โซนปลอดภัย (Cold Zone)**")

# ==========================================
# 6. วาดแผนที่ (Folium)
# ==========================================
m = folium.Map(location=st.session_state.map_center, zoom_start=st.session_state.map_zoom)

folium.TileLayer('http://{s}.google.com/vt/lyrs=m&x={x}&y={y}&z={z}', attr='Google', name='Google Maps', subdomains=['mt0', 'mt1', 'mt2', 'mt3']).add_to(m)

fg_boundary = folium.FeatureGroup(name="🟥 ขอบเขต อ.สันทราย")
fg_hospital = folium.FeatureGroup(name="🏥 โรงพยาบาล")
fg_gas = folium.FeatureGroup(name="⛽ ปั๊มน้ำมัน")
fg_factory = folium.FeatureGroup(name="📍 โรงงาน (แยกตามความเสี่ยง)")
fg_impact_zones = folium.FeatureGroup(name="🎯 รัศมีผลกระทบ")

if boundary_geo:
    folium.GeoJson(boundary_geo, style_function=lambda x: {'color': 'red', 'weight': 3, 'fillColor': 'red', 'fillOpacity': 0.03}).add_to(fg_boundary)

for h in hospitals:
    folium.Marker([h['lat'], h['lon']], icon=folium.DivIcon(html="<div style='font-size:24px;'>🏥</div>"), popup=h['name']).add_to(fg_hospital)

for el in gas_stations:
    lat = el.get('lat') or (el.get('center', {}).get('lat'))
    lon = el.get('lon') or (el.get('center', {}).get('lon'))
    if lat and lon:
        name = el.get('tags', {}).get('name', 'ปั๊มน้ำมัน')
        folium.Marker([lat, lon], icon=folium.DivIcon(html="<div style='font-size:20px;'>⛽</div>"), popup=name).add_to(fg_gas)

# วาดหมุดโรงงาน (ใช้ข้อมูลที่กรองแล้ว)
if not df_filtered.empty:
    for idx, row in df_filtered.iterrows():
        try:
            if pd.notna(row.iloc[7]):
                coords_str = str(row.iloc[7]).replace('"', '').split(',')
                lat, lon = float(coords_str[0].strip()), float(coords_str[1].strip())
                
                risk_info = str(row.iloc[5])
                node_color = get_color(risk_info)
                
                full_name = str(row.iloc[1]).split('\n')[0]
                activity = str(row.iloc[4]).replace('\n', '<br>')
                
                popup_content = f"""
                    <div style="min-width: 200px; font-family: 'Noto Sans Thai', sans-serif;">
                        <b style="color: {node_color}; font-size: 14px;">🏭 {full_name}</b><br>
                        <hr style="margin: 5px 0;">
                        <b>🔥 ความเสี่ยง:</b><br>{risk_info}<br>
                        <b>⚙️ กิจการ:</b><br><small>{activity}</small>
                    </div>
                """
                folium.CircleMarker(
                    location=[lat, lon], radius=9, color='white', weight=2,
                    fill_color=node_color, fill_opacity=0.9,
                    popup=folium.Popup(popup_content, max_width=300)
                ).add_to(fg_factory)
        except Exception: continue

# วาดเส้นทางและวงรัศมี
if len(st.session_state.map_clicks) >= 1:
    folium.Marker(st.session_state.map_clicks[0], icon=folium.Icon(color='red', icon='fire', prefix='fa')).add_to(m)
    if st.session_state.route_data:
        rd = st.session_state.route_data
        folium.Circle(rd['start'], radius=500, color='#dc2626', fill=True, fill_opacity=0.2).add_to(fg_impact_zones)
        folium.Circle(rd['start'], radius=2000, color='#d97706', fill=True, fill_opacity=0.1).add_to(fg_impact_zones)
        folium.PolyLine(rd['coords'], color="#3388ff", weight=5).add_to(m)
        folium.Marker(rd['end'], icon=folium.Icon(color='green', icon='flag', prefix='fa')).add_to(m)

fg_boundary.add_to(m)
fg_hospital.add_to(m)
fg_gas.add_to(m)
fg_factory.add_to(m)
fg_impact_zones.add_to(m)
folium.LayerControl(collapsed=False).add_to(m)

# ==========================================
# 7. Render แผนที่และดักจับคลิก
# ==========================================
map_output = st_folium(m, use_container_width=True, height=750, returned_objects=["last_clicked"])

if map_output and map_output.get("last_clicked"):
    clicked = map_output["last_clicked"]
    if clicked != st.session_state.last_processed_click:
        st.session_state.last_processed_click = clicked
        if enable_routing_click:
            if len(st.session_state.map_clicks) >= 2:
                st.session_state.map_clicks = [(clicked['lat'], clicked['lng'])]
                st.session_state.route_data = None
            else:
                st.session_state.map_clicks.append((clicked['lat'], clicked['lng']))
            st.rerun()
