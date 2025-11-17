import requests
import json

# HTTP로 (HTTPS 아님!)
url = 'http://api.data.go.kr/openapi/tn_pubr_public_nutri_info_api'

service_key = 'ba3c5e17002f3a476792cc25414bc972865b5360a19bfc9d1d5bdcda8038ada7'

params = {
    'serviceKey': service_key,
    'pageNo': '1',
    'numOfRows': '10',
    'type': 'json'
}

print(f"요청 URL: {url}")

try:
    response = requests.get(url, params=params)
    print(f"상태코드: {response.status_code}")
    
    if response.status_code == 200:
        print("\n응답:")
        print(json.dumps(response.json(), indent=2, ensure_ascii=False))
    else:
        print(f"응답: {response.text}")
except Exception as e:
    print(f"에러: {e}")