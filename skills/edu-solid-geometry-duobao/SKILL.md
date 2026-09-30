---
name: edu-solid-geometry-doubao
description: >-
  把一道立体几何题解成一个自包含的交互教学网页：左侧 MathJax 分步解析，
  右侧 Three.js 可交互 3D 模型（分步高亮 + 镜头切换）。支持三种入口——给定文字题目、
  随机出题、上传题目图片识别后解题。覆盖正方体/长方体、棱锥/棱柱、圆柱/圆锥上的线面角、
  二面角、异面直线夹角、点到平面距离、体积等题型，统一用"建系+向量法"，并由 sympy 精确
  计算驱动（答案、3D 坐标、步骤数值同源一致）。其他 agent 也可调用本技能生成此类网页。
  触发词：立体几何, 线面角, 二面角, 异面直线, 点到平面距离, 正四棱锥, 正方体求角, 解这道几何题,
  随机出一道立体几何题, 这张图里的立体几何题; solid geometry, line-plane angle, dihedral angle,
  angle between skew lines, distance to plane, interactive geometry solution page.
---

# 立体几何解题 → 交互网页

产出一个可直接用浏览器打开的单页 HTML：左侧题面/答案/分步解析（MathJax），
右侧对应的 3D 模型（Three.js，可旋转缩放，分步高亮 + 切镜头）。

## 只读这两个文件

- `references/api.md` —— spec 格式、query 题型、占位符、命令。**开工前读它。**
- `references/problem-schema.md` —— lesson.json 的字段与元素类型。写讲解时读它。

**不要读** `template/lesson.html`（51KB）、`lib/*.py`、`scripts/*.py`——里面的东西
`api.md` 全都写清楚了，读源码纯属浪费上下文。英文界面文案会自动注入，不需要去翻模板。

## 流程（2 次工具调用：写一个 JSON，跑一条命令）

`problem.json` 顶层四个键：`spec`（题目结构）+ `lesson` / `steps` / `model`（讲解内容）。

### 1a. `spec` —— 把题目变成结构（格式见 api.md）

几何体 + 尺寸 + 构造点 + 所求 + 语言。内置几何体覆盖长方体/正方体、正 n 棱柱与正 n 棱锥、
直棱柱（底面任意）、正四面体、圆柱、圆锥；**再冷门的多面体用 `body: "custom"` 直接给顶点坐标**，
不要因为"没有内置"就去写 Python。三种入口都归一到这里：
- **文字题目**：直接抽取。
- **图片**：视觉读图后，**把识别到的题面/几何体/尺寸/所求回显给用户确认**再继续。
- **随机出题**：直接用 `scripts/generate.py random <seed> ./random.html`，一条命令出图，流程到此结束。

> **输出语言跟随提示词语言**：英文提示 → 英文网页。在 spec 里写 `"language": "en"` 即可，
> 界面文案自动切换，你只需把 `title` / `steps` 用英文写。

### 1b. `lesson` / `steps` / `model` —— 讲解内容

`lesson`（题面）+ `steps`（4 步左右：建系 → 关键向量 → 法向量 → 代公式）+ `model.elements`。

- **所有数值一律用占位符**（`{{answer}}` / `{{vals.sin}}` / `{{mp.A}}`），不要心算、不要手抄。
- `points` / `spheres` / `edges` / `target` / `initialCamera` / `answerValue` **不用写**，会自动补全。
- **多问题目**（题面有 `(1)(2)(3)`）：小问之间用 `<br>` 分行，答案用 `lesson.answers` 逐问列出，
  **不要**把多个答案用 `；` 串进 `answerValue`——那会把答案卡撑变形，校验也会拦下。
- 题面给出线段长度时，在 spec 的 `lengths` 里声明，再加一个 `measure` 元素，
  并把它放进"建系"那步的 `highlight`。

### 2. 出图 + 自检

```bash
python3 <技能目录>/scripts/build.py problem.json "$(pwd)/solution-<题目简述>.html"
```

一条命令完成求解、占位符替换、默认值补全、渲染、静态自检。
打印 `PASS` 即通过（答案一致性、highlight 键、点名引用、公式定界符都已校验过）；
打印 `FAIL` 时按它列出的问题改 problem.json 重跑，**不要**靠起服务截图去排查。

> 📍 **成品和中间文件都写到用户当前工作目录（cwd）**，绝不要写进技能自身目录。
> 只有用户明确要求"看看效果"时才起本地服务预览，看完立刻停掉，不要留下占用端口的进程。

### 3. 交付

把 cwd 下的 HTML 路径告诉用户，可直接浏览器打开。

## 装不上依赖时

需要 `sympy`。import 失败时**先询问用户是否安装**，同意后再
`python3 -m pip install sympy`，或换一个已装该库的解释器；**不要未经询问直接装**。

## 扩展与维护

- **加题型/几何体**：在 `lib/geometry_kernel.py` 加函数，在 `scripts/solve.py` 的
  `BODIES` / `QUERIES` 注册，并更新 `references/api.md` 的表格。
- **改完跑回归**：`python3 <技能目录>/scripts/selftest.py`（仅维护技能时用，解题流程里不要跑）。

## 目录
- `references/api.md` — spec 格式 / 题型 / 占位符 / 命令 ← 常读
- `references/problem-schema.md` — lesson.json 字段 ← 常读
- `scripts/build.py` — 求解+渲染+自检 一条命令
- `scripts/solve.py` — spec → 精确解（可单独跑来看答案）
- `scripts/validate.py` — 成品静态自检
- `scripts/generate.py` — 内置题目与随机出题
- `scripts/selftest.py` — 技能自身回归测试
- `lib/geometry_kernel.py` · `lib/bodies.py` · `template/lesson.html` — 内部实现，不必读
