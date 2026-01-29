"""Test TechStack API Endpoint"""

import requests
import json

BASE_URL = "http://localhost:8087"

def test_templates():
    try:
        response = requests.get(f"{BASE_URL}/api/v1/techstack/templates", timeout=5)
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"Templates Count: {data.get('count', 0)}")
            for t in data.get('templates', [])[:3]:
                print(f"  - {t.get('id')}: {t.get('name')}")
        else:
            print(f"Error: {response.text}")
    except requests.exceptions.ConnectionError as e:
        print(f"Connection Error: Server not running on {BASE_URL}")
    except Exception as e:
        print(f"Error: {e}")

def test_categories():
    try:
        response = requests.get(f"{BASE_URL}/api/v1/techstack/categories", timeout=5)
        print(f"\nCategories Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"Categories: {data.get('categories', [])}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    print("Testing TechStack API...")
    test_templates()
    test_categories()