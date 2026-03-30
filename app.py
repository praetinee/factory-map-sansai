import streamlit as st
import pandas as pd
import folium
from folium.plugins import MeasureControl
from streamlit_folium import st_folium
import requests

# ==========================================
# 1. การตั้งค่าหน้าเว็บ Streamlit และ ฟอนต์ Google Sans
# ==========================================
st.set_page_config(page_title="แผนที่โรงงาน อ.สันทราย", layout="wide", page_icon="📍")

# แทรก CSS เพื่อโหลดและตั้งค่าฟอนต์ Google Sans และ Noto Sans Thai ให้กับทั้งแอป
st.markdown("""
    <style>
        @import url('https://fonts.cdnfonts.com/css/google-sans');
        @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+Thai:wght@300;400;500;600;700&display=swap');
        
        * {
            font-family: 'Google Sans', 'Noto Sans Thai', sans-serif !important;
        }
    </style>
""", unsafe_allow_html=True)

st.title("📍 แผนที่ความเสี่ยงโรงงาน อ.สันทราย จ.เชียงใหม่")
st.markdown("แสดงพิกัดโรงงานตามระดับความเสี่ยง พร้อมเลเยอร์ขอบเขต ปั๊มน้ำมัน และโรงพยาบาล")

# ==========================================
# 2. ฟังก์ชันดึงข้อมูลและระบบนำทาง
# ==========================================

@st.cache_data(ttl=3600)
def load_boundary():
    url = 'https://nominatim.openstreetmap.org/search?q=อำเภอสันทราย+จังหวัดเชียงใหม่&format=geojson&polygon_geojson=1&limit=1'
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code == 200:
            data = r.json()
            features = [f for f in data.get('features', []) if f.get('geometry', {}).get('type') in ['Polygon', 'MultiPolygon']]
            if features:
                return features[0]
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
        headers = {'User-Agent': 'Mozilla/5.0'}
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
    # OSRM ต้องการพิกัดแบบ lon,lat
    url = f"http://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}?overview=full&geometries=geojson"
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            data = r.json()
            if data['code'] == 'Ok':
                route = data['routes'][0]
                distance_km = route['distance'] / 1000.0  # ระยะทางเป็นกิโลเมตร
                duration_min = route['duration'] / 60.0   # เวลาเป็นนาที
                geometry = route['geometry']['coordinates']
                # สลับพิกัดกลับมาเป็น lat, lon สำหรับใช้งานใน Folium
                route_coords = [[coord[1], coord[0]] for coord in geometry]
                return distance_km, duration_min, route_coords
    except Exception as e:
        pass
    return None, None, None

# ==========================================
# 3. เตรียมข้อมูลพิกัดสถานที่ทั้งหมดล่วงหน้า
# ==========================================
boundary_geo = load_boundary()
gas_stations = load_gas_stations()
df_factories = load_factories()

locations_dict = {}

hospitals = [
    {"name": "รพ. สันทราย", "lat": 18.921246, "lon": 98.994203},
    {"name": "รพ. นครพิงค์", "lat": 18.852547, "lon": 98.968389}
]
for h in hospitals:
    locations_dict[f"🏥 {h['name']}"] = (h['lat'], h['lon'])

for el in gas_stations:
    lat = el.get('lat') or (el.get('center', {}).get('lat'))
    lon = el.get('lon') or (el.get('center', {}).get('lon'))
    if lat and lon:
        name = el.get('tags', {}).get('name', 'ปั๊มน้ำมันทั่วไป')
        brand = el.get('tags', {}).get('brand', '')
        display_name = f"⛽ {name}" if name != 'ปั๊มน้ำมันทั่วไป' else f"⛽ {brand} (ปั๊มน้ำมัน)"
        locations_dict[display_name] = (lat, lon)

if not df_factories.empty:
    for idx, row in df_factories.iterrows():
        try:
            if len(row) >= 8 and pd.notna(row.iloc[7]):
                coords_str = str(row.iloc[7]).strip()
                if ',' in coords_str:
                    lat_str, lon_str = coords_str.replace('"', '').split(',')
                    lat, lon = float(lat_str.strip()), float(lon_str.strip())
                    raw_name = str(row.iloc[1]) if pd.notna(row.iloc[1]) else 'ไม่มีชื่อ'
                    full_name = raw_name.split('\n')[0].replace('"', '')
                    locations_dict[f"🏭 {full_name}"] = (lat, lon)
        except Exception:
            pass

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
st.sidebar.markdown("### 🚗 ระบบนำทางและระยะทาง")

