import streamlit as st

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
    st.sidebar.markdown("### 🌪️ จำลองอุบัติภัยและทิศทางลม")
    
    # 🌟 เลือกระยะผลกระทบและทิศทางลม
    hazard_type = st.sidebar.selectbox("ประเภทสารเคมี/อุบัติภัย:", [
        "ค่าเริ่มต้น (ทั่วไป)", 
        "แอมโมเนีย (ก๊าซพิษ)", 
        "ไฟไหม้ / หม้อน้ำระเบิด", 
        "ฝุ่นควัน / PM2.5"
    ])
    
    wind_speed = st.sidebar.slider("ความเร็วลม (กม./ชม.)", 0, 50, 0, help="หากความเร็วลม > 0 โซนเฝ้าระวังจะเปลี่ยนเป็นรูปพัดตามทิศทางลม")
    wind_dir = st.sidebar.slider("ทิศที่ลมพัดไป (องศา)", 0, 360, 90, help="ทิศที่สารเคมีกระจายไป (0=เหนือ, 90=ตะวันออก, 180=ใต้, 270=ตะวันตก)")


    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🎯 ประเมินและนำทาง")

    mode = st.sidebar.radio(
        "โหมดการใช้งานแผนที่",
        ["🔍 ดูข้อมูลปกติ", "🖱️ คลิกบนแผนที่", "📋 เลือกจากรายชื่อ"]
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

    if len(st.session_state.map_clicks) > 0 or st.session_state.route_data:
        if st.sidebar.button("🗑️ ล้างเส้นทาง (เริ่มใหม่)", use_container_width=True):
            st.session_state.map_clicks = []
            st.session_state.route_data = None
            st.session_state.last_processed_click = None
            st.rerun()

    if st.session_state.route_data:
        rd = st.session_state.route_data
        s_dist = rd['straight_dist']
        
        # 🌟 กำหนดระยะตามประเภทที่ผู้ใช้เลือกใน Sidebar 
        if hazard_type == "แอมโมเนีย (ก๊าซพิษ)":
            hot_m, warm_m = 1000, 3000
        elif hazard_type == "ไฟไหม้ / หม้อน้ำระเบิด":
            hot_m, warm_m = 200, 500
        elif hazard_type == "ฝุ่นควัน / PM2.5":
            hot_m, warm_m = 500, 2000
        else:
            hot_m, warm_m = 500, 2000
            
        st.sidebar.markdown("---")
        st.sidebar.markdown("#### 🚗 สรุปการเดินทาง")
        col1, col2 = st.sidebar.columns(2)
        col1.metric("ระยะทางขับรถ", f"{rd['dist']:.2f} กม.")
        col2.metric("เวลาเดินทาง", f"~ {rd['dur']:.0f} นาที")
        
        st.sidebar.markdown("---")
        st.sidebar.markdown("#### 🎯 ระดับความปลอดภัย (อ้างอิงจุดหมาย)")
        st.sidebar.caption(f"ระยะกระจัดจากจุดเกิดเหตุ: {s_dist:.2f} กม.")
        if wind_speed > 0:
            st.sidebar.caption("*(กรุณาตรวจสอบแผนที่ประกอบ เนื่องจากมีการกระจายตัวตามทิศทางลม)*")
        
        if s_dist <= (hot_m / 1000.0):
            st.sidebar.error(f"**🔴 โซนอันตราย (Hot Zone) < {hot_m}ม.**\n\nอันตรายถึงชีวิต ต้องสวม PPE ระดับสูงสุดและอพยพทันที")
        elif s_dist <= (warm_m / 1000.0):
            st.sidebar.warning(f"**🟡 โซนเฝ้าระวัง (Warm Zone) < {warm_m}ม.**\n\nอาจได้รับผลกระทบจากกลุ่มควัน/ก๊าซพิษ เตรียมพร้อมอพยพหรือหลบในอาคาร (Shelter-in-place)")
        else:
            st.sidebar.success(f"**🟢 โซนปลอดภัย (Cold Zone) > {warm_m}ม.**\n\nอยู่นอกรัศมีผลกระทบรุนแรง เหมาะสำหรับตั้งศูนย์บัญชาการ (Incident Command)")

    return enable_routing_click, factory_filter, hazard_type, wind_speed, wind_dir
