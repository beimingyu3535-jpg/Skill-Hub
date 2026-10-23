"""Weaver 平台 HTTP 客户端 -- CATALOG + DESIGN 层.

设计目标
--------
让 ``generating-actionflows`` skill 在不依赖外部 MCP server 的前提下,直接调用
Weaver 平台接口拉取真实元数据并保存/回读动作流设计.

凭据来源(多环境)
-----------------
按优先级读取:
1. ``load_environment(path=...)`` 显式指定文件
2. 外部配置目录 ``WEAVER_CONFIG_DIR`` 下 ``environments/active`` 指向的环境
3. 外部配置目录下的 ``environment.json``
4. 环境变量兜底 ``WEAVER_BASE_URL`` / ``WEAVER_ETEAMSID`` / ``WEAVER_COOKIE``

默认外部配置目录为用户目录下的 ``.weaver-actionflows``。配置和凭据不属于
Skill 包，迁移 Skill 到其他环境时只需重新执行 ``env-add``，或设置环境变量。

激活环境文件格式:

    {
      "eteamSid": "PCACCOUNT_xxx",
      "baseUrl": "https://weapp.yunteams.cn",
      "defaultAppId": "",
      "defaultGroupId": ""
    }

切换环境: 使用 ``env-switch``，或修改外部配置目录下 ``environments/active``。
凭据文件不应放在 Skill 目录，也不应进入 Git 或分发包。

接口覆盖(http相关接口.txt)
---------------------------
CATALOG 层:
- ``list_apps``     -> GET  /api/ebuilder/common/ds/group
- ``list_forms``    -> POST /api/ebuilder/common/ds/list      (form-data)
- ``get_form_fields`` -> POST /api/bs/esb/setting/component/getEbField (JSON)

DESIGN 层:
- ``create_application``     -> POST /api/bs/esb/setting/application/save
- ``get_application``        -> GET  /api/bs/esb/setting/application/getAppById/{appId}
- ``get_version_list``       -> GET  /api/bs/esb/setting/application/version/versionList/{appId}
- ``save_stash_snapshot``    -> POST /api/bs/esb/setting/flow/design/saveStashSnapshot     (真机验证已通过)
- ``get_stash_snapshot``     -> POST /api/bs/esb/setting/flow/design/getStashSnapshot      (真机验证已通过)
- ``get_design``             -> GET  /api/bs/esb/setting/flow/design/getDesignBySceneId/{sceneId}

CONTEXT 层:
- ``search_workflows`` -> POST /api/workflow/pathdef/common/browser/condition/workflowPathBrowser
- ``list_workflow_nodes`` -> POST /api/workflow/pathdef/common/browser/complete/workflowPathNodeBrowser
- ``get_workflow_fields`` -> POST /api/bs/esb/setting/workflow/getWorkflowFields
- ``get_component_context`` -> POST /api/bs/esb/setting/component/getComponentContext
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from http.cookiejar import CookiePolicy
from pathlib import Path
from typing import Any

SKILL_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = Path(
    os.environ.get("WEAVER_CONFIG_DIR", str(Path.home() / ".weaver-actionflows"))
).expanduser()
ENV_FILE = CONFIG_DIR / "environment.json"
ENVIRONMENTS_DIR = CONFIG_DIR / "environments"
ACTIVE_FILE = ENVIRONMENTS_DIR / "active"

# ── 多环境管理 ─────────────────────────────────────────────────────────────

def env_list() -> list[dict[str, str]]:
    """列出所有环境."""
    envs: list[dict[str, str]] = []
    if not ENVIRONMENTS_DIR.is_dir():
        return envs
    active = env_current() or ""
    for f in sorted(ENVIRONMENTS_DIR.glob("*.json")):
        name = f.stem
        env = load_environment(f)
        envs.append({"name": name, "active": name == active,
                      "baseUrl": env.get("baseUrl", ""),
                      "hasCredential": bool(env.get("eteamSid") or env.get("cookie")),
                      "companyId": env.get("companyId", "")})
    return envs

def env_current() -> str | None:
    """获取当前激活的外部环境名."""
    if ACTIVE_FILE.is_file():
        return ACTIVE_FILE.read_text(encoding="utf-8").strip()
    if ENV_FILE.is_file():
        return "default"
    return None

def env_switch(name: str) -> bool:
    """切换到指定环境."""
    target = ENVIRONMENTS_DIR / f"{name}.json"
    if not target.is_file():
        return False
    ENVIRONMENTS_DIR.mkdir(parents=True, exist_ok=True)
    ACTIVE_FILE.write_text(name, encoding="utf-8")
    return True

def env_add(name: str, base_url: str, eteam_sid: str, *, company_id: str = "",
            use_system_proxy: bool = False) -> bool:
    """新增/覆盖一个环境."""
    ENVIRONMENTS_DIR.mkdir(parents=True, exist_ok=True)
    target = ENVIRONMENTS_DIR / f"{name}.json"
    target.write_text(json.dumps({
        "baseUrl": base_url, "eteamSid": eteam_sid,
        "defaultAppId": "", "defaultGroupId": "",
        "companyId": str(company_id), "useSystemProxy": bool(use_system_proxy),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return True

def env_delete(name: str) -> bool:
    """删除一个环境."""
    target = ENVIRONMENTS_DIR / f"{name}.json"
    if not target.is_file():
        return False
    target.unlink()
    # 如果删除的是当前激活的,清除 active
    if env_current() == name:
        ACTIVE_FILE.write_text("", encoding="utf-8")
    return True

# ── 凭据 / 配置 ────────────────────────────────────────────────────────────

class PlatformAuthError(RuntimeError):
    """ETEAMSID 失效或被网关拦截(401/403/307).刷新 environment.json 后重试."""

class PlatformRequestError(RuntimeError):
    """网络/HTTP 层错误(非鉴权),如超时、5xx、响应非 JSON."""

def load_environment(path: str | Path | None = None) -> dict[str, str]:
    """读取环境配置,返回连接、租户和网络选项。

    优先级:
      1. path 参数指定文件
      2. 外部 environments/active 指向的当前激活环境
      3. 外部 environment.json
      4. 环境变量兜底:WEAVER_BASE_URL / WEAVER_ETEAMSID / WEAVER_COOKIE /
         WEAVER_COMPANY_ID / WEAVER_USE_SYSTEM_PROXY
    """
    env: dict[str, str] = {
        "baseUrl": "", "eteamSid": "", "cookie": "",
        "defaultAppId": "", "defaultGroupId": "", "companyId": "",
        "useSystemProxy": "",
    }
    target: Path | None = None
    if path:
        target = Path(path)
    else:
        # 优先用激活环境
        active = env_current()
        if active and active != "default":
            candidate = ENVIRONMENTS_DIR / f"{active}.json"
            if candidate.is_file():
                target = candidate
        # 回退旧版
        if not target or not target.is_file():
            target = ENV_FILE

    if target and target.is_file():
        try:
            raw = json.loads(target.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                for key in env:
                    if key in raw and raw[key] is not None:
                        env[key] = str(raw[key])
        except (json.JSONDecodeError, OSError):
            pass
    # 环境变量兜底
    env["baseUrl"] = env["baseUrl"] or os.environ.get("WEAVER_BASE_URL", "")
    env["eteamSid"] = env["eteamSid"] or os.environ.get("WEAVER_ETEAMSID", "")
    env["cookie"] = env["cookie"] or os.environ.get("WEAVER_COOKIE", "")
    env["companyId"] = env["companyId"] or os.environ.get("WEAVER_COMPANY_ID", "")
    env["useSystemProxy"] = env["useSystemProxy"] or os.environ.get("WEAVER_USE_SYSTEM_PROXY", "")
    return env

def _cookie_header(env: dict[str, str]) -> str:
    """构造 Cookie 头.优先用完整 cookie 串,否则用 ETEAMSID=<eteamSid>."""
    if env.get("cookie"):
        return env["cookie"]
    sid = env.get("eteamSid", "")
    return f"ETEAMSID={sid}" if sid else ""

# ── HTTP 基础设施 ──────────────────────────────────────────────────────────

class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """禁止自动跟随重定向,以便捕获 307(ztrust 网关未鉴权拦截)."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D401
        return None  # 返回 None -> urllib 抛 HTTPError

