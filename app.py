import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import requests

# ==========================================
# 1. การตั้งค่าหน้าเว็บ Streamlit
# ==========================================
st.set_page_config(page_title="แผนที่โรงงาน อ.สันทราย", layout="wide", page_icon="📍")

st.title("📍 แผนที่ความเสี่ยงโรงงาน อ.สันทราย จ.เชียงใหม่")
st.markdown("แสดงพิกัดโรงงานตามระดับความเสี่ยง พร้อมเลเยอร์ขอบเขต ปั๊มน้ำมัน และโรงพยาบาล")

# ==========================================
# 2. ฟังก์ชันดึงข้อมูล (ใส่ @st.cache_data เพื่อให้โหลดเร็ว ไม่ต้องดึงใหม่ทุกครั้ง)
# ==========================================

@st.cache_data(ttl=3600) # เก็บ Cache ไว้ 1 ชั่วโมง
def load_boundary():
    url = 'https://nominatim.openstreetmap.org/search?q=อำเภอสันทราย+จังหวัดเชียงใหม่&format=geojson&polygon_geojson=1&limit=1'
    try:
        r = requests.get(url, headers={'User-Agent': 'StreamlitMapApp/1.0'})
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
        r = requests.post(url, data={'data': query})
        data = r.json()
        return data.get('elements', [])
    except Exception as e:
        st.sidebar.error(f"โหลดปั๊มน้ำมันไม่สำเร็จ: {e}")
        return []

@st.cache_data(ttl=300) # เก็บ Cache โรงงานแค่ 5 นาที เพื่อความสดใหม่
def load_factories():
    sheet_url = 'https://docs.google.com/spreadsheets/d/1qHJwpzbaFbn-ayQs4iAHodxAh1Lh5xiUuUHIL5t9v7k/export?format=csv&gid=0'
    try:
        # ดึงข้อมูลจาก Google Sheets
        df = pd.read_csv(sheet_url)
        return df
    except Exception as e:
        st.sidebar.error("เข้าถึง Google Sheets ไม่ได้ (ตรวจสอบการแชร์)")
        return pd.DataFrame()

# ==========================================
# 3. ส่วนแถบเมนูด้านข้าง (Sidebar)
# ==========================================
st.sidebar.header("⚙️ การจัดการข้อมูล")

# ปุ่มโหลดข้อมูลโรงงานใหม่ (เคลียร์ Cache ของโรงงาน)
if st.sidebar.button("🔄 รีโหลดข้อมูลโรงงานล่าสุด", use_container_width=True):
    load_factories.clear()
    st.sidebar.success("อัปเดตข้อมูลจากชีตแล้ว!")

st.sidebar.markdown("---")
st.sidebar.markdown("""
**สัญลักษณ์ความเสี่ยงโรงงาน:**
* 🔴 **เสี่ยงสูง** (High Risk)
* 🟡 **เสี่ยงปานกลาง** (Medium)
* 🟢 **เสี่ยงต่ำ** (Low Risk)
""")

# ==========================================
# 4. การสร้างแผนที่ด้วย Folium
# ==========================================
# 4.1 สร้างแผนที่เปล่า
m = folium.Map(location=[18.9135, 99.0279], zoom_start=11)

# เพิ่ม Tile Layer (พื้นหลัง Google Maps)
folium.TileLayer(
    tiles='http://{s}.google.com/vt/lyrs=m&x={x}&y={y}&z={z}',
    attr='Google Maps',
    name='Google Maps (ถนน)',
    subdomains=['mt0', 'mt1', 'mt2', 'mt3']
).add_to(m)

folium.TileLayer(
    tiles='http://{s}.google.com/vt/lyrs=s,h&x={x}&y={y}&z={z}',
    attr='Google Maps',
    name='Google Hybrid (ดาวเทียม)',
    subdomains=['mt0', 'mt1', 'mt2', 'mt3'],
    show=False # ซ่อนไว้เป็นทางเลือก
).add_to(m)

# 4.2 สร้างกลุ่มเลเยอร์ (Feature Groups)
fg_boundary = folium.FeatureGroup(name="🟥 ขอบเขต อ.สันทราย")
fg_hospital = folium.FeatureGroup(name="🏥 โรงพยาบาล")
fg_gas = folium.FeatureGroup(name="⛽ ปั๊มน้ำมัน")
fg_factory = folium.FeatureGroup(name="📍 โรงงาน (ตามความเสี่ยง)")

# 4.3 โหลดและเพิ่มข้อมูลขอบเขต
boundary_geo = load_boundary()
if boundary_geo:
    folium.GeoJson(
        boundary_geo,
        style_function=lambda x: {'color': 'red', 'weight': 4, 'fillColor': 'red', 'fillOpacity': 0.04}
    ).add_to(fg_boundary)

# 4.4 เพิ่มข้อมูลโรงพยาบาล
hospitals = [
    {"name": "รพ. สันทราย", "lat": 18.921246, "lon": 98.994203},
    {"name": "รพ. นครพิงค์", "lat": 18.852547, "lon": 98.968389}
]
for h in hospitals:
    icon_html = "<div style='font-size:24px; filter: drop-shadow(2px 2px 2px rgba(0,0,0,0.4));'>🏥</div>"
    folium.Marker(
        [h['lat'], h['lon']], 
        icon=folium.DivIcon(html=icon_html, icon_size=(30,30), icon_anchor=(15,15)),
        popup=folium.Popup(f"<b>🏥 {h['name']}</b>", max_width=200)
    ).add_to(fg_hospital)

