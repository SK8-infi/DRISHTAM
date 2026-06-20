import urllib.request
import json

req = urllib.request.Request(
    'http://127.0.0.1:8000/api/optimize/station',
    data=json.dumps({"n_officers": 49, "custom_allocation": {"Upparpet": 10, "Shivajinagar": 20, "Malleshwaram": 8, "HAL Old Airport": 6, "City Market": 5}}).encode('utf-8'),
    headers={'Content-Type': 'application/json'}
)

try:
    response = urllib.request.urlopen(req)
    print(response.read().decode('utf-8')[:500])
except Exception as e:
    print("Error:", e)
    if hasattr(e, 'read'):
        print(e.read().decode('utf-8'))
