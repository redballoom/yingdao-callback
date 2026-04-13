"""
本地调试入口（非部署文件）
用法：python app.py
然后 curl 测试：
  curl -X POST http://localhost:8000/yingdao/update ^
    -H "Content-Type: application/json" ^
    -d "{\"taskUuid\":\"test-001\",\"taskStatus\":\"running\",\"startTime\":\"2026-04-13 09:00:00\",\"endTime\":null,\"jobList\":[{\"robotName\":\"数据采集机器人\",\"jobStatus\":\"running\",\"startTime\":\"2026-04-13 09:00:00\",\"endTime\":null}]}"
"""

import uvicorn
from api.index import app

if __name__ == "__main__":
    print("影刀回调服务 - 本地调试")
    print("=" * 50)
    print("健康检查: http://localhost:8000/yingdao/health")
    print("任务回调: POST http://localhost:8000/yingdao/callback/task")
    print("应用回调: POST http://localhost:8000/yingdao/callback/app")
    print("手动更新: POST http://localhost:8000/yingdao/update")
    print("=" * 50)
    uvicorn.run(app, host="0.0.0.0", port=8000)