# จัดการ State สำหรับเก็บเส้นทาง
if "route_data" not in st.session_state:
    st.session_state.route_data = None

with st.sidebar.expander("คำนวณเส้นทางขับรถ", expanded=True):
    if locations_dict:
        location_names = list(locations_dict.keys())
        
        point1 = st.selectbox("จุดเริ่มต้น", options=location_names, index=0)
        point2 = st.selectbox("จุดปลายทาง", options=location_names, index=1 if len(location_names) > 1 else 0)
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("คำนวณเส้นทาง", type="primary", use_container_width=True):
                lat1, lon1 = locations_dict[point1]
                lat2, lon2 = locations_dict[point2]
                
                with st.spinner('กำลังค้นหาเส้นทาง...'):
                    dist_km, dur_min, coords = get_driving_route(lat1, lon1, lat2, lon2)
                
                if dist_km is not None:
                    st.session_state.route_data = {
                        'name1': point1[2:].strip(),
                        'name2': point2[2:].strip(),
                        'dist': dist_km,
                        'dur': dur_min,
                        'coords': coords,
                        'start': (lat1, lon1),
                        'end': (lat2, lon2)
                    }
                else:
                    st.error("ไม่สามารถคำนวณเส้นทางได้ กรุณาลองใหม่อีกครั้ง")
                    
        with col2:
            if st.button("ล้างเส้นทาง", use_container_width=True):
                st.session_state.route_data = None
                st.rerun()

    # แสดงผลการคำนวณ
    if st.session_state.route_data:
        rd = st.session_state.route_data
        st.success(f"""
        📍 **{rd['name1']}** ➔ **{rd['name2']}**
        
        🚗 ระยะทาง: **{rd['dist']:.2f} กม.**
        ⏳ เวลาเดินทาง: **~ {rd['dur']:.0f} นาที**
        """)

# ==========================================
# 5. การสร้างแผนที่ด้วย Folium
# ==========================================
m = folium.Map(location=[18.9135, 99.0279], zoom_start=11)

m.add_child(MeasureControl(position='topleft', primary_length_unit='kilometers', secondary_length_unit='meters', primary_area_unit='sqmeters'))

folium.TileLayer('http://{s}.google.com/vt/lyrs=m&x={x}&y={y}&z={z}', attr='Google', name='Google Maps (ถนน)', subdomains=['mt0', 'mt1', 'mt2', 'mt3']).add_to(m)
folium.TileLayer('http://{s}.google.com/vt/lyrs=s,h&x={x}&y={y}&z={z}', attr='Google', name='Google Hybrid (ดาวเทียม)', subdomains=['mt0', 'mt1', 'mt2', 'mt3'], show=False).add_to(m)

fg_boundary = folium.FeatureGroup(name="🟥 ขอบเขต อ.สันทราย")
fg_hospital = folium.FeatureGroup(name="🏥 โรงพยาบาล")
fg_gas = folium.FeatureGroup(name="⛽ ปั๊มน้ำมัน")
fg_factory = folium.FeatureGroup(name="📍 โรงงาน (ตามความเสี่ยง)")

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

factory_count = 0
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
                    factory_count += 1
        except Exception:
            continue

# วาดเส้นทางบนแผนที่ (ถ้ามีการคำนวณไว้)
if st.session_state.route_data:
    rd = st.session_state.route_data
    # เพิ่มเส้นทางนำทาง
    folium.PolyLine(
        rd['coords'],
        color="#3388ff", # สีฟ้าสดใส
        weight=5,
        opacity=0.8,
        tooltip=f"ระยะทางขับรถ {rd['dist']:.1f} กม."
    ).add_to(m)
    
    # เพิ่มหมุดแบบพิเศษ ระบุจุดเริ่มและจุดจบชัดเจน
    folium.Marker(rd['start'], icon=folium.Icon(color='green', icon='play', prefix='fa'), tooltip="จุดเริ่มต้น").add_to(m)
    folium.Marker(rd['end'], icon=folium.Icon(color='red', icon='stop', prefix='fa'), tooltip="จุดปลายทาง").add_to(m)
    
    # ปรับมุมมองแผนที่ให้ซูมพอดีกับเส้นทางอัตโนมัติ
    m.fit_bounds(rd['coords'])

fg_boundary.add_to(m)
fg_hospital.add_to(m)
fg_gas.add_to(m)
fg_factory.add_to(m)
folium.LayerControl(collapsed=False).add_to(m)

# ==========================================
# 6. นำแผนที่มาแสดงในหน้าเว็บ
# ==========================================
st_folium(m, width="100%", height=700)
