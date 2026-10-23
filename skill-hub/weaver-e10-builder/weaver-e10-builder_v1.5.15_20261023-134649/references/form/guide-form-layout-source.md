# 图片和 Excel 源样式还原

字段类型、选项、关联、公式、默认值和主明细创建继续由现有 CLI 完成。本功能只把已有字段放入源布局，生成原生 pageLayouts 和 workbook，再保存和独立回读。运行不依赖 Form Engine 或 Python。

## 当前范围

支持已有单个 PC EXCEL 页面、普通主表、多个普通明细、XLSX 网格、合并、行列尺寸、静态文字及可支持的字体、颜色、边框和对齐。复用当前值组件、标题组件、明细系统控件及其 ID，保留字段业务配置。

FLOW 转换、嵌套容器、二级明细、移动端、多页、宏和旧 XLS 文件不属于当前源还原范围。已有这些布局的普通命令继续保留；源还原遇到它们会明确阻断，不会降级为 Text 或默认两字段一行。

源标题要与现有字段标题一致。字段重名时用真实 fieldId，主明细归属不同不能混绑。图片星号若与已有必填设置冲突，应先通过字段业务路径处理，不能在样式编译中推断并修改。

## Excel 路径

```bash
e10-cli form layout extract 样表.xlsx --out layout-source.json
```

提取结果保留所有 Sheet，由 layout-spec 显式选择一个。行列坐标从零开始，合并控件绑定左上角。检查源文件哈希、静态说明、合并、字段位置和未支持项，再产出 LayoutSpec。

```json
{
  "schemaVersion": "e10.layout-spec/v1",
  "sourceHash": "<复制 extract 输出的 sourceHash>",
  "sheet": "样表",
  "fields": [
    {"fieldName":"金额","title":{"row":1,"col":0},"value":{"row":1,"col":1}},
    {"fieldId":"<真实字段ID>","title":{"row":2,"col":0},"value":{"row":2,"col":1}}
  ]
}
```

Schema 随 CLI 发布在 `assets/layout-spec.schema.json`，可通过 `skill root` 定位文档，通过 npm 包 assets 获取。名称可唯一匹配时允许 fieldName；fieldId 始终使用字符串。该描述不接受 componentKey、required、options、formula 或关联创建指令。

```bash
e10-cli form layout compile <objId> --source @layout-source.json --spec @layout-spec.json --out layout-artifact.json
```

compile 仅查询当前字段和布局，不写业务系统，不分配 ID。输出包含原生前置快照、目标和输入指纹、完整保存请求及验证条件。对源文件、映射和布局草稿做聚合确认后执行：

```bash
e10-cli form layout apply <objId> --artifact @layout-artifact.json --out layout-result.json
e10-cli form layout verify <objId> --artifact @layout-artifact.json --out layout-verification.json
```

apply 会单次保存并自动独立回读。verify 可单独再次验证。旧快照或字段配置变化需要重新 compile；写响应丢失时先查询，不盲目重试，不执行 initLayout。

Excel 证据在 compile/apply 时会从真实文件重新提取比对；只填一个哈希或修改源 JSON 的样式不能通过。XLSX 到 Native 是兼容投影，字体使用 pt×96/72、列宽按兼容算法转换，并不证明浏览器像素完全一致。

空白行尺寸及网格范围内的行列继承样式也参与提取。源 JSON 只接受约定的单元格、行列、合并和样式属性，不接收原生 cellType、脚本或回调，行列尺寸数组必须完整。主 workbook 保留原有其他配置；冻结范围超出新网格时阻断。Excel 和旧图片产物的 VALUE 前景色使用配对 TITLE；新图片 imageStyles 模式保留分别观察到的标题/值颜色，不把标题红字自动传播成输入值红字。

公式保留在源证据中，字段绑定后移除源输入占位和源公式，计算仍使用已有字段配置。未绑定的静态公式默认阻断；有缓存显示值且明确设置 allowUnsupported=true 时，只投影缓存值并报告遗漏，不创建计算规则。没有缓存值不能继续。

## 图片路径

```bash
e10-cli form layout image-context 样图.png --out image-context.json
```

