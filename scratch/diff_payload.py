import sys
import os
import requests
import json

sys.path.insert(0, os.path.abspath("."))
from cert_repository import _normalize_raw_payload
from data.query import get_offline_certificate_data

def get_online_raw(student_id, grouping_mode):
    url = f"http://localhost:8000/certificates/{student_id}?grouping_mode={grouping_mode}"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        print(f"Online fetch error: {e}")
    return {}

def main():
    st_id = 12
    g_mode = "DEFAULT"
    
    on_raw = get_online_raw(st_id, g_mode)
    off_raw = get_offline_certificate_data(st_id, g_mode)
    
    on_norm = _normalize_raw_payload(on_raw, st_id, g_mode)
    off_norm = _normalize_raw_payload(off_raw, st_id, g_mode)
    
    keys_to_check = ["student_info", "academic_timeline", "courses_grouped"]
    
    for key in keys_to_check:
        print(f"\n--- {key.upper()} ---")
        on_data = on_norm.get(key, [])
        off_data = off_norm.get(key, [])
        
        if isinstance(on_data, dict):
            on_data = [on_data]
        if isinstance(off_data, dict):
            off_data = [off_data]
            
        print(f"Lengths: Online={len(on_data)}, Offline={len(off_data)}")
        
        for idx in range(min(len(on_data), len(off_data))):
            on_item = on_data[idx]
            off_item = off_data[idx]
            
            all_keys = set(on_item.keys()).union(set(off_item.keys()))
            
            diffs = False
            for k in sorted(all_keys):
                on_v = on_item.get(k)
                off_v = off_item.get(k)
                if on_v != off_v:
                    if not diffs:
                        print(f"  Item {idx}:")
                        diffs = True
                    print(f"    Key: {k}")
                    print(f"      Online : {repr(on_v)} (type: {type(on_v).__name__})")
                    print(f"      Offline: {repr(off_v)} (type: {type(off_v).__name__})")

if __name__ == "__main__":
    main()