# 4.5 โหลดและเพิ่มปั๊มน้ำมัน
gas_stations = load_gas_stations()
for el in gas_stations:
    lat = el.get('lat') or (el.get('center', {}).get('lat'))
    lon = el.get('lon') or (el.get('center', {}).get('lon'))
    if lat and lon:
        name = el.get('tags', {}).get('name', 'ปั๊มน้ำมันทั่วไป')
        brand = el.get('tags', {}).get('brand', '')
        popup_text = f"<b>⛽ {name}</b><br><small>{brand}</small>"
        
        icon_html = "<div style='font-size:24px; filter: drop-shadow(2px 2px 2px rgba(0,0,0,0.4));'>⛽</div>"
        folium.Marker(
            [lat, lon],
            icon=folium.DivIcon(html=icon_html, icon_size=(30,30), icon_anchor=(15,15)),
            popup=folium.Popup(popup_text, max_width=250)
        ).add_to(fg_gas)

# 4.6 โหลดและเพิ่มข้อมูลโรงงาน (จาก CSV/Google Sheets)
df_factories = load_factories()
factory_count = 0

if not df_factories.empty:
    for idx, row in df_factories.iterrows():
        try:
            # คอลัมน์ที่ 7 (Index 7) คือพิกัด
            if len(row) >= 8 and pd.notna(row.iloc[7]):
                coords_str = str(row.iloc[7]).strip()
                if ',' in coords_str:
                    lat_str, lon_str = coords_str.replace('"', '').split(',')
                    lat, lon = float(lat_str.strip()), float(lon_str.strip())
                    
                    raw_name = str(row.iloc[1]) if pd.notna(row.iloc[1]) else 'ไม่มีชื่อ'
                    full_name = raw_name.split('\n')[0].replace('"', '')
                    location = str(row.iloc[2]).replace('\n', '<br>') if pd.notna(row.iloc[2]) else 'ไม่ระบุ'
                    activity = str(row.iloc[4]).replace('\n', '<br>') if pd.notna(row.iloc[4]) else 'ไม่ระบุ'
                    risk_details = str(row.iloc[5]).replace('\n', '<br>') if pd.notna(row.iloc[5]) else 'ไม่ระบุ'
                    risk_level = str(row.iloc[6]) if pd.notna(row.iloc[6]) else 'ไม่ระบุ'

                    # จัดการสีหมุด
                    marker_color, fill_color = '#95a5a6', '#bdc3c7' # Default (เทา)
                    if '🔴' in risk_level or 'เสี่ยงสูง' in risk_level:
                        marker_color, fill_color = '#c0392b', '#e74c3c'
                    elif '🟡' in risk_level or 'ปานกลาง' in risk_level:
                        marker_color, fill_color = '#d35400', '#f1c40f'
                    elif '🟢' in risk_level or 'เสี่ยงต่ำ' in risk_level:
                        marker_color, fill_color = '#27ae60', '#2ecc71'

                    popup_html = f"""
                        <div style="min-width: 250px; font-family: sans-serif;">
                            <h4 style="color: {marker_color}; border-bottom: 2px solid #eee; padding-bottom: 5px; margin-top: 0;">🏭 {full_name}</h4>
                            <div style="margin-bottom: 8px;"><strong>⚠️ ระดับความเสี่ยง:</strong><br>{risk_level}</div>
                            <div style="margin-bottom: 8px;"><strong>📍 สถานที่ตั้ง:</strong><br>{location}</div>
                            <div style="margin-bottom: 8px;"><strong>⚙️ การประกอบกิจการ:</strong><br>{activity}</div>
                            <div style="margin-bottom: 8px;"><strong>🔥 ความเสี่ยง:</strong><br>{risk_details}</div>
                        </div>
                    """

                    folium.CircleMarker(
                        location=[lat, lon],
                        radius=8,
                        color='white', # ขอบสีขาว
                        weight=2,
                        fill_color=fill_color,
                        fill_opacity=0.95,
                        popup=folium.Popup(popup_html, max_width=320)
                    ).add_to(fg_factory)
                    factory_count += 1
        except Exception as e:
            continue # ข้ามแถวที่ Error

st.sidebar.success(f"พบปั๊มน้ำมัน: {len(gas_stations)} แห่ง")
st.sidebar.success(f"พบโรงงาน: {factory_count} แห่ง")

# นำกลุ่มเลเยอร์ใส่ลงในแผนที่
fg_boundary.add_to(m)
fg_hospital.add_to(m)
fg_gas.add_to(m)
fg_factory.add_to(m)

# เพิ่มเมนูควบคุมการเปิด-ปิด เลเยอร์
folium.LayerControl(collapsed=False).add_to(m)

# ==========================================
# 5. นำแผนที่มาแสดงในหน้าเว็บ Streamlit
# ==========================================
st_folium(m, width="100%", height=700)
