"""
影刀 RPA 回调接收服务
FastAPI 应用 — 部署于 Vercel

回调地址：https://blog.redballoon.icu/yingdao/callback/
"""

import sys
import os
import logging
import time
from collections import deque
from typing import Optional

# -----------------------------------------------
# 回调日志（最多保留50条）
# -----------------------------------------------
_callback_log = deque(maxlen=50)  # 线程安全，限制最大50条

# 确保项目根目录在 import 路径中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, Request, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# 业务逻辑
import config
from services.yingdao_service import (
    process_yingdao_callback,
    update_task_record,
    update_job_record,
    map_task_status,
    map_job_status,
)
from models import YDTaskCallback, CallbackResponse

# -----------------------------------------------
# 日志配置
# -----------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


# -----------------------------------------------
# FastAPI 应用
# -----------------------------------------------
app = FastAPI(
    title="影刀 RPA 回调服务",
    version="1.0.0",
    description="接收影刀回调，自动更新飞书多维表格状态",
)

# 允许跨域（影刀服务器推送可能来自不同域）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -----------------------------------------------
# 查看回调日志（调试用）
# -----------------------------------------------
@app.get("/yingdao/logs")
async def get_callback_logs(limit: int = Query(20, ge=1, le=50)):
    """
    查看最近收到的影刀回调原始数据
    用法：GET /yingdao/logs 或 /yingdao/logs?limit=10
    """
    logs = list(_callback_log)
    logs.reverse()  # 最新的在前
    return {
        "total": len(logs),
        "logs": logs[:limit],
    }


# -----------------------------------------------
# 健康检查
# -----------------------------------------------
@app.get("/yingdao/health")
async def health_check():
    """健康检查接口，Vercel 部署验证用"""
    return {"status": "ok", "service": "yingdao-callback"}


# -----------------------------------------------
# 任务回调接口（影刀推送）
# -----------------------------------------------
@app.post("/yingdao/callback/task", response_model=CallbackResponse)
async def callback_task(request: Request):
    """
    影刀回调接收（兼容两种格式）

    格式一：任务级回调（dataType=task）
    {
        "dataType": "task",
        "taskUuid": "ea947f83-82fb-4afb-8412-4021255fd7cd",
        "status": "finish",
        "startTime": 1642837962000,
        "endTime": 1642837962000,
        "jobList": [
            {"robotName": "导出淘宝订单", "status": "finish",
             "startTime": "2021-02-03 11:11:11", "endTime": "2021-03-03 12:12:12"}
        ]
    }

    格式二：单应用回调（dataType=job，Postman 模拟格式）
    {
        "dataType": "job",
        "jobUuid": "42c2e0ce-499b-47aa-8642-3a1125b4759a",
        "status": "finish",
        "robotClientName": "ceshi1@csqy1",
        "robotName": "导出淘宝订单",
        "startTime": "2021-02-03 11:11:11",
        "endTime": "2021-03-03 12:12:12"
    }
    """
    try:
        body = await request.json()

        # 记录原始回调数据
        _callback_log.append({
            "time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "endpoint": "/yingdao/callback/task",
            "data": body,
        })

        data_type = body.get("dataType", "")
        task_uuid = body.get("taskUuid")

        logger.info(f"[TASK Callback] dataType={data_type}, taskUuid={task_uuid}, keys={list(body.keys())}")

        # 格式二：单应用回调（dataType=job），没有 taskUuid
        # 透传给 callback_app 处理逻辑
        if data_type == "job" or not task_uuid:
            robot_name = body.get("robotName", "")
            # 真实回调用 robotClientName 代替 robotName
            if not robot_name:
                robot_name = body.get("robotClientName", "")
            job_status = body.get("status") or body.get("jobStatus")
            start_time = body.get("startTime")
            end_time = body.get("endTime")
            job_uuid = body.get("jobUuid", "")

            result = update_job_record(
                robot_name=robot_name,
                status=job_status,
                start_time=start_time,
                end_time=end_time,
                job_uuid=job_uuid,
            )

            logger.info(f"[TASK Callback] 单应用回调处理: {result}")
            return CallbackResponse(
                success=result.get("success", False),
                message="单应用回调处理成功",
                detail={"jobs": [result]},
            )

        # 格式一：任务级回调（dataType=task）
        task_status = body.get("status") or body.get("taskStatus")
        logger.info(f"[TASK Callback] 任务回调: taskUuid={task_uuid}, status={task_status}")

        result = process_yingdao_callback(body)

        logger.info(f"[TASK Callback] 处理完成: {result}")

        return CallbackResponse(
            success=True,
            message="Task 回调处理成功",
            detail=result,
        )

    except Exception as e:
        logger.error(f"[TASK Callback] 处理失败: {e}")
        return CallbackResponse(
            success=False,
            message=f"处理失败: {str(e)}",
        )


