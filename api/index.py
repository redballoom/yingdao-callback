"""
影刀 RPA 回调接收服务
FastAPI 应用 — 部署于 Vercel

回调地址：https://blog.redballoon.icu/yingdao/callback/
"""

import sys
import os
import logging
from typing import Optional

# 确保项目根目录在 import 路径中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, Request, HTTPException
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
    影刀任务运行回调
    触发时机：整个任务状态变化时推送

    请求体示例：
    {
        "taskUuid": "abc-123",
        "taskStatus": "running",
        "startTime": "2026-04-10 14:00:00",
        "endTime": null,
        "jobList": [
            {
                "robotName": "数据采集机器人",
                "jobStatus": "running",
                "startTime": "2026-04-10 14:00:00",
                "endTime": null
            }
        ]
    }
    """
    try:
        body = await request.json()
        logger.info(f"[TASK Callback] taskUuid={body.get('taskUuid')}, status={body.get('taskStatus')}")

        # 解析并处理回调
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

    请求体示例：
    {
        "jobUuid": "job-456",
        "robotName": "数据采集机器人",
        "jobStatus": "finish",
        "startTime": "2026-04-10 14:00:00",
        "endTime": "2026-04-10 14:30:00",
        "result": {"output_key": "output_value"}
    }
    """
    try:
        body = await request.json()
        robot_name = body.get("robotName", "")
        job_status = body.get("jobStatus", "")
        start_time = body.get("startTime")
        end_time = body.get("endTime")

        logger.info(f"[APP Callback] robotName={robot_name}, status={job_status}")

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
