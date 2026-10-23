# Skill Hub · 技能归档仓

> 存放 YG 所有自建 / 安装的 skill 的全量版本快照。
> 一个技能一个文件夹，文件夹里放它的每一个版本。

---

## 一、这个仓库解决什么

| 问题 | 做法 |
|---|---|
| 技能改坏了想退回 | 每个版本一份完整快照，`rollback` 一键还原 |
| 不知道该用哪版 | `README.md` 里「当前确认版本」一栏，只有你点头的版本才算数 |
| 不知道每版改了什么 | `CHANGELOG.md` 记录变更摘要 + 文件级 diffstat + 时间 |
| 改到一半想留一手 | 未确认版本只活在 `skill/<技能>/v<版本>` 分支上，`main` 永远干净 |
| 记不清有没有备份 | `audit` 比对本地活目录与快照指纹，漏了就报出来 |

---

## 二、目录结构

```
E:\知识库\skill-hub\
├─ INDEX.md                    自动生成：所有技能总览
├─ README.md                   本文件
├─ .gitignore / .gitattributes
├─ _tools\
│   ├─ skillhub.ps1            主脚本（全部操作入口）
│   ├─ skillhub.config.json    路径 / 排除规则 / 敏感正则 / GitHub IP 池
│   └─ labels.json             所有中文文案模板（脚本本身纯 ASCII）
├─ _templates\                 模板
├─ _inbox\                     来源不明、未定版本的技能，暂存待你认领
├─ _archive\                   弃用技能、历史备份、回滚前的自动备份
├─ _pending\                   推送队列（网络不通时排队）
└─ <技能名>\                    一个技能一个文件夹
    ├─ README.md               索引：当前确认版本 / 版本一览 / 来源 / 活目录
    ├─ CHANGELOG.md            变更流水：每版改了什么、什么时候、确认状态
    ├─ _raw\                   原始安装包 + .sha256
    └─ <技能名>_v<版本>_<时间>\  版本快照（完整文件树 + MANIFEST.json）
```

### 命名规则

| 对象 | 规则 | 例 |
|---|---|---|
| 技能文件夹 | 与 `SKILL.md` 的 `name` 完全一致，kebab-case | `weaver-e10-builder` |
| 版本快照目录 | `<技能名>_v<semver>_<YYYYMMDD-HHmmss>` | `weaver-e10-builder_v1.5.15_20261023-134649` |
| 分支 | `skill/<技能名>/v<semver>` | `skill/weaver-e10-builder/v1.5.15` |
| tag | `<技能名>@v<semver>` | `weaver-e10-builder@v1.5.15` |
| 提交信息 | `feat(<技能名>): v<版本> - <一句话>` | `feat(weaver-e10-builder): v1.5.15 - 补齐条件规则` |

---

## 三、三个文件各管什么

| 文件 | 给谁看 | 内容 |
|---|---|---|
| `README.md` | 你 | 当前确认版本、版本一览表、来源、活目录、体积 |
| `CHANGELOG.md` | 你 | 每版的变更摘要、diffstat（A/M/D）、快照 id、分支/commit、确认状态 |
| `MANIFEST.json` | 脚本 | 版本、时间、来源、git 坐标、`tree_sha256`、文件数、父版本、publish 开关 |

`MANIFEST.json` 里的 `tree_sha256` 是整棵文件树的指纹。`audit` 就是拿它跟活目录比 —— 不一致就说明你改过但没归档。

---

## 四、日常操作

> 全部通过一个脚本：`powershell -NoProfile -ExecutionPolicy Bypass -File "E:\知识库\skill-hub\_tools\skillhub.ps1" <命令>`

| 命令 | 用途 | 参数 |
|---|---|---|
| `status` | 看仓库状态、当前分支、GitHub IP 钉扎 | — |
| `list` | 列所有技能 + 快照数 + 最新快照 | — |
| `audit` | 比对活目录与快照，报未归档 / 漂移 / 版本不一致 | — |
| `snapshot` | 归档一个技能版本 | `-Name -Version -Note [-Source -SourceType -Status -Force -NoCommit]` |
| `install` | 归档一个已安装技能 | 同上，`-SourceType installZip` |
| `import-zip` | 解包 + 存原始包 + 归档 | `-Zip [-Name -Version -Note]` |
| `diff` | 比两个版本的文件差异 | `-Name -From -To` |
| `promote` | 你确认后合入 main 并打 tag | `-Name [-Version]` |
| `rollback` | 把某版还原进活目录（先自动备份当前） | `-Name -Version [-Yes]` |
| `push` | 敏感扫描 + 推送当前分支 | `[-Name] [-Block]` |
| `net-probe` | 探测 GitHub 边缘 IP 并钉扎 | — |
| `refresh` | 重生成所有 README / CHANGELOG 索引 / INDEX | — |
| `index` | 只重生成 INDEX.md | — |

### 常见流程

**改了技能之后归档**

```powershell
$sh = "E:\知识库\skill-hub\_tools\skillhub.ps1"
powershell -NoProfile -ExecutionPolicy Bypass -File $sh snapshot -Name weaver-e10-builder -Version 1.5.16 -Note "补齐条件规则"
```

