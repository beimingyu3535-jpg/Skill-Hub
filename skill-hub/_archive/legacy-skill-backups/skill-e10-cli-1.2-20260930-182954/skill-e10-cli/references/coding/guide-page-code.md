# 页面编码指南

> 本文件为 SKILL.md 的子模块，在需要写页面代码时加载。
> 页面是搭建流程的最后一步，写代码前确保应用、表单、流程都已建好。

---

## 项目结构（从sample拷贝过来）

```
├── entry.js          ← 路由注册入口
├── pages/            ← 页面组件
├── api/
│   └── formApi.js    ← 表单数据 API
└── config/           ← 配置文件（不用管）
```

- entry.js 只完成入口注册，不要写入业务逻辑。
- formApi.js 默认自带。
- 该项目只能在泛微云运行，其他环境缺少依赖都会报错。
- 只能支持 js 编码，**不支持 jsx 或 ts**。
- 尽量使用原生 React 编码。

---

## entry.js 路由注册模板（严格照抄）

```js
import React from 'react';
import { Route } from 'react-router-dom';
import { regOvProps, appInfo, regReactChildren } from '@weapp/utils';
import { asyncImport } from '@weapp/ecodesdk';

var { publicUrl } = appInfo('@weapp/ecodesdk');

// 1. 异步引入页面组件 — asyncImport 第一个参数固定为 '${appId}'，不允许留空
var MyPage = React.lazy(function () {
  return asyncImport('${appId}', 'pages/MyPage');
});

// 2. 路由 path 写死字符串，
var ROUTE_PATH = '/sp/custom/ecode/my-page';

var extract = (
  <Route path={publicUrl + ROUTE_PATH}>
    <React.Suspense fallback={<div>Loading...</div>}>
      <MyPage />
    </React.Suspense>
  </Route>
);

regOvProps('weappEcodesdk', 'Switch', function (props) {
  regReactChildren(props, extract);
  return props;
}, 0);
```

**铁律**：
- `asyncImport('${appId}', 'pages/xxx')` — 第一个参数**固定**是 `'${appId}'`，不能写空字符串、不能写别的值
- `React.Suspense` **只包裹一层**，不要双层嵌套
- 路由 path 写死字符串（如 `/sp/custom/ecode/my-page`），**不拼接 `${appId}` 变量**

**一个项目可以包含多个页面**，在 entry.js 中按同样模式注册：

```js
var MeetingList = React.lazy(function () {
  return asyncImport('${appId}', 'pages/MeetingList');
});

var MeetingForm = React.lazy(function () {
  return asyncImport('${appId}', 'pages/MeetingForm');
});

var extract = (
  <>
    <Route path={publicUrl + '/sp/custom/ecode/meeting-list'}>
      <React.Suspense fallback={<div>Loading...</div>}>
        <MeetingList />
      </React.Suspense>
    </Route>
    <Route path={publicUrl + '/sp/custom/ecode/meeting-form'}>
      <React.Suspense fallback={<div>Loading...</div>}>
        <MeetingForm />
      </React.Suspense>
    </Route>
  </>
);
```

> 新页面导出和路由注册详见 `references/coding/guide-page-export.md`

---

## 引用规则

- **前置加载文件（entry.js）**可以直接 import：`import { getSimpleData } from './api/formApi.js'`
- **非前置加载文件（pages/ 下的所有文件）**只能通过 `React.lazy(() => asyncImport('${appId}', 'pages/xxx'))` 引用
- entry.js 中只能使用 `React`、`ReactDOM`、`@weapp/utils`、`@weapp/ecodesdk`、`axios`，**不能使用 `@weapp/ui` 组件**

---

## @weapp/ui 可用组件清单

**只能使用以下明确列出的组件**，不要从 `@weapp/ui` 里编造任何不在此列表中的组件名。

| 组件 | import 方式 | 参考文档 |
|------|-----------|---------|
| Table | `import { Table } from '@weapp/ui'` | `references/components/display-Table.md` |
| Avatar | `import { Avatar } from '@weapp/ui'` | `references/components/display-Avatar.md` |
| List | `import { List } from '@weapp/ui'` | `references/components/display-List.md` |
| Pagination | `import { Pagination } from '@weapp/ui'` | `references/components/display-Pagination.md` |
| Icon | `import { Icon } from '@weapp/ui'` | `references/components/display-Icon.md` |
| Button | `import { Button } from '@weapp/ui'` | `references/components/@weapp-Button.md` |
| EChart | `import { EChart } from '@weapp/ui'` | `references/components/generic-Echarts.md` |
| CorsComponent | `import { CorsComponent } from '@weapp/ui'` | `references/components/display-FilePreview.md` |
| Browser（人员） | `import { Browser } from '@weapp/ui'`<br>`type="resource"` | `references/components/form-EmployeeBrowser-api.md` |
| Browser（部门） | `import { Browser } from '@weapp/ui'`<br>`type="department"` | `references/components/form-DepartmentBrowser-api.md` |
| Upload | `import { Upload } from '@weapp/ui'` | `references/components/form-Upload.md` |
| Badge | `import { Badge } from '@weapp/ui'` | `references/components/base-Badge.md` |
| Tag | `import { Tag } from '@weapp/ui'` | `references/components/base-Tag.md` |

