# lesson.json 数据格式

注入模板 `__LESSON_DATA__` 的对象，分三部分：`lesson` / `steps` / `model`。
题目结构（spec.json）、占位符、以及哪些字段会被自动补全，见 `api.md`。

```jsonc
{
  "lesson": {
    "meta": "交互解题 · 线面角",                  // 顶部小标签
    "title": "……题面……",                        // 可含 $…$ 与 <br>；小问之间用 <br> 分行
    "answerLabel": "……答案的文字说明……"
    // language / answerValue / ui 由 build.py 自动补全，不用写
  },
  "steps": [
    {
      "title": "步骤标题",
      "content": "<p>HTML 段落，行内公式 $…$，独立公式 $$…$$，数值用 {{vals.x}} 占位</p>",
      "highlight": ["Line_BE", "Plane_PAC"],     // 该步要“可见”的可切换元素（绝对集合）
      "cameraPos": { "x": 4, "y": 4.5, "z": 4 }  // 该步镜头位置（three 坐标）
    }
  ],
  "model": {
    "elements": {                                // 可切换命名元素，默认隐藏
      "Line_BE":   { "type": "line",  "a": "B", "b": "E", "color": "emphasis", "depthTest": false },
      "Plane_PAC": { "type": "plane", "pts": ["P", "A", "C"] },
      "Normal_Vector": { "type": "arrow", "origin": "O", "dir": [0,0,1], "length": 1.5, "color": "normal" },
      "Len_AB":    { "type": "measure", "a": "A", "b": "B", "label": "{{vals.len_AB}}" },
      "Axis":      { "type": "axes",  "size": 3 }
    }
    // points / spheres / edges / target / initialCamera 由 build.py 自动补全，不用写
  }
}
```

需要覆盖自动补全时（例如要额外画一条命名的辅助棱），再手写对应字段：

```jsonc
"edges": [
  { "a": "A", "b": "B" },
  { "a": "D", "b": "A", "dashed": true },
  { "a": "B", "b": "D", "color": "aux", "dashed": true, "name": "Line_BD" }  // 命名后可被 highlight
]
```

## 答案卡：单问 vs 多问

答案卡只有一个大号数值位。**`answerValue` 只放一个简短的值**（如 `$\dfrac{\sqrt{39}}{26}$`），
build.py 会自动填好，通常你不用写。

题面含 `(1)(2)(3)` 等多个小问时，**必须改用 `lesson.answers` 逐问列出**，否则校验不通过：

```jsonc
"lesson": {
  "title": "……菱形底面……<br>(1) 证明：$AD\\perp EF$；<br>(2) 求 $\\dfrac{V_1}{V_2}$；<br>(3) 求线面角正弦值。",
  "answerLabel": "三问结论",
  "answers": [
    { "label": "(1) 垂直关系",              "value": "$AD \\perp EF$" },
    { "label": "(2) 体积比 $\\dfrac{V_1}{V_2}$", "value": "$\\dfrac{3}{64}$" },
    { "label": "(3) 线面角正弦值",           "value": "${{answer}}$" }
  ]
}
```

> ⚠️ **占位符不自带 `$`**：`{{answer}}` / `{{vals.x}}` / `{{mp.A}}` 展开出来是裸 LaTeX。
> 必须自己包上定界符——写 `"${{answer}}$"`，不是 `"{{answer}}"`。漏了就会原样显示成
> `\frac{\sqrt{39}}{26}`。校验会检查每个字段里落在 `$…$` 之外的 LaTeX 命令并拦下。
> （唯一例外是 `measure` 元素的 `label`，模板会自动补 `$`，那里**不要**写 `$`。）

给了 `answers` 就不要再写 `answerValue`。把多个答案用 `；` 串进 `answerValue`
会把答案卡撑变形（左侧标签被挤成一字一行），校验会直接拦下。

题面长度不受限：超过约 62 字自动缩小字号，超过约 150 字再缩一档，最多占三成屏高后可滚动，
不会把下方解析区压扁。

