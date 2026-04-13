# ============================================================
# 飞书多维表格 — 双表配置
# 影刀 RPA 回调系统专用
# ============================================================

# ---------- 飞书应用凭证 ----------
# 优先从环境变量读取（Vercel 部署），否则使用默认值
import os
APP_ID = os.environ.get("FEISHU_APP_ID", "cli_a94b4d8925e49bd3")
APP_SECRET = os.environ.get("FEISHU_APP_SECRET", "zj0CjbyN2dwCAop6enlQogxGcQvpTwHD")

# ---------- API 配置 ----------
API_BASE_URL = "https://open.feishu.cn/open-apis"


# ============================================================
# Task 表（任务总览表）
# URL: https://xxx.feishu.cn/base/Z86IbHdoiajCCGsim1Zc6BISnlc?table=tbllXMN6akGNedjE&view=vewl9bCH4X
# ============================================================
TASK_APP_TOKEN = "Z86IbHdoiajCCGsim1Zc6BISnlc"
TASK_TABLE_ID = "tbllXMN6akGNedjE"
TASK_VIEW_ID = "vewl9bCH4X"

# Task 表字段名
TASK_FIELD_TASK_UUID = "taskUUID"               # 存储影刀 taskUuid 的字段（搜索条件）
TASK_FIELD_STATUS = "资产状态"                  # 执行状态（单选）
TASK_FIELD_START_TIME = "开始运行时间"          # 执行开始时间（日期，毫秒时间戳）
TASK_FIELD_END_TIME = "最后结束运行时间"         # 执行结束时间（日期，毫秒时间戳）


# ============================================================
# Job 表（应用执行记录表）
# URL: https://xxx.feishu.cn/base/Z86IbHdoiajCCGsim1Zc6BISnlc?table=tblG3lAggRTgfiZy&view=vewQAS31Lf
# ============================================================
JOB_APP_TOKEN = "Z86IbHdoiajCCGsim1Zc6BISnlc"
JOB_TABLE_ID = "tblG3lAggRTgfiZy"
JOB_VIEW_ID = "vewQAS31Lf"

# Job 表字段名
JOB_FIELD_ROBOT_NAME = "当前执行应用名称"          # 应用名称（搜索条件）
JOB_FIELD_STATUS = "任务状态"                      # 执行状态（单选）
JOB_FIELD_START_TIME = "开始运行时间"              # 执行开始时间（日期，毫秒时间戳）
JOB_FIELD_END_TIME = "最后结束运行时间"             # 执行结束时间（日期，毫秒时间戳）


# ============================================================
# 批量操作配置
# ============================================================
BATCH_CREATE_SIZE = 500
BATCH_UPDATE_SIZE = 1000
BATCH_DELETE_SIZE = 500
BATCH_GET_SIZE = 500
SEARCH_PAGE_SIZE = 500
