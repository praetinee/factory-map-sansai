# ... existing code ...
# ==========================================
# 3. ส่วนแถบเมนูด้านข้าง (Sidebar)
# ==========================================
st.sidebar.header("⚙️ การจัดการข้อมูล")

# ปุ่มโหลดข้อมูลโรงงานใหม่ (เคลียร์ Cache ของโรงงาน)
if st.sidebar.button("🔄 รีโหลดข้อมูลโรงงานล่าสุด", use_container_width=True):
    load_factories.clear()
    st.sidebar.success("อัปเดตข้อมูลจากชีตแล้ว!")

st.sidebar.markdown("---")

# แทนที่ข้อความเดิมด้วย HTML แบบปรับแต่งสีสันและรูปแบบ
st.sidebar.markdown("""
<div class="risk-legend-container" style="background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 15px; margin-bottom: 20px; font-family: sans-serif; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
    
    <h4 style="margin: 0 0 12px 0; font-size: 16px; font-weight: 600; color: #1f2937; border-bottom: 1px solid #e2e8f0; padding-bottom: 8px;">
        คำนิยามระดับความเสี่ยง
    </h4>

    <!-- เสี่ยงสูง -->
    <div style="margin-bottom: 12px; font-size: 13px; line-height: 1.5; color: #4b5563;">
        <span style="color: #dc2626; font-weight: bold; font-size: 14px;">🔴 เสี่ยงสูง:</span> 
        กิจการอันตราย (เช่น น้ำแข็ง, สารเคมี, พลาสติก, แช่แข็ง, อบพืช) หรือ เครื่องจักร > 500 HP หรือ คนงาน > 100 คน
    </div>

    <!-- เสี่ยงกลาง -->
    <div style="margin-bottom: 12px; font-size: 13px; line-height: 1.5; color: #4b5563;">
        <span style="color: #d97706; font-weight: bold; font-size: 14px;">🟡 เสี่ยงปานกลาง:</span> 
        กิจการโรงกลึง, โลหะ, ซักรีด, เฟอร์นิเจอร์, กระจก หรือ เครื่องจักร > 100 HP หรือ คนงาน > 30 คน
    </div>

    <!-- เสี่ยงต่ำ -->
    <div style="font-size: 13px; line-height: 1.5; color: #4b5563;">
        <span style="color: #059669; font-weight: bold; font-size: 14px;">🟢 เสี่ยงต่ำ:</span> 
        กิจการขนาดเล็กทั่วไปที่ไม่ได้อยู่ในหมวดอันตราย และเครื่องจักร < 100 HP
    </div>

</div>
""", unsafe_allow_html=True)

# ==========================================
# 4. การสร้างแผนที่ด้วย Folium
# ==========================================
# 4.1 สร้างแผนที่เปล่า
# ... existing code ...
