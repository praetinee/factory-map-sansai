import streamlit as st

def render_sidebar(locations_dict):
    st.sidebar.header("⚙️ การจัดการข้อมูล")

    # เพิ่มประสิทธิภาพปุ่มรีโหลด ให้ล้างความจำทุกอย่างแล้วโหลดใหม่ทั้งหมด
    if st.sidebar.button("🔄 รีโหลดข้อมูลใหม่ทั้งหมด", use_container_width=True):
        st.cache_data.clear()
        st.sidebar.success("ล้างความจำและอัปเดตข้อมูลใหม่ทั้งหมดแล้ว!")
        st.rerun()

    st.sidebar.markdown("---")
    
    # เพิ่ม Dropdown สำหรับกรองกลุ่มโรงงาน (อัปเดตเพิ่มหมวดหมู่ใหม่)
    st.sidebar.markdown("### 🏭 กรองประเภทโรงงาน")
    factory_filter = st.sidebar.selectbox(
        "เลือกกลุ่มโรงงานที่ต้องการแสดง:",
        [
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
    )

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

    return enable_routing_click, factory_filter
