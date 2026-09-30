#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
selftest.py — 技能自身的回归测试（开发维护用，**不是**每次解题的流程步骤）。

覆盖：五类 query 的答案正确性、构造点、占位符替换、默认值补全、
校验器能否抓到错误、英文 UI 自动注入、generate.py 的内置题目。

    python3 scripts/selftest.py
"""

import json
import sys
import tempfile
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL_DIR / "scripts"))
sys.path.insert(0, str(SKILL_DIR / "lib"))

import sympy as sp  # noqa: E402

from solve import solve  # noqa: E402
from build import build, substitute  # noqa: E402
from validate import validate, extract  # noqa: E402
import generate  # noqa: E402

failures = []


def check(ok, name, detail=""):
    print(("PASS  " if ok else "FAIL  ") + name + (f"   {detail}" if detail else ""))
    if not ok:
        failures.append(name)


# ---------- 1. 五类 query 的答案 ----------
CASES = [
    ("棱锥线面角 BE-PAC = 2√22/11",
     {"body": "regular_quad_pyramid", "dims": {"base_edge": 2, "height": 1},
      "givens": [{"name": "E", "kind": "midpoint", "of": ["P", "C"]}],
      "query": {"type": "line_plane_angle", "line": ["B", "E"], "plane": ["P", "A", "C"]}},
     2 * sp.sqrt(22) / 11),
    ("正方体线面角 A1C-底面 = √3/3",
     {"body": "cube", "dims": {"edge": 1},
      "query": {"type": "line_plane_angle", "line": ["A1", "C"], "plane": ["A", "B", "D"]}},
     sp.sqrt(3) / 3),
    ("异面直线 A1C·AB cos = √3/3",
     {"body": "cube", "dims": {"edge": 1},
      "query": {"type": "line_line_angle", "line1": ["A1", "C"], "line2": ["A", "B"]}},
     sp.sqrt(3) / 3),
    ("正四面体二面角 C-AB-D cos = 1/3",
     {"body": "regular_tetrahedron", "dims": {},
      "query": {"type": "dihedral", "edge": ["A", "B"], "p1": "C", "p2": "D"}},
     sp.Rational(1, 3)),
    ("A1 到底面 ABCD 距离 = 1",
     {"body": "cube", "dims": {"edge": 1},
      "query": {"type": "point_plane_distance", "point": "A1", "plane": ["A", "B", "D"]}},
     sp.Integer(1)),
    ("长方体体积 2×3×4 = 24",
     {"body": "cuboid", "dims": {"lx": 2, "ly": 3, "lz": 4},
      "query": {"type": "volume", "kind": "box", "lx": 2, "ly": 3, "lz": 4}},
     sp.Integer(24)),
    ("正四面体(棱2√2)体积 = 8/3",
     {"body": "regular_tetrahedron", "dims": {},
      "query": {"type": "volume", "kind": "tetra", "pts": ["A", "B", "C", "D"]}},
     sp.Rational(8, 3)),
    # ---- 参数化几何体 ----
    ("正三棱柱(棱1高2) A1B-底面 sin = 2√5/5",
     {"body": "regular_prism", "dims": {"n": 3, "base_edge": 1, "height": 2},
      "query": {"type": "line_plane_angle", "line": ["A1", "B"], "plane": ["A", "B", "C"]}},
     2 * sp.sqrt(5) / 5),
    ("正三棱锥(底2高3) 侧棱-底面 sin = 3√93/31",
     {"body": "regular_pyramid", "dims": {"n": 3, "base_edge": 2, "height": 3},
      "query": {"type": "line_plane_angle", "line": ["P", "A"], "plane": ["A", "B", "C"]}},
     3 * sp.sqrt(93) / 31),
    ("直三棱柱(直角底面) C 到平面 A1BC1 = 20√41/41",
     {"body": "right_prism", "dims": {"base": {"A": [3, 0], "B": [0, 4], "C": [0, 0]},
                                      "height": 5},
      "query": {"type": "point_plane_distance", "point": "C", "plane": ["A1", "B", "C1"]}},
     20 * sp.sqrt(41) / 41),
    ("圆柱 母线⊥底面 sin = 1",
     {"body": "cylinder", "dims": {"radius": 1, "height": 2},
      "query": {"type": "line_plane_angle", "line": ["A", "A1"], "plane": ["A", "B", "C"]}},
     sp.Integer(1)),
    ("圆锥 r=h 母线-底面 sin = √2/2",
     {"body": "cone", "dims": {"radius": 1, "height": 1},
      "query": {"type": "line_plane_angle", "line": ["P", "A"], "plane": ["A", "B", "C"]}},
     sp.sqrt(2) / 2),
    ("custom 显式坐标四面体体积 = 1/6",
     {"body": "custom",
      "points": {"A": [0, 0, 0], "B": [1, 0, 0], "C": [0, 1, 0], "D": [0, 0, 1]},
      "topo": {"spheres": ["A", "B", "C", "D"],
               "edges": [{"a": "A", "b": "B"}, {"a": "A", "b": "C"}, {"a": "A", "b": "D"},
                         {"a": "B", "b": "C"}, {"a": "C", "b": "D"}, {"a": "B", "b": "D"}]},
      "query": {"type": "volume", "kind": "tetra", "pts": ["A", "B", "C", "D"]}},
     sp.Rational(1, 6)),
]

for name, spec, expected in CASES:
    sol = solve(spec)
    ok = sp.simplify(sp.sympify(sol["_exact"]) - expected) == 0
    check(ok, name, sol["answer"])

# ---------- 2. 构造点 ----------
sol = solve({"body": "cube", "dims": {"edge": 2},
             "givens": [{"name": "P", "kind": "ratio", "of": ["A1", "C1"], "t": "3/4"},
                        {"name": "M", "kind": "midpoint", "of": ["A", "C"]},
                        {"name": "G", "kind": "centroid", "of": ["A", "B", "C"]}],
             "lengths": {"A1P": ["A1", "P"]},
             "query": {"type": "volume", "kind": "tetra", "pts": ["B1", "A", "P", "C"]}})
check(sol["vals"]["len_A1P"] == r"\frac{3 \sqrt{2}}{2}", "ratio 构造点 A1P = 3√2/2",
      sol["vals"]["len_A1P"])
check(sol["mp"]["M"] == "(1, 1, 0)", "midpoint 构造点 M", sol["mp"]["M"])
check("G" in sol["mp"], "centroid 构造点 G", sol["mp"]["G"])

# 正六棱柱：12 个顶点、18 条棱
sol = solve({"body": "regular_prism", "dims": {"n": 6, "base_edge": 1, "height": 2},
             "query": {"type": "line_line_angle", "line1": ["A", "B1"], "line2": ["A1", "C1"]}})
check(len(sol["mp"]) == 12 and len(sol["topo"]["edges"]) == 18,
      "正六棱柱拓扑：12 顶点 / 18 棱",
      f'{len(sol["mp"])} 点 {len(sol["topo"]["edges"])} 棱')

# 圆柱/圆锥自动带出曲面，半径已换算到 three 坐标
sol = solve({"body": "cone", "dims": {"radius": 2, "height": 3}, "scale": 1.5,
             "query": {"type": "line_plane_angle", "line": ["P", "A"], "plane": ["A", "B", "C"]}})
check(sol["solid"] == {"type": "cone", "base": "O", "apex": "P", "radius": 3.0},
      "圆锥自动带出 model.solid（半径 2×1.5=3）", str(sol["solid"]))

# custom 缺 topo 要有明确报错
try:
    solve({"body": "custom", "points": {"A": [0, 0, 0]},
           "query": {"type": "volume", "kind": "box", "lx": 1, "ly": 1, "lz": 1}})
    check(False, "custom 缺 topo 应报错")
except ValueError as e:
    check("topo" in str(e), "custom 缺 topo 时报错并说明怎么补")

# ---------- 3. 占位符替换 ----------
ctx = {"answer": "X", "vals": {"v": "(1,1,-1)"}, "topo": {"spheres": ["A", "B"]}}
check(substitute("值是 {{vals.v}}，答案 {{answer}}", ctx) == "值是 (1,1,-1)，答案 X",
      "行内占位符替换")
check(substitute("{{topo.spheres}}", ctx) == ["A", "B"], "整串占位符还原为原始对象")
try:
    substitute("{{vals.nope}}", ctx)
    check(False, "未知占位符应报错")
except KeyError as e:
    check("nope" in str(e) and "可用键" in str(e), "未知占位符报错并列出可用键")

# ---------- 4. 校验器能抓到错误 ----------
bad = {
    "lesson": {"answerValue": "$1$"},
    "steps": [{"title": "t", "content": "<p>只有一个 $ 符号，答案 1</p>",
               "highlight": ["Typo_Key"], "cameraPos": {"x": 1, "y": 1, "z": 1}}],
    "model": {"points": {"A": [0, 0, 0]},
              "elements": {"L": {"type": "line", "a": "A", "b": "NoSuchPoint"}}},
}
errs = validate(bad, answer="1")
check(any("Typo_Key" in e for e in errs), "抓到拼错的 highlight 键")
check(any("NoSuchPoint" in e for e in errs), "抓到不存在的点名")
check(any("$" in e for e in errs), "抓到 $ 未配对")

# 模板支持的全部元素类型都要被校验器认可（曾漏掉 sphere 导致误判）
ok_all = {
    "lesson": {"title": "正方体 $ABCD$ 中求线面角", "answerValue": "$1$"},
    "steps": [{"title": "t", "content": "<p>答案 1</p>",
               "highlight": ["S", "Cy", "Co", "Ln", "Pl", "Ar", "Ax", "Me"],
               "cameraPos": {"x": 1, "y": 1, "z": 1}}],
    "model": {"points": {"A": [0, 0, 0], "B": [1, 0, 0], "O": [0, 0, 0], "O1": [0, 1, 0],
                         "P": [0, 2, 0]},
              "solid": {"type": "cylinder", "bottom": "O", "top": "O1", "radius": 1},
              "elements": {
                  "S": {"type": "sphere", "center": "O", "radius": 1.5},
                  "Cy": {"type": "cylinder", "bottom": "O", "top": "O1", "radius": 1},
                  "Co": {"type": "cone", "base": "O", "apex": "P", "radius": 1},
                  "Ln": {"type": "line", "a": "A", "b": "B"},
                  "Pl": {"type": "plane", "pts": ["A", "B", "O"]},
                  "Ar": {"type": "arrow", "origin": "A", "dir": [0, 1, 0]},
                  "Ax": {"type": "axes", "size": 3},
                  "Me": {"type": "measure", "a": "A", "b": "B", "label": "1"}}},
}
check(validate(ok_all, answer="1") == [], "sphere/cylinder/cone 等全部元素类型都被认可",
      str(validate(ok_all, answer="1")))

# ---------- 4b. 模板与英文文案的键必须一一对应 ----------
import re  # noqa: E402

tpl_src = (SKILL_DIR / "template" / "lesson.html").read_text(encoding="utf-8")
ui_block = re.search(r"const defaultUI = \{(.*?)\n        \};", tpl_src, re.S).group(1)
tpl_keys = set(re.findall(r"^\s*([A-Za-z]+):", ui_block, re.M))
en_keys = set(json.loads((SKILL_DIR / "template" / "ui-en.json").read_text(encoding="utf-8")))
# pageTitle 不翻译：默认取 lesson.title
check(tpl_keys - en_keys == {"pageTitle"} and not en_keys - tpl_keys,
      "ui-en.json 覆盖模板 defaultUI 的全部可翻译键",
      f"模板独有 {sorted(tpl_keys - en_keys)} / 英文独有 {sorted(en_keys - tpl_keys)}")

# 模板里用到的每个 ui.* 键都必须在 defaultUI 里有兜底
used = set(re.findall(r"\bui\.([A-Za-z]+)", tpl_src))
check(not used - tpl_keys, "模板引用的 ui 键都有 defaultUI 兜底", f"缺失 {sorted(used - tpl_keys)}")

# 脚本里 getElementById 的每个 id 都必须真的存在（改版式时最容易漏掉，页面会直接抛错）
body_html = tpl_src[tpl_src.index("<body>"):]
wanted = set(re.findall(r"getElementById\('([a-z0-9-]+)'\)", tpl_src))
present = set(re.findall(r'id="([a-z0-9-]+)"', tpl_src))
dangling = wanted - present - {"readout-panel"}   # readout-panel 是运行时动态创建的
check(not dangling, "getElementById 引用的元素都存在于标记中", f"悬空 {sorted(dangling)}")

# 题面 h1 必须落在某次 typesetMath 的范围里，否则题面的 $…$ 会原样显示。
# 合法的两种写法：h1 在被 typeset 的 #sidebar 内，或单独为 h1 调用一次。
body_only = tpl_src[tpl_src.index("<body>"):tpl_src.index("<!-- 逻辑脚本 -->")]
aside_start = body_only.find('<aside id="sidebar"')
aside_end = body_only.find("</aside>", aside_start)
title_in_sidebar = (aside_start != -1
                    and aside_start < body_only.find('id="lesson-title"') < aside_end)
typeset_targets = set(re.findall(r"typesetMath\(document\.getElementById\('([a-z0-9-]+)'\)\)", tpl_src))
check(("lesson-title" in typeset_targets)
      or (title_in_sidebar and "sidebar" in typeset_targets),
      "题面 h1 落在 MathJax 排版范围内",
      f"h1 在 sidebar 内={title_in_sidebar}, typeset 目标={sorted(typeset_targets)}")
check("titleEl.innerHTML = lesson.title" in tpl_src,
      "题面用 innerHTML 渲染（<br> 分小问才有效）")

# ---------- 4c. 答案卡：拦住会把版式撑坏的形状 ----------
def answer_case(name, lesson_patch, expect_hit):
    d = {
        "lesson": {"title": "正方体 $ABCD$ 中求线面角", "answerValue": "$1$", **lesson_patch},
        "steps": [{"title": "t", "content": "<p>答案 1</p>",
                   "highlight": [], "cameraPos": {"x": 1, "y": 1, "z": 1}}],
        "model": {"points": {"A": [0, 0, 0]}, "elements": {}},
    }
    errs_ = validate(d, answer="1")
    hit = any(expect_hit in e for e in errs_)
    check(hit, name, str(errs_) if not hit else "")

answer_case("拦住超长 answerValue",
            {"answerValue": "$(1)\\,AD \\perp EF$（证毕）；$(2)\\,\\frac{3}{64}$；$(3)\\,\\frac{\\sqrt{39}}{26}$，答案 1"},
            "过长")
answer_case("拦住 answerValue 里的 <br>",
            {"answerValue": "$1$<br>$2$"}, "<br>")
answer_case("拦住多问题面却只给单个答案",
            {"title": "四棱锥 $P\\!-\\!ABCD$ 中……(1) 证明 $AD \\perp EF$；(2) 求 $\\frac{V_1}{V_2}$"},
            "lesson.answers")
answer_case("拦住题面 $ 未配对",
            {"title": "四棱锥 $P-ABCD$ 中，$\\angle BAD=\\frac{2\\pi}{3}"}, "配对")
# 截图里的真实故障：answers[].value 写成 {{answer}} 而漏了 $，页面显示成原始 LaTeX
answer_case("拦住漏掉 $ 的裸 LaTeX（answers）",
            {"answers": [{"label": "(3) 线面角正弦值", "value": "\\frac{\\sqrt{39}}{26}"}]},
            "没被 $…$ 包住")
answer_case("拦住漏掉 $ 的裸 LaTeX（题面）",
            {"title": "求 \\dfrac{V_1}{V_2} 的值"}, "没被 $…$ 包住")

# measure 的 label 规则相反：模板自动补 $，写了反而会渲染成 $$…$$
bad_measure = {
    "lesson": {"title": "正方体求线面角", "answerValue": "$1$"},
    "steps": [{"title": "t", "content": "<p>答案 1</p>", "highlight": ["L"],
               "cameraPos": {"x": 30, "y": 30, "z": 30}}],
    "model": {"points": {"A": [0, 0, 0], "B": [1, 0, 0]}, "target": [0, 0, 0],
              "elements": {"L": {"type": "measure", "a": "A", "b": "B", "label": "$2$"}}},
}
check(any("不要写 $" in e for e in validate(bad_measure, answer="1")),
      "拦住 measure.label 里多写的 $")

# ---------- 4d. 镜头必须装得下几何体 ----------
framing = {
    "lesson": {"title": "正方体求线面角", "answerValue": "$1$"},
    "steps": [{"title": "t", "content": "<p>答案 1</p>", "highlight": [],
               "cameraPos": {"x": 1, "y": 1, "z": 1}}],
    "model": {"points": {"A": [0, 0, 0], "B": [4, 4, 4]}, "target": [2, 2, 2], "elements": {}},
}
errs_f = validate(framing, answer="1")
check(any("裁出画面" in e for e in errs_f), "拦住会把几何体裁出画面的镜头", str(errs_f))
framing["steps"][0]["cameraPos"] = {"x": 20, "y": 20, "z": 20}
check(validate(framing, answer="1") == [], "拉远后的镜头通过校验",
      str(validate(framing, answer="1")))

# 正确的多问写法应当通过
ok_multi = {
    "lesson": {"title": "四棱锥中……(1) 证明 $AD \\perp EF$；(2) 求 $\\frac{V_1}{V_2}$",
               "answerLabel": "三问结论",
               "answers": [{"label": "(1) $AD \\perp EF$", "value": "$证毕$"},
                           {"label": "(2) 体积比", "value": "$1$"}]},
    "steps": [{"title": "t", "content": "<p>答案 1</p>",
               "highlight": [], "cameraPos": {"x": 1, "y": 1, "z": 1}}],
    "model": {"points": {"A": [0, 0, 0]}, "elements": {}},
}
check(validate(ok_multi, answer="1") == [], "lesson.answers 的正确多问写法通过校验",
      str(validate(ok_multi, answer="1")))

# ---------- 5. 端到端：默认值补全 + 英文 UI ----------
spec = {"language": "en", "body": "cube", "dims": {"edge": 1}, "scale": 2,
        "query": {"type": "line_plane_angle", "line": ["A1", "C"], "plane": ["A", "B", "D"]}}
lesson_data = {
    "lesson": {"meta": "Line-plane angle", "title": "Cube ABCD-A1B1C1D1 with edge 1",
               "answerLabel": "sine of the angle"},
    "steps": [{"title": "Set up coordinates",
               "content": "<p>$A{{mp.A}}$, direction ${{vals.v}}$, answer ${{answer}}$.</p>",
               "highlight": ["Line_A1C"], "cameraPos": {"x": 6, "y": 5, "z": 7}}],
    "model": {"elements": {"Line_A1C": {"type": "line", "a": "A1", "b": "C",
                                        "color": "emphasis"}}},
}
with tempfile.TemporaryDirectory() as td:
    out = Path(td) / "en.html"
    build(spec, json.loads(json.dumps(lesson_data)), out)
    data = extract(out.read_text(encoding="utf-8"))
    check(data["model"]["points"], "model.points 自动补全")
    check(len(data["model"]["edges"]) == 12, "model.edges 自动补全（正方体 12 棱）")
    check(data["model"].get("target") and data["model"].get("initialCamera"),
          "target / initialCamera 自动补全")
    # 地平面靠 scale 把网格格宽对齐到数学坐标 1 个单位，缺了刻度说明就不成立
    check(data["model"].get("scale") == 2, "model.scale 自动补全（地平面网格刻度用）",
          str(data["model"].get("scale")))
    check(data["lesson"]["ui"]["next"] == "Next", "language=en 自动注入英文 UI")
    check(validate(data) == [], "生成结果通过校验")

    # ---------- 6. generate.py 的内置题目仍可用 ----------
    for problem in ("pyramid", "cube", "box"):
        d = generate.PROBLEMS[problem]()
        d.pop("_answer", None)
        p = Path(td) / f"{problem}.html"
        generate.render_html(d, p)
        check(p.exists() and validate(d) == [], f"generate.py {problem} 仍可生成并通过校验")
    d = generate.build_random_data(7)
    d.pop("_answer", None)
    check(validate(d) == [], "generate.py random 仍可用")
    check(all(generate.PROBLEMS[p]()["model"].get("scale") for p in generate.PROBLEMS),
          "generate.py 的内置题都带 model.scale")

    # ---------- 7. 单文件 problem.json 形式 + FAIL 时不写出文件 ----------
    import subprocess
    doc = json.loads(json.dumps(lesson_data))
    doc["spec"] = spec
    single = Path(td) / "problem.json"
    single.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    out2 = Path(td) / "single.html"
    r = subprocess.run([sys.executable, str(SKILL_DIR / "scripts" / "build.py"),
                        str(single), str(out2)], capture_output=True, text=True)
    check(r.returncode == 0 and out2.exists(), "单文件 problem.json 形式可用", r.stdout.strip())

    doc["steps"][0]["highlight"] = ["Typo_Key"]
    bad_path = Path(td) / "bad.json"
    bad_path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    out3 = Path(td) / "bad.html"
    r = subprocess.run([sys.executable, str(SKILL_DIR / "scripts" / "build.py"),
                        str(bad_path), str(out3)], capture_output=True, text=True)
    check(r.returncode == 1 and not out3.exists() and "Typo_Key" in r.stderr,
          "校验失败时退出码 1 且不写出文件")

print()
if failures:
    print(f"❌ {len(failures)} 项失败: {failures}")
    sys.exit(1)
print("✅ 全部自检通过")
