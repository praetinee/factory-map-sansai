import streamlit as st
import requests
import re

# 🌟 ฟังก์ชันจัดการและดึงข้อมูลพิกัด GPS อัจฉริยะ ป้องกันการพิมพ์ผิด
def parse_gps_input(text):
    # ลบอักขระที่ไม่จำเป็นออก หาเฉพาะตัวเลข ทศนิยม และเครื่องหมายลบ
    nums = re.findall(r'-?\d+\.\d+|-?\d+', text)
    if len(nums) >= 2:
        val1, val2 = float(nums[0]), float(nums[1])
        # พิกัดประเทศไทย Lat ปกติอยู่ระหว่าง 5 ถึง 21, Lon ระหว่าง 97 ถึง 106
        # ถ้าค่าแรกเยอะกว่า 50 แสดงว่าผู้ใช้น่าจะพิมพ์ Lon ก่อน Lat ให้สลับให้ถูก
        if val1 > 50 and val2 < 50:
            return val2, val1
        return val1, val2
    return None, None

def fetch_realtime_weather(lat, lon):
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
    try:
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            data = r.json()
            cw = data.get("current_weather", {})
            return cw.get("windspeed", 0), cw.get("winddirection", 0)
    except Exception:
        pass
    return None, None

def render_sidebar(locations_dict, category_counts=None):
    st.sidebar.header("⚙️ การจัดการข้อมูล")

    if st.sidebar.button("🔄 รีโหลดข้อมูลใหม่ทั้งหมด", use_container_width=True):
        st.cache_data.clear()
        st.sidebar.success("ล้างความจำและอัปเดตข้อมูลใหม่ทั้งหมดแล้ว!")
        st.rerun()

    st.sidebar.markdown("---")
    
    st.sidebar.markdown("### 🏭 กรองประเภทโรงงาน")
    
    base_categories = [
        "แสดงทั้งหมด", 
        "หม้อน้ำ (Boiler)", 
        "ฝุ่น (PM2.5)", 
        "แอมโมเนีย (Ammonia/ห้องเย็น)", 
        "ซิลิกา (Silica)",
        "เชื้อโรค (Biohazard)",
        "แร่ใยหิน (Asbestos)",
        "อับอากาศ (Confined Space)",
        "ตะกั่ว (Lead)",
        "ทั่วไป (อื่นๆ)"
    ]
    
    if category_counts:
        options = [f"{cat} ({category_counts.get(cat, 0)})" for cat in base_categories]
    else:
        options = base_categories

    factory_filter = st.sidebar.selectbox(
        "เลือกกลุ่มโรงงานที่ต้องการแสดง:",
        options
    )

    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🎯 ประเมินและนำทาง")

    # 🌟 เพิ่มโหมดที่ 4 สำหรับการระบุพิกัดโดยตรง
    mode = st.sidebar.radio(
        "โหมดการใช้งานแผนที่",
        ["🔍 ดูข้อมูลปกติ", "🖱️ คลิกบนแผนที่", "📋 เลือกจากรายชื่อ", "📍 ระบุพิกัด GPS"]
    )

    enable_routing_click = False

    if mode == "🔍 ดูข้อมูลปกติ":
        st.sidebar.info("💡 **สถานะ: ดูข้อมูลปกติ** \nคลิกที่หมุดบนแผนที่เพื่อดูรายละเอียดโรงงาน การคลิกจะไม่ถูกนำไปคำนวณเส้นทาง")

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

    # 🌟 โหมดใหม่: ระบุพิกัด GPS ตรงๆ
    elif mode == "📍 ระบุพิกัด GPS":
        st.sidebar.info("💡 ระบุพิกัด Latitude, Longitude")
        coord_start = st.sidebar.text_input("จุดเริ่มต้น (จุดเกิดเหตุ):", placeholder="เช่น 18.9135, 99.0279")
        coord_end = st.sidebar.text_input("จุดปลายทาง (ศูนย์อพยพ/รพ.):", placeholder="เช่น 18.9212, 98.9942")

        if st.sidebar.button("🚀 คำนวณเส้นทาง", type="primary", use_container_width=True):
            lat1, lon1 = parse_gps_input(coord_start)
            lat2, lon2 = parse_gps_input(coord_end)

            if lat1 is not None and lon1 is not None and lat2 is not None and lon2 is not None:
                st.session_state.map_clicks = [(lat1, lon1), (lat2, lon2)]
                st.session_state.route_data = None
                st.session_state.map_center = [lat1, lon1]
                st.rerun()
            else:
                st.sidebar.error("❌ รูปแบบพิกัดไม่ถูกต้อง กรุณาตรวจสอบตัวเลขอีกครั้ง (ตัวอย่าง: 18.9135, 99.0279)")

    if len(st.session_state.map_clicks) > 0 or st.session_state.route_data:
        if st.sidebar.button("🗑️ ล้างเส้นทาง (เริ่มใหม่)", use_container_width=True):
            st.session_state.map_clicks = []
            st.session_state.route_data = None
            st.session_state.last_processed_click = None
            st.rerun()

    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🌪️ จำลองอุบัติภัยและทิศทางลม")
    
    # 🌟 เลือกระยะผลกระทบและทิศทางลม
    hazard_type = st.sidebar.selectbox("ประเภทสารเคมี/อุบัติภัย:", [
        "ค่าเริ่มต้น (ทั่วไป)", 
        "แอมโมเนีย (ก๊าซพิษ)", 
        "ไฟไหม้ / หม้อน้ำระเบิด", 
        "ฝุ่นควัน / PM2.5"
    ])
    
    # กำหนดพิกัดสำหรับใช้ดึงสภาพอากาศ
    lat_for_weather, lon_for_weather = 18.9135, 99.0279 # ค่าเริ่มต้น (อ.สันทราย)
    if 'map_clicks' in st.session_state and len(st.session_state.map_clicks) > 0:
        lat_for_weather, lon_for_weather = st.session_state.map_clicks[0]

    # เก็บค่าลมไว้ใน session_state เพื่อไม่ให้ข้อมูลหายเวลาโหลดใหม่
    if 'wind_speed' not in st.session_state:
        st.session_state.wind_speed = 0.0
    if 'wind_dir_deg' not in st.session_state:
        st.session_state.wind_dir_deg = 90.0

    if st.sidebar.button("📡 ดึงข้อมูลลม ณ จุดเกิดเหตุ (Real-time)", help="ฟรี API จาก Open-Meteo ไม่ต้องใช้ Key", use_container_width=True):
        with st.spinner("กำลังดึงข้อมูลจากกรมอุตุนิยมวิทยา (Open-Meteo)..."):
            ws, wd = fetch_realtime_weather(lat_for_weather, lon_for_weather)
            if ws is not None and wd is not None:
                st.session_state.wind_speed = float(ws)
                st.session_state.wind_dir_deg = float(wd)
                st.sidebar.success(f"✔️ สำเร็จ! ความเร็ว {ws} กม./ชม. ทิศทาง {wd}°")
            else:
                st.sidebar.error("❌ ดึงข้อมูลไม่สำเร็จ กรุณากรอกตัวเลขเอง")

    wind_speed = st.sidebar.number_input("ความเร็วลม (กม./ชม.)", min_value=0.0, max_value=200.0, value=float(st.session_state.wind_speed), step=1.0)
    wind_dir = st.sidebar.number_input("ทิศที่ลมพัดไป (องศา 0-360)", min_value=0.0, max_value=360.0, value=float(st.session_state.wind_dir_deg), step=1.0)
    
    st.session_state.wind_speed = wind_speed
    st.session_state.wind_dir_deg = wind_dir

    if st.session_state.route_data:
        rd = st.session_state.route_data
        s_dist = rd['straight_dist']
        
        try:
            from map_builder import calculate_hazard_zones
            from datetime import datetime
            current_hour = datetime.now().hour
            is_night = current_hour < 6 or current_hour >= 18
            hot_m, warm_m, spread_angle = calculate_hazard_zones(hazard_type, wind_speed, is_night)
        except ImportError:
            hot_m, warm_m, spread_angle = 500, 2000, 360 # Fallback
            
        st.sidebar.markdown("---")
        st.sidebar.markdown("#### 🚗 สรุปการเดินทาง")
        col1, col2 = st.sidebar.columns(2)
        
        # 🌟 แก้ไข: ลบการกำหนดสีตายตัวออก เพื่อให้รองรับ Dark Mode / Light Mode อัตโนมัติ
        col1.markdown(f"**ระยะทางขับรถ**<br/><span style='font-size: 1.25rem; font-weight: bold;'>{rd['dist']:.2f} กม.</span>", unsafe_allow_html=True)
        col2.markdown(f"**เวลาเดินทาง**<br/><span style='font-size: 1.25rem; font-weight: bold;'>~ {rd['dur']:.0f} นาที</span>", unsafe_allow_html=True)
        
        st.sidebar.markdown("---")
        st.sidebar.markdown("#### 🎯 ระดับความปลอดภัย (อ้างอิงจุดหมาย)")
        st.sidebar.caption(f"ระยะกระจัดจากจุดเกิดเหตุ: {s_dist:.2f} กม.")
        if wind_speed > 2:
            st.sidebar.caption(f"*(อ้างอิง Plume Physics: ควันถูกพัดพาลึกสุด {warm_m:.0f}ม. มุมกระจายตัว {spread_angle}°)*")
        
        if s_dist <= (hot_m / 1000.0):
            st.sidebar.error(f"**🔴 โซนอันตราย (Hot Zone) < {hot_m}ม.**\n\nอันตรายถึงชีวิต ต้องสวม PPE ระดับสูงสุดและอพยพทันที")
        elif wind_speed > 2:
            st.sidebar.warning(f"**🟡 โซนเฝ้าระวัง (Warm Zone)**\n\nมีโอกาสโดนผลกระทบจากกลุ่มควัน/ก๊าซพิษที่ถูกพัดไปตามทิศทางลม เตรียมพร้อมอพยพ")
        elif s_dist <= (warm_m / 1000.0):
            st.sidebar.warning(f"**🟡 โซนเฝ้าระวัง (Warm Zone) < {warm_m:.0f}ม.**\n\nอาจได้รับผลกระทบจากกลุ่มควัน/ก๊าซพิษ เตรียมพร้อมอพยพ")
        else:
            st.sidebar.success(f"**🟢 โซนปลอดภัย (Cold Zone)**\n\nอยู่นอกรัศมีผลกระทบรุนแรง เหมาะสำหรับตั้งศูนย์บัญชาการ (Incident Command)")

    return enable_routing_click, factory_filter, hazard_type, wind_speed, wind_dir
