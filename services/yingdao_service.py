"""
影刀 RPA 回调 → 飞书多维表格更新服务

职责：
- Task 表更新（按 taskUUID 精确匹配）
- Job 表更新（按应用名称搜索，取「创建时间」最新的一条记录）
- 日期格式转换（yyyy-MM-dd HH:mm:ss → 毫秒时间戳）
"""

from datetime import datetime
from typing import Optional, List
from .bitable_sdk import BitableSDK, create_filter
import config


# ============================================================
# 日期工具
# ============================================================

def parse_datetime_to_ms(dt_value: Optional[str | int | float]) -> Optional[int]:
    """
    将各种格式的时间值转换为飞书所需的毫秒时间戳。

    支持的输入格式：
    - "2026-04-10 14:00:00"       → 整数毫秒时间戳
    - "2026-04-10T14:00:00Z"      → ISO 格式
    - 1744274400000               → 已是时间戳，原样返回
    - None / "" / 0               → 返回 None（不上传）
    """
    if dt_value is None:
        return None
    if isinstance(dt_value, (int, float)) and dt_value > 0:
        # 已经是时间戳（可能是秒或毫秒）
        if dt_value < 10**12:  # 秒级时间戳
            return int(dt_value * 1000)
        return int(dt_value)
    if isinstance(dt_value, str) and dt_value.strip() == "":
        return None

    # 尝试解析字符串格式
    dt_str = str(dt_value).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S.%fZ", "%Y/%m/%d %H:%M:%S"):
        try:
            dt = datetime.strptime(dt_str, fmt)
            return int(dt.timestamp() * 1000)
        except ValueError:
            pass

    raise ValueError(f"无法解析时间值: {dt_value}")


# ============================================================
# 状态值映射（需与飞书单选选项名称一致）
# ============================================================

# 影刀 taskStatus → 飞书 Task 表「资产状态」选项名
# 注意：必须与飞书表格里的单选选项名称完全一致（包括 emoji）
TASK_STATUS_MAP = {
    "created":   "🟢 空闲",
    "waiting":   "🟢 空闲",
    "running":   "🔵 运行中",
    "paused":    "🔵 运行中",
    "finish":    "任务运行结束",
    "stopped":   "🟢 空闲",
    "error":     "🔴 故障/离线",
}

# 影刀 jobStatus → 飞书 Job 表「任务状态」选项名
# Job 表直接存影刀状态码，无需映射
JOB_STATUS_MAP = {}  # 不做转换，直接用影刀原始状态码


def map_task_status(yingdao_status: str) -> str:
    """影刀 taskStatus → 飞书 Task 表状态显示名"""
    return TASK_STATUS_MAP.get(yingdao_status, yingdao_status)


def map_job_status(yingdao_status: str) -> str:
    """影刀 jobStatus → 直接返回原始状态码（Job表存的是状态码本身）"""
    return yingdao_status


# ============================================================
# SDK 实例（延迟创建，避免模块加载时发起请求）
# ============================================================

def _get_task_sdk() -> BitableSDK:
    return BitableSDK(
        config.APP_ID,
        config.APP_SECRET,
        config.TASK_APP_TOKEN,
        config.TASK_TABLE_ID,
    )


def _get_job_sdk() -> BitableSDK:
    return BitableSDK(
        config.APP_ID,
        config.APP_SECRET,
        config.JOB_APP_TOKEN,
        config.JOB_TABLE_ID,
    )


# ============================================================
# Task 表更新
# ============================================================

def update_task_record(
    task_uuid: str,
    status: str,
    start_time: Optional[str | int | float] = None,
    end_time: Optional[str | int | float] = None,
) -> dict:
    """
    在 Task 表中查找 taskUUID 对应的记录，更新执行状态和时间。

    参数：
        task_uuid  — 影刀回调中的 taskUuid（精确匹配 TASK_FIELD_TASK_UUID 字段）
        status     — 影刀回调中的 taskStatus（如 "running", "finish"）
        start_time — 任务开始时间（支持字符串或时间戳）
        end_time   — 任务结束时间（支持字符串或时间戳）

    返回：
        dict，key "success"=bool，"updated"=更新记录数，"message"=说明
    """
    sdk = _get_task_sdk()

    # 按 taskUUID 精确匹配搜索
    records = sdk.search_records(
        filter=create_filter(config.TASK_FIELD_TASK_UUID, "is", task_uuid),
    )

    if not records:
        return {
            "success": False,
            "updated": 0,
            "message": f"Task 表中未找到 taskUUID={task_uuid} 的记录",
        }

    # 构建更新字段
    fields = {"资产状态": map_task_status(status)}
    if start_time is not None:
        ts = parse_datetime_to_ms(start_time)
        if ts:
            fields[config.TASK_FIELD_START_TIME] = ts
    if end_time is not None:
        ts = parse_datetime_to_ms(end_time)
        if ts:
            fields[config.TASK_FIELD_END_TIME] = ts

    # 更新所有匹配记录（通常应为 1 条）
    updated_count = 0
    for record in records:
        sdk.update_record(record["record_id"], fields)
        updated_count += 1

    return {
        "success": True,
        "updated": updated_count,
        "message": f"Task 表更新成功，共 {updated_count} 条记录",
    }