Agent 必须实际查看原图，在此哈希下输出结构化观察。只记录可见网格、合并、尺寸、标题、控件区域和样式；不根据灰色、星号或控件外观改变字段类型、只读、默认值和关联。没有独立 OCR/模型 API。

观察 JSON 使用以下形状；该例为结构示意，内容必须来自本次原图：

```json
{
  "schemaVersion":"e10.layout-source/v1",
  "sourceType":"image",
  "sourceHash":"<本次 image-context 返回的哈希>",
  "observations":{"confidence":"HIGH","confirmed":false},
  "unsupported":[],
  "sheets":[{
    "name":"图片观察","rowCount":2,"columnCount":2,
    "rows":[{"size":40,"visible":true},{"size":30,"visible":true}],
    "columns":[{"size":100,"visible":true},{"size":180,"visible":true}],
    "spans":[],
    "cells":[
      {"row":"1","col":"0","value":"金额","style":{"foreColor":"#000000"}},
      {"row":"1","col":"1","value":"[金额]","style":{"backColor":"#FFFFFF"}}
    ]
  }]
}
```

HIGH 可以进入可审阅草稿；MEDIUM 必须经用户确认后将 confirmed 记为 true；低置信度或无法表示的结构不能猜测。对观察稿的确认不自动授权远程写入。

```bash
e10-cli form layout extract 样图.png --observation @image-observation.json --out layout-source.json
```

然后使用与 Excel 相同的 compile/apply/verify。图片不会进入默认两字段一行模板，也不会伪装成确定性 Excel 证据。`sourceStyleVerified` 对图片保持 false，表示没有确定性 Excel 源样式证明；`pixelVerified` 单独表示像素验收，两者不能混为一谈。新图片模式用 imageStyleReport 报告观察样式的原生投影与回读，不代表原图像素相同。

### 图片样式二次确认（2026-10-15）

图片提取后，Agent 必须主动展示识别出的样式并等待用户确认。按主标题、字段标题、输入内容等分组列出字体、字号及单位、颜色（色名与十六进制值）、粗细、水平和垂直对齐；不同样式不能混成一套。字体与字号是视觉估计，未知值显示“未识别”，不能把默认 sans-serif、12px 或左对齐冒充图片识别结果。字段标题必须逐个观察居中/居左/居右和垂直对齐；不能只识别页面大标题的对齐。

```bash
e10-cli form layout style-review --source @layout-source.json --spec @layout-spec.json --out layout-review-source.json --report style-review.json
```

报告同时提供 recognized（图片原识别值）、effective（本次最终配置）、accepted/rejected（用户调整成功/失败项）及 missingAttributes（标题未识别属性）。MEDIUM 观察尚未能 extract 时，可将 image-context 的真实 sourceFile 写入观察稿，先对观察稿运行 style-review，用户确认后再 extract。HIGH 只允许先编译草稿，不表示用户已同意样式。`observations.confirmed` 只可反映本次用户真实确认，不能为了通过命令自行置 true。

用户可直接说“来文单位改为微软雅黑、小四、蓝色并居中”。Agent 负责将自然语言定位到已创建字段或静态单元格，CLI 不调用另一套模型。将调整写成以下 JSON（示意 fieldId 必须替换为真实值），而不是修改已签名产物或原生保存请求：

```json
{
  "fields": [{"fieldId":"<真实字段ID>","title":{
    "fontFamily":"微软雅黑","fontSize":"小四","color":"蓝色",
    "textAlign":"居中","verticalAlign":"垂直居中"
  }}],
  "cells": [{"sheet":"图片观察","row":0,"col":0,"style":{"fontFamily":"方正小标宋简体","fontSize":"22pt","color":"#FF0000"}}]
}
```

fields 只接受 title/content 文字样式，cells 指向源网格合并区域左上角，page 仅支持 backgroundColor。字段必须已在图片样式或 LayoutSpec 中唯一定位，不新建字段、不修改必填/只读/默认值。原生字体选项中文名映射为字体配置值；未知字体、模糊字号、无效颜色等逐项拒绝，保留该项原图片识别配置，其他有效项照常采用。常见中文字号、小四=12pt=16px，显式 pt/磅 按 96/72 转 px，裸数字默认 px。映射可编码不等于目标电脑已安装字体，最终字形需运行态核对。

