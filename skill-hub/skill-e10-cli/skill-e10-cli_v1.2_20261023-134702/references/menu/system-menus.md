# 系统内置菜单 URL 参考

通过 `savePublishMenu` API 挂载系统内置页面到应用菜单。menuUrl 格式固定，禁止瞎编。

> **暂不支持 H5/移动端菜单**。移动端是独立体系（不同 URL + 不同 pageId），目前尚未整理完整，禁止 AI 自行编造。

---

## PC 端菜单

### 工作流页面 (pageType: WORKFLOW)

| 菜单名 | pageId | menuUrl |
|--------|--------|---------|
| 待办流程 | todo | `/sp/ebdfpage/workflow/{appId}_todo` |
| 已办流程 | done | `/sp/ebdfpage/workflow/{appId}_done` |
| 我提交的流程 | mine | `/sp/ebdfpage/workflow/{appId}_mine` |
| 共享给我的流程 | share | `/sp/ebdfpage/workflow/{appId}_share` |
| 下属的待办流程 | subordinates | `/sp/ebdfpage/workflow/{appId}_subordinates` |
| 全部流程 | all | `/sp/ebdfpage/workflow/{appId}_all` |
| 草稿流程 | draft | `/sp/ebdfpage/workflow/{appId}_draft` |
| 流程监控 | monitor | `/sp/ebdfpage/workflow/{appId}_monitor` |

### 独立页面（不跟 appId）

| 菜单名 | pageId | menuUrl |
|--------|--------|---------|
| 提交申请 | newflow | `/sp/ebdfpage/ebflowpage/create/` |

### 其他系统页面

| 菜单名 | pageId | pageType | menuUrl |
|--------|--------|----------|---------|
| 我的关注 | followList | BASE | `/sp/ebdfpage/followlist/{appId}` |
| 共享给我的 | shareList | BASE | `/sp/ebdfpage/sharelist/{appId}` |

---

## 用法

```json
{
  "content": "待办流程",
  "menuType": "1",
  "page": {
    "pageId": "todo",
    "pageName": "待办流程",
    "pageType": "WORKFLOW",
    "appid": "{appId}"
  },
  "menuUrl": "/sp/ebdfpage/workflow/{appId}_todo",
  "shareMap": [{
    "id": "0",
    "content": "所有人",
    "permissionId": "sys_view",
    "targetType": 11,
    "sourceType": 1,
    "objIdList": ["所有人"]
  }]
}
```

> **只有包含工作流的应用**才能挂载工作流系统页面。表单台账会自动挂入菜单，无需手动操作。
