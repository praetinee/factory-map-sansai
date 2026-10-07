import pandas as pd
import requests
import math
import streamlit as st

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
    # ใช้พิกัดกรอบสี่เหลี่ยม (Bounding Box) ครอบ อ.สันทราย แทนการใช้ชื่อภาษาไทย
    # (พิกัด: ทิศใต้ 18.81, ทิศตะวันตก 98.95, ทิศเหนือ 19.12, ทิศตะวันออก 99.16)
    query = """[out:json][timeout:25];
    (
      node["amenity"="fuel"](18.81,98.95,19.12,99.16);
      way["amenity"="fuel"](18.81,98.95,19.12,99.16);
      relation["amenity"="fuel"](18.81,98.95,19.12,99.16);
    );
    out center;"""
    
    endpoints = [
        'https://overpass.openstreetmap.fr/api/interpreter',
        'https://overpass.osm.ch/api/interpreter',
        'https://overpass-api.de/api/interpreter',
        'https://lz4.overpass-api.de/api/interpreter'
    ]
    
    headers = {'User-Agent': 'FactoryRiskMapApp/1.0 (praetinee@example.com)'}
    
    for url in endpoints:
        try:
            r = requests.post(url, data=query.encode('utf-8'), headers=headers, timeout=15)
            if r.status_code == 200:
                data = r.json()
                return data.get('elements', [])
        except Exception:
            continue
            
    st.sidebar.warning("⚠️ ไม่สามารถโหลดข้อมูลปั๊มน้ำมันได้ชั่วคราว")
    return []

@st.cache_data(ttl=300)
def load_factories():
    sheet_url = 'https://docs.google.com/spreadsheets/d/1qHJwpzbaFbn-ayQs4iAHodxAh1Lh5xiUuUHIL5t9v7k/export?format=csv&gid=0'
    try:
        return pd.read_csv(sheet_url)
    except Exception as e:
        return pd.DataFrame()

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

def calculate_straight_distance(lat1, lon1, lat2, lon2):
    R = 6371.0 # รัศมีโลก (กม.)
    lat1_rad, lon1_rad = math.radians(lat1), math.radians(lon1)
    lat2_rad, lon2_rad = math.radians(lat2), math.radians(lon2)
    dlon = lon2_rad - lon1_rad
    dlat = lat2_rad - lat1_rad
    a = math.sin(dlat / 2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c
