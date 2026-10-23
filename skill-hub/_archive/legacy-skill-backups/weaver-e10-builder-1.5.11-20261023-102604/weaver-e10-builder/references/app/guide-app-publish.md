# 应用发布：启用 → 发布到前台 → 改发布信息 → 取消发布

应用建出来只是「壳」。要让成员真正在前台用上，还要走**启用**和**发布到前台**两步；
应用名还可以按语言给不同显示。

## 一、四个动作与先后关系

| 命令 | 作用 | 前置 |
|---|---|---|
| `app enable <appId>` | 启用应用 | — |
| `app publish <appId>` | 发布到前台（应用中心里出现入口） | 先 `enable` |
| `app publish-info <appId>` | 改前台的显示名 / 简介 / 分类 | 先 `publish` |
| `app unpublish <appId>` | 取消发布（收回前台入口） | 先 `publish` |

`app read <appId>` 里的 `publishEnabled`：`1` 已启用、`2` 已停用、`0` 从未启用。

> ⚠️ **停用会连带收回已发布状态。** 前台那句「应用暂未启用，启用后才可以发布给成员使用」
> 说的就是这个 —— 别把 `app disable` 当成「临时关一下、发布态还在」。

## 二、发布

```bash
e10-cli app enable <appId>
e10-cli app publish <appId> --name "会议室管理" --description "预约与审批" --category 综合办公
```

- `--name` 不给就用应用名；`--description` 不给就用应用描述。
- `--category` 是**应用中心里的分类**：汇报 / 协作 / HRM / 审批 / 数据协作 / 综合办公 / CRM / 自定义。
  不指定则落**自定义**。
- 发布后前台入口的地址形如 `/ebdapp/view/<appId>`。

> ⚠️ **每次发布都会生成一个新的前台 id**，取消后重新发布**不会**沿用旧号。
> 别把这个 id 当稳定标识存下来，要用的时候现查（`app publish-info` 会报出来）。

## 三、改发布信息

`app publish-info` 改的是**前台那份配置**（显示名 / 简介 / 分类），
**不动应用本身的名称与描述** —— 后者用 `app edit`。

```bash
e10-cli app publish-info <appId> --name "新的前台名"
e10-cli app publish-info <appId> --description "改后的简介"
e10-cli app publish-info <appId> --category CRM
```

三个参数至少给一个；不给分类就**沿用现有的**，不会被打回「自定义」。

## 四、取消发布

```bash
e10-cli app unpublish <appId>
```

> ⚠️ **不可逆**，也没有回收站。移除后前台入口消失，成员看不到；
> 重新发布会是一个**新入口**。命令会回读确认入口确实没了才报成功，
> 重复执行只会提示「未发布到前台，无需取消」。

## 五、应用名多语言

应用名可以按语言给不同显示。

```bash
e10-cli app lang get <appId>              # 看各语言当前值
e10-cli app lang set <appId> --en "Meeting Room"
e10-cli app lang set <appId> --zh "会议室管理" --en "Meeting Room"
```

- **简体中文那档就是应用名本身。** 只给 `--en` 时，命令会先把现有各语言读回来再整份写回，
  **不会**出现「只改英文、中文被清空」。
- 简体中文缺省沿用应用当前名称，可以用 `--zh` 显式覆盖。
- 已经建过多语言标签时是**原地更新**，不会堆积一堆标签。
- 单独改应用名（`app edit --name`）**不动**多语言配置，两者互不干扰。

## 六、命令一览

| 命令 | 说明 |
|---|---|
| `e10-cli app enable <appId>` | 启用应用 |
| `e10-cli app disable <appId>` | 停用应用（**会收回已发布状态**） |
| `e10-cli app publish <appId> [--name] [--description] [--category]` | 发布到前台 |
| `e10-cli app publish-info <appId> [--name] [--description] [--category]` | 改发布信息 |
| `e10-cli app unpublish <appId>` | 取消发布 |
| `e10-cli app lang get <appId>` | 查看应用名多语言 |
| `e10-cli app lang set <appId> [--zh] [--en]` | 设置应用名多语言 |

以上命令都支持全局 `--json`。

## 关联

- 应用本身的增删改查（`create` / `list` / `folder` / `read` / `edit` / `delete`）：
  [`ref-cli-commands.md`](../common/ref-cli-commands.md) 的 app 段
- 前台入口的可见范围（谁能看到这个应用）：`menu` / `menu-permission` 那套
