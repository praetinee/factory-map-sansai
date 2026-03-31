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

# แทรก CSS เพื่อความสวยงาม และแก้ปัญหาฟอนต์ภาษาไทย
st.markdown("""
    <style>
        @import url('https://fonts.cdnfonts.com/css/google-sans');
        @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+Thai:wght@300;400;500;600;700&display=swap');
        
        html, body, [class*="st-"], p, h1, h2, h3, h4, h5, h6, span, label, div {
            font-family: 'Google Sans', 'Noto Sans Thai', sans-serif !important;
            line-height: 1.6 !important; 
        }
        
        /* ปรับสไตล์ Sidebar ให้ดูสะอาดตาขึ้น */
        section[data-testid="stSidebar"] {
            background-color: #f8f9fa;
            border-right: 1px solid #e9ecef;
        }

        /* ปรับแต่งส่วนของ Filter ให้ดูเด่นชัด */
        .filter-container {
            background-color: white;
            padding: 15px;
            border-radius: 10px;
            border: 1px solid #dee2e6;
            margin-bottom: 20px;
        }
        
        .block-container {
            padding-top: 1.5rem !important;
            padding-bottom: 1.5rem !important;
            padding-left: 3% !important; 
            padding-right: 3% !important;
            max-width: 100% !important; 
        }
    </style>
""", unsafe_allow_html=True)

st.title("📍 แผนที่โรงงานแยกตามประเภทความเสี่ยง อ.สันทราย")
st.markdown("แสดงพิกัดโรงงานแบ่งตามกลุ่มความเสี่ยง (ข้อมูลจากคอลัมน์ F)")

# ==========================================
# 2. ฟังก์ชันดึงข้อมูลและคำนวณ
# ==========================================

@st.cache_data(ttl=3600)
def load_boundary():
    url = 'https://nominatim.openstreetmap.org/search?q=อำเภอสันทราย+จังหวัดเชียงใหม่&format=geojson&polygon_geojson=1&limit=1'
    try:
        headers = {'User-Agent': 'FactoryRiskMapApp/1.0'}
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code == 200:
            data = r.json()
            features = [f for f in data.get('features', []) if f.get('geometry', {}).get('type') in ['Polygon', 'MultiPolygon']]
            return features[0] if features else None
    except: pass
    return None

@st.cache_data(ttl=3600)
def load_gas_stations():
    query = """[out:json][timeout:30];
    area["name"~"สันทราย"]["admin_level"="6"]->.searchArea;
    (node["amenity"="fuel"](area.searchArea);way["amenity"="fuel"](area.searchArea);relation["amenity"="fuel"](area.searchArea););
    out center;"""
    url = 'https://overpass-api.de/api/interpreter'
    try:
        r = requests.post(url, data=query.encode('utf-8'), timeout=30)
        return r.json().get('elements', []) if r.status_code == 200 else []
    except: return []

@st.cache_data(ttl=300)
def load_factories():
    sheet_url = 'https://docs.google.com/spreadsheets/d/1qHJwpzbaFbn-ayQs4iAHodxAh1Lh5xiUuUHIL5t9v7k/export?format=csv&gid=0'
    try:
        df = pd.read_csv(sheet_url)
        return df
    except: return pd.DataFrame()

def get_driving_route(lat1, lon1, lat2, lon2):
    url = f"http://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}?overview=full&geometries=geojson"
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            data = r.json()
            if data['code'] == 'Ok':
                route = data['routes'][0]
                return route['distance']/1000.0, route['duration']/60.0, [[c[1], c[0]] for c in route['geometry']['coordinates']]
    except: pass
    return None, None, None

def calculate_straight_dist(lat1, lon1, lat2, lon2):
    R = 6371.0
    lat1_r, lon1_r, lat2_r, lon2_r = map(math.radians, [lat1, lon1, lat2, lon2])
    a = math.sin((lat2_r-lat1_r)/2)**2 + math.cos(lat1_r)*math.cos(lat2_r)*math.sin((lon2_r-lon1_r)/2)**2
    return R * (2 * math.atan2(math.sqrt(a), math.sqrt(1-a)))

# ==========================================
# 3. จัดการ State
# ==========================================
if "map_center" not in st.session_state: st.session_state.map_center = [18.9135, 99.0279]
if "map_zoom" not in st.session_state: st.session_state.map_zoom = 11
if "map_clicks" not in st.session_state: st.session_state.map_clicks = [] 
if "last_processed_click" not in st.session_state: st.session_state.last_processed_click = None 
if "route_data" not in st.session_state: st.session_state.route_data = None 

# ==========================================
# 4. เตรียมข้อมูลพิกัดสถานที่
# ==========================================
boundary_geo = load_boundary()
gas_stations = load_gas_stations()
df_factories = load_factories()

