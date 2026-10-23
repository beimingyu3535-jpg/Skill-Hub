# Skill Ebcoder 目录索引

> 此文件列出所有子文档的加载条件，供 Agent 按需加载。不要一次性加载全部。

## Guides（编码指南）

| 用户意图关键词 | 加载文档 |
|---------------|---------|
| 表单CRUD、增删改查、getSimpleData、withDisplayNames、getFieldOptions、saveFormData、updateFormData、deleteFormData、字段类型 | `references/coding/guide-form-crud.md`（前端代码） |
| 编辑、修改、回显、handleEdit、getAllData、rawData、selectedPerson、editForm、数据回填 | `references/coding/guide-edit-backfill.md`（前端代码） |
| 字段联动、显隐联动、条件显示、form linkage | `references/form/guide-form-linkage.md` |
| 新建表单、form create、字段定义、字段类型 | `references/form/guide-create-form.md` |
| 表单数据读写、form data、写入数据、查询数据、删除数据 | `references/form/guide-form-data.md` |
| 流程、审批、workflow、提交流程、flowpage、预填、URL传参、节点、操作者、审批人、连线 | `references/workflow/guide-workflow.md` |
| 分支条件、出口条件、条件JSON、save-condition、连线条件、condition add | `references/workflow/guide-workflow-condition.md` |
| 条件操作符编码、字段类型矩阵、关系符 | `references/workflow/operator-matrix.md` |
| 动作流、跨表单、写入台账、ActionEbAdd/ActionEbUpdate/ActionEbDelete、提交事件 | `references/workflow/guide-workflow-action.md` |
| 鉴权、登录、auth、ETEAMSID、多环境、profile、切换环境 | `references/auth/guide-auth.md` |
| HRM矩阵、条件矩阵、matrix、映射表 | `references/hrm/guide-matrix.md` |
| 新页面、导出、路由、entry.js、regOvProps、regReactChildren、asyncImport、publicUrl、Suspense | `references/coding/guide-page-export.md`（前端代码） |
| 写页面、页面代码、React编码、组件、entry.js模板 | `references/coding/guide-page-code.md`（前端代码） |

## Reference（参考手册）

| 用户意图关键词 | 加载文档 |
|---------------|---------|
| CLI、命令、打包、build、import、创建应用、创建表单、菜单、project、form create、app create、matrix | `references/common/ref-cli-commands.md` |
| 编译、语法、报错、不支持、babel、打包、var、const、let、es2015、stage-2 | `references/coding/ref-compile-rules.md`（前端代码） |

## Components（组件文档）

| 用户意图关键词 | 加载文档 |
|---------------|---------|
| Button、按钮 | `references/components/@weapp-Button.md` |
| Table、表格 | `references/components/display-Table.md` |
| List、列表 | `references/components/display-List.md` |
| Pagination、分页 | `references/components/display-Pagination.md` |
| Icon、图标 | `references/components/display-Icon.md` |
| Avatar、头像 | `references/components/display-Avatar.md` |
| EChart、图表、Echarts | `references/components/generic-Echarts.md` |
| 文件预览、CorsComponent | `references/components/display-FilePreview.md` |
| Input、输入框、文本框 | `references/components/form-Input.md` |
| 人员选择、Browser Employee、resource | `references/components/form-EmployeeBrowser-api.md` |
| 部门选择、Browser Department、department | `references/components/form-DepartmentBrowser-api.md` |
| Upload、文件上传、附件、FileComponent | `references/components/form-Upload.md` |
| Badge、徽标 | `references/components/base-Badge.md` |
| Tag、标签 | `references/components/base-Tag.md` |

## 组合场景

| 场景 | 需加载的文档 |
|------|-------------|
| CRUD 列表页 | `coding/guide-form-crud.md`（前端代码） + `components/display-Table.md` + `components/display-Pagination.md` |
| 表单新增/编辑弹窗 | `coding/guide-form-crud.md`（前端代码） + `coding/guide-edit-backfill.md` + 对应表单组件文档 |
| 新建完整应用 | `common/ref-cli-commands.md` + `form/guide-create-form.md` + `coding/guide-page-export.md`（前端代码） |
| 流程触发页面 | `workflow/guide-workflow.md` + `coding/guide-form-crud.md`（前端代码） |
| 流程分支条件 | `workflow/guide-workflow.md` + `workflow/guide-workflow-condition.md` |
| 跨表单动作流 | `workflow/guide-workflow.md` + `workflow/guide-workflow-action.md` |
| 编译报错排查 | `coding/ref-compile-rules.md`（前端代码） |
