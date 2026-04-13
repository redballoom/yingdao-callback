"""
Pydantic 数据模型 — 影刀回调请求体 + 内部处理结果
"""

from typing import Optional, List, Any
from pydantic import BaseModel, Field


# ============================================================
# Task 任务回调（整体任务级别的回调）
# ============================================================

class YDJobResult(BaseModel):
    """jobList[].result 中的单个输出参数"""
    name: str = Field(..., description="参数名称")
    value: Optional[Any] = Field(None, description="参数值（类型任意：str/number/dict/list 等）")
    type: Optional[str] = Field(None, alias="type", description="参数类型 (str/file/number 等）")

    class Config:
        populate_by_name = True


class YDJobItem(BaseModel):
    """jobList 中的单个应用执行记录（task 回调的子应用节点）"""
    data_type: Optional[str] = Field(None, alias="dataType", description="数据类型，固定为 'job'")
    job_uuid: Optional[str] = Field(None, alias="jobUuid", description="Job 唯一标识")
    robot_client_uuid: Optional[str] = Field(None, alias="robotClientUuid", description="机器人客户端UUID")
    robot_client_name: Optional[str] = Field(None, alias="robotClientName", description="机器人客户端名称")
    robot_name: str = Field(..., alias="robotName", description="应用名称")
    robot_uuid: Optional[str] = Field(None, alias="robotUuid", description="应用UUID")
    status: Optional[str] = Field(None, alias="status", description="应用执行状态")
    start_time: Optional[str | int] = Field(None, alias="startTime", description="开始时间（字符串 yyyy-MM-dd HH:mm:ss 或毫秒时间戳）")
    end_time: Optional[str | int] = Field(None, alias="endTime", description="结束时间（字符串 yyyy-MM-dd HH:mm:ss 或毫秒时间戳）")
    msg: Optional[str] = Field(None, alias="msg", description="备注信息")
    idempotent_uuid: Optional[str] = Field(None, alias="idempotentUuid", description="幂等ID")
    screenshot_url: Optional[str] = Field(None, alias="screenshotUrl", description="异常截屏URL")
    result: Optional[List[YDJobResult]] = Field(None, alias="result", description="输出参数列表")

    class Config:
        populate_by_name = True


class YDTaskCallback(BaseModel):
    """
    影刀任务运行回调（整体任务级别，影刀实际回调格式）

    触发时机：整个任务状态变化时推送
    回调地址：https://yingdao.redballoon.icu/yingdao/callback/task

    实际回调格式：
    {
        "dataType": "task",
        "taskUuid": "ea947f83-82fb-4afb-8412-4021255fd7cd",
        "status": "finish",            // ← 影刀用 status 字段
        "startTime": 1744274400000,    // 毫秒时间戳（数字），可为空
        "endTime": 1744278000000,
        "jobList": [
            {"robotName": "xxx", "status": "finish",
             "startTime": "2021-02-03 11:11:11", "endTime": "..."}
        ]
    }
    """
    data_type: Optional[str] = Field(None, alias="dataType", description="数据类型，固定为 'task'")
    task_uuid: Optional[str] = Field(None, alias="taskUuid", description="任务唯一标识（对应 Task 表 taskUUID 字段）")
    status: Optional[str] = Field(None, alias="status", description="任务状态 created/waiting/running/finish/error/stopped")
    start_time: Optional[str | int] = Field(None, alias="startTime", description="任务开始时间（毫秒时间戳或字符串）")
    end_time: Optional[str | int] = Field(None, alias="endTime", description="任务结束时间（毫秒时间戳或字符串）")
    msg: Optional[str] = Field(None, alias="msg", description="任务运行备注")
    job_list: List[YDJobItem] = Field(default_factory=list, alias="jobList", description="子应用执行列表")

    class Config:
        populate_by_name = True

    def get_task_status(self) -> str:
        """获取任务状态（兼容 None）"""
        return self.status or ""

    def to_legacy_dict(self) -> dict:
        """兼容旧代码的字典格式（process_yingdao_callback 使用）"""
        return {
            "dataType": self.data_type or "task",
            "taskUuid": self.task_uuid,
            "status": self.status,
            "startTime": self.start_time,
            "endTime": self.end_time,
            "msg": self.msg,
            "jobList": [
                {
                    "dataType": j.data_type or "job",
                    "jobUuid": j.job_uuid,
                    "robotClientUuid": j.robot_client_uuid,
                    "robotClientName": j.robot_client_name,
                    "robotName": j.robot_name,
                    "robotUuid": j.robot_uuid,
                    "status": j.status,
                    "startTime": j.start_time,
                    "endTime": j.end_time,
                    "msg": j.msg,
                    "idempotentUuid": j.idempotent_uuid,
                    "screenshotUrl": j.screenshot_url,
                    "result": [r.model_dump() for r in j.result] if j.result else None,
                }
                for j in self.job_list
            ],
        }