脚本会自动：抓快照 → 写 MANIFEST → 追加 CHANGELOG → 刷新 README/INDEX → 建分支 → 提交。

**确认某版为正式版**

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File $sh promote -Name weaver-e10-builder -Version 1.5.16
```

合入 `main`、打 tag、把 MANIFEST 的 `status` 改成 `confirmed`、记 `confirmed_by: YG`。

**退回旧版**

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File $sh rollback -Name weaver-e10-builder -Version 1.5.11
# 先看它备份到哪、确认无误后再加 -Yes 真正覆盖
```

---

## 五、版本与确认规则

1. **`main` 只放你确认过的版本**，禁止直接提交。
2. 每次改动走 `skill/<技能>/v<版本>` 分支，开 PR 或本地 `promote`。
3. **同一个版本号下内容不同 = 直接报错**，必须先升版本号。版本号是唯一主键，不许复用。
4. 版本号来源优先级：命令行 `-Version` > `SKILL.md` frontmatter `version` > 安装包文件名。
   用文件名推导时，`MANIFEST.version_source` 会记 `filename`，提醒你这版号是猜的。
5. 历史备份导入的版本一律 `status: archived`，标「内容未校验」，不可作为回滚依据的正式版本。

---

## 六、自动化的三个层级

| 层级 | 机制 | 说明 |
|---|---|---|
| L1 提示词 | `~/.dsh/prompt-inject.md` 末尾的铁律 | 让模型记得调脚本 |
| L2 元技能 | `~/.dsh/skills/skill-hub-keeper` | 技能目录里能命中，仍靠模型自觉 |
| L3 脚本 | 本仓库 `_tools/skillhub.ps1` | **硬执行**，不依赖模型，随时可手动跑 |

**半自动约定**：新建 / 安装 / 修改技能后，模型**先问你**「要不要归档」，你点头才执行 `snapshot`。
合并 `main` 这一步永远要你明确说。

---

## 七、网络说明（GitHub 通道）

这台机器的 GitHub 连通性是**波动的**：DNS 把 `github.com` 解析到 `20.205.243.166`，该 IP 经常不可达；
而 `140.82.112.3` / `140.82.113.3` / `20.27.177.113` 这些边缘 IP 时通时不通。

处理方式：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "E:\知识库\skill-hub\_tools\skillhub.ps1" net-probe
```

它会：逐 IP 做 TLS 握手 → 设 `http.curloptResolve` → 用 `git ls-remote` 验证 → 只保留真正能通的那个。

**推不上去不会丢东西**：本地提交照常，失败记录进 `_pending/push-queue.json`，网络好了重跑 `push` 即可。

> 所以本仓库的可用性**不依赖网络**。GitHub 只是异地冗余那一层。

---

## 八、安全约定（YG 定）

- **公司和客户数据不上传，不管哪个库。** 这类技能在 `MANIFEST.json` 里设 `"publish": false`，永不出本机。
- 推送前脚本会跑敏感扫描（token / 私钥 / 内网 IP 等）。当前配置 `block: false` = **只告警不阻断**，由你自己判断。
- 想改成硬阻断：把 `_tools/skillhub.config.json` 里 `secretScan.block` 改成 `true`，或调用时加 `-Block`。
- 仓库建议保持 **private**。

---

## 九、故障处理

| 现象 | 处理 |
|---|---|
| `audit` 报 `NOT_ARCHIVED` | 新技能没归档，跑 `snapshot` |
| `audit` 报 `DRIFT` | 活目录改过没归档，跑 `snapshot`（需先升版本号） |
| `audit` 报 `VERSION_MISMATCH` | `SKILL.md` 的 version 比最新快照新，说明改完没归档 |
| `snapshot` 报 "version already archived with different content" | 升版本号，别复用 |
| `push` 失败 | 看 `_pending/push-queue.json`，网络恢复后重跑 `push` |
| 脚本报编码问题 | 脚本本身必须保持 ASCII；中文只放 `labels.json`。宿主是 PS 5.1 + gb2312 ANSI |

---

## 十、脚本维护注意

宿主环境是 **Windows PowerShell 5.1**（没有 pwsh 7），系统 ANSI 代码页是 **gb2312**。因此：

1. `skillhub.ps1` **必须纯 ASCII**，任何中文字面量都会被 gb2312 解码搞坏。
2. 所有中文文案放 `_tools/labels.json`，脚本按 UTF-8 显式读取。
3. 写文件一律走 `[IO.File]::WriteAllText(..., UTF8Encoding($false))`，禁止 `Set-Content -Encoding utf8`（5.1 会加 BOM）。
4. `Split-Path -LiteralPath ... -Parent` 在 5.1 是参数集冲突，用 `[IO.Path]::GetDirectoryName()`。
5. 函数返回数组要 `return ,@(...)`，否则单元素会被展开成标量，调用方 `.Count` 变空。
6. 捕获函数返回值时用 `@( ... )[-1]`，否则会把函数里所有输出（含日志）一起收进去。
