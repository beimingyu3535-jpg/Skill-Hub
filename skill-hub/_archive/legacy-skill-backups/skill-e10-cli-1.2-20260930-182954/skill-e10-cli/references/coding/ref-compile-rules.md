# 编译规则参考

## 编译命令

```bash
ecodecmd build {project-dir} --target=e10
```

- 其中 `{project-dir}` 为代码项目的目录
- 打包会在项目产生一个 `.target` 文件夹，包含一个 `.zip` 文件
- **打包得 cd 到项目的前一级**，要不然传的目录里面没有名称

---

## 编译配置

ecodecmd 内部使用 `@babel/standalone` v7.5.5 编译代码，E10 模式下调用 `compileJsE10`。

```
presets: ['es2015', 'react', ['stage-2', {decoratorsLegacy: true, loose: true}]]
plugins: ['proposal-object-rest-spread', 'proposal-optional-chaining']
```

---

## 支持的语法

| 语法 | 示例 |
|------|------|
| JSX | `<div className="app">{content}</div>` |
| 箭头函数 | `(x) => x + 1` |
| async/await | `const data = await getSimpleData(...)` |
| 模板字符串 | `` `Hello ${name}` `` |
| 对象展开 `...` | `{ ...oldObj, newKey: val }` |
| 可选链 `?.` | `obj?.nested?.value` |
| Class 组件 | `class MyPage extends React.Component {}` |

---

## Babel 编译陷阱（语法合法但编译后行为异常）

| 陷阱 | 说明 | 解决方案 |
|------|------|---------|
| `forEach(fn, this)` 传 context | `this` 在 Babel 编译后丢失，回调内的 `this` 变成 `undefined` | 提前 `var self = this;`，回调内用 `self` |
| `map/filter/find` 同样受影响 | 所有数组方法只要传了第二个参数 `this`，编译后都失效 | 一律用 `var self = this;` 模式 |
| 漏写 `var` 直接赋值 | `x = {}` 未经声明直接赋值，Babel 编译后严格模式报 `ReferenceError: x is not defined` | **所有变量必须先 `var x = ...` 再使用** |

```js
// ❌ Babel 编译后 this 丢失，setState 报错
data.forEach(function (item) {
  this.setState({ ... });
}, this);

// ✅ 提前捕获 this
var self = this;

// ❌ 漏写 var，Babel 编译后报 ReferenceError
priorityColorCache = {};
priorityOpts.forEach(function(opt) { ... });

// ✅ 先声明再赋值
var priorityColorCache = {};
priorityOpts.forEach(function(opt) { ... });
data.forEach(function (item) {
  self.setState({ ... });
});
```

---

## 不支持的语法（会编译报错）

| 语法 | 解决方案 |
|------|---------|
| `catch { }` 无参数 catch | 必须写成 `catch(e) {}` |
| `??` 空值合并运算符 | 用 `||` 或三元表达式替代 |
| `import()` 动态导入 | 必须用 `asyncImport` |
| `private class fields #` | 不用 class fields，用普通方法 |
| `globalThis` | 用 `window` |
| `BigInt` | 不用 |

---

## 打包 & 上传流程

```bash
# 1. 编译检查
e10-cli check <项目目录>

# 2. 打包（cd 到项目前一级）
cd /path/to/parent && ecodecmd build project-dir --target=e10

# 3. 上传（先删旧应用）
e10-cli project tree <projectId>              # 找旧应用 folderId
e10-cli project delete-folder <folderId>
e10-cli project import <projectId> .target/xxx.zip --main-url /sp/custom/...
```

---

## 关键注意事项

1. **所有变量用 var 声明**，非前置加载文件引用确保使用 `React.lazy(() => asyncImport...)`
2. `${appId}` 是占位符，运行时由 ecode SDK 替换
3. 写完代码后运行 `e10-cli check <项目目录>` 逐条自检，全部确认通过后再 build
4. 本地修改后一定要及时 `ecodecmd build` + `import` 上传，否则用户无法验证（用户看不到本地代码）
