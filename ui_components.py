import streamlit as st

def render_sidebar():
    """
    ฟังก์ชันสำหรับจัดการส่วน Sidebar ของแอปพลิเคชัน
    - นำคำนิยามระดับความเสี่ยง (สีแดง, สีเหลือง, สีเขียว) ออกแล้ว
    - คงโค้ดส่วนการรับ Gemini Token ไว้เหมือนเดิมเด๊ะ ไม่เปลี่ยนแปลง
    """
    st.sidebar.header("ตั้งค่าระบบ (Settings)")
    
    # โค้ดรับ Token Gemini ที่ไม่เกี่ยวข้องกับความเสี่ยง (ห้ามแก้เด็ดขาด ตามคำขอ)
    gemini_token = st.sidebar.text_input("Gemini API Token", type="password")
    
    st.sidebar.markdown("---")
    st.sidebar.info("📌 นำข้อมูลคำนิยามความเสี่ยงออกเรียบร้อยแล้ว เพื่อให้หน้าจอดูสะอาดขึ้น")
    
    # คืนค่า token เพื่อให้ app.py เอาไปใช้งานต่อได้
    return gemini_token
