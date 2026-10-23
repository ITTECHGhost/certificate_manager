import sys
import os
import requests
import copy

sys.path.insert(0, os.path.abspath("."))
from cert_repository import _normalize_raw_payload
from data.query import get_offline_certificate_data

def get_online_raw(student_id, grouping_mode):
    url = f"http://localhost:8000/certificates/{student_id}?grouping_mode={grouping_mode}"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            return resp.json()
        else:
            print(f"API Error: {resp.status_code} - {resp.text}")
    except Exception as e:
        print(f"Failed to fetch online data for {student_id} ({grouping_mode}): {e}")
    return {}

def get_offline_raw(student_id, grouping_mode):
    return get_offline_certificate_data(student_id, grouping_mode)

def calculate_similarity(dict1, dict2):
    if not isinstance(dict1, (dict, list)) or not isinstance(dict2, (dict, list)):
        return 100.0 if dict1 == dict2 else 0.0

    def flatten(item, prefix=""):
        flat = {}
        if isinstance(item, dict):
            for k, v in item.items():
                flat.update(flatten(v, f"{prefix}.{k}"))
        elif isinstance(item, list):
            for i, v in enumerate(item):
                flat.update(flatten(v, f"{prefix}[{i}]"))
        else:
            flat[prefix] = str(item).strip() if item is not None else ""
        return flat

    f1 = flatten(dict1)
    f2 = flatten(dict2)
    
    all_keys = set(f1.keys()).union(set(f2.keys()))
    if not all_keys:
        return 100.0
        
    matches = 0
    for k in all_keys:
        v1 = str(f1.get(k, "")).strip()
        v2 = str(f2.get(k, "")).strip()
        if v1 == v2:
            matches += 1
            
    return (matches / len(all_keys)) * 100.0

def main():
    students = [
        (12, "Annual System"), 
        (2010, "Semester System")
    ]
    grouping_modes = [
        ("DEFAULT", "Defulte"),
        ("BY_PERIOD_STAGE", "By year")
    ]
    keys = ["settings", "student_info", "ranking", "signers", "academic_timeline", "courses_grouped"]
    
    for st_id, st_type in students:
        print(f"\nSTD ID {st_id} ({st_type})")
        for i, (g_mode, g_name) in enumerate(grouping_modes, 1):
            print(f"Grouping {i} ({g_name})")
            
            on_raw = get_online_raw(st_id, g_mode)
            off_raw = get_offline_raw(st_id, g_mode)
            
            on_norm = _normalize_raw_payload(on_raw, st_id, g_mode)
            off_norm = _normalize_raw_payload(off_raw, st_id, g_mode)
            
            for key in keys:
                sim = calculate_similarity(on_norm.get(key), off_norm.get(key))
                print(f"({key}): Offline and online result similarity is {sim:.1f}%")

if __name__ == "__main__":
    main()
