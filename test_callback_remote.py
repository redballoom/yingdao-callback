"""
影刀回调接口远程测试脚本
不需要本地运行 FastAPI，直接请求部署在 Vercel 上的接口

用法：双击运行此脚本
"""

import urllib.request
import urllib.error
import json
import sys

# 部署后的回调地址
BASE_URL = "https://yingdao.redballoon.icu/yingdao"

# ============================================================
# 测试 1：健康检查
# ============================================================
def test_health():
    print("\n" + "=" * 50)
    print("测试 1：健康检查")
    print("=" * 50)
    url = f"{BASE_URL}/health"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            body = resp.read().decode("utf-8")
            print(f"✅ HTTP {resp.status}")
            print(f"响应: {body}")
            return True
    except Exception as e:
        print(f"❌ 失败: {e}")
        return False


# ============================================================
# 测试 2：Task 回调（模拟影刀推送）
# ============================================================
def test_task_callback():
    print("\n" + "=" * 50)
    print("测试 2：Task 回调（模拟任务运行中）")
    print("=" * 50)

    payload = {
        "taskUuid": "test-task-20260413-001",
        "taskStatus": "running",
        "startTime": "2026-04-13 12:00:00",
        "endTime": None,
        "jobList": [
            {
                "robotName": "数据采集机器人",
                "jobStatus": "running",
                "startTime": "2026-04-13 12:00:00",
                "endTime": None
            },
            {
                "robotName": "数据清洗机器人",
                "jobStatus": "waiting",
                "startTime": None,
                "endTime": None
            }
        ]
    }

    url = f"{BASE_URL}/callback/task"
    data = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read().decode("utf-8")
            result = json.loads(body)
            print(f"✅ HTTP {resp.status}")
            print(f"成功: {result.get('success')}")
            print(f"消息: {result.get('message')}")
            if result.get("detail"):
                print(f"详情: {result.get('detail')}")
            return result.get("success", False)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        print(f"❌ HTTP {e.code}: {body}")
        return False
    except Exception as e:
        print(f"❌ 失败: {e}")
        return False


# ============================================================
# 测试 3：模拟任务结束回调
# ============================================================
def test_task_finish():
    print("\n" + "=" * 50)
    print("测试 3：Task 回调（模拟任务结束）")
    print("=" * 50)

    payload = {
        "taskUuid": "test-task-20260413-001",
        "taskStatus": "finish",
        "startTime": "2026-04-13 12:00:00",
        "endTime": "2026-04-13 12:30:00",
        "jobList": [
            {
                "robotName": "数据采集机器人",
                "jobStatus": "finish",
                "startTime": "2026-04-13 12:00:00",
                "endTime": "2026-04-13 12:15:00"
            },
            {
                "robotName": "数据清洗机器人",
                "jobStatus": "finish",
                "startTime": "2026-04-13 12:15:00",
                "endTime": "2026-04-13 12:30:00"
            }
        ]
    }

    url = f"{BASE_URL}/callback/task"
    data = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read().decode("utf-8")
            result = json.loads(body)
            print(f"✅ HTTP {resp.status}")
            print(f"成功: {result.get('success')}")
            print(f"消息: {result.get('message')}")
            if result.get("detail"):
                print(f"详情: {result.get('detail')}")
            return result.get("success", False)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        print(f"❌ HTTP {e.code}: {body}")
        return False
    except Exception as e:
        print(f"❌ 失败: {e}")
        return False


# ============================================================
# 测试 4：手动更新（不依赖影刀，直接更新飞书）
# ============================================================
def test_manual_update():
    print("\n" + "=" * 50)
    print("测试 4：手动更新接口")
    print("=" * 50)

    payload = {
        "taskUuid": "test-task-20260413-001",
        "taskStatus": "error",
        "startTime": "2026-04-13 12:00:00",
        "endTime": "2026-04-13 12:05:00",
        "jobList": [
            {
                "robotName": "数据采集机器人",
                "jobStatus": "error",
                "startTime": "2026-04-13 12:00:00",
                "endTime": "2026-04-13 12:05:00"
            }
        ]
    }

    url = f"{BASE_URL}/update"
    data = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read().decode("utf-8")
            result = json.loads(body)
            print(f"✅ HTTP {resp.status}")
            print(f"成功: {result.get('success')}")
            print(f"消息: {result.get('message')}")
            if result.get("detail"):
                print(f"详情: {result.get('detail')}")
            return result.get("success", False)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        print(f"❌ HTTP {e.code}: {body}")
        return False
    except Exception as e:
        print(f"❌ 失败: {e}")
        return False


# ============================================================
# 主入口
# ============================================================
if __name__ == "__main__":
    print("🚀 影刀回调服务测试")
    print(f"目标地址: https://yingdao.redballoon.icu")
    print(f"回调地址: https://yingdao.redballoon.icu/yingdao/callback/task")
    print()

    results = []
    results.append(("健康检查", test_health()))
    results.append(("Task 回调（运行中）", test_task_callback()))
    results.append(("Task 回调（结束）", test_task_finish()))
    results.append(("手动更新", test_manual_update()))

    print("\n" + "=" * 50)
    print("测试结果汇总")
    print("=" * 50)
    all_passed = True
    for name, passed in results:
        icon = "✅" if passed else "❌"
        print(f"{icon} {name}")
        if not passed:
            all_passed = False

    print()
    if all_passed:
        print("🎉 全部测试通过！回调服务运行正常。")
    else:
        print("⚠️  有测试失败，请检查上面的错误信息。")

    sys.exit(0 if all_passed else 1)