risk_categories = []
if not df_factories.empty:
    # คอลัมน์ F (ความเสี่ยงที่อาจเกิดขึ้นได้) คือ index 5
    df_factories['risk_group'] = df_factories.iloc[:, 5].fillna('ไม่ระบุประเภท').astype(str).str.strip()
    risk_categories = sorted(df_factories['risk_group'].unique().tolist())

# ระบบสี
color_map = {
    "อัคคีภัย": "#e74c3c", "สารเคมี": "#9b59b6", "แอมโมเนีย": "#3498db",
    "ฝุ่นละออง": "#95a5a6", "เสียงดัง": "#f1c40f", "น้ำเสีย": "#2980b9"
}
def get_node_color(risk_text):
    for k, v in color_map.items():
        if k in risk_text: return v
    colors = ["#16a085", "#27ae60", "#2980b9", "#8e44ad", "#2c3e50", "#f39c12", "#d35400"]
    return colors[abs(hash(risk_text)) % len(colors)]

# ==========================================
# 5. ส่วนแถบเมนูด้านข้าง (Sidebar) - ปรับโฉมตัวกรอง
# ==========================================
st.sidebar.header("⚙️ เมนูควบคุม")

if st.sidebar.button("🔄 อัปเดตข้อมูลทั้งหมด", use_container_width=True):
    load_factories.clear(); load_gas_stations.clear(); load_boundary.clear()
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.subheader("📊 ตัวกรองประเภทความเสี่ยง")

# ส่วนเลือกทั้งหมด / ไม่เลือกเลย
col_all, col_none = st.sidebar.columns(2)
if col_all.button("✅ ทั้งหมด", use_container_width=True):
    st.session_state['selected_risks'] = risk_categories
if col_none.button("❌ ไม่เลือก", use_container_width=True):
    st.session_state['selected_risks'] = []

if 'selected_risks' not in st.session_state:
    st.session_state['selected_risks'] = risk_categories

selected_risks = []
with st.sidebar.container():
    # ใช้ expander เพื่อไม่ให้ sidebar ยาวเกินไปถ้ามีประเภทเยอะ
    with st.expander("เลือกกลุ่มที่ต้องการแสดง", expanded=True):
        for risk in risk_categories:
            is_checked = risk in st.session_state['selected_risks']
            if st.checkbox(risk, value=is_checked, key=f"chk_{risk}"):
                selected_risks.append(risk)

st.session_state['selected_risks'] = selected_risks
df_filtered = df_factories[df_factories['risk_group'].isin(selected_risks)] if not df_factories.empty else df_factories

# แสดงจำนวนที่พบ
if not df_filtered.empty:
    st.sidebar.success(f"พบโรงงานทั้งหมด {len(df_filtered)} แห่ง")
else:
    st.sidebar.warning("ไม่พบข้อมูล (โปรดเลือกตัวกรอง)")

st.sidebar.markdown("---")
st.sidebar.subheader("🎯 การนำทาง")
mode = st.sidebar.radio("โหมดแผนที่", ["🔍 ปกติ", "🖱️ คลิกบนแผนที่", "📋 เลือกจากชื่อ"])

# จัดการข้อมูลสถานที่สำหรับ Dropdown
locations_dict = {}
hospitals = [{"name": "รพ. สันทราย", "lat": 18.921246, "lon": 98.994203}, {"name": "รพ. นครพิงค์", "lat": 18.852547, "lon": 98.968389}]
for h in hospitals: locations_dict[f"🏥 {h['name']}"] = (h['lat'], h['lon'])
for el in gas_stations:
    lat = el.get('lat') or (el.get('center', {}).get('lat'))
    lon = el.get('lon') or (el.get('center', {}).get('lon'))
    if lat and lon: locations_dict[f"⛽ {el.get('tags', {}).get('name', 'ปั๊มน้ำมัน')}"] = (lat, lon)

if not df_filtered.empty:
    for _, row in df_filtered.iterrows():
        try:
            c = str(row.iloc[7]).replace('"', '').split(',')
            locations_dict[f"🏭 {str(row.iloc[1]).split('\\n')[0]}"] = (float(c[0]), float(c[1]))
        except: pass

enable_routing_click = False
if mode == "🖱️ คลิกบนแผนที่":
    enable_routing_click = True
elif mode == "📋 เลือกจากชื่อ" and locations_dict:
    p1 = st.sidebar.selectbox("จาก", options=list(locations_dict.keys()), index=0)
    p2 = st.sidebar.selectbox("ไป", options=list(locations_dict.keys()), index=1 if len(locations_dict)>1 else 0)
    if st.sidebar.button("🚀 คำนวณทาง", use_container_width=True):
        st.session_state.map_clicks = [locations_dict[p1], locations_dict[p2]]
        st.session_state.route_data = None
        st.rerun()

