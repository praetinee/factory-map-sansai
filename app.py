import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import requests
import math

# ==========================================
# 1. การตั้งค่าหน้าเว็บ Streamlit และ ฟอนต์
# ==========================================
st.set_page_config(page_title="แผนที่โรงงาน อ.สันทราย", layout="wide", page_icon="📍")

# ปรับแต่ง CSS เฉพาะที่จำเป็น เพื่อป้องกัน UI พัง
st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+Thai:wght@300;400;500;600;700&display=swap');
        
        /* ใช้ฟอนต์ Noto Sans Thai เป็นหลักเพื่อให้รองรับภาษาไทยได้สมบูรณ์ */
        html, body, [class*="st-"], p, h1, h2, h3, h4, h5, h6, span, label, div {
            font-family: 'Noto Sans Thai', sans-serif !important;
        }
        
        /* ปรับแต่งความกว้างของเนื้อหา */
        .block-container {
            padding-top: 2rem !important;
            padding-bottom: 2rem !important;
            max-width: 95% !important; 
        }

        /* ปรับแต่งสไตล์ของปุ่มใน Sidebar */
        .stButton>button {
            border-radius: 8px;
        }
    </style>
""", unsafe_allow_html=True)

st.title("📍 แผนที่โรงงานแยกตามประเภทความเสี่ยง อ.สันทราย")
st.write("แสดงพิกัดโรงงานแบ่งตามกลุ่มความเสี่ยงที่เลือกจากแถบด้านข้าง")

# ==========================================
# 2. ฟังก์ชันดึงข้อมูลและคำนวณ
# ==========================================

@st.cache_data(ttl=3600)
def load_boundary():
    url = 'https://nominatim.openstreetmap.org/search?q=อำเภอสันทราย+จังหวัดเชียงใหม่&format=geojson&polygon_geojson=1&limit=1'
    try:
        headers = {'User-Agent': 'FactoryRiskMapApp/1.1'}
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            data = r.json()
            if data.get('features'):
                return data['features'][0]
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
        r = requests.post(url, data=query.encode('utf-8'), timeout=20)
        return r.json().get('elements', [])
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

# ==========================================
# 3. จัดการ State และการโหลดข้อมูล
# ==========================================
if "map_center" not in st.session_state: st.session_state.map_center = [18.9135, 99.0279]
if "map_clicks" not in st.session_state: st.session_state.map_clicks = [] 
if "route_data" not in st.session_state: st.session_state.route_data = None 

boundary_geo = load_boundary()
gas_stations = load_gas_stations()
df_raw = load_factories()

# จัดการข้อมูลโรงงานและกลุ่มเสี่ยง (คอลัมน์ F คือ index 5)
risk_categories = []
if not df_raw.empty:
    df_raw['risk_group'] = df_raw.iloc[:, 5].fillna('ไม่ระบุประเภท').astype(str).str.strip()
    risk_categories = sorted(df_raw['risk_group'].unique().tolist())

# ==========================================
# 4. ส่วนแถบข้าง (Sidebar)
# ==========================================
st.sidebar.header("⚙️ ตั้งค่าการแสดงผล")

if st.sidebar.button("🔄 รีเฟรชข้อมูล", use_container_width=True):
    load_factories.clear(); load_gas_stations.clear(); load_boundary.clear()
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.subheader("📊 เลือกกลุ่มความเสี่ยง")

# ใช้ Multiselect ที่สะอาดตาและจัดการสถานะได้ดีกว่า
if 'selected_risks' not in st.session_state:
    st.session_state.selected_risks = risk_categories

selected_risks = st.sidebar.multiselect(
    "แสดงผลเฉพาะกลุ่มที่เลือก:",
    options=risk_categories,
    default=st.session_state.selected_risks
)
st.session_state.selected_risks = selected_risks

# กรองข้อมูล
df_filtered = df_raw[df_raw['risk_group'].isin(selected_risks)] if not df_raw.empty else df_raw

st.sidebar.info(f"📍 แสดงโรงงาน {len(df_filtered)} จากทั้งหมด {len(df_raw)} แห่ง")

st.sidebar.markdown("---")
st.sidebar.subheader("🎯 โหมดการใช้งาน")
mode = st.sidebar.radio("เครื่องมือ:", ["🔍 ดูข้อมูล", "🖱️ คลิกนำทาง", "📋 ค้นหาชื่อ"])

# ==========================================
# 5. เตรียม Marker และพิกัด
# ==========================================
hospitals = [{"name": "รพ. สันทราย", "lat": 18.921246, "lon": 98.994203}, {"name": "รพ. นครพิงค์", "lat": 18.852547, "lon": 98.968389}]
locations_dict = {}
for h in hospitals: locations_dict[f"🏥 {h['name']}"] = (h['lat'], h['lon'])

# ระบบสีตามประเภทความเสี่ยง
color_map = {
    "อัคคีภัย": "#D32F2F", "สารเคมี": "#7B1FA2", "แอมโมเนีย": "#1976D2",
    "ฝุ่นละออง": "#616161", "เสียงดัง": "#FBC02D", "น้ำเสีย": "#0288D1"
}
def get_node_color(risk_text):
    for k, v in color_map.items():
        if k in risk_text: return v
    colors = ["#00796B", "#388E3C", "#5D4037", "#C2185B", "#E64A19"]
    return colors[abs(hash(risk_text)) % len(colors)]

# ==========================================
# 6. สร้างแผนที่ (Folium)
# ==========================================
m = folium.Map(location=st.session_state.map_center, zoom_start=12, control_scale=True)
folium.TileLayer('https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}', attr='Google', name='Google Maps').add_to(m)

# 6.1 ขอบเขตอำเภอ
if boundary_geo:
    folium.GeoJson(boundary_geo, name="ขอบเขต อ.สันทราย", style_function=lambda x: {'color': '#FF0000', 'weight': 2, 'fillOpacity': 0.02}).add_to(m)

# 6.2 จุดโรงงาน (สำคัญ: ปรับปรุงตรรกะการดึงพิกัด)
fg_factories = folium.FeatureGroup(name="โรงงาน")
if not df_filtered.empty:
    for _, row in df_filtered.iterrows():
        try:
            # ดึงพิกัดจากคอลัมน์ index 7
            raw_val = str(row.iloc[7]).replace('"', '').replace(' ', '').strip()
            if ',' in raw_val:
                lat_str, lon_str = raw_val.split(',')
                lat, lon = float(lat_str), float(lon_str)
                
                risk_txt = str(row.iloc[5])
                color = get_node_color(risk_txt)
                name = str(row.iloc[1]).split('\n')[0]
                
                popup_html = f"""<div style="font-family: 'Noto Sans Thai'; width: 200px;">
                    <b style="color:{color}; font-size:14px;">🏭 {name}</b><br>
                    <hr style="margin:5px 0;">
                    <small><b>ความเสี่ยง:</b> {risk_txt}</small>
                </div>"""
                
                folium.CircleMarker(
                    location=[lat, lon], radius=8, color='white', weight=1,
                    fill_color=color, fill_opacity=0.8,
                    popup=folium.Popup(popup_html, max_width=300)
                ).add_to(fg_factories)
                
                # เก็บไว้ใช้ใน Dropdown
                locations_dict[f"🏭 {name}"] = (lat, lon)
        except: continue
fg_factories.add_to(m)

# 6.3 ปั๊มน้ำมันและโรงพยาบาล
fg_poi = folium.FeatureGroup(name="ปั๊มน้ำมัน & รพ.", show=False)
for h in hospitals:
    folium.Marker([h['lat'], h['lon']], icon=folium.DivIcon(html="<div style='font-size:20px;'>🏥</div>"), popup=h['name']).add_to(fg_poi)
for el in gas_stations:
    lt = el.get('lat') or el.get('center', {}).get('lat')
    ln = el.get('lon') or el.get('center', {}).get('lon')
    if lt and ln:
        name = el.get('tags', {}).get('name', 'ปั๊มน้ำมัน')
        folium.Marker([lt, ln], icon=folium.DivIcon(html="<div style='font-size:18px;'>⛽</div>"), popup=name).add_to(fg_poi)
fg_poi.add_to(m)

# 6.4 การนำทางและรัศมี
if mode == "📋 ค้นหาชื่อ":
    p1 = st.sidebar.selectbox("จุดเริ่มต้น", options=list(locations_dict.keys()), index=0)
    p2 = st.sidebar.selectbox("จุดปลายทาง", options=list(locations_dict.keys()), index=1 if len(locations_dict)>1 else 0)
    if st.sidebar.button("🚗 เริ่มคำนวณ", use_container_width=True):
        st.session_state.map_clicks = [locations_dict[p1], locations_dict[p2]]
        st.session_state.route_data = None
        st.rerun()

if st.session_state.map_clicks:
    folium.Marker(st.session_state.map_clicks[0], icon=folium.Icon(color='red', icon='fire', prefix='fa')).add_to(m)
    # แสดงรัศมี
    folium.Circle(st.session_state.map_clicks[0], radius=500, color='red', fill=True, fill_opacity=0.1).add_to(m)
    folium.Circle(st.session_state.map_clicks[0], radius=2000, color='orange', fill=True, fill_opacity=0.05).add_to(m)
    
    if len(st.session_state.map_clicks) == 2:
        if not st.session_state.route_data:
            d, t, c = get_driving_route(*st.session_state.map_clicks[0], *st.session_state.map_clicks[1])
            if d: st.session_state.route_data = {'dist': d, 'dur': t, 'coords': c}
        
        if st.session_state.route_data:
            rd = st.session_state.route_data
            folium.PolyLine(rd['coords'], color="#3388ff", weight=5, opacity=0.7).add_to(m)
            folium.Marker(st.session_state.map_clicks[1], icon=folium.Icon(color='green', icon='flag', prefix='fa')).add_to(m)
            st.sidebar.success(f"ระยะทาง: {rd['dist']:.1f} กม. | เวลา: {rd['dur']:.0f} นาที")

if st.sidebar.button("🗑️ ล้างการนำทาง", use_container_width=True):
    st.session_state.map_clicks = []; st.session_state.route_data = None; st.rerun()

folium.LayerControl().add_to(m)

# ==========================================
# 7. แสดงผลแผนที่และประมวลผลคลิก
# ==========================================
output = st_folium(m, use_container_width=True, height=700, returned_objects=["last_clicked"])

if mode == "🖱️ คลิกนำทาง" and output and output.get("last_clicked"):
    clicked = output["last_clicked"]
    coord = (clicked['lat'], clicked['lng'])
    if not st.session_state.map_clicks or coord != st.session_state.map_clicks[-1]:
        if len(st.session_state.map_clicks) >= 2:
            st.session_state.map_clicks = [coord]
        else:
            st.session_state.map_clicks.append(coord)
        st.session_state.route_data = None
        st.rerun()
