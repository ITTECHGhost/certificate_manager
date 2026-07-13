# test_dashboard.py
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.repositories import DashboardRepository

repo = DashboardRepository()
counts = repo.get_counts()

print("Dashboard Counts:", counts)