if st.session_state.map_clicks:
    if st.sidebar.button("🗑️ ล้างเส้นทาง", use_container_width=True):
        st.session_state.map_clicks = []; st.session_state.route_data = None; st.rerun()

# ประมวลผลเส้นทาง
if len(st.session_state.map_clicks) == 2 and not st.session_state.route_data:
    d, t, c = get_driving_route(*st.session_state.map_clicks[0], *st.session_state.map_clicks[1])
    if d: st.session_state.route_data = {'dist': d, 'dur': t, 'coords': c, 'start': st.session_state.map_clicks[0], 'end': st.session_state.map_clicks[1], 's_dist': calculate_straight_dist(*st.session_state.map_clicks[0], *st.session_state.map_clicks[1])}

if st.session_state.route_data:
    rd = st.session_state.route_data
    st.sidebar.info(f"🚗 {rd['dist']:.1f} กม. (~{rd['dur']:.0f} นาที)")

# ==========================================
# 6. วาดแผนที่ (Folium)
# ==========================================
m = folium.Map(location=st.session_state.map_center, zoom_start=st.session_state.map_zoom)
folium.TileLayer('http://{s}.google.com/vt/lyrs=m&x={x}&y={y}&z={z}', attr='Google', name='Google Maps', subdomains=['mt0','mt1','mt2','mt3']).add_to(m)

fg_factory = folium.FeatureGroup(name="📍 โรงงาน (แยกประเภท)")
fg_impact = folium.FeatureGroup(name="🎯 รัศมีผลกระทบ")

if boundary_geo:
    folium.GeoJson(boundary_geo, style_function=lambda x: {'color': 'red', 'weight': 2, 'fillOpacity': 0.03}).add_to(m)

for h in hospitals:
    folium.Marker([h['lat'], h['lon']], icon=folium.DivIcon(html="<div style='font-size:20px;'>🏥</div>"), popup=h['name']).add_to(m)

# วาดหมุดโรงงาน (ปรับการดึงพิกัดให้แม่นยำขึ้น)
if not df_filtered.empty:
    for _, row in df_filtered.iterrows():
        try:
            raw_coords = str(row.iloc[7]).replace('"', '').strip()
            if ',' in raw_coords:
                lat, lon = [float(x.strip()) for x in raw_coords.split(',')]
                risk_txt = str(row.iloc[5])
                color = get_node_color(risk_txt)
                
                popup_html = f"""<div style="font-family: 'Noto Sans Thai'; min-width: 150px;">
                    <b style="color:{color};">🏭 {str(row.iloc[1]).split('\\n')[0]}</b><br>
                    <small><b>ประเภท:</b> {risk_txt}</small>
                </div>"""
                
                folium.CircleMarker(
                    location=[lat, lon], radius=8, color='white', weight=1,
                    fill_color=color, fill_opacity=0.8,
                    popup=folium.Popup(popup_html, max_width=300)
                ).add_to(fg_factory)
        except: continue

if st.session_state.map_clicks:
    folium.Marker(st.session_state.map_clicks[0], icon=folium.Icon(color='red', icon='fire', prefix='fa')).add_to(m)
    if st.session_state.route_data:
        rd = st.session_state.route_data
        folium.PolyLine(rd['coords'], color="#3388ff", weight=5).add_to(m)
        folium.Marker(rd['end'], icon=folium.Icon(color='green', icon='flag', prefix='fa')).add_to(m)
        # วาดรัศมี
        folium.Circle(rd['start'], radius=500, color='red', fill=True, fill_opacity=0.1).add_to(fg_impact)
        folium.Circle(rd['start'], radius=2000, color='orange', fill=True, fill_opacity=0.05).add_to(fg_impact)

fg_factory.add_to(m)
fg_impact.add_to(m)
folium.LayerControl().add_to(m)

# ==========================================
# 7. Render และดักจับ Event
# ==========================================
map_res = st_folium(m, use_container_width=True, height=700, returned_objects=["last_clicked"])

if map_res and map_res.get("last_clicked"):
    clicked = map_res["last_clicked"]
    if clicked != st.session_state.last_processed_click:
        st.session_state.last_processed_click = clicked
        if enable_routing_click:
            if len(st.session_state.map_clicks) >= 2:
                st.session_state.map_clicks = [(clicked['lat'], clicked['lng'])]
                st.session_state.route_data = None
            else:
                st.session_state.map_clicks.append((clicked['lat'], clicked['lng']))
            st.rerun()
