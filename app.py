import streamlit as st
import pandas as pd
from streamlit_folium import st_folium

# นำเข้าฟังก์ชันจากไฟล์ที่แยกไว้
from data_loader import load_boundary, load_gas_stations, load_factories, get_driving_route, calculate_straight_distance
from ui_sidebar import render_sidebar
from map_builder import generate_map

# ==========================================
# 1. การตั้งค่าหน้าเว็บ Streamlit และ ฟอนต์ Google Sans
# ==========================================
st.set_page_config(page_title="แผนที่โรงงาน อ.สันทราย", layout="wide", page_icon="📍")

# แทรก CSS เพื่อโหลดฟอนต์ แก้ปัญหาไม้เอกหาย และปรับให้ยืดหยุ่น (Responsive)
st.markdown("""
    <style>
        @import url('https://fonts.cdnfonts.com/css/google-sans');
        @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+Thai:wght@300;400;500;600;700&display=swap');
        
        html, body, [class*="st-"], p, h1, h2, h3, h4, h5, h6, span, label, div {
            font-family: 'Google Sans', 'Noto Sans Thai', sans-serif !important;
            line-height: 1.6 !important; 
        }
        h1, h2, h3 {
            padding-top: 12px !important;
            padding-bottom: 8px !important;
        }
        svg, svg *, i, .material-icons, [class*="icon"] {
            font-family: inherit !important;
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

st.title("📍 แผนที่โรงงาน อ.สันทราย จ.เชียงใหม่")
st.markdown("แสดงพิกัดโรงงาน พร้อมเลเยอร์ขอบเขต ปั๊มน้ำมัน และโรงพยาบาล")

# ==========================================
# 2. จัดการ State สำหรับระบบคลิกแผนที่และการจดจำมุมมอง
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
# 3. เตรียมข้อมูลพิกัดสถานที่ทั้งหมด (ใช้สำหรับ Dropdown)
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
            # ค้นหาพิกัดแบบอัตโนมัติ ไม่ต้องฟิกซ์หมายเลขคอลัมน์
            lat, lon = None, None
            for val in row.values:
                val_str = str(val).strip().replace('"', '')
                if ',' in val_str:
                    parts = val_str.split(',')
                    if len(parts) == 2:
                        try:
                            temp_lat, temp_lon = float(parts[0].strip()), float(parts[1].strip())
                            if 5 < temp_lat < 21 and 97 < temp_lon < 106: # พิกัดในไทย
                                lat, lon = temp_lat, temp_lon
                                break
                        except ValueError:
                            pass
            
            if lat is not None and lon is not None:
                # พยายามหาชื่อโรงงาน (สมมติว่าอยู่คอลัมน์ที่ 1 หรือหาคอลัมน์แรกที่เป็น string)
                raw_name = str(row.iloc[1]) if pd.notna(row.iloc[1]) else 'ไม่มีชื่อ'
                full_name = raw_name.split('\n')[0].replace('"', '')
                locations_dict[f"🏭 {full_name}"] = (lat, lon)
        except Exception:
            pass

# ==========================================
# 4. ส่วนแถบเมนูด้านข้าง (Sidebar)
# ==========================================
enable_routing_click, factory_filter = render_sidebar(locations_dict)

# ==========================================
# 5. กรองข้อมูลโรงงานตาม Dropdown ที่เลือก
# ==========================================
if not df_factories.empty and factory_filter != "แสดงทั้งหมด":
    # นำทุกคอลัมน์มาต่อกันเป็นข้อความเดียว เพื่อค้นหาแบบครอบคลุม ป้องกันตารางโดนลบคอลัมน์
    df_search = df_factories.astype(str).fillna('')
    combined_text = df_search.apply(lambda r: ' '.join(r.values), axis=1)
    
    # 🌟 จัดกลุ่มคีย์เวิร์ดใหม่ (ตัดคำที่อาจซ้ำกับชื่อที่อยู่ออก เช่น 'ทราย' จากสันทราย, 'บ่อ' จากชื่อหมู่บ้าน)
    kw_boiler = 'หม้อน้ำ|boiler'
    kw_pm25 = 'ฝุ่น|pm2.5|ควัน|แอสฟัลท์|โรงสี'
    kw_ammonia = 'แอมโมเนีย|น้ำแข็ง|ห้องเย็น|ammonia'
    kw_silica = 'ซิลิกา|silica|บ่อทราย|ท่าทราย|ดูดทราย|โม่หิน|กระจก|เซรามิก' 
    kw_pathogen = 'เชื้อโรค|ชีวภาพ|ขยะติดเชื้อ|โรงพยาบาล|คลินิก'
    kw_asbestos = 'แร่ใยหิน|asbestos|กระเบื้อง|ฉนวน|เบรก'
    kw_confined = 'อับอากาศ|ไซโล|ถังขนาดใหญ่|อุโมงค์|confined'
    kw_lead = 'ตะกั่ว|lead|แบตเตอรี่|หลอม|อิเล็กทรอนิกส์'
    
    if factory_filter == "หม้อน้ำ (Boiler)":
        mask = combined_text.str.contains(kw_boiler, case=False)
    elif factory_filter == "ฝุ่น (PM2.5)":
        mask = combined_text.str.contains(kw_pm25, case=False)
    elif factory_filter == "แอมโมเนีย (Ammonia/ห้องเย็น)":
        mask = combined_text.str.contains(kw_ammonia, case=False)
    elif factory_filter == "ซิลิกา (Silica)":
        mask = combined_text.str.contains(kw_silica, case=False)
    elif factory_filter == "เชื้อโรค (Biohazard)":
        mask = combined_text.str.contains(kw_pathogen, case=False)
    elif factory_filter == "แร่ใยหิน (Asbestos)":
        mask = combined_text.str.contains(kw_asbestos, case=False)
    elif factory_filter == "อับอากาศ (Confined Space)":
        mask = combined_text.str.contains(kw_confined, case=False)
    elif factory_filter == "ตะกั่ว (Lead)":
        mask = combined_text.str.contains(kw_lead, case=False)
    elif factory_filter == "ทั่วไป (อื่นๆ)":
        all_hazards = f"{kw_boiler}|{kw_pm25}|{kw_ammonia}|{kw_silica}|{kw_pathogen}|{kw_asbestos}|{kw_confined}|{kw_lead}"
        mask = ~combined_text.str.contains(all_hazards, case=False)
    
    df_factories = df_factories[mask]

# ==========================================
# 6. โหลดข้อมูลแผนที่หลัก (Folium) และ Render
# ==========================================
m = generate_map(
    boundary_geo, 
    hospitals, 
    gas_stations, 
    df_factories, 
    st.session_state.map_center, 
    st.session_state.map_zoom,
    st.session_state.map_clicks,
    st.session_state.route_data
)

# Render แผนที่และดักจับ Event การคลิกเมาส์
map_data = st_folium(
    m, 
    use_container_width=True, 
    height=800, 
    returned_objects=["last_object_clicked", "last_clicked"]
)

clicked_point = None
if map_data:
    if map_data.get("last_object_clicked"):
        clicked_point = map_data["last_object_clicked"]
    elif map_data.get("last_clicked"):
        clicked_point = map_data["last_clicked"]

if clicked_point and clicked_point != st.session_state.last_processed_click:
    st.session_state.last_processed_click = clicked_point
    
    if enable_routing_click:
        if len(st.session_state.map_clicks) >= 2:
            st.session_state.map_clicks = [(clicked_point['lat'], clicked_point['lng'])]
            st.session_state.route_data = None
        else:
            st.session_state.map_clicks.append((clicked_point['lat'], clicked_point['lng']))
        
        st.rerun()