# ============================================================
# App 应用回调（单个应用节点级别的回调，影刀实际回调格式）
# ============================================================

class YDAppCallback(BaseModel):
    """
    影刀应用运行回调（单个应用节点级别）

    触发时机：每个应用节点开始/结束运行时推送
    回调地址：https://yingdao.redballoon.icu/yingdao/callback/app

    实际回调格式（dataType=job）：
    {
        "dataType": "job",
        "jobUuid": "6de893bb-8224-4f60-9bff-b8597b8ed8fc",
        "robotClientUuid": "cfcc5904-2e82-4295-911c-0ce65c9099f2",
        "robotClientName": "ceshi1@csqy1",
        "startTime": "2021-02-03 11:11:11",
        "endTime": "2021-03-03 12:12:12",
        "robotName": "导出淘宝订单",
        "robotUuid": "xxxxx",
        "status": "finish",
        "msg": "",
        "idempotentUuid": "xxxx",
        "screenshotUrl": "xxxx",
        "result": [...]
    }
    """
    data_type: Optional[str] = Field(None, alias="dataType", description="数据类型，固定为 'job'")
    job_uuid: Optional[str] = Field(None, alias="jobUuid", description="Job 唯一标识")
    robot_client_uuid: Optional[str] = Field(None, alias="robotClientUuid", description="机器人客户端UUID")
    robot_client_name: Optional[str] = Field(None, alias="robotClientName", description="机器人客户端名称")
    robot_name: Optional[str] = Field(None, alias="robotName", description="应用名称（对应 Job 表 当前执行应用名称）")
    robot_uuid: Optional[str] = Field(None, alias="robotUuid", description="应用UUID")
    status: Optional[str] = Field(None, alias="status", description="应用状态")
    start_time: Optional[str | int] = Field(None, alias="startTime", description="开始时间（字符串 yyyy-MM-dd HH:mm:ss 或毫秒时间戳）")
    end_time: Optional[str | int] = Field(None, alias="endTime", description="结束时间（字符串 yyyy-MM-dd HH:mm:ss 或毫秒时间戳）")
    msg: Optional[str] = Field(None, alias="msg", description="备注信息")
    idempotent_uuid: Optional[str] = Field(None, alias="idempotentUuid", description="幂等ID")
    screenshot_url: Optional[str] = Field(None, alias="screenshotUrl", description="异常截屏URL")
    result: Optional[List[YDJobResult]] = Field(None, alias="result", description="输出参数列表")
    task_uuid: Optional[str] = Field(None, alias="taskUuid", description="所属任务 UUID（可能不存在）")

    class Config:
        populate_by_name = True

    def get_job_status(self) -> str:
        """获取应用状态（兼容 None）"""
        return self.status or ""

    def get_robot_name(self) -> str:
        """获取应用名称（优先用 robotName，fallback 到 robotClientName）"""
        return self.robot_name or self.robot_client_name or ""


# ============================================================
# 响应模型
# ============================================================

class CallbackResponse(BaseModel):
    """回调接口统一响应"""
    success: bool
    message: str
    detail: Optional[dict] = None


# ============================================================
# 内部处理结果（用于记录日志）
# ============================================================

class JobUpdateResult(BaseModel):
    robot_name: str
    success: bool
    record_id: Optional[str] = None
    message: str


class TaskProcessResult(BaseModel):
    """process_yingdao_callback 的返回结构"""
    task: dict          # update_task_record 的返回
    jobs: List[JobUpdateResult]