## 元素类型（model.elements[*].type）
- `line` — `a`、`b`（点名）；`color`；`dashed`；`depthTest:false` 表示永远画在最前。
- `plane` — `pts`（3 或 4 个点名）。
- `arrow` — `origin`（点名或坐标）、`dir`（three 方向向量）、`length`、`color`。
- `axes` — `size`。一般只在建系那步显示。
- `sphere` — 半透明球面 + 经纬线框，用于外接球 / 内切球：`center`（点名或坐标）、`radius`、
  可选 `color`、`opacity`（默认 0.12）。**radius 用 three 坐标**（= 数学半径 × `scale`）。
- `cylinder` / `cone` — 圆柱侧面 / 圆锥侧面：`bottom`+`top` / `base`+`apex`（点名）、`radius`
  （同样是 three 坐标）、可选 `color`、`opacity`。用 `body: "cylinder"|"cone"` 时**不必手写**，
  曲面会作为 `model.solid` 自动补全并常驻显示；只有要额外画一个圆柱/圆锥时才写进 `elements`。
- `measure` — 线段长度标注：在 `a`、`b` 中点朝外偏移贴一个 MathJax 长度标签。
  - `label`：长度 LaTeX（不带 `$`），用 `{{vals.len_XX}}` 取值（需在 spec 的 `lengths` 里声明）。
  - `offset`：可选，朝外偏移量（默认 0.24）。
  - **何时用**：题面给出了线段长度就为对应棱加一个 `measure`，并把 key 放进"建系/列已知条件"那步的 `highlight`。
  - 存在任一 `measure` 时，画布左上自动出现"长度标注：开/关"总开关，无需额外数据。

## 地平面（自动，不用写）
场景里会自动铺一块比背景略亮、向外渐隐的水平底板 + 网格，给学生一个空间参照。
尺寸跟着几何体走，**一格 = 数学坐标 1 个单位**（格宽取 `model.scale`，由 build.py 自动补），
所以学生可以直接数格子读坐标。底板贴在几何体最低点（常规几何体就是 $z=0$ 建系平面）。

## 颜色语义名（COLORS）
`frame`(骨架灰) · `aux`(辅助浅灰) · `emphasis`(强调洋红) · `normal`(法向量红) · `plane`(平面蓝) · `point`(顶点深蓝)

## highlight 规则
每步的 `highlight` 是该步**应可见的可切换元素的完整列表**（绝对集合，不是增量）。
骨架棱与顶点小球始终可见，不必列入。拼错的键会被模板静默忽略——`build.py` 会当成错误拦下来。

典型 4 步节奏：建系（亮 `Axis` + 各 `measure`）→ 亮出所求直线 → 亮出平面与法向量 → 代公式求解。

## 渲染取色建议
- 所求直线：`emphasis` + `depthTest:false`（始终可见，不被几何体挡住）。
- 辅助线（对角线、投影）：`aux` + `dashed`。
- 所求平面：`plane`（半透明）。法向量：`arrow` + `normal`。
- 坐标轴：`axes`，一般只在建系那步显示。
- 每步 `cameraPos` 给一个能看清当前重点的视角；`target` 默认取几何体中心（自动补全）。

## 动点拖拽 + 实时数值（model.draggable，可选）
让一个动点沿约束线段拖动，联动依赖点与图元，并实时显示真实几何量（在**数学坐标**下计算）。
`model.scale` 与 `model.mathPoints` 由 build.py 自动补全。

```jsonc
"draggable": {
  "point": "P",                     // 被拖动的点（画成更大的强调色球）
  "along": ["A1", "C1"],            // 约束线段端点
  "t": 0.75,                        // 题目设定位置的参数 t∈[0,1]（如 A1P=3PC1 -> 0.75）
  "standardLabel": "标准位 A₁P=3PC₁",
  "dependent": [ { "name": "D", "kind": "midpoint", "of": ["P", "C"] } ],
  "readouts": [
    { "label": "三棱锥 B₁-APC 体积", "type": "volume_tetra", "pts": ["B1","A","P","C"] },
    { "label": "A₁P 长度", "type": "length", "pts": ["A1","P"] }
  ]
}
```
- readout `type`：`volume_tetra`(4点)、`length`(2点)、`line_plane_angle_sin`(`line`:2点, `plane`:3点)。
- 拖到 `t` 附近显示"标准位 ✓"。步骤里的精确符号解仍对应该标准位。