收到用户确认或明确修改指令后，告知采用项与回退项，使用同一最终配置标记确认并重新编译：

```bash
e10-cli form layout style-review --source @layout-source.json --spec @layout-spec.json --overrides @style-overrides.json --confirm --out layout-confirmed-source.json --report style-confirmed.json
e10-cli form layout compile <id> --module workflow --source @layout-confirmed-source.json --spec @layout-spec.json --context @layout-context.json --out layout-artifact.json
```

用户接受原识别样式时省略 --overrides。最后一个命令的 module 按真实目标选择，示例 workflow 不是自动切换规则。未带 --confirm 只生成待确认源文件及报告，输出不能覆盖原观察；确认后改了样式需重新确认、重新 compile，不能沿用之前的已签名请求。新 v4 图片 apply 在任何远程查询/保存前检查确认状态，form create 的图片源选项也在建表前检查；Excel 与旧编译产物保留既有行为。

v4 将几何区域、单元格规则和字段规则形成的最终文字样式同步到 config.styles.title/content，包含水平 text-align 与垂直 align-items；单元格仍保存 hAlign/vAlign。明确的字段规则优先于单元格规则，单元格规则优先于区域规则。不推定所有标题均居中，也不将纵向排字等同于居中；平台未核对的排字效果仍需报告遗漏。v3 及更旧产物按原版本重编译校验，修复不会改变它们的摘要；要获得新修复需要重新观察/确认并 compile。

### 图片样式观察与诊断（2026-10-13）

观察 JSON 可以增加 imageStyles（完整 Schema 在 `assets/schemas/image-style-observation.schema.json`；CLI 包 assets 内也提供）。图片 extract 自动规范化旧单元格 align/bold 键，并启用新图片样式模式；旧的已编译产物保留原编译版本校验；新编译的图片和 Excel 布局使用下文的留白及列宽规则。

```json
{
  "imageStyles": {
    "schemaVersion": "e10.image-styles/v1",
    "page": {"backgroundColor":"white"},
    "cells": [
      {"sheet":"图片观察","row":0,"col":0,"style":{
        "color":"#F00","fontSize":18,"fontUnit":"pt","fontFamily":"SimSun",
        "bold":true,"align":"center",
        "border":{"color":"red","width":1,"line":"solid"}
      }}
    ],
    "fields": [
      {"fieldId":"<真实字段ID>","title":{"color":"red","fontSize":16,"bold":true},
       "content":{"color":"black"},
       "input":{"height":40,"backgroundColor":"white","border":{"color":"red","width":1,"line":"solid"}}}
    ],
    "issues": []
  }
}
```

cells 的位置相对于源 Sheet，必须是合并区域锚点；这里的静态标题示例需要在源网格中另留一行，不能与业务字段 TITLE/VALUE 共用同一单元格。fields 支持精确 fieldId/fieldName 和 subFormId，不能携带 required、options、公式或其他业务属性。issues 记录字体无法判断、水印、未知控件等遗漏；默认阻断，有明确接受时才用 allowUnsupported。

颜色支持 #RGB/#RRGGBB/rgb 与有限常用色名；pt 转 px。align 是 textAlign 别名，bold 对应字体粗细 700/400，**不是 textDecoration=1**（下划线）。字号和字体家族不能仅凭 bold 推定；静态文字缺少必要字号时阻断。单元格的 font/hAlign/vAlign/wordWrap 与分边边框继续保留。

编译同时处理单元格样式、关联值组件的原生 config.styles（title/content/inputStyle）、页面 formStyle.styleConfig.formLayout.background。只使用已有 applyStyle 分类，不重分配类别、不切换模板。缺失或未核对的样式分类明确报告。TextArea 不接受 inputStyle.height；使用字段样式的 textArea.rows、fitCell、autoHeight，对应原生 config.height、fullHeight、disableAutoHeight。fitCell=true 时优先撑满单元格，v3 不额外写 rows 高度；autoHeight 仍独立校验，不能因 fullHeight 已落库就忽略该属性。仅支持普通 TextArea，不转换富文本、只读和字段业务配置。

