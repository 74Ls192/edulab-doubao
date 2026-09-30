# API 速查（读这一页就够，不要去读 lib/ 和 scripts/ 的源码）

## 命令

```bash
python3 <技能目录>/scripts/build.py problem.json out.html        # 求解+渲染+自检，一步到位
python3 <技能目录>/scripts/solve.py  problem.json                # 可选：只看答案和中间量
```
`problem.json` 一个文件搞定，顶层结构是 `{ "spec": {…}, "lesson": {…}, "steps": […], "model": {…} }`：
`spec` 是题目结构（下一节），其余是讲解内容。也可拆成两个文件：
`build.py spec.json lesson.json out.html`。

`build.py` 成功打印 `PASS 已生成: …`；有问题打印 `FAIL` 并列出每个问题，**不写出文件**。

## spec —— 题目结构

```jsonc
{
  "language": "zh-CN",              // zh-CN / en；en 时英文界面文案自动注入
  "body": "cube",                   // 见下表
  "dims": { "edge": 1 },            // 该 body 的尺寸参数
  "scale": 2,                       // 3D 观感缩放，不影响解题数值（默认 1.5）
  "givens": [                       // 可选：构造点
    { "name": "E", "kind": "midpoint", "of": ["P", "C"] },
    { "name": "F", "kind": "ratio",    "of": ["A1", "C1"], "t": "3/4" },  // F = A1 + t(C1-A1)
    { "name": "G", "kind": "centroid", "of": ["A", "B", "C"] },
    { "name": "H", "kind": "point",    "at": [1, 0, "1/2"] }
  ],
  "vectors": { "BE": ["B", "E"] },  // 可选：额外要展示的向量 -> vals.vec_BE
  "lengths": { "AB": ["A", "B"] },  // 可选：额外要展示的长度 -> vals.len_AB
  "query": { "type": "line_plane_angle", "line": ["B","E"], "plane": ["P","A","C"] }
}
```

### body（`dims` 的键就是下表 dims 列的名字）

| body | dims | 建系 | 点名 |
|---|---|---|---|
| `cuboid` | `lx`, `ly`, `lz` | A 为原点，AB 沿 x、AD 沿 y、AA1 沿 z | A,B,C,D,A1,B1,C1,D1 |
| `cube` | `edge` | 同上 | 同上 |
| `regular_quad_pyramid` | `base_edge`, `height` | 底面中心 O 为原点，对角线 AC 在 x 轴、BD 在 y 轴、P 在 z 轴 | O,A,B,C,D,P |
| `regular_prism` | `n`, `base_edge`, `height` | 底面正 n 边形中心为原点、在 z=0；第一个顶点在 x 轴正向 | A,B,…（n 个）+ A1,B1,… |
| `regular_pyramid` | `n`, `base_edge`, `height` | 底面正 n 边形中心 O 为原点，顶点 P 在 z 轴 | O,P,A,B,…（n 个） |
| `right_prism` | `base`（`{"A":[x,y],…}`）, `height` | 底面按你给的 2D 坐标放在 z=0，沿 z 拉伸 | 你给的名字 + 加 `1` 的顶面 |
| `regular_tetrahedron` | `edge`（默认 2√2） | 对称建系 | A,B,C,D |
| `cylinder` | `radius`, `height` | 底面圆心 O 为原点，轴沿 z 轴 | O,O1 + 底面圆周 A,B,C,D(0°/90°/180°/270°) + A1,B1,C1,D1 |
| `cone` | `radius`, `height` | 底面圆心 O 为原点，顶点 P 在 z 轴 | O,P + 底面圆周 A,B,C,D |
| `custom` | —（改用 `points`） | 你自己定 | 你给的名字 |

- **正三棱柱 / 正六棱柱** 用 `regular_prism` + `n: 3` / `n: 6`；**正三棱锥 / 正六棱锥** 用 `regular_pyramid`。
  正四棱柱用 `cuboid`（`lx = ly`）。
- **底面不规则的直棱柱**（如底面是直角三角形）用 `right_prism`，底面顶点直接给 2D 坐标。
- **圆柱 / 圆锥**：曲面会自动渲染（`model.solid`），骨架只画轴线与 4 条母线。
- **上面都表达不了的多面体**：用 `custom`，在 spec 里直接给
  `"points": {"A": [0,0,0], "B": [1,0,"sqrt(3)"], …}`（坐标可写 `"1/2"`、`"sqrt(3)"` 这类字符串）
  和 `"topo": {"spheres": […], "edges": [{"a":"A","b":"B"}, …]}`。**不要为此去写 Python。**

棱拓扑（spheres/edges）随 body 自动带出。想覆盖时在 spec 里给 `"topo": {…}`。

### query.type 与它产出的 `vals` 键

统一走"建系 + 向量法"。**不要心算任何数值**，全部用占位符引用下表的 `vals`。

