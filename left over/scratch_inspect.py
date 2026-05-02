import sqlite3
import pprint
import sys
sys.path.append('.')
from data.queries import get_full_certificate_data

def test_student():
    data = get_full_certificate_data(124)
    print("Number of periods:", len(data['periods']))
    for p in data['periods']:
        print("Stage:", p['stage_number'], "Year:", p['academic_year'], "Enrollments:", len(p['enrollments']))

if __name__ == '__main__':
    test_student()