保存请求的 formStyle 是对象，但内部 styleConfig 必须是 **JSON 字符串**，与后端 FormStyle 的 String 字段一致。CLI 内部解析为对象修改后会编码回字符串；不能因为前端展示时将其解析成对象，就把对象原样发给 saveFormAndLayout。2026-10-13 fix1 已修复此序列化错误，旧版本含页面样式的编译产物应重新 inspect/compile，不手工修改已签名请求。

附件/FileComponent 的 UploadStyleConfig 不支持 inputStyle。附件的标题、内容使用 title/content，不能借用单行输入框的样式属性；这属于正确的原生类型限制。

图片样式只覆盖明确观察的属性，保留其他原生展示配置和业务属性。标题/内容区域宽高通过 rows/columns/spans 表达，单行输入框尺寸使用 input。不能只写单元格颜色并忽略已有组件 customStyle 的覆盖，也不能用一套默认红色模板代替观察。

```bash
e10-cli form layout style-audit <objId> --artifact @layout-artifact.json --out style-report.json
# 离线核对：current-context 必须来自独立 inspect，不把编译产物自拷贝当真实验收
e10-cli form layout style-audit <objId> --artifact @layout-artifact.json \
  --context @current-context.json --out style-report.json
```

imageStyleReport 分别报告 COMPILED、VERIFIED、MISMATCH、INCOMPLETE 或 NOT_OBSERVED，包含比较属性数、匹配数及 cell/component/page 差异。VERIFIED 表示投影属性回读一致；整体 verified 还要求字段、布局身份及结构一致。没有观察样式或未闭合属性不能自动宣称还原完成，更不能转默认布局继续执行。

### 整行、快照与认证诊断

- 独占整行通过 TITLE 与 VALUE 各自的合并跨度完成；例如 4 列的一整行用标题第 0 列和值第 1～3 列，绑定各自锚点。不要将二者绑同坐标，也不要为通过校验改 singleRow 业务配置。
- LAYOUT_SNAPSHOT_CHANGED 表示 updateTime/pageVersion 或其他布局内容变化：重新 inspect → compile → apply。不能只改时间戳来绕过并发检查；LAYOUT_FIELDS_CHANGED 单独表示字段配置变化。
- 认证处理沿用现有 CLI。登录态缺失时使用当前入口重新认证，不手工修改 enc/data 或复制其他工具的密钥；离线 compile 不迁移登录态。
- 源布局保存使用单次请求，认证恢复或响应未知仍先独立回读，不因登录恢复盲目重复保存。

源布局 JSON 与原生回读使用专用解析器：裸长整数保留为精确字符串，网格尺寸及字号小数保留为数值。原客户端默认解析保持基线行为；仅源布局命令、带 layout-source 的创建及 read --raw/--out 启用专用解析，不改变其他命令的数据类型。

## 普通明细

LayoutSpec 可增加 details，必须使用真实 subFormId。anchor 是主表中明细容器的源位置；sourceRegion 是迁入独立明细 workbook 的源矩形，必须与 anchor 分开。fields 的 title/value 坐标仍相对于原源 Sheet。

```json
{
  "subFormId":"<真实subFormId>",
  "anchor":{"row":4,"col":0},
  "sourceRegion":{"row":5,"col":0,"rowCount":2,"colCount":4},
  "fields":[
    {"fieldId":"<真实明细字段ID>","title":{"row":5,"col":0},"value":{"row":6,"col":0}}
  ]
}
```

迁移按完整行处理，区域外的主表字段或静态说明也不能占这些行。未绑定的明细静态内容、跨界合并、相互重叠的明细区域均会阻断。原生明细需要既有完整子 workbook、五个结构行、至少二十个逻辑行和八类标准系统控件；不生成只有一行的表壳。

保留明细系统配置、按钮和结构行。只把源字段标题和值样式投影到既有明细列，并按源尺寸调整业务列及相关行；字段 ID、dataKey 和业务选项等保持原样。

