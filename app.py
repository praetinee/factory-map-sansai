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
    # ปรับปรุง Query Overpass API ให้ค้นหาแม่นยำและถูกต้องยิ่งขึ้น
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
        # ส่ง data เป็น utf-8 string ตรงๆ แทน เพื่อป้องกันปัญหาการแปลงฟอร์แมตผิดพลาด
        r = requests.post(url, data=query.encode('utf-8'), headers=headers, timeout=30)
        if r.status_code == 200:
            data = r.json()
            return data.get('elements', [])
        else:
            st.sidebar.error(f"⚠️ โหลดข้อมูลปั๊มน้ำมันไม่สำเร็จ (API Status: {r.status_code})")
    except Exception as e:
        st.sidebar.error(f"⚠️ เกิดข้อผิดพลาดในการโหลดปั๊มน้ำมัน: {e}")
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

# หากผู้ใช้มีจุด 2 จุดในความจำ ให้คำนวณเส้นทางอัตโนมัติก่อนที่จะนำไปวาดบนแผนที่
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
            st.sidebar.error("❌ ไม่สามารถคำนวณเส้นทางได้ (จุดที่เลือกอาจอยู่ห่างไกลถนนเกินไป)")
            st.session_state.map_clicks.pop()

# ==========================================
# 4. เตรียมข้อมูลพิกัดสถานที่ทั้งหมด (ใช้สำหรับ Dropdown)
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
# 5. ส่วนแถบเมนูด้านข้าง (Sidebar)
# ==========================================
st.sidebar.header("⚙️ การจัดการข้อมูล")

# เพิ่มประสิทธิภาพปุ่มรีโหลด ให้ล้างความจำทุกอย่างแล้วโหลดใหม่ทั้งหมด
if st.sidebar.button("🔄 รีโหลดข้อมูลใหม่ทั้งหมด", use_container_width=True):
    load_factories.clear()
    load_gas_stations.clear()
    load_boundary.clear()
    st.sidebar.success("ล้างความจำและอัปเดตข้อมูลใหม่ทั้งหมดแล้ว!")
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.markdown("### 📌 คำนิยามระดับความเสี่ยง")

st.sidebar.error("**🔴 เสี่ยงสูง (High Risk)**\n\nกิจการอันตราย (เช่น น้ำแข็ง, สารเคมี, พลาสติก, แช่แข็ง, อบพืช) หรือ เครื่องจักร > 500 HP หรือ คนงาน > 100 คน")
st.sidebar.warning("**🟡 เสี่ยงปานกลาง (Medium)**\n\nกิจการโรงกลึง, โลหะ, ซักรีด, เฟอร์นิเจอร์, กระจก หรือ เครื่องจักร > 100 HP หรือ คนงาน > 30 คน")
st.sidebar.success("**🟢 เสี่ยงต่ำ (Low Risk)**\n\nกิจการขนาดเล็กทั่วไปที่ไม่ได้อยู่ในหมวดอันตราย และเครื่องจักร < 100 HP")

st.sidebar.markdown("---")
st.sidebar.markdown("### 🎯 ประเมินอุบัติภัยและนำทาง")

# วิชเก็ตตัวเลือกโหมดการใช้งาน
mode = st.sidebar.radio(
    "โหมดการใช้งานแผนที่",
    ["🔍 ดูข้อมูลปกติ", "🖱️ คลิกบนแผนที่", "📋 เลือกจากรายชื่อ"]
)

enable_routing_click = False

# การแสดงผลตามโหมดที่เลือก
if mode == "🔍 ดูข้อมูลปกติ":
    st.sidebar.info("💡 **สถานะ: ดูข้อมูลปกติ** \nคลิกที่หมุดบนแผนที่เพื่อดูรายละเอียดโรงงาน/ปั๊มน้ำมัน การคลิกจะไม่ถูกนำไปคำนวณเส้นทาง")

elif mode == "🖱️ คลิกบนแผนที่":
    enable_routing_click = True
    st.sidebar.info("💡 **วิธีใช้งาน:** \n- **คลิก 1 ครั้ง:** จุดเกิดเหตุ\n- **คลิก 2 ครั้ง:** จุดปลายทาง")
    c1_txt = f"{st.session_state.map_clicks[0][0]:.4f}, {st.session_state.map_clicks[0][1]:.4f}" if len(st.session_state.map_clicks) > 0 else "รอคลิกแผนที่..."
    c2_txt = f"{st.session_state.map_clicks[1][0]:.4f}, {st.session_state.map_clicks[1][1]:.4f}" if len(st.session_state.map_clicks) > 1 else "รอคลิกแผนที่..."
    st.sidebar.markdown(f"🔥 **จุดเกิดเหตุ:** {c1_txt}")
    st.sidebar.markdown(f"🏁 **จุดปลายทาง:** {c2_txt}")