# -----------------------------------------------
# 应用回调接口（单个应用节点）
# -----------------------------------------------
@app.post("/yingdao/callback/app", response_model=CallbackResponse)
async def callback_app(request: Request):
    """
    影刀应用节点回调
    触发时机：每个应用节点开始/结束时推送

    影刀实际请求体格式：
    {
        "dataType": "job",
        "jobUuid": "6de893bb-8224-4f60-9bff-b8597b8ed8fc",
        "robotName": "导出淘宝订单",  // 应用名称
        "status": "finish",           // ← 影刀用 status
        "startTime": "2021-02-03 11:11:11",
        "endTime": "2021-03-03 12:12:12"
    }
    """
    try:
        body = await request.json()
        # 影刀实际字段名是 status，不是 jobStatus
        robot_name = body.get("robotName", "")
        job_status = body.get("status") or body.get("jobStatus")
        start_time = body.get("startTime")
        end_time = body.get("endTime")

        logger.info(f"[APP Callback] robotName={robot_name}, status={job_status}")

        # 记录原始回调数据
        _callback_log.append({
            "time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "endpoint": "/yingdao/callback/app",
            "data": body,
        })

        # 只更新 Job 表（按应用名称取最新）
        result = update_job_record(
            robot_name=robot_name,
            status=job_status,
            start_time=start_time,
            end_time=end_time,
        )

        logger.info(f"[APP Callback] 处理完成: {result}")

        return CallbackResponse(
            success=result.get("success", False),
            message=result.get("message", ""),
            detail=result,
        )

    except Exception as e:
        logger.error(f"[APP Callback] 处理失败: {e}")
        return CallbackResponse(
            success=False,
            message=f"处理失败: {str(e)}",
        )