明细的 `columnCount` 表示逻辑列容量，`columns` 表示显式列配置，平台可能省略尾部默认列，因此两者不必相等。例如 6 个业务字段加 2 个系统列，允许 `columnCount=10`、`columns.length=8`；原生容量与默认列表示原样保留，不增加业务字段凑数，也不擅自填充无引用的列配置。数字字符串容量可兼容读取；单元格和合并范围必须位于容量内，实际承载业务字段的列必须有可用的列配置。缺系统控件、越界、业务列配置缺失仍会阻断，不能简单放开校验或缩小容量绕过。

“八类标准系统控件”指按钮、勾选、序号等不同系统控件类型，不是要求 8 个业务字段。明细值区域是可重复展示数据的模板，不限制运行态只能一条记录。截图中的多条示例数据需与字段/布局分开确认；未绑定静态内容的保护继续保留，真实业务记录应另外处理数据，不能直接删除或新增字段冒充。

## 与创建命令衔接

独立建好字段后执行还原，是推荐的可审阅路径。需要串联时，form create 支持：

```bash
e10-cli form create <appId> "<表单名>" --fields @fields.json --layout EXCEL \
  --layout-source @layout-source.json --layout-spec @layout-spec.json \
  --layout-artifact-out layout-artifact.json
```

源输入、产物和报告路径在建表前检查；字段、高级属性、公式和归组重排完成后才精确保存。失败返回已创建的 objId/formId 和 layoutRestoration，不删除表单，也不重新创建。先检查差异，后续针对同一 objId 编译和重试。保存已回读通过但报告落盘失败时，明确返回 saved=true 与 reportWriteError，并以非零退出码提醒补存报告。

不要在源布局保存后运行会整体重排的 group/init 等命令。后续增量 add-field 和 move 保持现有行为，但将改变已验收的源布局；应按变更范围重新验收。

## 布局目标和离线编译

默认使用 eBuilder objId。Workflow 和 Business 传 `--module workflow|biaoge --id-type form`；这些请求适配已提供，仍需在对应环境独立验收。已创建的视图或节点布局使用 `--view-id`，视图原生路由按需要显式加 `--target-kind view`。不自动创建布局记录或改节点绑定。

```bash
e10-cli form layout inspect <objId> --out layout-context.json
e10-cli form layout compile <objId> --context @layout-context.json \
  --source @layout-source.json --spec @layout-spec.json --out layout-artifact.json
e10-cli form layout read <objId> --raw --out native-layout.json
```

inspect 仅查询并导出完整原生数据。带 context 的 compile 完全离线，无须登录；apply 仍会读取真实当前状态，无法用伪造上下文跳过目标和快照核对。read --json 的简化输出不能替代完整上下文。

## 验收与差异

报告分别输出 verified、structureVerified、sourceStyleVerified、fieldsPreserved、pixelVerified 和 differences。API 200 不代表通过，必须独立回读。服务端换组件 ID 时按 fieldId/associatedId/subFormId 一对一适配；身份缺失、重复或类型变化仍失败。

unsupported 包括源中的浮动图片、冻结、筛选、行列分组、富文本局部样式、条件格式、部分数值格式、链接、数据验证等尚未投影的内容。默认阻断；用户明确接受这些遗漏时可在 spec 中设置 allowUnsupported=true，报告仍列出遗漏，完整 sourceStyleVerified 不得为 true。

编译产物包含原始快照，保持到验收及故障处理结束。当前没有自动回滚；结果未知先回读，发现其他人修改后重新编译，不能盲目覆盖。产物及报告以私有权限保存到指定路径，禁止输出覆盖源文件、描述或产物本身。

### 图片几何与保存前结构核对（fix2）

图片视觉理解仍由 Agent 完成。image-context 返回真实 imageWidth/imageHeight；禁止按默认模板臆造列宽、行高和合并。新图片观察应提供 imageStyles.geometry，按原图像素记录边界和完整区域分割，CLI 据此计算 rows/columns/spans。区域边框沿整段合并边缘投影，不能只给左标签画框。标题在表格外时应独立留一行且无表格边框。

