import requests, json
from datetime import datetime, timezone

r = requests.get(
    'https://yingdao.redballoon.icu/yingdao/debug/search',
    params={'table': 'task', 'field': 'taskUUID', 'value': 'f5c6f5c0-128f-4de9-b2f2-f9405ef71289'},
    timeout=10
)
data = r.json()
with open('_check_result.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
print('done')