elif mode == "📋 เลือกจากรายชื่อ":
    st.sidebar.info("💡 เลือกระบุจุดเริ่มต้นและปลายทางจากรายชื่อสถานที่")
    if locations_dict:
        location_names = list(locations_dict.keys())
        point1 = st.sidebar.selectbox("จุดเริ่มต้น (เช่น จุดเกิดเหตุ)", options=location_names, index=0)
        point2 = st.sidebar.selectbox("จุดปลายทาง (เช่น ศูนย์อพยพ/รพ.)", options=location_names, index=1 if len(location_names) > 1 else 0)
        
        if st.sidebar.button("🚀 คำนวณเส้นทาง", type="primary", use_container_width=True):
            lat1, lon1 = locations_dict[point1]
            lat2, lon2 = locations_dict[point2]
            
            st.session_state.map_clicks = [(lat1, lon1), (lat2, lon2)]
            st.session_state.route_data = None
            st.session_state.map_center = [lat1, lon1] 
            st.rerun()

if len(st.session_state.map_clicks) > 0 or st.session_state.route_data:
    if st.sidebar.button("🗑️ ล้างเส้นทาง (เริ่มใหม่)", use_container_width=True):
        st.session_state.map_clicks = []
        st.session_state.route_data = None
        st.session_state.last_processed_click = None
        st.rerun()

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
# 6. โหลดข้อมูลแผนที่หลัก (Folium)
# ==========================================
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
                    risk_level = str(row.iloc[6]) if pd.notna(row.iloc[6]) else 'ไม่ระบุ'

                    marker_color, fill_color = '#95a5a6', '#bdc3c7'
                    if '🔴' in risk_level or 'เสี่ยงสูง' in risk_level:
                        marker_color, fill_color = '#c0392b', '#e74c3c'
                    elif '🟡' in risk_level or 'ปานกลาง' in risk_level:
                        marker_color, fill_color = '#d35400', '#f1c40f'
                    elif '🟢' in risk_level or 'เสี่ยงต่ำ' in risk_level:
                        marker_color, fill_color = '#27ae60', '#2ecc71'

                    popup_html = f"""
                        <div style="min-width: 250px; font-family: 'Google Sans', 'Noto Sans Thai', sans-serif; color: #333;">
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
# 7. วาดเส้นทางและวงกลมบนแผนที่
# ==========================================
if len(st.session_state.map_clicks) >= 1:
    folium.Marker(st.session_state.map_clicks[0], icon=folium.Icon(color='darkred', icon='fire', prefix='fa'), tooltip="จุดเกิดเหตุ (Start)").add_to(m)

if len(st.session_state.map_clicks) == 2 and st.session_state.route_data:
    rd = st.session_state.route_data
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

# ==========================================
# 8. Render แผนที่และดักจับ Event การคลิกเมาส์
# ==========================================
# ปรับใช้ use_container_width=True และลดความสูงเป็น 800 เพื่อให้ตอบโจทย์ทุกขนาดหน้าจอ
map_data = st_folium(
    m, 
    use_container_width=True, 
    height=800, 
    returned_objects=["last_object_clicked", "last_clicked"]
)

# เพิ่มการประกาศตัวแปรเริ่มต้น เพื่อป้องกัน NameError 
clicked_point = None

if map_data:
    if map_data.get("last_object_clicked"):
        clicked_point = map_data["last_object_clicked"]
    elif map_data.get("last_clicked"):
        clicked_point = map_data["last_clicked"]

if clicked_point and clicked_point != st.session_state.last_processed_click:
    st.session_state.last_processed_click = clicked_point
    st.session_state.map_center = [clicked_point['lat'], clicked_point['lng']]
    
    if enable_routing_click:
        if len(st.session_state.map_clicks) >= 2:
            st.session_state.map_clicks = [(clicked_point['lat'], clicked_point['lng'])]
            st.session_state.route_data = None
        else:
            st.session_state.map_clicks.append((clicked_point['lat'], clicked_point['lng']))
        
        st.rerun()