```json
{
  "geometry": {
    "imageWidth": 400, "imageHeight": 100,
    "sheets": [{
      "sheet": "图片观察",
      "xLines": [0, 40, 200, 240, 400], "yLines": [0, 40, 70, 100],
      "regions": [
        {"row":0,"col":0,"rowCount":1,"colCount":4},
        {"row":1,"col":0,"rowCount":1,"colCount":1,"style":{"border":{"color":"red","width":1,"line":"solid"}}},
        {"row":1,"col":1,"rowCount":1,"colCount":3,"style":{"border":{"color":"red","width":1,"line":"solid"}}},
        {"row":2,"col":0,"rowCount":1,"colCount":1},
        {"row":2,"col":1,"rowCount":1,"colCount":1},
        {"row":2,"col":2,"rowCount":1,"colCount":1},
        {"row":2,"col":3,"rowCount":1,"colCount":1}
      ]
    }]
  }
}
```

以上仅是 Schema 示意，坐标必须换成本次原图观察值，不是默认模板。边界严格递增且位于真实图片内，边界数为行/列数加一；regions 必须完整覆盖网格（含空白区），不重叠。尺寸、合并、区域边框以 geometry 为依据，独立 cells/fields 样式可细化颜色和字体。不能将星号、业务值、水印转成默认值。合并覆盖其他文字、字段坐标落在非锚点、遗漏区域都会阻断。旧观察与已编译产物未携带 geometry 时仍兼容，但只能证明观察稿被编译和保存，不能证明几何符合原图。

多行文本外观示例：

```json
{"fieldId":"<真实字段ID>","textArea":{"rows":1,"fitCell":false,"autoHeight":false}}
```

rows 是原生显示行数（1～50），不能填像素。不得看到源图空值或只读展示就自动改字段类型或 readOnly。

compile 后生成结构预览，并实际查看原图与预览；核对标签/值列比例、单字段行的值区域是否跨列、正文等行高、标题是否在表格外、整张网格边框与文字颜色，再进入 apply：

```bash
e10-cli form layout preview --artifact @layout-artifact.json --out layout-preview.html
```

preview 完全离线，不鉴权、不写业务系统；显示原图及原生 workbook 结构，字段值用占位符，不能把它当 E10 控件运行态截图。imageStyleReport.verificationScope 固定为 OBSERVATION_TO_NATIVE_READBACK、sourceImageCompared=false。VERIFIED 只代表观察投影的属性回读一致；还原完成必须补充 E10 浏览器实际视觉核对，pixelVerified 保持 false。

### 原生样式清理与输入层选择（WorkBuddy 补丁对照）

EXCEL 前端同时消费单元格与组件样式，组件 customStyle 会覆盖从单元格派生的内容样式。没有组件 styles 的基准样本，只能证明该样本不依赖自定义组件样式，不能推导所有组件样式无效。

imageStyles.componentStyles 的默认值 merge 保持原行为。replace 在编译副本中删除已绑定标题和值的旧 config.styles，再写入本次观察的组件样式；workbookOnly 则清理这些组件样式并仅保留 workbook 样式。范围外组件与原始 context 保持不变。清理不允许修改 inspect 导出的 context，更不能从 snapshotHash 中排除 config.styles：并发修改仍会被阻断。

字段 inputTarget 默认 component，描述输入控件自身边框、背景、宽高；显式 cell 描述整个值单元格边框与背景，写入 workbook 值格，不写新的 inputStyle。cell 不接受输入框宽高（网格尺寸使用 geometry）。workbookOnly 下有 input 的字段必须显式选择 cell，避免静默丢弃控件样式。不要把原图蓝色小输入框边框当成红色表格值区域边框。

字段 displayTitle 只能绑定真实 fieldId，内容是原图可见纯文本；通过原生 enableDisplayName/displayName.nameAlias 修改布局展示标题，保留字段名称与 ID。源 TITLE 必须与该显式展示标题相符。未指定时仍严格要求源标题与已有标题一致，不猜测别名、不给字段自动改名。

平台源网格的 parentName 仅接受原生 Normal，未解析的命名样式仍拒绝；locked 只接受布尔值，保留为网格单元格属性，不转换成字段 readOnly、权限或业务配置。未知属性、字符串形式 locked 均拒绝。

报告新增 projectionVerified（只有投影属性独立回读一致才为 true）；COMPILED 和 NOT_OBSERVED 均为 false。它与 pixelVerified 分开，不能将 true 翻译为“已按原图还原完成”。

