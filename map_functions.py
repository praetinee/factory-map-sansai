import folium

def create_factory_map(data):
    """
    ฟังก์ชันสำหรับสร้างแผนที่โรงงาน
    - เปลี่ยนสีของ Marker ทั้งหมดเป็น "สีเทา" (gray)
    - ไม่มีการเช็คเงื่อนไขระดับความเสี่ยงอีกต่อไป
    """
    # ตั้งค่าจุดศูนย์กลางแผนที่ไปที่อำเภอสันทราย เชียงใหม่
    m = folium.Map(location=[18.85, 99.01], zoom_start=13)
    
    # วนลูปสร้างจุดบนแผนที่จากข้อมูลที่มี
    for factory in data:
        # กำหนดให้สีของจุดเป็น 'gray' (สีเทา) ทั้งหมดเหมือนกันหมด
        folium.Marker(
            location=[factory['lat'], factory['lon']],
            popup=f"ชื่อโรงงาน: {factory['name']}", # ลบข้อมูลความเสี่ยงออกจาก Popup ด้วย
            icon=folium.Icon(color='gray', icon='info-sign')
        ).add_to(m)
        
    return m