def _build_opener(use_system_proxy: bool = False) -> urllib.request.OpenerDirector:
    """构造请求 opener；默认直连，受限网络可显式启用系统代理。"""
    handlers: list[urllib.request.BaseHandler] = [_NoRedirect]
    if not use_system_proxy:
        # 本机残留的失效 Clash/调试代理会让 urllib 全部请求失败，因此默认直连。
        handlers.append(urllib.request.ProxyHandler({}))
    return urllib.request.build_opener(*handlers)

class PlatformClient:
    """Weaver 平台 HTTP 客户端.所有方法返回解析后的 JSON(dict/list)."""

    def __init__(self, base_url: str, eteam_sid: str = "", *, cookie: str = "",
                 timeout: int = 0, company_id: str = "", use_system_proxy: bool = False) -> None:
        self.base_url = base_url.rstrip("/")
        self.cookie = cookie or (f"ETEAMSID={eteam_sid}" if eteam_sid else "")
        self.timeout = timeout  # 0=auto(: 普通10s/慢接口30s); >0 显式覆盖
        self.company_id = str(company_id or "")
        self.use_system_proxy = bool(use_system_proxy)
        if not self.base_url:
            raise PlatformRequestError("baseUrl 未配置;请填写 environment.json")
        if not self.cookie:
            raise PlatformRequestError("eteamSid 未配置;请填写 environment.json")

    # ── 底层请求 ──

    #: 慢接口白名单 — 查询类接口响应可能大/慢, 单接口超时放宽到 30s;
    # 其余接口 10s. 验证平台正常响应 <2s, 余量 6~20 倍.
    _SLOW_ENDPOINT_MARKERS = (
        "getComponentContext", "getFieldData", "getWorkflowField",
        "workflow/search", "recipient", "connector", "condition/save", "condition/get",
    )

    def _request(
        self,
        path: str,
        method: str = "POST",
        json_body: dict[str, Any] | None = None,
        form_body: dict[str, Any] | None = None,
        query: dict[str, Any] | None = None,
    ) -> Any:
        url = self.base_url + path
        if query:
            url += ("&" if "?" in url else "?") + urllib.parse.urlencode(query)

        data: bytes | None = None
        headers: dict[str, str] = {"Cookie": self.cookie}

        if json_body is not None:
            data = json.dumps(json_body, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json; charset=utf-8"
        elif form_body is not None:
            # Weaver "form-data" 接口验证多接受 application/x-www-form-urlencoded;
            # 若 raw-fetch 显示该编码被拒,再切换为 multipart.
            data = urllib.parse.urlencode(form_body).encode("utf-8")
            headers["Content-Type"] = "application/x-www-form-urlencoded; charset=utf-8"

        #: 单接口超时 — 显式设置覆盖, 否则按慢接口白名单自动 30s/10s
        if self.timeout > 0:
            timeout = self.timeout
        else:
            timeout = 30 if any(m in path for m in self._SLOW_ENDPOINT_MARKERS) else 10

        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        opener = _build_opener(self.use_system_proxy)
        raw: bytes | None = None
        last_err: Exception | None = None
        #: 可恢复失败 (网络错误/超时/HTTP 5xx) 重试 1 次 —
        # 用户原则"宁可多花时间, 不让能生成的东西生成不了"; 401/403/3xx/4xx 不重试.
        for attempt in range(2):
            try:
                with opener.open(req, timeout=timeout) as resp:
                    raw = resp.read()
                last_err = None
                break
            except urllib.error.HTTPError as exc:
                code = exc.code
                snippet = ""
                try:
                    snippet = exc.read().decode("utf-8", errors="replace")[:300]
                except Exception:
                    pass
                if code in (401, 403):
                    raise PlatformAuthError(
                        f"HTTP {code}:ETEAMSID 失效或无权限.请刷新 environment.json 的 eteamSid."
                        f" 响应片段: {snippet}"
                    ) from exc
                if code in (301, 302, 303, 307, 308):
                    raise PlatformAuthError(
                        f"HTTP {code} 重定向(疑似 ztrust 网关未鉴权拦截)."
                        "请确认 eteamSid 有效且 baseUrl 指向正确网关."
                        f" Location: {exc.headers.get('Location', '')}"
                    ) from exc
                err = PlatformRequestError(f"HTTP {code} 请求失败: {snippet}")
                if code >= 500 and attempt == 0:
                    last_err = err  # 5xx 首次 → 重试 1 次
                    continue
                raise err
            except urllib.error.URLError as exc:
                err = PlatformRequestError(f"网络错误: {exc.reason}")
                if attempt == 0:
                    last_err = err  # 网络错误/超时 → 重试 1 次
                    continue
                raise err
        if last_err is not None:
            raise last_err
        if not raw:
            return {}
        try:
            return json.loads(raw.decode("utf-8", errors="replace"))
        except json.JSONDecodeError as exc:
            raise PlatformRequestError(
                f"响应非 JSON: {raw[:300]!r}"
            ) from exc

    # ── CATALOG 接口 ──

    def list_apps(self) -> Any:
        """第一步:获取应用列表(ds/group).

        http相关接口.txt 标注 form-data,但 URL 已带查询参数,验证 GET 即可.
        """
        return self._request(
            "/api/ebuilder/common/ds/group",
            method="GET",
            query={
                "sourceType": "FORM",
                "showSqlDataset": "true",
                "appId": "default",
            },
        )

    def list_forms(self, group_id: str) -> Any:
        """第二步:获取某应用/分组下的表单列表(ds/list,form-data)."""
        return self._request(
            "/api/ebuilder/common/ds/list",
            method="POST",
            form_body={
                "groupId": group_id,
                "sourceType": "FORM",
                "dataUsage": "all",
                "otherParams": json.dumps({"terminal": "1"}, ensure_ascii=False),
            },
        )

    def get_form_fields(self, table_id: str, app_id: str) -> Any:
        """获取表单字段(getEbField,JSON).tableId 即 formId."""
        return self._request(
            "/api/bs/esb/setting/component/getEbField",
            method="POST",
            json_body={"tableId": table_id, "appId": app_id},
        )

    # ── 流程 / 上下文接口 ───────────────────────────────────────────────

    def get_workflow_browser_schema(self) -> Any:
        """读取流程选择器的筛选条件定义,不返回流程记录列表."""
        return self._request(
            "/api/workflow/pathdef/common/browser/condition/workflowPathBrowser",
            method="POST",
            json_body={"checkDetachable": True, "permissionCode": 3, "status": 1},
        )

    def search_workflows(self, search_value: str = "") -> Any:
        """按关键词查询当前登录账号可选择的流程.

        Browser 的 ``complete`` 接口支持名称关键词搜索,响应位于
        ``data.data``.它只适合名称明确时的候选缩小,不用于全量浏览.
         complete 接口对部分中文名不稳定(搜"采购合同报备"返回空) —
        全量浏览用 list_workflows_browser (data 接口 + 本地过滤).
        """
        return self._request(
            "/api/workflow/pathdef/common/browser/complete/workflowPathBrowser",
            method="POST",
            json_body={
                "checkDetachable": True,
                "permissionCode": 3,
                "status": 1,
                "newly": 1,
                "searchValue": search_value,
            },
        )

    def list_workflows_browser(self, page_size: int = 500,
                               search_key: str = "") -> list[dict]:
        """全量列出当前账号可选择的流程 (Browser data 接口, 可靠).

         前端源码实证: workflowPathBrowser 的 ``data`` 接口一次返回全部流程
        (searchKey 参数无效, 必须本地过滤). 记录含 id/name/formIds/fixedVersionId/
        activeWfId/bridgeService 等. 替代不可靠的 search_workflows.
        """
        if page_size < 1:
            raise ValueError("page_size must be >= 1")
        all_rows: list[dict] = []
        seen_pages: set[tuple[str, ...]] = set()
        current = 1
        while True:
            r = self._request(
                "/api/workflow/pathdef/common/browser/data/workflowPathBrowser",
                method="POST",
                json_body={
                    "checkDetachable": True, "permissionCode": 3, "status": 1,
                    "pageSize": page_size, "current": current, "searchKey": search_key,
                },
            )
            data = r.get("data", {}) if isinstance(r, dict) else {}
            rows = data.get("data", []) if isinstance(data, dict) else []
            rows = [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []
            # 某些版本忽略 current/pageSize 而反复返回首屏；不能因此无限请求。
            signature = tuple(str(row.get("id") or row.get("workflowId") or row) for row in rows)
            if signature and signature in seen_pages:
                return all_rows
            if signature:
                seen_pages.add(signature)
            all_rows.extend(rows)
            total = 0
            if isinstance(data, dict):
                for key in ("total", "count", "totalCount"):
                    try:
                        total = int(data.get(key) or 0)
                    except (TypeError, ValueError):
                        total = 0
                    if total:
                        break
            if not rows or len(rows) < page_size or (total and len(all_rows) >= total):
                return all_rows
            current += 1

    def list_workflows(self, *, current: int = 1, page_size: int = 30) -> Any:
        """分页浏览当前账号可选择的流程目录.

        ``data/workflowPathBrowser`` 返回具体流程记录,并在每条记录中提供
        ``workflowtype`` 与 ``workflowTypeName``,调用方可据此按流程类型分组.
        """
        if current < 1:
            raise ValueError("current must be >= 1")
        if not 1 <= page_size <= 100:
            raise ValueError("pageSize must be between 1 and 100")
        return self._request(
            "/api/workflow/pathdef/common/browser/data/workflowPathBrowser",
            method="POST",
            json_body={
                "checkDetachable": True,
                "permissionCode": 3,
                "status": 1,
                "newly": 1,
                "searchValue": "",
                "current": current,
                "pageSize": page_size,
            },
        )

    def search_recipients(
        self, search_value: str = "", *, current: int = 1, page_size: int = 30,
        company_id: str = "",
    ) -> Any:
        """分页查询当前账号在"所有人"范围可选的正常人员.

        这是资源浏览器点击"所有人"时的 ``data/resource`` 请求.当前页
        记录位于 ``data.data``.``quickSearchDatas.username`` 支持前端搜索框的
        姓名、拼音、部门名称、工号或手机号检索.该接口的 ``data.count`` 在验证
        中可能为 0,不能作为总数;调用方以"本页少于 pageSize 或下一页为空"停止翻页.
        """
        if current < 1:
            raise ValueError("current must be >= 1")
        if not 1 <= page_size <= 100:
            raise ValueError("pageSize must be between 1 and 100")
        return self._request(
            "/api/hrm/common/browser/data/resource",
            method="POST",
            json_body={
                "browserMultiple": True,
                "authWecahtBook": False,
                "wxDepNeedConvertCount": 0,
                "wxEmpNeedConvertCount": 0,
                "wxTotalNeedConvertCount": 0,
                "cmd": "all",
                "pageSize": page_size,
                "current": current,
                "formDatas": {
                    "username": [{"usernameOpt": "in"}],
                    "status": [{"statusSelect": ["normal"]}],
                    "subcompany": [{"subcompanyOpt": "in"}],
                    "department": [{"departmentOpt": "in"}],
                    "role": [{"roleOpt": "in"}],
                "position": [{"positionOpt": "in"}],
                },
                "quickSearchDatas": {
                    "username": search_value,
                    "status": "",
                    "subcompany": "",
                    "department": "",
                    "role": "",
                    "position": "",
                },
                "type": "and",
                "containsNoneAccount": False,
                "containsPartTimeEmployee": False,
                "companyId": str(company_id or self.company_id or "1"),
            },
        )

    def resolve_application_org_id(self) -> str:
        """返回当前租户新建动作流所需的机构 ID。

        非分权租户保持空值；分权租户从与前端相同的入口权限和机构树接口读取
        当前账号可用的第一个机构，绝不复用其它租户的 ID。探测失败时返回空值，
        由后端维持原有兼容行为。
        """
        try:
            entrance = self._request(
                "/api/bs/ebuilder/app/permit/entrance", method="GET")
            data = entrance.get("data", {}) if isinstance(entrance, dict) else {}
            if not (entrance.get("code") == 200 and isinstance(data, dict)
                    and data.get("isDetachable")):
                return ""
            tree = self._request(
                "/api/hrm/common/getOrgTree?menuCode=eBuilder&onlySubcompany=false"
                "&containDisableDept=false&moduleCode=EBUILDER&virtualId=1"
                "&loadCount=false&isMobile=false", method="GET")
            rows = tree.get("data", []) if isinstance(tree, dict) else []
            if tree.get("code") == 200 and isinstance(rows, list) and rows:
                first = rows[0]
                if isinstance(first, dict):
                    return str(first.get("id", "") or "")
        except (PlatformAuthError, PlatformRequestError):
            pass
        return ""

    def list_workflow_nodes(self, workflow_id: str, search_value: str = "") -> Any:
        """查询指定流程可作为触发点/出口的节点."""
        return self._request(
            "/api/workflow/pathdef/common/browser/complete/workflowPathNodeBrowser",
            method="POST",
            json_body={
                "workflowId": str(workflow_id),
                "nodeAttrs": "1,3",
                "nodeAttrsCondition": 3,
                "newly": 0,
                "searchValue": search_value,
            },
        )

    def get_workflow_fields(self, workflow_id: str, target_table_id: str) -> Any:
        """查询流程与已选目标表单之间的回写字段映射候选。

        前端 ``ActionEbAdd/ActionEbUpdate`` 传入的 ``objId`` 是当前节点
        ``tableType[0].id``，即目标 e-builder 表单 ID，不是工作流节点 ID。
        该接口服务于“回写数据 ID 对应字段”，不能替代触发器上下文查询。
        """
        return self._request(
            "/api/bs/esb/setting/workflow/getWorkflowFields",
            method="POST",
            json_body={
                "workflowModule": "workflow",
                "workflowId": str(workflow_id),
                "objId": str(target_table_id),
            },
        )

    def get_condition_visible_fields(
        self, workflow_id: str, source_id: str, source: int = 2,
        tab: str = "formField",
    ) -> list[dict[str, Any]]:
        """查询 Condition 设计器真实可见字段 (e10-cli 同款).

        用 ``/api/workflow/pathdef/common/browser/complete/conditionFieldBrowser``
        (source=2 workflow / source=8 esb). 这是设计器右栏字段的权威源,
        workflow-fields API 返回的字段和它不一致 (子表单/关联浏览字段差异).
        """
        resp = self._request(
            "/api/workflow/pathdef/common/browser/complete/conditionFieldBrowser",
            method="POST",
            json_body={
                "browserMultiple": False,
                "sourceId": str(source_id),
                "tab": tab,
                "source": int(source),
                "workflowId": str(workflow_id),
                "newly": 1,
                "searchValue": "",
            },
        )
        items = (resp.get("data") or {}).get("data") or []
        return [f for f in items if isinstance(f, dict)] if isinstance(items, list) else []

    def get_data_source_fields(
        self, source_id: str, group_id: str = "", source_type: str = "FORM"
    ) -> Any:
        """查询数据源(主表+明细)所有可选字段 — 含业务字段 + 平台系统变量
        (数据ID/创建者/创建时间/最后更新时间/最后更新人/数据状态/我的标签/公共标签/标题).

        POST /api/bs/esb/setting/component/showDataSourceFields
        返回 [{formId, formName, fields:[{id, content, parseMark, type, dbFieldType, fieldGroup}]}]
        业务字段 id=数字字段id; 系统变量 id=英文字符串 ('id'/'name'/'creator'/...)
        用于 TimeBatchTrigger.queryFields 全选 (业务+系统变量).
        """
        return self._request(
            "/api/bs/esb/setting/component/showDataSourceFields",
            method="POST",
            json_body={
                "sourceId": str(source_id),
                "groupId": str(group_id),
                "sourceType": str(source_type or "FORM"),
            },
        )

    def get_component_context(self, component_type: str, data: dict[str, Any]) -> Any:
        """以设计器节点完整 data 查询后续节点可引用的上下文."""
        if not isinstance(data, dict):
            raise ValueError("get_component_context.data must be an object")
        return self._request(
            "/api/bs/esb/setting/component/getComponentContext",
            method="POST",
            json_body={"type": component_type, "data": data},
        )

    def get_meeting_fields(self) -> Any:
        """读取 MeetingCreate 前端设置弹窗的真实基础字段/选项定义。"""
        return self._request(
            "/api/bs/esb/setting/component/getMeetingField",
            method="POST",
            json_body={},
        )

    def get_custom_meeting_fields(self) -> Any:
        """读取 MeetingCreate 前端设置弹窗的真实自定义表单定义。"""
        return self._request(
            "/api/bs/esb/setting/component/getCustomMeetingField",
            method="POST",
            json_body={},
        )
        """以设计器节点完整 data 查询后续节点可引用的上下文."""
        if not isinstance(data, dict):
            raise ValueError("get_component_context.data must be an object")
        return self._request(
            "/api/bs/esb/setting/component/getComponentContext",
            method="POST",
            json_body={"type": component_type, "data": data},
        )

    # ── DESIGN 层接口 ──

    def create_application(
        self,
        name: str,
        description: str = "",
        app_type: int = 0,
        org_id: str = "",
        module: str = "esb",
        app_sources: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """创建/初始化 ESB 应用(暂存的前置条件).

        POST /api/bs/esb/setting/application/save
        id="" 表示新建;与设计器和跨租户 CLI 的真实载荷一致，后端返回
        {code,data:{id:appId,activeVersion,...}}。部分租户将 "-1" 当作更新占位值，
        会返回表面 ID 却不初始化可暂存的动作流实体。
        """
        return self._request(
            "/api/bs/esb/setting/application/save",
            method="POST",
            json_body={
                "type": app_type,
                "name": name,
                "orgId": org_id,
                "description": description,
                "id": "",
                "moudle": str(module or "esb"),
                "appSources": list(app_sources or []),
                "lightId": "",
                "initData": "",
                "templateId": "",
                "templateVersionId": "",
            },
        )

    def get_application(self, app_id: str) -> dict[str, Any]:
        """查询应用详情(含 activeVersion / secretKey).

        GET /api/bs/esb/setting/application/getAppById/{appId}
        """
        return self._request(
            f"/api/bs/esb/setting/application/getAppById/{app_id}",
            method="GET",
        )

    def recycle_application(self, app_id: str) -> dict[str, Any]:
        """软删除应用(进回收站) — 仅用于回收"本次会话新建且最终未保存成功"的空应用.

        POST /api/bs/esb/setting/application/addRecycle
        body = {id, name, appInfo} — appInfo 需完整应用信息, 先 getAppById 拉取.
        软删除后可手动恢复; 平台无硬删接口.
        """
        info = self.get_application(str(app_id))
        app_info = info.get("data", info) if isinstance(info, dict) else info
        name = str(app_info.get("name", "")) if isinstance(app_info, dict) else ""
        response = self._request(
            "/api/bs/esb/setting/application/addRecycle",
            method="POST",
            json_body={"id": str(app_id), "name": name, "appInfo": app_info},
        )
        data = response.get("data") if isinstance(response, dict) else None
        success_ids = data.get("successAppIds") if isinstance(data, dict) else None
        failed = data.get("failDelExt") if isinstance(data, dict) else None
        if isinstance(success_ids, list) and str(app_id) in {str(item) for item in success_ids}:
            return response
        # 后端会把前置校验失败包装成 HTTP 200 + 空 successAppIds；不能据此宣称已回收。
        # 少数版本不回传 successAppIds，因此再以详情不可见作为最终证据。
        verify = self.get_application(str(app_id))
        if isinstance(verify, dict) and verify.get("status") is False:
            return response
        reason = failed if failed else "addRecycle 未返回 successAppIds，且应用仍可查询"
        raise PlatformRequestError(f"动作流 {app_id} 回收未确认: {reason}")

    def get_version_list(self, app_id: str) -> dict[str, Any]:
        """查询应用的版本/场景列表(含 secretKey).

        GET /api/bs/esb/setting/application/version/versionList/{appId}
        返回 {data:{actionFlowVersions:[{id,flowId,secretKey,...}],activeVersion}}
        """
        return self._request(
            f"/api/bs/esb/setting/application/version/versionList/{app_id}",
            method="GET",
        )

    def check_design(self, design: dict[str, Any]) -> dict[str, Any]:
        """校验动作流设计(check, 保存前预检, 验证可用).

        POST /api/bs/esb/setting/flow/design/check
        前端证据 (weapp-esb-develop/src/components/efdesigner/store.ts:2444-2452):
        ``onCheckDataByBack`` 用 formatAjaxDataByFront() 调 flow/design/check,
        载荷为当前设计结构 ({appId, sceneId, event, actions, addIds,
        deleteActions, version, addCheckMsg, assistLayer, versionConfig, ...}).

        用途: 暂存前调用，提前暴露组件结构/字段引用问题，避免平台 500。
        """
        payload: dict[str, Any] = {
            "appId": design.get("appId", ""),
            "sceneId": design.get("sceneId", ""),
            "event": design.get("event"),
            "actions": design.get("actions", []),
            "assistLayer": design.get("assistLayer", "{}"),
            "versionConfig": "{}",
            "version": design.get("version", 1),
            "addIds": design.get("addIds", []),
            "deleteActions": design.get("deleteActions", []),
            "addCheckMsg": [],
            "saveAndStart": False,
            "secretKey": design.get("secretKey", ""),
            "reloadFormula": design.get("reloadFormula", []),
        }
        return self._request(
            "/api/bs/esb/setting/flow/design/check",
            method="POST",
            json_body=payload,
        )

    def save_stash_snapshot(self, design: dict[str, Any]) -> dict[str, Any]:
        """保存动作流设计为暂存(saveStashSnapshot,真机验证已通过).

        POST /api/bs/esb/setting/flow/design/saveStashSnapshot

        前端证据(weapp-esb-develop/src/components/efdesigner/store.ts:2653-2674):
        ``onTemporarySave`` 的请求体是三段嵌套结构 ``{appId, versionId, storeInfo}``,
        而不是旧版扁平 ``{appId, sceneId, event, actions, ...}`` 结构。
        """
        store_info: dict[str, Any] = {
            "saveAndStart": design.get("saveAndStart", False),
            "appId": design.get("appId", ""),
            "sceneId": design.get("sceneId", ""),
            "event": design.get("event"),
            "actions": design.get("actions", []),
            "assistLayer": design.get("assistLayer", "{}"),
            "versionConfig": design.get("versionConfig", "{}"),
            "version": design.get("version", 1),
            "addIds": design.get("addIds", []),
            "deleteActions": design.get("deleteActions", []),
            "addCheckMsg": design.get("addCheckMsg", []),
            "secretKey": design.get("secretKey", ""),
            "reloadFormula": design.get("reloadFormula", []),
            "saveNewVersion": False,
            "lightId": "",
            "initData": "",
            "versionDes": None,
            "operateType": "",
            "appName": "",
        }
        payload: dict[str, Any] = {
            "appId": design.get("appId", ""),
            "versionId": design.get("sceneId", ""),
            "storeInfo": store_info,
        }
        return self._request(
            "/api/bs/esb/setting/flow/design/saveStashSnapshot",
            method="POST",
            json_body=payload,
        )

    def get_design(self, scene_id: str) -> dict[str, Any]:
        """Read design back for self-verification after save.

        GET /api/bs/esb/setting/flow/design/getDesignBySceneId/{sceneId}
        Returns: {code:200, status:true, data:{appId,sceneId,event,actions,assistLayer,...}}
        """
        return self._request(
            f"/api/bs/esb/setting/flow/design/getDesignBySceneId/{scene_id}",
            method="GET",
        )

    def get_stash_snapshot(self, app_id: str, version_id: str) -> dict[str, Any]:
        """读取指定应用版本的暂存设计。

        POST /api/bs/esb/setting/flow/design/getStashSnapshot

        前端 ``efdesigner/store.ts#getTempStoreInfoById`` 使用相同请求体。返回的
        ``data`` 是与 ``getDesignBySceneId`` 同构的设计对象，可直接用于
        ``verify_design_readback``；不能误用正式版本的 get_design 读取暂存。
        """
        return self._request(
            "/api/bs/esb/setting/flow/design/getStashSnapshot",
            method="POST",
            json_body={"appId": str(app_id), "versionId": str(version_id)},
        )

    # ── 流程节点绑定 ──

    def save_add_action_list(self, workflow_id: str, node_id: str,
                             actions: list[dict[str, Any]],
                             trigger_type: str = "pre",
                             obj_name: str = "") -> dict[str, Any]:
        """将动作流绑定到流程节点的触发事件.

        POST /api/bs/workflow/pathdef/addaction/saveAddActionList
        """
        return self._request(
            "/api/bs/workflow/pathdef/addaction/saveAddActionList",
            method="POST",
            json_body={
                "workflowId": str(workflow_id),
                "objId": str(node_id),
                "triggerType": trigger_type,
                "data": actions,
                "isNodeFlag": "1",
                "objName": str(obj_name),
            },
        )

    # ── 条件表达式 ─────────────────────────────────────────────────────

    def get_condition_set(self, workflow_id: str, source_id: str,
                          condition_name: str = "AI_COND") -> dict[str, Any]:
        """获取条件表达式 mapBaseId (e10-cli getConditionSet).

        POST /api/workflow/pathdef/rule/condition/getConditionSet
        """
        return self._request(
            "/api/workflow/pathdef/rule/condition/getConditionSet",
            method="POST",
            json_body={
                "source": 8, "sourceId": str(source_id),
                "workflowId": str(workflow_id),
                "conditionName": condition_name,
                "needFormfield": True, "readOnly": False,
                "templateTokenId": str(int(time.time() * 1000)),
            },
        )

    def save_condition(self, workflow_id: str, source_id: str,
                       map_base_id: str, childrens: list,
                       condition_name: str = "AI_COND",
                       relation: int = 1) -> dict[str, Any]:
        """保存条件表达式, 返回 server 分配的 conditionId/mapId/conditionCn.

        POST /api/workflow/pathdef/rule/condition/saveCondition
        """
        return self._request(
            "/api/workflow/pathdef/rule/condition/saveCondition",
            method="POST",
            json_body={
                "source": 8, "sourceId": str(source_id),
                "workflowId": str(workflow_id),
                "conditionName": condition_name,
                "needFormfield": True, "readOnly": False,
                "mapBaseId": str(map_base_id),
                "isEdit": False, "isFromRuleListPage": True,
                "relation": relation,
                "childrens": childrens,
                "allRuleIsEmpty": False,
            },
        )

    def esb_get_condition_set(self) -> str:
        """ESB 动作流条件 mapBaseId (RuleDesigner 用 GET).

        GET /api/bs/esb/setting/condition/getConditionSet
        返回 data (str mapBaseId); 失败返回 "".
        """
        resp = self._request(
            "/api/bs/esb/setting/condition/getConditionSet",
            method="GET",
        )
        data = resp.get("data") if isinstance(resp, dict) else None
        return str(data) if data else ""

    def esb_save_condition(self, workflow_id: str, source_id: str,
                           map_base_id: str, childrens: list,
                           condition_name: str = "AI_COND",
                           relation: int = 1) -> dict[str, Any]:
        """ESB 动作流条件保存 (RuleDesigner 专用端点).

        POST /api/bs/esb/setting/condition/saveCondition
        返回含 conditionId/conditionKey/mapId/conditionCn/conditionDataJson.
        """
        return self._request(
            "/api/bs/esb/setting/condition/saveCondition",
            method="POST",
            json_body={
                "source": 8, "sourceId": str(source_id),
                "workflowId": str(workflow_id),
                "conditionName": condition_name,
                "conditionCn": "",
                "needFormfield": True, "readOnly": False,
                "mapBaseId": str(map_base_id),
                "mapId": "", "conditionId": "",
                "isEdit": False, "isFromRuleListPage": True,
                "relation": relation,
                "allRuleIsEmpty": False,
                "childrens": childrens,
            },
        )

# ── 工厂 ──────────────────────────────────────────────────────────────────

def make_client(env: dict[str, str] | None = None) -> PlatformClient:
    """从 load_environment() 构造 PlatformClient."""
    if env is None:
        env = load_environment()
    return PlatformClient(
        base_url=env.get("baseUrl", ""),
        eteam_sid=env.get("eteamSid", ""),
        cookie=env.get("cookie", ""),
        company_id=env.get("companyId", ""),
        use_system_proxy=str(env.get("useSystemProxy", "")).strip().casefold() in {"1", "true", "yes", "on"},
    )

# ── 保存后回读校验 ────────────────────────────────────────────────────────

def _first_id(value: Any) -> str:
    """取浏览器值的稳定资源 ID，不比较保存时生成的节点/公式 ID。"""
    if isinstance(value, list):
        return _first_id(value[0]) if value else ""
    if isinstance(value, dict):
        for key in ("id", "sourceId", "formId", "workflowId"):
            if value.get(key) not in (None, ""):
                return str(value[key])
    return ""

def _formula_contract(value: Any) -> dict[str, Any]:
    """抽取 formula 的语义字段，忽略平台保存时重写的 ID、位置和排序字段。"""
    if not isinstance(value, dict):
        return {"literal": value}

    config = value.get("config")
    # config 可能是 JSON 字符串 (formula_fixed 生成 "{\"switchType\":\"fixvalue\"...}")
    if isinstance(config, str) and config.strip():
        try:
            parsed = json.loads(config)
            config = parsed if isinstance(parsed, dict) else {}
        except Exception:
            config = {}
    if not isinstance(config, dict):
        config = {}
    result: dict[str, Any] = {}
    # fieldType 由目标字段决定, 保存后服务端会剥离, 不能进契约
    for key in ("type", "formulaType", "value", "name"):
        if key in value and value[key] not in (None, ""):
            result[key] = value[key]
    # configObject 是 UI 专用结构, 保存后服务端会剥离, 不能进契约
    for key in ("paramKey", "switchType", "basisType", "functionType"):
        if key in config and config[key] not in (None, ""):
            result.setdefault("config", {})[key] = config[key]
    if isinstance(value.get("childs"), list):
        result["childs"] = [_formula_contract(item) for item in value["childs"]]
    return result

def _setting_contract(setting: Any) -> dict[str, Any]:
    """抽取 e-builder 字段映射：目标字段 + 固定/动态赋值语义。"""
    if not isinstance(setting, dict):
        return {}
    result: dict[str, Any] = {}
    for scope in ("main", "detail"):
        fields = setting.get(scope)
        if not isinstance(fields, dict):
            continue
        mapped: dict[str, Any] = {}
        for field_id, entry in fields.items():
            value = entry.get("value", {}) if isinstance(entry, dict) else {}
            if not isinstance(value, dict):
                continue
            item: dict[str, Any] = {
                "original": bool(value.get("original", False)),
            }
            for key in ("fieldKey", "switchType", "fieldType", "operate"):
                if key in value and value[key] not in (None, ""):
                    item[key] = value[key]
            if isinstance(value.get("assign"), dict):
                item["assign"] = _formula_contract(value["assign"])
            mapped[str(field_id)] = item
        if mapped:
            result[scope] = mapped
    return result

def _filter_contract(value: Any) -> Any:
    """保留筛选条件的字段、运算符和值，去掉 UI 生成的 key/节点 ID。

    conditions.value 在真实设计里是公式 bean(固定值 type=1 或上下文 type=3),
    服务端保存时可能重分配 id/frontId, 因此只提取语义签名(字符串值),
    避免回读比对因平台规范化产生误报.
    """
    if not isinstance(value, dict):
        return value

    def _cond_value_sig(v: Any) -> Any:
        if isinstance(v, dict):
            # 固定值/上下文公式: 取 value 字段(如 "病假" 或 "FormData.xxx")
            return v.get("value", v.get("name", ""))
        return v

    if isinstance(value.get("datas"), list):
        items = []
        for item in value["datas"]:
            if not isinstance(item, dict):
                continue
            condition = item.get("conditions", {})
            items.append({
                "fieldName": item.get("fieldName", ""),
                "fieldType": item.get("fieldType", ""),
                "optionType": item.get("optionType", ""),
                "conditions": {
                    key: condition.get(key, "")
                    for key in ("func", "text", "type")
                } | {"value": _cond_value_sig(condition.get("value"))}
                if isinstance(condition, dict) else {},
            })
        return {"relationship": value.get("relationship", ""), "datas": items}
    return value

def _condition_contract(value: Any) -> dict[str, Any]:
    """校验条件可读表达式及其引用 paramKey，不依赖平台生成的 conditionId。"""
    if not isinstance(value, dict):
        return {}
    result = {"conditionCn": value.get("conditionCn", "")}
    raw = value.get("conditionDataJson")
    try:
        parsed = json.loads(raw) if isinstance(raw, str) and raw else raw
    except json.JSONDecodeError:
        parsed = None

    keys: list[str] = []
    def collect(obj: Any) -> None:
        if isinstance(obj, dict):
            config = obj.get("config")
            if isinstance(config, dict) and config.get("paramKey"):
                keys.append(str(config["paramKey"]))
            for child in obj.values():
                collect(child)
        elif isinstance(obj, list):
            for child in obj:
                collect(child)
    collect(parsed)
    if keys:
        result["paramKeys"] = sorted(set(keys))
    return result

def _node_contract(node: Any) -> dict[str, Any]:
    """生成跨保存稳定的节点契约，用于 send/readback 深度比对。"""
    if not isinstance(node, dict):
        return {}
    data = node.get("data", {}) if isinstance(node.get("data"), dict) else {}
    result: dict[str, Any] = {"type": node.get("type", "")}
    for key in ("opType", "rate", "startTime", "triggerType", "executeMethod", "outputStatus"):
        if key in data:
            result[key] = data[key]
    for key in ("workflowPath", "targetForm"):
        resource_id = _first_id(data.get(key))
        if resource_id:
            result[f"{key}Id"] = resource_id
    target_form = data.get("targetForm")
    if isinstance(target_form, dict) and _first_id(target_form):
        # ``id`` alone is an incomplete e-builder reference: the designer
        # renders the selected form from text/groupName.  Include them in the
        # round-trip contract so an empty target selector cannot pass readback.
        result["targetFormDisplay"] = {
            "text": str(target_form.get("text") or ""),
            "groupName": str(target_form.get("groupName") or ""),
        }
    # workflowId/workflowModule 仅 Add/Update 继承流程绑定; Delete 平台数据无此字段
    if node.get("type") in ("ActionEbAdd", "ActionEbUpdate"):
        for key in ("workflowId", "workflowModule"):
            if data.get(key) not in (None, ""):
                result[key] = str(data[key])
    if data.get("msgContent") not in (None, ""):
        result["msgContent"] = _formula_contract(data["msgContent"])
    if data.get("msgTitle") not in (None, ""):
        result["msgTitle"] = _formula_contract(data["msgTitle"])
    if isinstance(data.get("person"), dict):
        result["person"] = _formula_contract(data["person"])
    # 公式型组件 (ScheduleCreate/MeetingCreate): 顶层公式字段做语义契约
    formula_fields = {
        "ScheduleCreate": ("title", "startTime", "endTime", "content", "creatorUser", "participants"),
        "MeetingCreate": ("operators",),
    }
    for key in formula_fields.get(node.get("type", ""), ()):
        if isinstance(data.get(key), dict):
            result[key] = _formula_contract(data[key])
    if isinstance(data.get("setting"), dict):
        # MeetingCreate 的 setting 是 Map<字段key, FormulaBean>, 与表单 setting 不同
        if node.get("type") == "MeetingCreate":
            result["setting"] = {
                k: _formula_contract(v) for k, v in data["setting"].items()
                if isinstance(v, dict)
            } or None
        else:
            # main"是误判 (假 formFieldKey 导致 main 没入库); formFieldKey='' 后
            # main 正常回读 (23 字段), 必须参与 _setting_contract 深度比对.
            result["setting"] = _setting_contract(data["setting"])
    if "filterInput" in data:
        result["filterInput"] = _filter_contract(data["filterInput"])
    if isinstance(data.get("conditionDetail"), dict):
        result["condition"] = _condition_contract(data["conditionDetail"])
    if node.get("type") == "Condition":
        result["branches"] = {
            "true": [_node_contract(item) for item in data.get("trueBranchActions", [])],
            "false": [_node_contract(item) for item in data.get("falseBranchActions", [])],
            "other": [
                {
                    "name": item.get("branchName", ""),
                    "condition": _condition_contract(item.get("conditionDetail", {})),
                    "actions": [_node_contract(action) for action in item.get("branchActions", [])],
                }
                for item in data.get("otherConditionBranch", []) if isinstance(item, dict)
            ],
        }
    return result

def _compare_contract(expected: Any, actual: Any, path: str = "") -> list[str]:
    """expected 必须是 actual 的语义子集；actual 可包含平台补充默认字段。"""
    issues: list[str] = []
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return [f"{path or '$'} expected object, got {type(actual).__name__}"]
        for key, value in expected.items():
            child_path = f"{path}.{key}" if path else key
            if key not in actual:
                issues.append(f"{child_path} missing after readback")
            else:
                issues.extend(_compare_contract(value, actual[key], child_path))
        return issues
    if isinstance(expected, list):
        if not isinstance(actual, list):
            return [f"{path or '$'} expected list, got {type(actual).__name__}"]
        if len(expected) != len(actual):
            issues.append(f"{path or '$'} length mismatch: sent={len(expected)}, back={len(actual)}")
        for index, value in enumerate(expected):
            if index < len(actual):
                issues.extend(_compare_contract(value, actual[index], f"{path}[{index}]"))
        return issues
    # 平台会把部分 SELECT/定时参数从 "1" 规范化为 1。两者业务语义相同，
    # 但不能把 bool 当作数值等价，否则 True/"1" 会掩盖类型错误。
    numeric_pair = (
        not isinstance(expected, bool)
        and not isinstance(actual, bool)
        and isinstance(expected, (str, int, float))
        and isinstance(actual, (str, int, float))
    )
    if numeric_pair:
        try:
            if float(expected) == float(actual):
                return issues
        except (TypeError, ValueError):
            pass
    if expected != actual:
        # 平台可能规范化组件类型大小写，业务语义等价。
        if path.endswith(".type") and isinstance(expected, str) and isinstance(actual, str) \
                and expected.lower() == actual.lower():
            return issues
        # type=8 字符串容器的 value 是占位符 "textarea#{id}#", 平台回读会重写容器 id
        # (容器内部 id 随机生成, 非业务语义) → 跳过比对
        if isinstance(expected, str) and expected.startswith("textarea#") \
                and isinstance(actual, str) and actual.startswith("textarea#"):
            return issues
        issues.append(f"{path or '$'} mismatch: sent={expected!r}, back={actual!r}")
    return issues

def verify_design_readback(sent_design: dict[str, Any], read_design: dict[str, Any]) -> dict[str, Any]:
    """校验回读设计是否保留业务语义，而不仅是事件和节点数量。"""
    expected = {
        "event": _node_contract(sent_design.get("event", {})),
        "actions": [_node_contract(item) for item in sent_design.get("actions", [])],
    }
    actual = {
        "event": _node_contract(read_design.get("event", {})),
        "actions": [_node_contract(item) for item in read_design.get("actions", [])],
    }
    issues = _compare_contract(expected, actual)
    # 组件包可增加仅属于自身的回读断言（例如平台会重写的资源字段）。
    from components import get_readback_assert
    pairs = [(sent_design.get("event", {}), read_design.get("event", {}))]
    pairs.extend(zip(sent_design.get("actions", []), read_design.get("actions", [])))
    for sent_node, read_node in pairs:
        if not isinstance(sent_node, dict) or not isinstance(read_node, dict):
            continue
        assertion = get_readback_assert(str(sent_node.get("type", "")))
        if assertion:
            issues.extend(assertion(sent_node, read_node))
    return {
        "ok": not issues,
        "eventMatch": expected["event"].get("type") == actual["event"].get("type"),
        "actionsCount": {"sent": len(expected["actions"]), "back": len(actual["actions"])},
        "checked": ["node-types", "resource-ids", "field-assignments", "filters", "conditions", "branch-topology", "message-content"],
        "issues": issues,
    }

def save_workflow_draft(
    design: dict[str, Any],
    client: PlatformClient | None = None,
    app_name: str = "AI生成的工作流",
    app_description: str = "",
    *,
    verify_readback: bool = True,
) -> dict[str, Any]:
    """编排:确保应用存在 -> 获取 sceneId/secretKey -> 暂存设计 -> 暂存回读自检.

    完整链路(验证验证):
      1. 创建应用(若需要)-> appId
      2. get_version_list -> sceneId(activeVersion)+ secretKey
      3. save_stash_snapshot
      4. get_stash_snapshot -> 回读校验(节点、资源、字段赋值、条件分支等语义)

    Args:
        design: draft_to_real.py convert() 输出
        client: 可选客户端;None 则从 environment.json 构造
        app_name: 新建应用名称
        app_description: 新建应用描述
        verify_readback: True=保存后回读自检(默认),False=跳过

    Returns:
        {"ok": bool, "appId": str, "sceneId": str, "msg": str,
         "workflowUrl": str,
         "appResponse": ..., "saveResponse": ..., "readBack": ...}
    """
    if client is None:
        client = make_client()

    app_id = str(design.get("appId", ""))
    env = load_environment()
    base_url = env.get("baseUrl", "").rstrip("/")
    default_app = env.get("defaultAppId", "")

    app_response = None
    new_app_created = False
    secret_key = ""
    # 调用方若刚通过 application/save 新建应用，设计中已携带该响应的
    # activeVersion。versionList 在部分租户有短暂延迟或直接返回 500；保留
    # 这个版本号即可避免误判应用不存在后再创建一个默认 esb 容器。
    scene_id = str(design.get("sceneId", "") or "")

    # 步骤 1: 确保应用存在
    app_verified = bool(app_id and scene_id and app_id != default_app)
    if app_id and app_id != default_app:
        # appId 已指定,尝试查询版本信息获取 sceneId/secretKey
        try:
            ver_resp = client.get_version_list(app_id)
            if ver_resp.get("code") == 200:
                ver_data = ver_resp.get("data", {})
                versions = ver_data.get("actionFlowVersions", [])
                scene_id = ver_data.get("activeVersion", "")
                if versions:
                    secret_key = versions[0].get("secretKey", "")
                app_verified = True
        except (PlatformAuthError, PlatformRequestError):
            pass

    if not app_verified and default_app:
        app_id = default_app
        try:
            ver_resp = client.get_version_list(app_id)
            if ver_resp.get("code") == 200:
                ver_data = ver_resp.get("data", {})
                versions = ver_data.get("actionFlowVersions", [])
                scene_id = ver_data.get("activeVersion", "")
                if versions:
                    secret_key = versions[0].get("secretKey", "")
                app_verified = True
        except (PlatformAuthError, PlatformRequestError):
            pass

    # 修改已有动作流: 从暂存快照读取旧节点 id，避免暂存时残留旧节点。
    if app_verified and scene_id:
        try:
            old_resp = client.get_stash_snapshot(app_id, scene_id)
            old_data = old_resp.get("data", {}) if isinstance(old_resp, dict) else {}
            old_actions = old_data.get("actions", []) if isinstance(old_data, dict) else []
            old_ids = [str(a.get("id", "")) for a in old_actions if a.get("id")]
            if old_ids:
                existing = design.get("deleteActions", [])
                if not isinstance(existing, list):
                    existing = []
                design["deleteActions"] = list(dict.fromkeys([*existing, *old_ids]))
        except (PlatformAuthError, PlatformRequestError):
            pass

    if not app_verified:
        # 新建一个应用
        try:
            app_response = client.create_application(
                app_name, app_description, org_id=client.resolve_application_org_id())
            code = app_response.get("code")
            data = app_response.get("data", {})
            if code == 200 and isinstance(data, dict):
                app_id = str(data.get("id", ""))
                if app_id:
                    new_app_created = True
                    # ⚠️ 2026-08-12 修复: create_application 后端同步初始化 V1 版本,
                    # 响应 data.activeVersion 可直接作 sceneId 兜底. 之前只依赖
                    # get_version_list, 该端点偶发 500 时 scene_id 保持 "" →
                    # save_stash_snapshot 的 versionId 为空 → 报"动作流信息不存在".
                    # 实测: sceneId=create.activeVersion + secretKey="" 暂存成功(200).
                    scene_id = str(data.get("activeVersion", "") or scene_id)
                    # 再尝试 get_version_list 补齐 secretKey / 权威 activeVersion
                    # (失败不阻断: scene_id 已有兜底, secretKey 缺失不影响暂存).
                    try:
                        ver_resp = client.get_version_list(app_id)
                        if ver_resp.get("code") == 200:
                            ver_data = ver_resp.get("data", {})
                            versions = ver_data.get("actionFlowVersions", [])
                            if ver_data.get("activeVersion"):
                                scene_id = ver_data.get("activeVersion", scene_id)
                            if versions:
                                secret_key = versions[0].get("secretKey", "")
                    except (PlatformAuthError, PlatformRequestError):
                        pass
                else:
                    return {"ok": False, "appId": "", "sceneId": "",
                            "msg": f"创建应用失败:响应中无 id,data={data}",
                            "appResponse": app_response, "saveResponse": None}
            else:
                return {"ok": False, "appId": "", "sceneId": "",
                        "msg": f"创建应用失败:code={code}, msg={app_response.get('msg','')}",
                        "appResponse": app_response, "saveResponse": None}
        except (PlatformAuthError, PlatformRequestError) as e:
            return {"ok": False, "appId": "", "sceneId": "",
                    "msg": f"创建应用异常:{e}", "appResponse": None, "saveResponse": None}

    if not app_id:
        return {"ok": False, "appId": "", "sceneId": "",
                "msg": "无法获取 appId",
                "appResponse": app_response, "saveResponse": None}

    # 补全 design 中的平台字段
    design["appId"] = app_id
    design["sceneId"] = scene_id
    design["secretKey"] = secret_key

    # 步骤 2.5: 保存前 check 预检 (flow/design/check, 提前暴露组件结构/引用问题)
    # 与当前设计结构一致；失败时返回明确错误，避免平台 500 后排查困难。
    check_response = None
    check_label = "check预检"
    try:
        check_response = client.check_design(design)
        if check_response.get("code") != 200:
            return {
                "ok": False,
                "appId": app_id,
                "sceneId": scene_id,
                "msg": f"{check_label}失败:code={check_response.get('code')}, msg={check_response.get('msg','')}",
                "appResponse": app_response,
                "saveResponse": check_response,
                "readBack": None,
            }
    except (PlatformAuthError, PlatformRequestError) as e:
        # check 是附加校验, 网络异常时不阻塞保存主链路
        check_response = {"code": -1, "msg": str(e)}

    # 步骤 3: 暂存设计 -> 暂存回读自检 (接口偶发失败时自动重试 1 次)
    try:
        save_response = client.save_stash_snapshot(design)
        save_label = "暂存"
        if save_response.get("code") != 200:
            retry = client.save_stash_snapshot(design)
            if retry.get("code") == 200:
                save_response = retry
        code = save_response.get("code")
        if code != 200:
            return {
                "ok": False,
                "appId": app_id,
                "sceneId": scene_id,
                "msg": f"{save_label}失败:code={code}, msg={save_response.get('msg','')}",
                "appResponse": app_response,
                "saveResponse": save_response,
                "readBack": None,
            }

        # 步骤 4: 回读自检(可选)
        # saveStashSnapshot 存的是 temp_store 暂存快照，不能用正式版本 get_design
        # 回读；必须以同一 appId/versionId 调 getStashSnapshot 严格比对。
        read_back: dict[str, Any] | None = None
        if verify_readback and app_id and scene_id:
            # 快照读取是幂等只读请求；仅在接口/网络失败时重读一次同一版本。
            # 若读到语义差异，不应重复请求或新建重复动作流。
            last_error = ""
            for attempt in range(1, 3):
                try:
                    rb_resp = client.get_stash_snapshot(app_id, scene_id)
                    if rb_resp.get("code") != 200:
                        last_error = f"getStashSnapshot returned code={rb_resp.get('code')}"
                        continue
                    rb_data = rb_resp.get("data", {})
                    verified = verify_design_readback(
                        design, rb_data if isinstance(rb_data, dict) else {}
                    )
                    read_back = {
                        **verified,
                        "stashed": True,
                        "attempts": attempt,
                        "note": "暂存快照已通过 getStashSnapshot 回读校验，尚未发布正式版本",
                    }
                    break
                except (PlatformAuthError, PlatformRequestError) as e:
                    last_error = str(e)
            if read_back is None:
                read_back = {
                    "ok": False,
                    "stashed": True,
                    "attempts": 2,
                    "error": last_error or "getStashSnapshot 未返回可用结果",
                }
        else:
            read_back = {
                "ok": True, "stashed": True,
                "note": "暂存已保存；调用方显式跳过 getStashSnapshot 回读校验",
            }

        # 保存成功但 checkReport 有内容 → 平台侧校验告警, 附到 msg 里提示调用方
        report_note = ""
        try:
            chk = (save_response or {}).get("data", {}).get("checkReport", {}) \
                if isinstance((save_response or {}).get("data"), dict) else {}
            chk_msgs = chk.get("msgs", "") if isinstance(chk, dict) else ""
            if isinstance(chk_msgs, str) and chk_msgs.strip():
                report_note = f"; 平台校验提示: {chk_msgs.strip()[:200]}"
            elif isinstance(chk_msgs, list) and chk_msgs:
                report_note = f"; 平台校验提示: {str(chk_msgs)[:200]}"
        except Exception:
            pass
        return {
            "ok": True,
            "appId": app_id,
            "sceneId": scene_id,
            "workflowUrl": f"{base_url}/sp/esb/efdesigner?application={app_id}" if base_url else "",
            "msg": f"{save_label}成功{'(新建应用: '+app_name+')' if new_app_created else ''}{report_note}",
            "appResponse": app_response,
            "saveResponse": save_response,
            "checkResponse": check_response,
            "readBack": read_back,
        }
    except (PlatformAuthError, PlatformRequestError) as e:
        return {"ok": False, "appId": app_id, "sceneId": scene_id,
                "msg": f"{save_label}异常:{e}", "appResponse": app_response,
                "saveResponse": None, "checkResponse": None, "readBack": None}

def gen_id() -> int:
    """生成 JS-safe 临时 ID(正整数,< 2^53)."""
    import random
    return random.randint(1000000000000000, 9000000000000000)

# ── 响应解析工具 ───────────────────────────────────────────────────────────

def _unwrap_list(resp: Any) -> list[dict[str, Any]]:
    """从常见 Weaver 响应信封中取出列表.

    处理: [..] / {data:[..]} / {data:{rows:[..]}} / {rows:[..]} / {list:[..]}
    """
    if isinstance(resp, list):
        return [x for x in resp if isinstance(x, dict)]
    if not isinstance(resp, dict):
        return []
    data = resp.get("data", resp)
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if isinstance(data, dict):
        for key in ("main", "detail", "rows", "list", "records", "datas", "items"):
            val = data.get(key)
            if isinstance(val, list):
                return [x for x in val if isinstance(x, dict)]
        # getEbField 返回 {data: {main: [...], detail: [...]}},二合一
        main_list = data.get("main")
        detail_list = data.get("detail")
        if isinstance(main_list, list) or isinstance(detail_list, list):
            result: list[dict[str, Any]] = []
            if isinstance(main_list, list):
                result.extend(x for x in main_list if isinstance(x, dict))
            if isinstance(detail_list, list):
                result.extend(x for x in detail_list if isinstance(x, dict))
            return result
    for key in ("rows", "list", "records", "datas", "items"):
        val = resp.get(key)
        if isinstance(val, list):
            return [x for x in val if isinstance(x, dict)]
    return []

def _pick(d: dict[str, Any], candidates: tuple[str, ...], default: str = "") -> str:
    for key in candidates:
        val = d.get(key)
        if val is not None and str(val) != "":
            return str(val)
    return default