### 空白边列与列宽（编译版本 v2）

新编译的图片和 Excel 主布局按全部可见列（包括留白）合计100%处理。缺少空白边列的一侧补一列4%；两侧都缺少时正文分配92%。已有空白边列时复用其原有比例，不再补该侧，不强制改成4%。隐藏列保持隐藏且百分比为0。

空白边列必须不含字段、正文文字、公式、区域横边框、外侧边框或非白色填充；仅与正文共用的内侧竖边框不妨碍复用。跨整页的静态标题允许跨原边距识别，编译后标题限定在正文列范围。无字段但含说明的边列不是留白列，不能丢弃。原字段、合并、静态内容和必要冻结位置同步调整；明细子 workbook 保持原生系统结构，不额外补左右空白列。

列宽以0.01%整数单位计算，总量10000。已有边距比例保留至两位小数，新增边距固定4%；正文列在相对理想比例偏差不超过0.25个百分点时优先整数，否则使用最多两位小数。尾差按比例误差分配，不让所有误差积到最后一列。不要使用浮点数直接相加相等作为100%的验算，应对每列乘100取整后合计10000。

compile 输出 presentation，包含补充/复用边距、最终列宽及合计100%的结果。v2 引入留白规则，v3 产物增加合并锚点边框、坐标归一和有效高度投影，当前新产物为 v5（见下文）。此前无标记/v2 的产物仍按原规则重编译校验。采用新规则时重新 inspect → compile → preview → apply，不手工改旧产物。

### 工作流模块、初始化及 WB 验收问题（2026-10-14）

工作流表单使用 formId，inspect 或在线 compile 必须传 --module workflow；eBuilder 默认使用 objId，已有 eBuilder formId 使用 --id-type form。模块缺失时只给出明确提示，不自动跨模块查询或切换。apply/verify 从编译产物继承目标模块，无需重复指定；preview 完全离线，不接收模块参数。

```bash
e10-cli form layout inspect <流程表单formId> --module workflow --out context.json
e10-cli form layout compile <流程表单formId> --module workflow \
  --source @source.json --spec @spec.json --context @context.json --out artifact.json
e10-cli form layout preview --artifact @artifact.json --out preview.html
e10-cli form layout apply <流程表单formId> --artifact @artifact.json --out result.json
```

新字段必须先生成完整原生组件，源布局不负责补造组件。推荐批量 wf-form add-fields，默认在末尾初始化一次，再 inspect。多次 add-field 可以在中间使用 --no-init，但全部字段完成后必须执行最后一次 layout init，再 inspect/compile。不能统一建议建字段加 --no-init 后直接还原；原布局中没有新字段组件时会阻断。源布局保存后不得再自动 initLayout。

图片 geometry 区域的跨行底边、跨列右边同时写入合并锚点与原外围单元格，以适配当前 E10 合并区域绘制。仅给覆盖格写边框可能导致运行态断线；额外边框计入投影和回读。workbook cells 的 row/col 统一为字符串，组件 excel.row/col 仍按原生数值契约保存。

保存后验收只从比较副本排除 pageLayouts 页级 updateTime/updateTimeStamp/pageVersion，并在 ignoredPageMetadata 列出。保存前 snapshotHash 仍保留完整版本及 config.styles；不得手工清理 context 或从摘要忽略样式来绕过并发保护。

apply 的 saveAccepted=true 表示接口接受请求；null 表示没有发送请求或响应未知，结合 mutationStarted 判断。saved/verified 表示独立回读符合目标，styleComplete 表示观察投影无遗漏且回读一致。接口接受与回读失败可以同时出现，不能把它解释成接口未保存，也不能据此自动重发。

若 TextArea 的高度/自动高度被字段元数据覆盖，报告会在 platformNotPersisted 列出，但有效展示差异仍保留在 differences。disableAutoHeight 被运行态使用，不能统一忽略。需要修改字段层配置时走字段配置路径，本模块不自动更新业务字段。fitCell=true 时 rows 不再独立投影，报告 notes 说明原因。

观察中的说明、识别依据、业务示例值不写默认值等放入 imageStyles.notes；真正未还原的虚线框、未知控件或样式属性放入 issues。notes 不导致 INCOMPLETE，issues 仍表示遗漏；不自动按关键词把历史 issues 改成 notes，也不因为 workbook 逐格一致就宣称像素还原完成。

