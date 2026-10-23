// 环境探测：查询平台表单存储设置，确定建表路径（物理表 vs 逻辑表）
// 用法: node probe-env.mjs <appId> [--auth <auth文件>]
// 输出: {"physical":true|false,"storageSettings":[...],"mainTablePrefix":"...","baseUrl":"..."}
// 判断规则:
//   physical 含于 storageSettings → 可用 `e10-cli form create`（物理表路径）
//   仅 share 等 → 只能建逻辑表，走「逻辑表建表脚本」（见 troubleshooting.md 1.1）
import { pathToFileURL } from 'node:url';

const CLI_ROOT = process.env.E10_CLI_ROOT || 'C:/Users/YW/AppData/Roaming/npm/node_modules/e10-cli/dist';
const { AuthSession } = await import(pathToFileURL(CLI_ROOT + '/core/auth.js').href);
const { ApiClient } = await import(pathToFileURL(CLI_ROOT + '/core/client.js').href);

const APP_ID = process.argv[2];
const AUTH_FILE = process.env.AUTH_FILE || 'C:/Users/YW/.e10-cli/profiles/eteams/auth';

if (!APP_ID) {
  console.error('用法: node probe-env.mjs <appId> [--auth <auth文件>]');
  process.exit(1);
}

const session = AuthSession.fromFile(AUTH_FILE);
if (!session) { console.error('认证失败'); process.exit(1); }
const client = new ApiClient(session);
const baseUrl = session.getBaseUrl();

const resp = await client.post(`${baseUrl}/api/ebuilder/form/form/comp/queryFormStorageSetting`, { module: 'ebuilderform' }, { ebbusinessid: APP_ID });
const data = resp?.data ?? resp;
const storageSettings = Array.isArray(data.storageSettings) ? data.storageSettings : [];
const physical = storageSettings.includes('physical');
const mainTablePrefix = String(data.mainTablePrefix ?? '');

console.log(JSON.stringify({
  physical,
  storageSettings,
  mainTablePrefix,
  baseUrl,
  buildPath: physical ? 'physical (e10-cli form create)' : 'logical (逻辑表脚本，见 troubleshooting.md 1.1)',
}, null, 2));
