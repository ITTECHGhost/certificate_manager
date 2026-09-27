import os
import sys
import requests
import json

# Setup path
workspace_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, workspace_dir)

from api_config import API_URL
from data.query import get_offline_certificate_data

STUDENT_IDS = [12, 2010]
GROUPING_MODES = ["DEFAULT", "BY_PERIOD_STAGE", "BY_CURRICULUM_STAGE", "BY_YEAR"]

def get_leaves(d, prefix=""):
    leaves = {}
    if isinstance(d, dict):
        for k, v in d.items():
            leaves.update(get_leaves(v, f"{prefix}.{k}"))
    elif isinstance(d, list):
        for i, v in enumerate(d):
            leaves.update(get_leaves(v, f"{prefix}[{i}]"))
    else:
        leaves[prefix] = d
    return leaves

def compare_dicts(d1, d2):
    l1 = get_leaves(d1)
    l2 = get_leaves(d2)
    
    if not l1 and not l2:
        return 100.0
    if not l1:
        return 0.0
        
    matches = 0
    mismatches = []
    for k, v in l1.items():
        if k in l2:
            # loose comparison for str vs int
            if str(l2[k]) == str(v):
                matches += 1
            elif v is None and l2[k] == "": # common db vs api mismatch
                matches += 1
            elif v == "" and l2[k] is None:
                matches += 1
            else:
                mismatches.append(f"{k}: online='{v}' != offline='{l2[k]}'")
        else:
            mismatches.append(f"{k}: missing in offline")
            
    return (matches / len(l1)) * 100, mismatches

for st_id in STUDENT_IDS:
    print(f"for STD ID {st_id}:")
    for mode in GROUPING_MODES:
        # online
        online_data = {}
        try:
            url = f"{API_URL}/certificates/{st_id}?grouping_mode={mode}"
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                online_data = resp.json()
            else:
                print(f"  Grouping {mode} : Failed to get online data, HTTP {resp.status_code}")
                continue
        except Exception as e:
            print(f"  Grouping {mode} : Online request failed: {e}")
            continue
            
        # offline
        offline_data = {}
        try:
            offline_data = get_offline_certificate_data(st_id, mode)
        except Exception as e:
            print(f"  Grouping {mode} : Offline request failed: {e}")
            continue
            
        # normalize online vs offline
        from cert_repository import _normalize_raw_payload
        online_norm = _normalize_raw_payload(online_data, st_id, mode)
        offline_norm = _normalize_raw_payload(offline_data, st_id, mode)
        
        # compare
        comp, mismatches = compare_dicts(online_norm, offline_norm)
        print(f"Grouping {mode} : Offline and Online compatibility is {comp:.2f}%.")
        if comp < 100.0:
            # show a few mismatches to help debug
            print(f"    Sample mismatches:")
            for m in mismatches[:5]:
                print(f"      {m}")
    print("")