## v5 表格边线完整性与粗细确认（2026-10-15）

图片必须逐个观察表格正文范围及四侧外框。范围使用源 Sheet 的零起始行列，不包含新增的 4% 留白，不把表格上方标题、编号或控件蓝框包进正文外框。贴着图片边缘的细线也要检查。边线存在时记录颜色、粗细与线型；明确没有边线填 none，不能判断填 unknown。只有原图明确没有表格时才能使用空数组；缺失 tableBorders 表示尚未观察，不等于没有外框。

```json
{
  "imageStyles": {
    "schemaVersion": "e10.image-styles/v1",
    "tableBorders": [{
      "sheet": "图片观察", "row": 2, "col": 0, "rowCount": 7, "colCount": 5,
      "top": {"color":"#000000", "width":2, "line":"solid"},
      "right": {"color":"#000000", "width":2, "line":"solid"},
      "bottom": {"color":"#000000", "width":2, "line":"solid"},
      "left": {"color":"#000000", "width":2, "line":"solid"}
    }],
    "issues": []
  }
}
```

该范围只为示意，须按本次原图填写；不能套成所有图片的默认范围或默认 2px。内部边线继续通过 geometry.regions.style 或 cells.style 记录。外框观察最后作用于正文边缘，覆盖冲突的旧外框样式；none 同时清除对应相邻格的共享边线，unknown 不补画。外框切断合并区、穿越源明细迁移行或多个声明冲突时阻断并要求修正观察。

v5 几何投影只清除合并内部的无效边线；区域没有声明某条外围边线时，保留源单元格已有的边线。明确区域样式优先于源单元格，最后采用 tableBorders 的外框声明。合并区域的外边线同时写入外围单元格和必要锚点，再整体平移以保留边距；不将边框画到新增空白列。Excel 不使用图片外框观察。

style-review 展示 tableBorders（四侧外框）和 gridBorderStyles（网格内已有线型、粗细、颜色清单），issues/notes 也必须向用户说明。字体、字号、对齐、几何比例、分行和竖排等仍要对照原图核对，已知遗漏不得以 API 回读通过替代视觉验收。

线宽按真实源图像素及缩放估计，不能把所有边线统一识别为 width=1。原生实线 1/2/3px 分别编码为 style=1/2/5；虚线 1/2px 为 style=3/8。原生点线与双线以 2px 绘制；旧观察中的 width=1 点线/双线仍保留历史编码，预览和清单如实显示原生宽度，不声称其为精确 1px。不能通过同时给相邻格画线模拟加粗。

用户明确要求表格线加粗或改色时，Agent 可整理如下 overrides；只修改已声明表格正文内已有边线及已识别外框，不新增 none/unknown 边线，不改变控件输入框边框、编号区或页标题：

```json
{"gridBorderStyle":{"width":"2px","color":"黑色","line":"实线"}}
```

使用已有 style-review --source ... --spec ... --overrides ... --confirm --out ... 命令，前提是用户已确认或明确给出修改指令；无法转换的粗细/线型逐项保留原值并列入 rejected，其他有效项继续采用。默认不修改内部线宽；用户仅调整外框时应修改观察稿的对应外框声明，不能使用全表格 gridBorderStyle。

compile 可对旧观察生成待审草稿并提示 IMAGE_BORDER_OBSERVATION_REQUIRED；新 v5 图片在确认、form create 前置检查和 apply 前要求明确 tableBorders。unknown 默认阻断，只有用户已明确接受缺失并使用 allowUnsupported 时才可继续，报告保持 INCOMPLETE。style-audit/verify/apply 结果增加 imageBorderReport，逐项核对已声明边线及明确无边线（含合并锚点），变细、缺失、错色和多画都能定位。此报告证明观察到原生回读的投影，不证明原图像素完全一致。

v5 承接 v4 的标题对齐和样式二次确认；无标记、v2、v3、v4 产物仍按对应版本重编译校验。采用本次修复需要重新观察边框、用户确认并 compile，不能直接修改旧产物中的保存请求。
