# 影刀RPA × 飞书多维表格 — 回调系统实现文档

> 本文档描述如何实现：影刀RPA 任务执行完毕后，通过回调机制将执行状态实时写入飞书多维表格，实现自动化状态同步。

---

## 目录

1. [系统概述](#1-系统概述)
2. [架构设计](#2-架构设计)
3. [飞书多维表格准备](#3-飞书多维表格准备)
4. [影刀RPA 配置](#4-影刀rpa-配置)
5. [代码实现](#5-代码实现)
6. [本地调试](#6-本地调试)
7. [部署上线](#7-部署上线)
8. [完整测试流程](#8-完整测试流程)
9. [排查清单](#9-排查清单)
10. [字段映射参考](#10-字段映射参考)

---

## 1. 系统概述

### 1.1 目标

当影刀RPA 任务执行完成时，自动将以下信息写入飞书多维表格：

| 信息 | 来源 | 写入位置 |
|------|------|---------|
| 任务状态 | 影刀回调 `status` | Task 表「资产状态」 |
| 结束时间 | 影刀回调 `endTime` | Task 表「最后结束运行时间」 |
| 应用执行状态 | 影刀回调 `jobList[].status` | Job 表「任务状态」 |
| 应用开始/结束时间 | 影刀回调 `jobList[].startTime/endTime` | Job 表「开始运行时间」「结束运行时间」 |

### 1.2 双表结构

```
Task 表（任务总览表）
├── taskUUID        — 影刀调度任务唯一标识（搜索主键）
├── 资产状态        — 单选：🟢空闲 / 🔵运行中 / 🔴故障/离线
├── 开始运行时间    — 日期（毫秒时间戳）
└── 最后结束运行时间 — 日期（毫秒时间戳）
    │
    └─ DuplexLink 双向关联 ─┘
                              │
Job 表（应用执行记录表）       │
├── 当前执行应用名称   — Text（搜索条件）← robotName
├── 任务状态           — 单选：created/waiting/running/finish/stopping/stopped/error
├── 开始运行时间       — Text（直接存字符串）
├── 结束运行时间       — Text（直接存字符串）
└── 💻 环境与资产       — DuplexLink（关联回 Task 表）
```

### 1.3 技术栈

| 层级 | 技术选型 | 说明 |
|------|---------|------|
| 后端框架 | FastAPI + Uvicorn | 轻量异步 Python Web 框架 |
| 部署平台 | Vercel（Serverless Functions） | 自动 HTTPS，免费域名 |
| 本地调试 | `vercel dev` 或 `uvicorn` | 模拟 Vercel 环境 |
| 飞书 API | 飞书开放平台 REST API | 多维表格读写 |
| 回调接收 | POST JSON Body | 影刀主动推送 |

---

## 2. 架构设计

### 2.1 回调流程

```
影刀RPA
  │ 任务执行完成
  ▼
POST https://yingdao.redballoon.icu/yingdao/callback/task
  │  Content-Type: application/json
  │  Body: { dataType, taskUuid, status, jobList, ... }
  │
  ▼
FastAPI 服务（Vercel）
  │
  ├─ 日志记录（_callback_log）
  │
  ├─ dataType="task" 路径：
  │    update_task_record(taskUuid, status, startTime, endTime)
  │    遍历 jobList → update_job_record(robotName, status, startTime, endTime)
  │
  └─ dataType="job" 路径（单应用回调）：
       update_job_record(robotName, status, startTime, endTime)
         │
         ▼
         飞书开放平台 API
           │
           ├─ search_records(当前执行应用名称=robotName)
           └─ update_record(任务状态, 开始运行时间, 最后结束运行时间)
```

### 2.2 两种回调格式

影刀实际发送两种格式的回调，代码需要全部兼容：

**格式 A：任务级回调（dataType="task"）**
```json
{
  "dataType": "task",
  "taskUuid": "ea947f83-82fb-4afb-8412-4021255fd7cd",
  "status": "finish",
  "endTime": 1744275600000,
  "jobList": [
    {
      "robotName": "开发模板",
      "status": "finish",
      "startTime": "2026-04-13 12:00:00",
      "endTime": "2026-04-13 12:30:00"
    }
  ]
}
```

**格式 B：单应用回调（dataType="job"，Postman 模拟格式）**
```json
{
  "dataType": "job",
  "jobUuid": "42c2e0ce-499b-47aa-8642-3a1125b4759a",
  "status": "finish",
  "robotClientName": "ceshi1@csqy1",
  "robotName": "开发模板",
  "startTime": "2026-04-13 12:00:00",
  "endTime": "2026-04-13 12:30:00"
}
```

### 2.3 目录结构

```
yingdao_and_feishu_callback/
├── api/
│   └── index.py          # FastAPI 路由：回调入口 + 调试接口
├── services/
│   ├── yingdao_service.py # 业务逻辑：Task/Job 表更新
│   └── bitable_sdk.py    # 飞书 API SDK（搜索/更新记录）
├── config.py              # 飞书凭证 + 字段名配置
├── vercel.json           # Vercel 部署配置
├── requirements.txt      # Python 依赖
├── test_callback.py      # 本地回调测试脚本
└── README.md
```

---

## 3. 飞书多维表格准备

### 3.1 创建多维表格

1. 打开飞书 → 新建多维表格
2. 创建两个表：
   - **任务总览表**（Task）
   - **应用执行记录表**（Job）
3. 记录表格 URL 中的 `app_token` 和 `table_id`

URL 格式：
```
https://xxx.feishu.cn/base/{app_token}?table={table_id}&view={view_id}
```

### 3.2 Task 表字段设计

| 字段名 | 类型 | 用途 |
|--------|------|------|
| taskUUID | Text | 存储影刀 taskUuid（搜索主键） |
| 资产状态 | SingleSelect | 🟢空闲 / 🔵运行中 / 🔴故障/离线 |
| 开始运行时间 | DateTime | 任务开始时间（毫秒时间戳） |
| 最后结束运行时间 | DateTime | 任务结束时间（毫秒时间戳） |
| 💻 环境与资产 | DuplexLink | 关联到 Job 表 |

**SingleSelect 选项（资产状态）：**
```
🟢 空闲
🔵 运行中
🔴 故障/离线
```

### 3.3 Job 表字段设计

| 字段名 | 类型 | 用途 |
|--------|------|------|
| jobUUID | Text | 存储影刀 jobUuid |
| 当前执行应用名称 | Text | 应用名称（搜索条件） |
| 任务状态 | SingleSelect | created/waiting/running/finish/error |
| 开始运行时间 | Text | 时间字符串 "YYYY-MM-DD HH:mm:ss" |
| 最后结束运行时间 | Text | 时间字符串 "YYYY-MM-DD HH:mm:ss" |
| 💻 环境与资产 | DuplexLink | 关联到 Task 表 |

**SingleSelect 选项（任务状态）：**
```
created
waiting
running
finish
stopping
stopped
error
skipped
cancel
```

### 3.4 DuplexLink 双向关联配置

1. Task 表的「💻 环境与资产」字段 → 关联 Job 表
2. Job 表的「💻 环境与资产」字段 → 关联 Task 表
3. 关联后自动建立双向链接，可双向跳转

### 3.5 获取飞书凭证

1. 打开 [飞书开放平台](https://open.feishu.cn/app) → 创建企业自建应用
2. 获取 `App ID` 和 `App Secret`
3. 开通权限：
   - `bitable:app`（多维表格权限）
   - 具体读写权限根据字段类型确定
4. 发布应用版本

### 3.6 配置 config.py

```python
# 飞书应用凭证
APP_ID = "cli_xxxxxx"
APP_SECRET = "your_app_secret"

# Task 表
TASK_APP_TOKEN = "Z86IbHdoiajCCGsim1Zc6BISnlc"
TASK_TABLE_ID = "tbllXMN6akGNedjE"
TASK_FIELD_TASK_UUID = "taskUUID"
TASK_FIELD_STATUS = "资产状态"
TASK_FIELD_START_TIME = "开始运行时间"
TASK_FIELD_END_TIME = "最后结束运行时间"

# Job 表
JOB_APP_TOKEN = "Z86IbHdoiajCCGsim1Zc6BISnlc"
JOB_TABLE_ID = "tblG3lAggRTgfiZy"
JOB_FIELD_ROBOT_NAME = "当前执行应用名称"
JOB_FIELD_STATUS = "任务状态"
JOB_FIELD_START_TIME = "开始运行时间"
JOB_FIELD_END_TIME = "最后结束运行时间"
```

---

## 4. 影刀RPA 配置

### 4.1 回调地址设置

在影刀后台配置回调地址：

```
https://yingdao.redballoon.icu/yingdao/callback/task
```

路径选择 `/yingdao/callback/task`（兼容两种 dataType 格式）。

### 4.2 回调触发时机

影刀支持以下回调触发时机：
- **任务开始时**：`dataType=task`, `status=start`
- **任务结束时**：`dataType=task`, `status=finish/error`
- **应用节点开始/结束**：每个应用执行完成时推送 `dataType=job`

### 4.3 回调内容说明

| 字段 | 说明 |
|------|------|
| `dataType` | `"task"` 或 `"job"` |
| `taskUuid` | 整个调度任务的唯一标识（任务级回调有） |
| `jobUuid` | 单个应用执行的唯一标识（应用级回调有） |
| `status` | 执行状态：`start/finish/error/stopping/stopped` |
| `startTime` | 开始时间（任务级=毫秒时间戳，应用级=字符串） |
| `endTime` | 结束时间（同上） |
| `robotName` | 应用名称（和 Job 表「当前执行应用名称」对应） |
| `robotClientName` | 执行账号名称 |
| `jobList` | 任务级回调中的应用列表（应用级回调没有此字段） |

---

## 5. 代码实现

### 5.1 飞书 SDK（bitable_sdk.py）

核心功能：获取访问令牌 → 搜索记录 → 更新记录。

```python
class BitableSDK:
    def __init__(self, app_id, app_secret, app_token, table_id):
        self.app_token = app_token
        self.table_id = table_id
        self.token = self._get_tenant_access_token(app_id, app_secret)

    def _get_tenant_access_token(self, app_id, app_secret):
        """获取飞书 tenant_access_token"""
        resp = requests.post(
            f"{API_BASE_URL}/auth/v3/tenant_access_token/internal",
            json={"app_id": app_id, "app_secret": app_secret},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != 0:
            raise Exception(f"获取 token 失败: {data}")
        return data["tenant_access_token"]

    def search_records(self, filter: dict, page_size: int = 100) -> List[dict]:
        """搜索记录"""
        resp = requests.post(
            f"{API_BASE_URL}/bitable/v1/apps/{self.app_token}/tables/{self.table_id}/records/search",
            headers=self._headers(),
            json={"filter": filter, "page_size": page_size},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != 0:
            raise Exception(f"搜索失败: {data}")
        return data.get("data", {}).get("items", [])

    def update_record(self, record_id: str, fields: dict) -> dict:
        """更新单条记录"""
        resp = requests.put(
            f"{API_BASE_URL}/bitable/v1/apps/{self.app_token}/tables/{self.table_id}/records/{record_id}",
            headers=self._headers(),
            json={"fields": fields},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != 0:
            raise Exception(f"更新失败: {data}")
        return data.get("data", {}).get("record", {})
```

### 5.2 状态映射（yingdao_service.py）

Task 表状态使用表情符号，需要映射：

```python
TASK_STATUS_MAP = {
    "waiting":  "🟢 空闲",
    "running":  "🔵 运行中",
    "finish":   "🟢 空闲",
    "stopping": "🔵 运行中",
    "stopped":  "🟢 空闲",
    "error":    "🔴 故障/离线",
}

def map_task_status(yingdao_status: str) -> str:
    """影刀状态 → 飞书单选选项名"""
    return TASK_STATUS_MAP.get(yingdao_status, "🟢 空闲")

def map_job_status(yingdao_status: str) -> str:
    """影刀状态 → Job 表单选选项（直接存状态码）"""
    return yingdao_status  # Job 表直接存状态码，不做映射
```

### 5.3 时间格式处理

**Task 表**（DateTime 类型）→ 需要毫秒时间戳：

```python
def parse_datetime_to_ms(dt_value) -> Optional[int]:
    """将各种格式转为毫秒时间戳"""
    if isinstance(dt_value, (int, float)) and dt_value > 0:
        return int(dt_value * 1000) if dt_value < 10**12 else int(dt_value)
    if isinstance(dt_value, str) and dt_value.strip():
        dt = datetime.strptime(dt_value.strip(), "%Y-%m-%d %H:%M:%S")
        return int(dt.timestamp() * 1000)
    return None
```

**Job 表**（Text 类型）→ 需要 "YYYY-MM-DD HH:mm:ss" 字符串：

```python
def format_datetime_for_text(dt_value) -> Optional[str]:
    """将各种格式转为标准日期字符串"""
    if isinstance(dt_value, str) and dt_value.strip():
        try:
            datetime.strptime(dt_value.strip(), "%Y-%m-%d %H:%M:%S")
            return dt_value.strip()
        except ValueError:
            pass
        for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y/%m/%d %H:%M:%S"):
            try:
                dt = datetime.strptime(dt_value.strip(), fmt)
                return dt.strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                pass
        return dt_value.strip()

    if isinstance(dt_value, (int, float)) and dt_value > 0:
        ts_ms = dt_value * 1000 if dt_value < 10**12 else dt_value
        dt = datetime.fromtimestamp(ts_ms / 1000)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    return None
```

### 5.4 Task 表更新

```python
def update_task_record(task_uuid, status, start_time=None, end_time=None) -> dict:
    sdk = _get_task_sdk()

    # 搜索
    records = sdk.search_records(
        filter=create_filter("taskUUID", "is", task_uuid),
    )

    if not records:
        return {"success": False, "updated": 0, "message": f"未找到 taskUUID={task_uuid}"}

    # 构建更新字段
    fields = {"资产状态": map_task_status(status)}
    if start_time is not None:
        ts = parse_datetime_to_ms(start_time)
        if ts:
            fields["开始运行时间"] = ts
    if end_time is not None:
        ts = parse_datetime_to_ms(end_time)
        if ts:
            fields["最后结束运行时间"] = ts

    # 更新
    updated = 0
    for record in records:
        sdk.update_record(record["record_id"], fields)
        updated += 1

    return {"success": True, "updated": updated}
```

### 5.5 Job 表更新

```python
def update_job_record(robot_name, status, start_time=None, end_time=None, job_uuid=None) -> dict:
    sdk = _get_job_sdk()

    # 搜索（按应用名称精确匹配，取最新一条）
    records = sdk.search_records(
        filter=create_filter("当前执行应用名称", "is", robot_name),
    )

    if not records:
        return {"success": False, "message": f"未找到应用名称={robot_name}"}

    # 取最新（record_id 倒序）
    records_sorted = sorted(records, key=lambda r: r["record_id"], reverse=True)
    target = records_sorted[0]

    # 构建字段（时间存字符串）
    fields = {"任务状态": map_job_status(status)}
    if start_time is not None:
        s = format_datetime_for_text(start_time)
        if s:
            fields["开始运行时间"] = s
    if end_time is not None:
        e = format_datetime_for_text(end_time)
        if e:
            fields["最后结束运行时间"] = e

    sdk.update_record(target["record_id"], fields)

    return {"success": True, "record_id": target["record_id"]}
```

### 5.6 回调入口（FastAPI 路由）

```python
from fastapi import FastAPI, Request

app = FastAPI()

_callback_log: List[dict] = []

@app.post("/yingdao/callback/task")
async def callback_task(request: Request):
    """兼容 dataType=task 和 dataType=job 两种格式"""
    body = await request.json()

    # 记录日志
    _callback_log.append({
        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "endpoint": "/yingdao/callback/task",
        "data": body,
    })

    data_type = body.get("dataType", "")
    task_uuid = body.get("taskUuid")

    # dataType=job 或无 taskUuid → 单应用回调
    if data_type == "job" or not task_uuid:
        robot_name = body.get("robotName") or body.get("robotClientName", "")
        result = update_job_record(
            robot_name=robot_name,
            status=body.get("status", ""),
            start_time=body.get("startTime"),
            end_time=body.get("endTime"),
            job_uuid=body.get("jobUuid", ""),
        )
        return {"success": result.get("success", False), "message": "单应用回调处理成功"}

    # dataType=task → 任务级回调
    result = process_yingdao_callback(body)
    return {"success": True, "message": "Task 回调处理成功", "detail": result}


@app.get("/yingdao/health")
async def health():
    return {"status": "ok", "service": "yingdao-callback"}


@app.get("/yingdao/logs")
async def get_logs():
    """查看回调日志（调试用）"""
    return {"total": len(_callback_log), "logs": _callback_log[-20:]}
```

---

## 6. 本地调试

### 6.1 启动本地服务

```bash
cd yingdao_and_feishu_callback

# 安装依赖
pip install -r requirements.txt

# 启动服务
uvicorn api.index:app --host 0.0.0.0 --port 8000 --reload
```

服务启动后访问：http://localhost:8000/yingdao/health

### 6.2 本地测试脚本（test_callback.py）

```python
import requests
import json

BASE_URL = "http://localhost:8000"

# 测试 1：任务级回调
def test_task_callback():
    payload = {
        "dataType": "task",
        "taskUuid": "f5c6f5c0-128f-4de9-b2f2-f9405ef71289",
        "status": "finish",
        "startTime": 1776081600000,
        "endTime": 1776092400000,
        "jobList": [
            {
                "robotName": "开发模板",
                "status": "finish",
                "startTime": "2026-04-13 12:00:00",
                "endTime": "2026-04-13 12:30:00"
            }
        ]
    }
    resp = requests.post(f"{BASE_URL}/yingdao/callback/task", json=payload)
    print("Task 回调:", resp.json())


# 测试 2：单应用回调（Postman 真实格式）
def test_app_callback():
    payload = {
        "dataType": "job",
        "jobUuid": "42c2e0ce-499b-47aa-8642-3a1125b4759a",
        "status": "finish",
        "robotClientName": "ceshi1@csqy1",
        "robotName": "开发模板",
        "startTime": "2026-04-13 12:00:00",
        "endTime": "2026-04-13 12:30:00"
    }
    resp = requests.post(f"{BASE_URL}/yingdao/callback/task", json=payload)
    print("App 回调:", resp.json())


if __name__ == "__main__":
    test_task_callback()
    test_app_callback()
    print("\n回调日志:")
    resp = requests.get(f"{BASE_URL}/yingdao/logs")
    print(json.dumps(resp.json(), indent=2, ensure_ascii=False))
```

### 6.3 查看日志

```bash
curl http://localhost:8000/yingdao/logs
```

### 6.4 调试端点

| 端点 | 用途 |
|------|------|
| `GET /yingdao/health` | 健康检查 |
| `GET /yingdao/logs` | 查看最近 20 条回调记录 |
| `GET /yingdao/debug?task_uuid=xxx&robot_name=xxx` | 打印 Task/Job 表字段信息 |
| `POST /yingdao/force-update-job` | 强制更新 Job 表（手动修复） |

---

## 7. 部署上线

### 7.1 Vercel 部署

```bash
# 1. 安装 Vercel CLI
npm i -g vercel

# 2. 登录
vercel login

# 3. 部署（项目根目录）
vercel --prod

# 4. 设置环境变量（飞书凭证）
vercel env add FEISHU_APP_ID
vercel env add FEISHU_APP_SECRET --prod
```

### 7.2 vercel.json 配置

```json
{
  "version": 2,
  "builds": [
    { "src": "api/**/*.py", "use": "@vercel/python" }
  ],
  "routes": [
    { "src": "/(.*)", "dest": "api/index.py" }
  ]
}
```

### 7.3 requirements.txt

```
fastapi==0.111.0
uvicorn==0.30.0
requests==2.32.3
pydantic==2.7.1
python-multipart==0.0.9
```

### 7.4 环境变量

在 Vercel 控制台设置：

| 变量名 | 值 |
|--------|-----|
| `FEISHU_APP_ID` | `cli_a94b4d8925e49bd3` |
| `FEISHU_APP_SECRET` | `zj0CjbyN2dwCAop6enlQogxGcQvpTwHD` |

### 7.5 自定义域名（可选）

Vercel 自动提供 `https://yingdao-callback.vercel.app`，也可绑定自定义域名。

---

## 8. 完整测试流程

### 8.1 步骤

```
Step 1: 本地启动
  → uvicorn api.index:app --reload

Step 2: 本地测试 Task 回调
  → python test_callback.py
  → 检查飞书 Task 表，确认状态/时间更新

Step 3: 本地测试 App 回调
  → curl -X POST http://localhost:8000/yingdao/callback/task \
      -H "Content-Type: application/json" \
      -d '{"dataType":"job","robotName":"开发模板","status":"finish"}'
  → 检查飞书 Job 表

Step 4: 部署到 Vercel
  → vercel --prod

Step 5: 触发影刀真实任务
  → 在影刀后台手动运行一个任务
  → 等待回调推送

Step 6: 验证
  → GET https://yingdao.redballoon.icu/yingdao/logs
  → 检查飞书 Task 表和 Job 表数据是否正确
```

### 8.2 验证清单

- [ ] `/yingdao/health` 返回 `{"status":"ok"}`
- [ ] `/yingdao/logs` 显示回调记录（非空）
- [ ] Task 表「资产状态」正确更新
- [ ] Task 表「开始运行时间」「最后结束运行时间」正确显示
- [ ] Job 表「任务状态」正确更新
- [ ] Job 表时间字段显示为 "YYYY-MM-DD HH:mm:ss" 格式
- [ ] DuplexLink 双向关联正确建立

---

## 9. 排查清单

### 9.1 回调未到达

```
排查路径：
1. GET /yingdao/logs 返回空？
   → 回调根本没到，检查影刀后台回调地址是否正确配置
   → 检查影刀是否成功推送（查看影刀日志）

2. 部署后 /yingdao/logs 仍为空？
   → Vercel 免费版有冷启动，首次回调可能超时
   → 等待 30 秒后再试

3. Vercel 函数报错？
   → vercel logs --prod 查看函数执行日志
```

### 9.2 搜索找不到记录

```
排查路径：
1. 确认字段名完全匹配（大小写敏感！）
   → 飞书表里叫 "taskUUID"，代码里也要一模一样
   → 区分 taskUUID（大写U）和 taskUuid（小写u）

2. 确认搜索条件字段存在
   → Task 表按 taskUUID 搜
   → Job 表按 当前执行应用名称 搜

3. 使用调试接口：
   GET /yingdao/debug?task_uuid=xxx&robot_name=xxx
   → 返回找到的字段名和类型
```

### 9.3 更新失败

```
排查路径：
1. 检查飞书字段类型
   → Task 表时间字段是 DateTime → 必须传毫秒时间戳
   → Job 表时间字段是 Text → 必须传字符串 "YYYY-MM-DD HH:mm:ss"

2. 检查 SingleSelect 选项是否存在
   → 飞书单选字段的选项必须预先创建
   → 传一个不存在的选项名，飞书会报错

3. 检查 App Secret 是否正确
   → 本地 .env 和 Vercel 环境变量都要配置
   → 错误码 10014 = APP_SECRET 无效

4. 检查 App Token 和 Table ID
   → 确认 config.py 里的 app_token 和 table_id 和实际一致
```

### 9.4 常见错误码

| 错误码 | 含义 | 解决 |
|--------|------|------|
| `99991664` | 无权限 | 飞书应用未开通多维表格权限 |
| `10014` | APP_SECRET 错误 | 检查环境变量配置 |
| `InvalidFilter` | 过滤条件字段不存在 | 检查 config.py 字段名 |
| `99991400` | 参数错误 | 检查字段类型是否匹配 |

---

## 10. 字段映射参考

### 10.1 影刀回调 → 飞书字段

```
影刀字段              →  飞书字段（Task 表）
─────────────────────────────────────────
dataType              →  无（路由判断用）
taskUuid              →  taskUUID（搜索主键）
status                →  资产状态（单选，映射后）
startTime（数字ms）    →  开始运行时间（DateTime，parse_datetime_to_ms）
endTime（数字ms）      →  最后结束运行时间（DateTime，parse_datetime_to_ms）
jobList[].robotName   →  Job 表 当前执行应用名称（搜索条件）
jobList[].status      →  Job 表 任务状态（单选，直接存）
jobList[].startTime   →  Job 表 开始运行时间（Text，format_datetime_for_text）
jobList[].endTime     →  Job 表 最后结束运行时间（Text，format_datetime_for_text）
```

### 10.2 状态映射

```
影刀 taskStatus  →  Task 表「资产状态」
──────────────────────────────────────
created           →  🟢 空闲
waiting           →  🟢 空闲
running           →  🔵 运行中
paused            →  🔵 运行中
finish            →  🟢 空闲
stopping          →  🟢 空闲
stopped           →  🟢 空闲
error             →  🔴 故障/离线

影刀 jobStatus   →  Job 表「任务状态」（直接存储，不做映射）
────────────────────────────────────────────────────────────
created / waiting / running / finish / stopping / stopped / error / skipped / cancel
```

### 10.3 时间格式

```
输入格式                          →  输出格式          →  写入位置
───────────────────────────────────────────────────────────────────
1744274400000（毫秒时间戳）       →  1744274400000     →  Task 表 DateTime
"2026-04-13 12:00:00"             →  1744274400000     →  Task 表 DateTime
1744274400000（毫秒时间戳）       →  "2026-04-13 12:00:00" →  Job 表 Text
"2026-04-13 12:00:00"             →  "2026-04-13 12:00:00" →  Job 表 Text
```

---

## 附录：快捷命令

```bash
# 本地启动
uvicorn api.index:app --host 0.0.0.0 --port 8000 --reload

# 查看回调日志
curl https://yingdao.redballoon.icu/yingdao/logs

# 本地模拟 Task 回调
curl -X POST http://localhost:8000/yingdao/callback/task \
  -H "Content-Type: application/json" \
  -d '{"dataType":"task","taskUuid":"测试","status":"finish"}'

# 本地模拟 App 回调
curl -X POST http://localhost:8000/yingdao/callback/task \
  -H "Content-Type: application/json" \
  -d '{"dataType":"job","robotName":"开发模板","status":"finish","startTime":"2026-04-13 12:00:00","endTime":"2026-04-13 12:30:00"}'

# 查看 Vercel 日志
vercel logs yingdao-callback --prod

# 部署
vercel --prod
```


curl -X POST http://127.0.0.1:8000/yingdao/callback/task \
-H "Content-Type: application/json" \
-d '{
  "dataType": "task",
  "endTime": 1642837962000,
  "status": "finish",
  "msg": "运行结束",
  "taskUuid": "170e9fdd-2831-40d2-aa7c-e1f6f2193f06",
  "jobList": [
    {
      "dataType": "job",
      "jobUuid": "3d297e35-67b1-4ce8-b29e-0349246fc6bc",
      "msg": "",
      "robotClientName": "redballoon@YFLe",
      "robotName": "开发模板",
      "status": "finish",
      "startTime": "2026-04-13 12:00:00",
      "endTime": "2026-04-13 12:12:12",
      "result": []
    },
    {
      "dataType": "job",
      "jobUuid": "6d8a9343-ccf4-4433-870a-2d2715e3c502",
      "msg": "",
      "robotClientName": "redballoon@YFLe",
      "robotName": "开发模板--副本",
      "status": "finish",
      "startTime": "2026-04-13 12:12:12",
      "endTime": "2026-04-13 12:30:00",
      "result": []
    }
  ]
}'

$body = @{
    dataType = "task"
    endTime = 1776072984000
    status = "finish"
    msg = "运行结束"
    taskUuid = "170e9fdd-2831-40d2-aa7c-e1f6f2193f06"
    jobList = @(
        @{
            dataType = "job"
            jobUuid = "3d297e35-67b1-4ce8-b29e-0349246fc6bc"
            msg = ""
            robotClientName = "redballoon@YFLe"
            robotName = "开发模板"
            status = "finish"
            startTime = "2026-04-13 12:00:00"
            endTime = "2026-04-13 12:12:12"
            result = @()
        },
        @{
            dataType = "job"
            jobUuid = "6d8a9343-ccf4-4433-870a-2d2715e3c502"
            msg = ""
            robotClientName = "redballoon@YFLe"
            robotName = "开发模板--副本"
            status = "finish"
            startTime = "2026-04-13 12:12:12"
            endTime = "2026-04-13 12:30:00"
            result = @()
        }
    )
}

# 转换为 JSON 并发送请求
Invoke-RestMethod -Uri "http://127.0.0.1:8000/yingdao/callback/task" `
                  -Method Post `
                  -ContentType "application/json; charset=utf-8" `
                  -Body ($body | ConvertTo-Json -Depth 10)