# -----------------------------------------------
# 调试接口（查看字段和搜索结果）
# -----------------------------------------------
@app.get("/yingdao/debug/fields")
async def debug_fields():
    """
    调试接口：列出两个表的字段信息，帮助排查字段名不匹配问题
    """
    try:
        from services.bitable_sdk import BitableSDK

        task_sdk = BitableSDK(
            config.APP_ID,
            config.APP_SECRET,
            config.TASK_APP_TOKEN,
            config.TASK_TABLE_ID,
        )
        job_sdk = BitableSDK(
            config.APP_ID,
            config.APP_SECRET,
            config.JOB_APP_TOKEN,
            config.JOB_TABLE_ID,
        )

        # 获取字段列表
        task_fields = task_sdk.list_fields()
        job_fields = job_sdk.list_fields()

        return {
            "success": True,
            "task_table": {
                "app_token": config.TASK_APP_TOKEN,
                "table_id": config.TASK_TABLE_ID,
                "fields": task_fields,
            },
            "job_table": {
                "app_token": config.JOB_APP_TOKEN,
                "table_id": config.JOB_TABLE_ID,
                "fields": job_fields,
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/yingdao/debug/search")
async def debug_search_get(
    table: str = "",
    field: str = "",
    value: str = "",
):
    """
    调试接口（GET 版本）：搜索指定表的记录
    用法：/yingdao/debug/search?table=task&field=taskUUID&value=xxx
    """
    return await _do_debug_search({"table": table, "field": field, "value": value})


async def _do_debug_search(body: dict) -> dict:
    """搜索指定表的记录，通用实现"""
    try:
        table_type = body.get("table", "task")
        field_name = body.get("field", "")
        field_value = body.get("value", "")

        from services.bitable_sdk import BitableSDK, create_filter

        if table_type == "task":
            sdk = BitableSDK(
                config.APP_ID,
                config.APP_SECRET,
                config.TASK_APP_TOKEN,
                config.TASK_TABLE_ID,
            )
        else:
            sdk = BitableSDK(
                config.APP_ID,
                config.APP_SECRET,
                config.JOB_APP_TOKEN,
                config.JOB_TABLE_ID,
            )

        records = sdk.search_records(
            filter=create_filter(field_name, "is", field_value),
        )

        return {
            "success": True,
            "table": table_type,
            "search_field": field_name,
            "search_value": field_value,
            "found_count": len(records),
            "records": records[:5],  # 只返回前5条
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.post("/yingdao/debug/search")
async def debug_search(request: Request):
    """
    调试接口（POST 版本）：搜索指定表的记录
    Body: {"table": "task"|"job", "field": "字段名", "value": "搜索值"}
    """
    return await _do_debug_search(await request.json())


# -----------------------------------------------
# 诊断 Job 搜索问题（直接暴露 search_records 的原始返回）
# -----------------------------------------------
@app.get("/yingdao/debug/search-raw")
async def debug_search_raw(
    table: str = Query(..., description="task 或 job"),
    field: str = Query(..., description="字段名"),
    value: str = Query(..., description="字段值"),
):
    """
    直接调用 sdk.search_records，返回原始返回结果（不经过 force-update 逻辑）
    用于诊断搜索为什么返回 0 条记录
    """
    try:
        if table == "job":
            sdk = _get_job_sdk()
            raw_filter = create_filter(field, "is", value)
            records = sdk.search_records(filter=raw_filter)
            # 打印传给 API 的原始 filter 结构
            return {
                "table": table,
                "sdk_filter": raw_filter,
                "found_count": len(records),
                "records": [
                    {
                        "record_id": r.get("record_id"),
                        "fields": {k: v for k, v in r.get("fields", {}).items() if k in [field, "任务状态"]},
                    }
                    for r in records
                ],
            }
        else:
            return {"error": "只支持 job 表"}
    except Exception as e:
        import traceback
        return {"error": str(e), "trace": traceback.format_exc()}


# -----------------------------------------------
# 强制更新接口（直接指定 record_id 强制更新，用于排除搜索问题）
# -----------------------------------------------
@app.post("/yingdao/force-update-job")
async def force_update_job(request: Request):
    """
    强制更新 Job 表的指定记录（不搜索，直接用 record_id）
    Body: {"record_id": "xxx", "status": "finish", "start_time": "2026-04-13 12:00:00", "end_time": "2026-04-13 12:30:00"}
    """
    try:
        body = await request.json()
        record_id = body.get("record_id")
        status = body.get("status", "")
        start_time = body.get("start_time")
        end_time = body.get("end_time")

        from services.bitable_sdk import BitableSDK
        sdk = BitableSDK(
            config.APP_ID,
            config.APP_SECRET,
            config.JOB_APP_TOKEN,
            config.JOB_TABLE_ID,
        )

        fields = {"任务状态": status}
        if start_time:
            fields[config.JOB_FIELD_START_TIME] = str(start_time)
        if end_time:
            fields[config.JOB_FIELD_END_TIME] = str(end_time)

        result = sdk.update_record(record_id, fields)

        return {"success": True, "record_id": record_id, "fields": fields, "result": result}
    except Exception as e:
        return {"success": False, "error": str(e)}


# -----------------------------------------------
# 手动触发更新（供调试/测试用）
# -----------------------------------------------
@app.post("/yingdao/update", response_model=CallbackResponse)
async def manual_update(request: Request):
    """
    手动触发更新（不依赖影刀推送，用于调试）
    接收与回调相同的 JSON 格式
    """
    try:
        body = await request.json()
        logger.info(f"[Manual Update] 收到请求: {body}")

        result = process_yingdao_callback(body)

        return CallbackResponse(
            success=True,
            message="手动更新完成",
            detail=result,
        )

    except Exception as e:
        logger.error(f"[Manual Update] 失败: {e}")
        return CallbackResponse(
            success=False,
            message=f"失败: {str(e)}",
        )


# -----------------------------------------------
# 本地调试入口（直接运行 python app.py 时使用）
# -----------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
