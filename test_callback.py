"""
本地模拟测试脚本
不真实调用飞书 API，只验证：
1. 日期解析是否正确
2. 状态映射是否正确
3. 数据模型解析是否正确
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.yingdao_service import (
    parse_datetime_to_ms,
    map_task_status,
    map_job_status,
    update_task_record,
    update_job_record,
    process_yingdao_callback,
)
from models import YDTaskCallback, YDAppCallback


def test_date_parsing():
    print("=" * 50)
    print("Test 1: Date Parsing")
    print("=" * 50)

    test_cases = [
        ("2026-04-10 14:00:00", 1744264800000),
        ("2026-04-13 10:30:00", None),
        (None, None),
        ("", None),
        (1744264800000, 1744264800000),
        (1744264800, 1744264800000),
    ]

    for value, expected in test_cases:
        try:
            result = parse_datetime_to_ms(value)
            if expected and result != expected:
                print(f"  [X] {value!r} -> {result} (expect {expected})")
            else:
                print(f"  [OK] {value!r} -> {result}")
        except Exception as e:
            print(f"  [X] {value!r} parse error: {e}")


def test_status_mapping():
    print("\n" + "=" * 50)
    print("Test 2: Status Mapping")
    print("=" * 50)

    task_tests = [
        ("running",  "任务运行中"),
        ("finish",   "任务运行结束"),
        ("error",    "异常"),
        ("created",  "等待调度"),
        ("waiting",  "等待调度"),
        ("stopped",  "已结束"),
        ("paused",   "任务正在停止"),
        ("unknown",  "unknown"),
    ]

    print("  Task table (资产状态):")
    for yd_status, expected in task_tests:
        result = map_task_status(yd_status)
        ok = "[OK]" if result == expected else "[X]"
        print(f"    {ok} {yd_status!r} -> {result!r}")

    print("\n  Job table (任务状态):")
    job_tests = ["created", "waiting", "running", "finish", "stopped", "error", "skipped", "cancel"]
    for status in job_tests:
        result = map_job_status(status)
        ok = "[OK]" if result == status else "[X]"
        print(f"    {ok} {status!r} -> {result!r}")


def test_pydantic_parsing():
    print("\n" + "=" * 50)
    print("Test 3: Pydantic Model Parsing")
    print("=" * 50)

    callback_json = {
        "taskUuid": "task-abc-12345",
        "taskStatus": "running",
        "startTime": "2026-04-13 09:00:00",
        "endTime": None,
        "jobList": [
            {
                "robotName": "数据采集机器人",
                "jobStatus": "running",
                "startTime": "2026-04-13 09:00:00",
                "endTime": None,
            },
            {
                "robotName": "数据清洗机器人",
                "jobStatus": "finish",
                "startTime": "2026-04-13 09:05:00",
                "endTime": "2026-04-13 09:10:00",
            },
        ],
    }

    try:
        model = YDTaskCallback(**callback_json)
        print(f"  [OK] Task UUID: {model.task_uuid}")
        print(f"  [OK] Task status: {model.task_status} -> {map_task_status(model.task_status)}")
        print(f"  [OK] Start time: {model.start_time} -> {parse_datetime_to_ms(model.start_time)}")
        print(f"  [OK] Job count: {len(model.job_list)}")
        for job in model.job_list:
            print(f"     - {job.robot_name} | {job.job_status} -> {map_job_status(job.job_status)}")
        print(f"\n  [OK] Legacy dict format:")
        legacy = model.to_legacy_dict()
        print(f"     {legacy}")
    except Exception as e:
        print(f"  [X] Parse failed: {e}")


def test_full_callback_flow():
    print("\n" + "=" * 50)
    print("Test 4: Full Callback Flow (requires Feishu API)")
    print("=" * 50)
    print("  This test requires real Feishu API calls.")
    print("  Use Step 4 (curl test) to verify end-to-end.")
    print()
    example = {
        "taskUuid": "task-test-001",
        "taskStatus": "finish",
        "startTime": "2026-04-13 09:00:00",
        "endTime": "2026-04-13 10:00:00",
        "jobList": [
            {
                "robotName": "数据采集机器人",
                "jobStatus": "finish",
                "startTime": "2026-04-13 09:00:00",
                "endTime": "2026-04-13 09:30:00",
            },
            {
                "robotName": "数据清洗机器人",
                "jobStatus": "finish",
                "startTime": "2026-04-13 09:30:00",
                "endTime": "2026-04-13 10:00:00",
            },
        ],
    }
    print(f"  Example callback_data:\n  {example}")


if __name__ == "__main__":
    print("影刀回调系统 - Local Simulation Test")
    print("=" * 50)
    print()
    test_date_parsing()
    test_status_mapping()
    test_pydantic_parsing()
    test_full_callback_flow()
    print("\n" + "=" * 50)
    print("Test complete")