# ============================================================
# Job 表更新（取最新一条）
# ============================================================

def update_job_record(
    robot_name: str,
    status: str,
    start_time: Optional[str | int | float] = None,
    end_time: Optional[str | int | float] = None,
) -> dict:
    """
    在 Job 表中查找「当前执行应用名称 = robot_name」的记录，
    按「创建时间」倒序取最新一条，更新执行状态和时间。

    注意：Job 表的时间字段是 Text 类型，直接传字符串，不需要转时间戳！

    参数：
        robot_name — 应用名称（精确匹配 JOB_FIELD_ROBOT_NAME 字段）
        status     — 影刀回调中的 jobStatus（如 "running", "finish"）
        start_time — 应用开始时间（字符串格式，如 "2026-04-13 12:00:00"）
        end_time   — 应用结束时间（字符串格式）

    返回：
        dict，key "success"=bool，"updated"=bool，"record_id"=被更新的记录ID
    """
    sdk = _get_job_sdk()

    # 按应用名称精确匹配搜索（完全一致）
    records = sdk.search_records(
        filter=create_filter(config.JOB_FIELD_ROBOT_NAME, "is", robot_name),
    )

    if not records:
        return {
            "success": False,
            "updated": False,
            "record_id": None,
            "message": f"Job 表中未找到应用名称={robot_name} 的记录",
        }

    # 按记录 ID 倒序（ID 越大创建时间越新，近似取最新）
    # 注：飞书 Bitable record_id 是有序递增字符串
    records_sorted = sorted(records, key=lambda r: r["record_id"], reverse=True)
    target_record = records_sorted[0]

    # 构建更新字段
    # Job 表的时间字段是 Text 类型，直接传字符串
    fields = {"任务状态": map_job_status(status)}
    if start_time is not None:
        # 直接传字符串，不转时间戳
        fields[config.JOB_FIELD_START_TIME] = str(start_time)
    if end_time is not None:
        fields[config.JOB_FIELD_END_TIME] = str(end_time)

    sdk.update_record(target_record["record_id"], fields)

    return {
        "success": True,
        "updated": True,
        "record_id": target_record["record_id"],
        "message": f"Job 表记录 {target_record['record_id']} 更新成功",
    }


# ============================================================
# 批量处理回调（从影刀回调主入口调用）
# ============================================================

def process_yingdao_callback(callback_data: dict) -> dict:
    """
    处理影刀任务运行回调的主函数。

    影刀回调格式示例：
    {
        "taskUuid": "abc-123",
        "taskStatus": "running",
        "startTime": "2026-04-10 14:00:00",
        "endTime": null,
        "jobList": [
            {
                "robotName": "应用A",
                "jobStatus": "running",
                "startTime": "2026-04-10 14:00:00",
                "endTime": null
            },
            ...
        ]
    }

    处理逻辑：
    1. 更新 Task 表（按 taskUuid）
    2. 遍历 jobList，逐个更新 Job 表（按 robotName，取最新记录）

    返回：
        处理结果摘要 dict
    """
    task_uuid = callback_data.get("taskUuid", "")
    task_status = callback_data.get("taskStatus", "")
    task_start = callback_data.get("startTime")
    task_end = callback_data.get("endTime")
    job_list: List[dict] = callback_data.get("jobList", [])

    # Step 1: 更新 Task 表
    task_result = update_task_record(task_uuid, task_status, task_start, task_end)

    # Step 2: 更新 Job 表（每个应用一条）
    job_results = []
    for job in job_list:
        result = update_job_record(
            robot_name=job.get("robotName", ""),
            status=job.get("jobStatus", ""),
            start_time=job.get("startTime"),
            end_time=job.get("endTime"),
        )
        job_results.append({
            "robotName": job.get("robotName"),
            **result,
        })

    return {
        "task": task_result,
        "jobs": job_results,
    }
