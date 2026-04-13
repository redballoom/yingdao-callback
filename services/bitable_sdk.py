# -*- coding: utf-8 -*-
"""
飞书多维表格（Bitable）Python SDK
支持记录的增删改查及批量操作，自动处理超限分批
"""

import json
import time
import requests
from typing import Any, Optional


class BitableSDK:
    """飞书多维表格 SDK"""

    def __init__(self, app_id: str, app_secret: str,
                 app_token: str, table_id: str,
                 base_url: str = "https://open.feishu.cn/open-apis"):
        """
        初始化 SDK

        Args:
            app_id: 飞书应用 ID
            app_secret: 飞书应用密钥
            app_token: 多维表格 app_token
            table_id: 数据表 table_id
            base_url: API 基础 URL
        """
        self.app_id = app_id
        self.app_secret = app_secret
        self.app_token = app_token
        self.table_id = table_id
        self.base_url = base_url
        self._access_token: Optional[str] = None
        self._token_expire_time = 0

        # 批量操作默认每批数量
        self.batch_create_size = 500
        self.batch_update_size = 1000
        self.batch_delete_size = 500
        self.batch_get_size = 500
        self.search_page_size = 500

    # ==================== 认证 ====================

    def get_access_token(self, force_refresh: bool = False) -> str:
        """
        获取 tenant_access_token

        Args:
            force_refresh: 强制刷新 token

        Returns:
            access_token 字符串
        """
        # 检查是否需要刷新
        if not force_refresh and self._access_token and time.time() < self._token_expire_time - 300:
            return self._access_token

        # 重新获取
        url = f"{self.base_url}/auth/v3/tenant_access_token/internal"
        data = {
            "app_id": self.app_id,
            "app_secret": self.app_secret
        }

        resp = requests.post(url, json=data, timeout=30)
        resp.raise_for_status()

        result = resp.json()
        if result.get("code") != 0:
            raise Exception(f"获取 token 失败: {result.get('msg')}")

        self._access_token = result["tenant_access_token"]
        self._token_expire_time = time.time() + result.get("expire", 7200)
        return self._access_token

    def _request(self, method: str, path: str, **kwargs) -> dict:
        """
        发起 API 请求

        Args:
            method: HTTP 方法
            path: API 路径（如 /bitable/v1/apps/xxx/records）
            **kwargs: 其他参数（params, json 等）

        Returns:
            API 响应数据
        """
        token = self.get_access_token()

        url = f"{self.base_url}{path}"
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {token}"

        resp = requests.request(method, url, headers=headers, timeout=30, **kwargs)
        resp.raise_for_status()

        result = resp.json()
        if result.get("code") != 0:
            raise Exception(f"API 请求失败: {result.get('msg')}")

        return result.get("data", {})

    # ==================== 字段操作 ====================

    def list_fields(self, view_id: Optional[str] = None) -> list:
        """
        列出所有字段

        Args:
            view_id: 视图 ID（可选）

        Returns:
            字段列表
        """
        path = f"/bitable/v1/apps/{self.app_token}/tables/{self.table_id}/fields"
        params = {}
        if view_id:
            params["view_id"] = view_id

        data = self._request("GET", path, params=params)
        return data.get("items", [])

    def get_field_id(self, field_name: str) -> Optional[str]:
        """
        根据字段名获取 field_id

        Args:
            field_name: 字段名称

        Returns:
            field_id 或 None
        """
        fields = self.list_fields()
        for field in fields:
            if field.get("field_name") == field_name:
                return field.get("field_id")
        return None

    # ==================== 记录操作 ====================

    def create_record(self, fields: dict,
                      user_id_type: str = "open_id",
                      client_token: Optional[str] = None,
                      ignore_consistency_check: bool = False) -> dict:
        """
        新增单条记录

        Args:
            fields: 字段值字典，如 {"字段名": "值"}
            user_id_type: 用户 ID 类型 (open_id/union_id/user_id)
            client_token: 幂等操作 token (uuid4)
            ignore_consistency_check: 是否忽略读写一致性检查

        Returns:
            包含 record_id 的记录对象
        """
        path = f"/bitable/v1/apps/{self.app_token}/tables/{self.table_id}/records"

        params = {"user_id_type": user_id_type}
        if client_token:
            params["client_token"] = client_token
        if ignore_consistency_check:
            params["ignore_consistency_check"] = ignore_consistency_check

        data = self._request("POST", path, params=params, json={"fields": fields})
        return data.get("record", {})

    def batch_create_records(self, records: list,
                            user_id_type: str = "open_id",
                            ignore_consistency_check: bool = False) -> list:
        """
        批量新增记录（自动分批）

        Args:
            records: 记录列表，每条为 fields 字典
            user_id_type: 用户 ID 类型
            ignore_consistency_check: 是否忽略读写一致性检查

        Returns:
            所有创建的记录列表
        """
        all_results = []

        for i in range(0, len(records), self.batch_create_size):
            batch = records[i:i + self.batch_create_size]
            results = self._batch_create(
                batch, user_id_type, ignore_consistency_check
            )
            all_results.extend(results)

        return all_results

    def _batch_create(self, records: list,
                       user_id_type: str = "open_id",
                       ignore_consistency_check: bool = False) -> list:
        """
        内部方法：批量新增（单次请求）
        """
        path = f"/bitable/v1/apps/{self.app_token}/tables/{self.table_id}/records/batch_create"

        params = {"user_id_type": user_id_type}
        if ignore_consistency_check:
            params["ignore_consistency_check"] = ignore_consistency_check

        data = self._request("POST", path, params=params,
                           json={"records": [{"fields": r} for r in records]})
        return data.get("records", [])

    def update_record(self, record_id: str, fields: dict,
                      user_id_type: str = "open_id",
                      ignore_consistency_check: bool = False) -> dict:
        """
        更新单条���录

        Args:
            record_id: 记录 ID
            fields: 要更新的字段值字典
            user_id_type: 用户 ID 类型
            ignore_consistency_check: 是否忽略读写一致性检查

        Returns:
            更新后的记录对象
        """
        path = f"/bitable/v1/apps/{self.app_token}/tables/{self.table_id}/records/{record_id}"

        params = {"user_id_type": user_id_type}
        if ignore_consistency_check:
            params["ignore_consistency_check"] = ignore_consistency_check

        data = self._request("PUT", path, params=params, json={"fields": fields})
        return data.get("record", {})

    def batch_update_records(self, records: list,
                            user_id_type: str = "open_id",
                            ignore_consistency_check: bool = False) -> list:
        """
        批量更新记录（自动分批）

        Args:
            records: 记录列表，每条为 {"record_id": "xxx", "fields": {...}}
            user_id_type: 用户 ID 类型
            ignore_consistency_check: 是否忽略读写一致性检查

        Returns:
            所有更新后的记录列表
        """
        all_results = []

        for i in range(0, len(records), self.batch_update_size):
            batch = records[i:i + self.batch_update_size]
            results = self._batch_update(batch, user_id_type, ignore_consistency_check)
            all_results.extend(results)

        return all_results

    def _batch_update(self, records: list,
                      user_id_type: str = "open_id",
                      ignore_consistency_check: bool = False) -> list:
        """
        内部方法：批量更新（单次请求）
        """
        path = f"/bitable/v1/apps/{self.app_token}/tables/{self.table_id}/records/batch_update"

        params = {"user_id_type": user_id_type}
        if ignore_consistency_check:
            params["ignore_consistency_check"] = ignore_consistency_check

        data = self._request("POST", path, params=params, json={"records": records})
        return data.get("records", [])

    def delete_record(self, record_id: str,
                     ignore_consistency_check: bool = False) -> bool:
        """
        删除单条记录

        Args:
            record_id: 记录 ID
            ignore_consistency_check: 是否忽略读写一致性检查

        Returns:
            是否删除成功
        """
        path = f"/bitable/v1/apps/{self.app_token}/tables/{self.table_id}/records/{record_id}"

        params = {}
        if ignore_consistency_check:
            params["ignore_consistency_check"] = ignore_consistency_check

        data = self._request("DELETE", path, params=params)
        return data.get("deleted", False)

    def batch_delete_records(self, record_ids: list,
                          ignore_consistency_check: bool = False) -> list:
        """
        批量删除记录（自动分批）

        Args:
            record_ids: 记录 ID 列表
            ignore_consistency_check: 是否忽略读写一致性检查

        Returns:
            删除结果列表
        """
        all_results = []

        for i in range(0, len(record_ids), self.batch_delete_size):
            batch = record_ids[i:i + self.batch_delete_size]
            results = self._batch_delete(batch, ignore_consistency_check)
            all_results.extend(results)

        return all_results

    def _batch_delete(self, record_ids: list,
                     ignore_consistency_check: bool = False) -> list:
        """
        内部方法：批量删除（单次请求）
        """
        path = f"/bitable/v1/apps/{self.app_token}/tables/{self.table_id}/records/batch_delete"

        params = {}
        if ignore_consistency_check:
            params["ignore_consistency_check"] = ignore_consistency_check

        data = self._request("POST", path, params=params,
                           json={"records": record_ids})
        return data.get("records", [])

    def batch_get_records(self, record_ids: list,
                         field_names: Optional[list] = None,
                         user_id_type: str = "open_id",
                         ignore_consistency_check: bool = False) -> list:
        """
        批量获取记录（自动分批）

        Args:
            record_ids: 记录 ID 列表
            field_names: 指定返回的字段名列表（None 返回所有）
            user_id_type: 用户 ID 类型
            ignore_consistency_check: 是否忽略读写一致性检查

        Returns:
            记录列表
        """
        all_records = []

        for i in range(0, len(record_ids), self.batch_get_size):
            batch = record_ids[i:i + self.batch_get_size]
            records = self._batch_get(batch, field_names, user_id_type,
                                    ignore_consistency_check)
            all_records.extend(records)

        return all_records

    def _batch_get(self, record_ids: list,
                   field_names: Optional[list] = None,
                   user_id_type: str = "open_id",
                   ignore_consistency_check: bool = False) -> list:
        """
        内部方法：批量获取（单次请求）
        """
        path = f"/bitable/v1/apps/{self.app_token}/tables/{self.table_id}/records/batch_get"

        params = {"user_id_type": user_id_type}
        if ignore_consistency_check:
            params["ignore_consistency_check"] = ignore_consistency_check

        payload = {"record_ids": record_ids}
        if field_names:
            payload["field_names"] = field_names

        data = self._request("POST", path, params=params, json=payload)
        return data.get("records", [])

    # ==================== 查询 ====================

    def search_records(self, filter: Optional[dict] = None,
                        field_names: Optional[list] = None,
                        sort: Optional[list] = None,
                        automatic_fields: bool = False,
                        return_all: bool = False) -> list:
        """
        查询记录

        Args:
            filter: 筛选条件，格式：
                {
                    "conjunction": "and",  # or
                    "conditions": [
                        {"field_name": "字段名", "operator": "eq", "value": "值"}
                    ]
                }
                operator: eq/ne/gt/gte/lt/lte/is/is_not/contains/starts_with
            field_names: 指定返回的字段名列表
            sort: 排序条件，如 [{"field_name": "创建时间", "order": "desc"}]
            automatic_fields: 是否返回自动字段（创建时间等）
            return_all: 是否返回所有记录（自动分页）

        Returns:
            记录列表
        """
        all_records = []
        page_token = None

        while True:
            records, has_more, page_token = self._search(
                filter, field_names, sort, automatic_fields, page_token
            )
            all_records.extend(records)

            if not return_all or not has_more:
                break

        return all_records

    def _search(self, filter: Optional[dict] = None,
                field_names: Optional[list] = None,
                sort: Optional[list] = None,
                automatic_fields: bool = True,
                page_token: Optional[str] = None) -> tuple:
        """
        内部方法：单次查询
        """
        path = f"/bitable/v1/apps/{self.app_token}/tables/{self.table_id}/records/search"

        params = {}

        payload = {}
        if filter:
            payload["filter"] = filter
        if field_names:
            payload["field_names"] = field_names
        if sort:
            payload["sort"] = sort
        payload["automatic_fields"] = automatic_fields

        if page_token:
            params["page_token"] = page_token
        else:
            params["page_size"] = self.search_page_size

        data = self._request("POST", path, params=params, json=payload)

        items = data.get("items", [])
        has_more = data.get("has_more", False)
        new_page_token = data.get("page_token")

        return items, has_more, new_page_token

    def list_records(self, view_id: Optional[str] = None,
                    field_names: Optional[list] = None,
                    return_all: bool = False) -> list:
        """
        列出记录（使用视图筛选）

        Args:
            view_id: 视图 ID
            field_names: 指定返回的字段名列表
            return_all: 是否返回所有记录

        Returns:
            记录列表
        """
        all_records = []
        page_token = None

        while True:
            records, has_more, page_token = self._list(
                view_id, field_names, page_token
            )
            all_records.extend(records)

            if not return_all or not has_more:
                break

        return all_records

    def _list(self, view_id: Optional[str] = None,
              field_names: Optional[list] = None,
              page_token: Optional[str] = None) -> tuple:
        """
        内部方法：单次列表
        """
        path = f"/bitable/v1/apps/{self.app_token}/tables/{self.table_id}/records"

        params = {}
        if view_id:
            params["view_id"] = view_id
        if field_names:
            params["field_names"] = ",".join(field_names)

        if page_token:
            params["page_token"] = page_token
        else:
            params["page_size"] = self.search_page_size

        data = self._request("GET", path, params=params)

        items = data.get("items", [])
        has_more = data.get("has_more", False)
        new_page_token = data.get("page_token")

        return items, has_more, new_page_token


