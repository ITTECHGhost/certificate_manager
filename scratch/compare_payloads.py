import sys
import os
import requests
import copy

sys.path.insert(0, os.path.abspath("."))
from cert_repository import _normalize_raw_payload
from data.query import get_offline_certificate_data

import mysql.connector

def get_online_raw(student_id):
    datasets = []
    try:
        conn = mysql.connector.connect(
            host="localhost", port=3306, user="root", password="12345678", database="certificate_manager",
            charset="utf8mb4", collation="utf8mb4_unicode_ci"
        )
        cur = conn.cursor(dictionary=True)
        cur.callproc("sp_GetFullCertificateData", (student_id, "DEFAULT"))
        if hasattr(cur, "stored_results"):
            for result in cur.stored_results():
                datasets.append(result.fetchall())
        else:
            datasets.append(cur.fetchall())
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Online error: {e}")
        return {}

    return {
        "student_id": student_id,
        "grouping_mode": "DEFAULT",
        "settings": datasets[0][0] if (len(datasets) > 0 and datasets[0]) else {},
        "student_info": datasets[1][0] if (len(datasets) > 1 and datasets[1]) else {},
        "ranking": datasets[2][0] if (len(datasets) > 2 and datasets[2]) else {},
        "signers": datasets[3] if (len(datasets) > 3 and datasets[3]) else [],
        "academic_timeline": datasets[4] if (len(datasets) > 4 and datasets[4]) else [],
        "courses_grouped": datasets[5] if (len(datasets) > 5 and datasets[5]) else [],
    }

def get_offline_raw(student_id):
    return get_offline_certificate_data(student_id, "DEFAULT")

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
    students = [12, 2010]
    keys = ["settings", "student_info", "ranking", "signers", "academic_timeline", "courses_grouped"]
    
    for st_id in students:
        print(f"\nSTD ID {st_id}:")
        on_raw = get_online_raw(st_id)
        off_raw = get_offline_raw(st_id)
        
        on_norm = _normalize_raw_payload(on_raw, st_id, "DEFAULT")
        off_norm = _normalize_raw_payload(off_raw, st_id, "DEFAULT")
        
        for i, key in enumerate(keys, 1):
            sim = calculate_similarity(on_norm.get(key), off_norm.get(key))
            print(f"Grouping {i} ({key}): Offline and online result similarity is {sim:.1f}%.")

if __name__ == "__main__":
    main()