| type | 必填字段 | 公式 / answer | vals 键 |
|---|---|---|---|
| `line_plane_angle` | `line`(2点), `plane`(3或4点) | $\sin\theta=\frac{\|\vec v\cdot\vec n\|}{\|\vec v\|\|\vec n\|}$ | `v` `n` `n_simpl` `dot` `norm_v` `norm_n` `sin` |
| `line_line_angle` | `line1`(2点), `line2`(2点) | $\cos\theta=\frac{\|\vec{d_1}\cdot\vec{d_2}\|}{\|\vec{d_1}\|\|\vec{d_2}\|}$ | `d1` `d2` `dot` `norm_d1` `norm_d2` `cos` |
| `dihedral` | `edge`(2点), `p1`, `p2` | 两半平面内垂直于棱的向量夹角；cos 带符号，负=钝角 | `u` `v1` `v2` `dot` `norm_v1` `norm_v2` `cos` |
| `point_plane_distance` | `point`, `plane`(3点) | $d=\frac{\|(P-P_0)\cdot\vec n\|}{\|\vec n\|}$ | `n` `n_simpl` `w` `dot` `norm_n` `dist` |
| `volume` | `kind`: `tetra`(+`pts` 4点) / `box`(+`lx,ly,lz`) / `prism`·`pyramid`(+`base_area,height`) | 按体型公式 | `V` |

> 坐标系：题面与公式里展示的是**数学坐标（z 轴向上）**；3D 渲染用 **three.js 坐标（y 轴向上）**，
> 映射为 `three = (x, z, y) * scale`。`scale` 只影响观感，不影响解题数值。两者同源，不要手填 3D 坐标。

## lesson / steps / model —— 讲解内容

字段含义见 `problem-schema.md`。**所有数值一律用占位符**，不要自己算、也不要抄：

| 占位符 | 内容 |
|---|---|
| `{{answer}}` | 最终答案的 LaTeX（不带 `$`） |
| `{{mp.A}}` | 点 A 的数学坐标，如 `(0, 0, 1)` |
| `{{vals.sin}}` | 上表里该题型的中间量 |
| `{{vals.len_AB}}` / `{{vals.vec_BE}}` | spec 里 `lengths` / `vectors` 声明的量 |

行内替换（`"$\\vec n = {{vals.n_simpl}}$"`），整串就是一个占位符时会还原成原始对象。占位符拼错会直接报错并列出可用键。

> ⚠️ **占位符展开的是裸 LaTeX，不带 `$`。** 自己把定界符写上：`"${{answer}}$"`，
> 不是 `"{{answer}}"`——后者会原样显示成 `\frac{\sqrt{39}}{26}`。
> 任何字段里落在 `$…$` 之外的 LaTeX 命令都会被校验拦下。
> 例外：`measure` 元素的 `label` 由模板自动补 `$`，那里写 `"{{vals.len_AB}}"` 即可。

### build.py 自动补全的字段（**能省则省，不要手写**）

`model.points`（=three 坐标）、`model.spheres`、`model.edges`、`model.target`、`model.initialCamera`、
`lesson.language`、`lesson.answerValue`（=`${{answer}}$`）、英文 `lesson.ui`；
有 `model.draggable` 时还会补 `model.scale` 与 `model.mathPoints`。

你**必须**手写的只有：`lesson.meta/title/answerLabel`、`steps[*]`（title/content/highlight/cameraPos）、
`model.elements`。

## 逃生通道：spec 表达不了的题

**先试 `body: "custom"`**（任意多面体都能用显式坐标表达）。只有当**所求**不属于上面 5 类
query 时，才手写 Python 调 kernel。可用函数：

```python
import geometry_kernel as gk        # lib/ 下
gk.V(x,y,z) · gk.midpoint(a,b) · gk.normal_from_points(p,q,r) · gk.simplify_vec(v)
gk.line_plane_angle_sin(v,n) · gk.line_line_angle_cos(d1,d2) · gk.dihedral_cos(A,B,C,D)
gk.point_plane_distance(P,P0,n) · gk.volume_box/prism/pyramid/tetra(...)
gk.regular_quad_pyramid(a,h) · gk.cuboid(lx,ly,lz) · gk.cube(e) · gk.regular_tetrahedron(e)
gk.regular_prism(n,a,h) · gk.regular_pyramid(n,a,h) · gk.right_prism(base,h)
gk.cylinder(r,h) · gk.cone(r,h) · gk.tetrahedron({name:(x,y,z)})
gk.to_three(points, scale)  -> {name: [x,y,z]}   # three 坐标，y 向上
gk.tex(expr) · gk.tex_vec(v) · gk.is_clean(expr)  # LaTeX 输出 / 随机题答案规整判定

import bodies                       # 棱拓扑
bodies.quad_pyramid() · bodies.tri_pyramid() · bodies.cuboid() · bodies.prism(bottom, top)
bodies.pyramid(apex, base) · bodies.round_solid(bottom, top=…|apex=…, axis=…)

from generate import render_html    # render_html(data, out_path)
from validate import validate       # validate(data) -> 问题列表，空=通过
```

出图后仍要跑 `python3 <技能目录>/scripts/validate.py out.html` 自检。

## 内置题目 / 随机出题

```bash
python3 <技能目录>/scripts/generate.py cube|box|pyramid ./x.html
python3 <技能目录>/scripts/generate.py random 7 ./random.html      # 内部用 is_clean 判答案规整，不过重抽
```
