import requests, json
r = requests.get('https://yingdao.redballoon.icu/yingdao/debug/fields', timeout=10)
data = r.json()
with open('_debug_fields.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
print('done')
