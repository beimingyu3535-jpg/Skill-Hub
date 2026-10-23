# 安装、升级与文档同步

## 版本必须匹配

skill 与 CLI 的版本要一致（见 SKILL.md frontmatter 的 `version`）。版本不一致时，命令、选项和文档可能对不上。

```bash
e10-cli --version          # 应与 SKILL.md 标注的版本一致
npm install -g weaver-e10-builder
```

## CLI 升级

- 一般工具：先 `npm rm -g weaver-e10-builder` 卸掉旧包，再重新安装，避免 bin 残留冲突。
- WorkBuddy：先直接用 bash 删除旧包目录（不走 npm 删除），再用 npm 纯安装，并指定一个有权限的工作目录作为缓存地址。

## skill 安装 / 升级

先卸旧（旧名 `skill-e10-cli`），再装新：

```bash
npx -y skills remove skill-e10-cli
npx -y skills add ./weaver-e10-builder.zip --skill -y
```

`skills remove` 无效时手动删除后再 add：

- Claude Code：`rm -rf ~/.claude/skills/skill-e10-cli` → 新 skill 装到 `~/.claude/skills/weaver-e10-builder`
- WorkBuddy：`rm -rf ~/.workbuddy/skills/skill-e10-cli` → 新 skill 装到 `~/.workbuddy/skills/weaver-e10-builder`

## 文档树同步

1.1.0 起发布的 skill 是**薄指令层**：只带 SKILL.md、`_catalog.md`、actionflows 指令层和 scripts，不含深目录文档树（适配 marketplace 两级目录限制）。完整文档随配套 CLI 的 `skill-docs` 分发。

- 每次 `e10-cli auth status` 会自动探测本机已装 skill（`~/.claude/skills`、`~/.workbuddy/skills`、`~/.codex/skills`）并同步文档；版本一致则跳过。
- 手动刷新：`e10-cli skill sync`；可 `--target <安装根目录>` 指定其他工具目录。
- 装完 skill 后看到 references 文档多出/更新、旧文档被清理，都是正常的同步现象，不是装错或重复安装。
- 读 `references/...` 提示文件不存在 → 先 `e10-cli skill sync`，或确认 skill 已装后重跑 `e10-cli auth status`。

## 文档读取与模板拷贝

- 文档在 skill 目录内（如 `~/.claude/skills/weaver-e10-builder/`），`references/...`、`actionflows/...`、`assets/...` 均相对该目录。
- 按决策树命中哪个读哪个，不要一次性全部读入。
- 页面模板用 `e10-cli skill copy [目录]` 拷到工作区（默认当前目录，放出 `references/`、`actionflows/`、`assets/`）。