表单输入控件（文本框、下拉框、日期选择等）用原生 HTML：
```js
<input type="text" value={form[F.name]} onChange={...} />
<input type="date" value={form[F.date]} onChange={...} />
<select value={form[F.status]} onChange={...}>
  {options.map(function (opt) {
    return <option key={opt.valueKey} value={opt.valueKey}>{opt.name}</option>;
  })}
</select>
```

---

## 表单数据操作（核心模式）

**四个 API 各有分工，不要混用：**

| API | 用途 | 返回内容 |
|-----|------|---------|
| `getSimpleData(objId, userId)` | 读 ID、写回 formToSave | 所有特殊字段统一返回 `fieldOptionId`（纯数字串） |
| `getAllData(objId, userId)` | 提取名称、编辑回显 | 含 `fieldOptionName`，mainTable key 是随机哈希 |
| `withDisplayNames(rows, map)` | 表格展示：ID → 名称 | 把 Select 的 `valueKey` 映射为中文名 |
| `getFieldOptions(fieldId, objId)` | 拿下拉选项 | `[{valueKey, name}]` |

**不同字段类型，名称来源不同（写在墙上）：**

| 字段类型 | getSimpleData 返回 | 展示时名称来源 |
|---------|-------------------|--------------|
| Text / Number / Date | `"值"` / `123` / `"2026-01-01"` | 直接展示 |
| Select / RadioBox / CheckBox | `"1283421826353889337"`（选项 ID） | `getFieldOptions` → `withDisplayNames` 映射 |
| **Employee** | `"2765550234448235905"`（用户 ID） | `getAllData` 的 `fieldOptionName`，**不是** getFieldOptions |
| **Department** | `"2765550234448235905"`（部门 ID） | 同上 |
| FileComponent | `"fileid1,fileid2"`（文件 ID 串） | 上传组件的 `name` |

**表格页面标准加载模式：**

```js
var [data, setData] = useState([]);

useEffect(function () {
  Promise.all([
    getSimpleData(OBJ_ID, USER_ID),
    getFieldOptions(F.status, OBJ_ID),   // Select 字段拿选项
  ]).then(function ([rows, statusOpts]) {
    // 加载时为每个需要展示名称的 Select/Employee 字段做映射
    // Employee/Department 的名称要另外从 getAllData 提取！
    var displayRows = withDisplayNames(rows, {
      [F.status]: statusOpts,
    });
    // Employee 字段需要额外用 getAllData 构建 ID→名称 map
    setData(displayRows);
  });
}, []);
```

**写入 / 更新：**

```js
// form 中所有值已经是 ID，直接拼入 formToSave
var formToSave = {};
Object.keys(form).forEach(function (key) {
  if (form[key] !== '' && form[key] !== null && form[key] !== undefined) {
    formToSave[key] = form[key];
  }
});
// 选择器新值覆盖
if (selectedPerson.length > 0) formToSave[F.person] = selectedPerson[0].id;

if (editingId) {
  updateFormData(OBJ_ID, formToSave, editingId, USER_ID);
} else {
  saveFormData(OBJ_ID, formToSave, USER_ID);
}
```

> 完整的数据读写指南见 `references/coding/guide-form-crud.md`，编辑回显见 `references/coding/guide-edit-backfill.md`（前端代码）。

---

## 编译规则（简要）

- `ecodecmd build {project-dir} --target=e10` 打包（cd 到项目前一级）
- 所有变量用 `var` 声明
- 不支持的语法：`catch{}` 无参数 catch、`??`、`import()` 动态导入、`BigInt`
- 详见 `references/coding/ref-compile-rules.md`（编译配置）、`references/coding/guide-page-export.md`（引用规范）

---

## 代码质量检查清单

生成代码后逐项检查：

1. [ ] 变量用 `var` 声明，非 `const`/`let`
2. [ ] 非前置加载文件引用使用 `React.lazy(() => asyncImport(...))`
3. [ ] **表格中没有任何裸 ID 展示**：Employee/Department 用 `fieldOptionName`，Select 用 `withDisplayNames`，用户看到的必须是中文名称
4. [ ] `getSimpleData` 返回值直接 `item[字段ID]`，没有 `_raw` 层
5. [ ] Select 字段读写统一用选项 ID（`valueKey`），不是显示名称
6. [ ] React state 不直接修改，创建新对象 `var newForm = {}; Object.keys(form).forEach(...)`
7. [ ] entry.js 不引入 `@weapp/ui` 组件
8. [ ] 没有 `forEach/map/filter(fn, this)` 传 context 的写法，用 `var self = this;` 替代
9. [ ] 表单数据 key 用字段 ID（纯数字字符串），对照 `form read --out fields.json`
10. [ ] Employee/Department 字段写入前已转为 ID
11. [ ] 写完代码后运行 `e10-cli check <项目目录>` 逐条自检
