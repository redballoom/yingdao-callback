"""
Pydantic 数据模型 — 影刀回调请求体 + 内部处理结果
"""

from typing import Optional, List
from pydantic import BaseModel, Field


# ============================================================
# Task 任务回调（整体任务级别的回调）
# ============================================================

class YDJobItem(BaseModel):
    """jobList 中的单个应用执行记录"""
    robot_name: str = Field(..., alias="robotName", description="应用名称")
    job_status: str = Field(..., alias="jobStatus", description="应用执行状态")
    start_time: Optional[str] = Field(None, alias="startTime", description="开始时间 yyyy-MM-dd HH:mm:ss")
    end_time: Optional[str] = Field(None, alias="endTime", description="结束时间 yyyy-MM-dd HH:mm:ss")
    job_uuid: Optional[str] = Field(None, alias="jobUuid", description="Job 唯一标识（可能不存在）")
    result: Optional[dict] = Field(None, description="输出参数（执行结果）")

    class Config:
        populate_by_name = True


class YDTaskCallback(BaseModel):
    """
    影刀任务运行回调（整体任务级别）

    触发时机：整个任务状态变化时推送
    回调地址：https://blog.redballoon.icu/yingdao/callback/
    """
    task_uuid: str = Field(..., alias="taskUuid", description="任务唯一标识（对应 Task 表 taskUUID 字段）")
    task_status: str = Field(..., alias="taskStatus", description="任务状态 created/waiting/running/finish/error/stopped")
    start_time: Optional[str] = Field(None, alias="startTime", description="任务开始时间")
    end_time: Optional[str] = Field(None, alias="endTime", description="任务结束时间")
    job_list: List[YDJobItem] = Field(default_factory=list, alias="jobList", description="子应用执行列表")

    class Config:
        populate_by_name = True

    def to_legacy_dict(self) -> dict:
        """兼容旧代码的字典格式（process_yingdao_callback 使用）"""
        return {
            "taskUuid": self.task_uuid,
            "taskStatus": self.task_status,
            "startTime": self.start_time,
            "endTime": self.end_time,
            "jobList": [
                {
                    "robotName": j.robot_name,
                    "jobStatus": j.job_status,
                    "startTime": j.start_time,
                    "endTime": j.end_time,
                }
                for j in self.job_list
            ],
        }


# ============================================================
# App 应用回调（单个应用节点级别的回调）
# ============================================================

class YDAppCallback(BaseModel):
    """
    影刀应用运行回调（单个应用节点级别）

    触发时机：每个应用节点开始/结束运行时推送
    """
    job_uuid: str = Field(..., alias="jobUuid", description="Job 唯一标识")
    robot_name: str = Field(..., alias="robotName", description="应用名称（对应 Job 表 当前执行应用名称）")
    job_status: str = Field(..., alias="jobStatus", description="应用状态")
    start_time: Optional[str] = Field(None, alias="startTime", description="开始时间")
    end_time: Optional[str] = Field(None, alias="endTime", description="结束时间")
    result: Optional[dict] = Field(None, description="输出参数（可能不存在）")
    task_uuid: Optional[str] = Field(None, alias="taskUuid", description="所属任务 UUID（可能不存在）")

    class Config:
        populate_by_name = True


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