# ==================== 便捷函数 ====================

def create_filter(field_name: str, operator: str, value: Any,
                 conjunction: str = "and") -> dict:
    """
    创建单条件筛选器

    注意：筛选条件的 value 格式根据操作符不同而有差异：
    - is, is_not: value 必须是数组格式
    - contains, starts_with: value 必须是数组格式
    - eq, ne, gt, gte, lt, lte: value 可以是单个值或数组

    Args:
        field_name: 字段名
        operator: 操作符
                 文本字段: is, is_not, contains, starts_with, eq, ne
                 数字字段: eq, ne, gt, gte, lt, lte
        value: 值（单个值或数组）
        conjunction: 逻辑 (and/or)

    Returns:
        筛选条件字典
    """
    # 值需要转换为数组格式（is/is_not/contains 必须用数组）
    if operator in ("is", "is_not", "contains", "starts_with"):
        value_list = [value] if not isinstance(value, list) else value
    else:
        value_list = [value] if not isinstance(value, list) else value

    return {
        "conjunction": conjunction,
        "conditions": [
            {
                "field_name": field_name,
                "operator": operator,
                "value": value_list
            }
        ]
    }


def create_multi_filter(conditions: list, conjunction: str = "and") -> dict:
    """
    创建多条件筛选器

    Args:
        conditions: 条件列表，每项为 {"field_name": "", "operator": "", "value": ""}
                   value 可以是单个值或数组
        conjunction: 逻辑 (and/or)

    Returns:
        筛选条件字典
    """
    # 将所有 value 转换为数组格式
    formatted_conditions = []
    for c in conditions:
        value = c.get("value", "")
        value_list = [value] if not isinstance(value, list) else value
        formatted_conditions.append({
            "field_name": c.get("field_name"),
            "operator": c.get("operator"),
            "value": value_list
        })

    return {
        "conjunction": conjunction,
        "conditions": formatted_conditions
    }