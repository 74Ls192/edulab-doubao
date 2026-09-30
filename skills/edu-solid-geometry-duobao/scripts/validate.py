#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
validate.py — 对生成的 lesson data 做静态自检，替代"起服务 + 截图"的人工检查。

覆盖模板会**静默忽略**的那些错误（拼错的 highlight 键、不存在的点名等），
以及答案一致性。build.py 会自动调用；也可单独对成品 HTML 跑：

    python3 scripts/validate.py solution-xxx.html
"""

import json
import math
import re
import sys
from pathlib import Path

LATEX_CMD = re.compile(r"\\[a-zA-Z]+")
# 相机 fov = 45°（见 template/lesson.html）：装下半径 r 的包围球需 d >= r / sin(22.5°)
CAMERA_FIT = 1 / math.sin(math.radians(22.5))   # ≈ 2.61

ELEMENT_REQUIRED = {
    "line": ("a", "b"),
    "plane": ("pts",),
    "arrow": ("origin", "dir"),
    "axes": ("size",),
    "measure": ("a", "b", "label"),
    "sphere": ("center", "radius"),      # 外接球 / 内切球
    "cylinder": ("bottom", "top", "radius"),
    "cone": ("base", "apex", "radius"),
}
# 各元素类型里"值是点名"的字段，需要校验点存在
POINT_FIELDS = ("a", "b", "origin", "center", "bottom", "top", "base", "apex")


def validate(data, answer=None):
    """返回问题列表，空列表表示通过。"""
    errs = []
    lesson = data.get("lesson") or {}
    steps = data.get("steps") or []
    model = data.get("model") or {}
    points = model.get("points") or {}
    elements = model.get("elements") or {}
    edges = model.get("edges") or []

    if not steps:
        errs.append("steps 为空")
    if not points:
        errs.append("model.points 为空")

    # 1. 所有被引用的点名都必须存在于 model.points
    def check_point(name, where):
        if isinstance(name, str) and name not in points:
            errs.append(f"{where} 引用了不存在的点 {name!r}（已有：{sorted(points)}）")

    for i, e in enumerate(edges):
        check_point(e.get("a"), f"model.edges[{i}]")
        check_point(e.get("b"), f"model.edges[{i}]")

    def check_element(key, el):
        etype = el.get("type")
        if etype not in ELEMENT_REQUIRED:
            errs.append(f"elements[{key!r}].type={etype!r} 不是合法类型："
                        f"{sorted(ELEMENT_REQUIRED)}")
            return
        for field in ELEMENT_REQUIRED[etype]:
            if field not in el:
                errs.append(f"elements[{key!r}] 缺少 {etype} 必需的字段 {field!r}")
        for field in POINT_FIELDS:
            if field in el:
                check_point(el[field], f"elements[{key!r}].{field}")
        for j, p in enumerate(el.get("pts") or []):
            check_point(p, f"elements[{key!r}].pts[{j}]")
        if etype == "plane" and not 3 <= len(el.get("pts") or []) <= 4:
            errs.append(f"elements[{key!r}] 是 plane，pts 必须是 3 或 4 个点")

    for key, el in elements.items():
        check_element(key, el)
    if model.get("solid"):
        check_element("model.solid", model["solid"])

    # 2. highlight 必须命中真实存在的可切换对象（模板对未知键是静默忽略的）
    switchable = set(elements) | {e["name"] for e in edges if e.get("name")}
    for i, st in enumerate(steps):
        for key in st.get("highlight") or []:
            if key not in switchable:
                errs.append(f"steps[{i}].highlight 的 {key!r} 不存在，"
                            f"该步不会显示任何东西（可用：{sorted(switchable)}）")
        if not st.get("cameraPos"):
            errs.append(f"steps[{i}] 缺少 cameraPos")
        if not st.get("content"):
            errs.append(f"steps[{i}] 缺少 content")
        if (st.get("content") or "").count("$") % 2:
            errs.append(f"steps[{i}].content 里 $ 数量为奇数，公式定界符没配对")

    # 3. 题面 + 所有会显示公式的字段：LaTeX 必须被 $…$ 包住
    title = lesson.get("title") or ""
    if not title:
        errs.append("lesson.title 为空")
    check_latex(title, "lesson.title", errs)
    check_latex(lesson.get("answerLabel"), "lesson.answerLabel", errs)
    for i, st in enumerate(steps):
        check_latex(st.get("title"), f"steps[{i}].title", errs)
        check_latex(st.get("content"), f"steps[{i}].content", errs)
    # measure 的 label 由模板自动补 $，这里规则相反
    for key, el in elements.items():
        if el.get("type") == "measure" and "$" in str(el.get("label", "")):
            errs.append(f"elements[{key!r}].label 不要写 $，模板会自动补上"
                        f"（现在是 {el.get('label')!r}，会渲染成 $$…$$）")

    # 4. 答案一致性：答案卡 == 末步骤展示的值 == kernel 算出的值
    answers = lesson.get("answers")
    av = lesson.get("answerValue") or ""
    multipart = bool(re.search(r"[(（]\s*1\s*[)）]", title) and re.search(r"[(（]\s*2\s*[)）]", title))

    if answers is not None:
        if not isinstance(answers, list) or not answers:
            errs.append("lesson.answers 必须是非空数组：[{\"label\": \"(1) …\", \"value\": \"$…$\"}, …]")
        else:
            for i, a in enumerate(answers):
                if not isinstance(a, dict) or not a.get("label") or not a.get("value"):
                    errs.append(f"lesson.answers[{i}] 需要同时有非空的 label 和 value")
                else:
                    check_latex(a["label"], f"lesson.answers[{i}].label", errs)
                    check_latex(a["value"], f"lesson.answers[{i}].value", errs)
    elif not av:
        errs.append("lesson.answerValue 为空（多问题目请改用 lesson.answers）")

    if av:
        check_latex(av, "lesson.answerValue", errs)
        plain = re.sub(r"<[^>]+>", "", av)
        if len(plain) > 40:
            errs.append(f"lesson.answerValue 过长（{len(plain)} 字），答案卡会被撑变形。"
                        "它只放一个简短的值；多问题目改用 "
                        'lesson.answers: [{"label": "(1) …", "value": "$…$"}, …]')
        if "<br" in av.lower():
            errs.append("lesson.answerValue 里不要放 <br>，多问答案改用 lesson.answers")

    if multipart and not answers:
        errs.append("题面含 (1)(2) 等多个小问，但只提供了单个 answerValue。"
                    '请改用 lesson.answers 逐问列出：[{"label": "(1) 证明 AD⊥EF", "value": "$…$"}, …]')

    # kernel 算出的答案必须出现在答案卡与末步骤里（answers 形式则任一条命中即可）
    if answer:
        shown = av + "".join(str(a.get("value", "")) for a in (answers or []) if isinstance(a, dict))
        if answer not in shown:
            errs.append(f"答案卡未出现 kernel 答案 {answer!r}（答案卡内容：{shown!r}）")
        if steps and answer not in (steps[-1].get("content") or ""):
            errs.append(f"末步骤 content 未出现 kernel 答案 {answer!r}")

    # 镜头必须装得下整个几何体，否则图会被裁出画面
    target = model.get("target")
    if points and isinstance(target, (list, tuple)) and len(target) == 3:
        def dist(a, b):
            return math.sqrt(sum((float(a[i]) - float(b[i])) ** 2 for i in range(3)))

        radius = max(dist(p, target) for p in points.values())
        need = CAMERA_FIT * radius
        for i, st in enumerate(steps):
            cp = st.get("cameraPos")
            if not isinstance(cp, dict):
                continue
            d = dist([cp.get("x", 0), cp.get("y", 0), cp.get("z", 0)], target)
            if d < need:
                errs.append(
                    f"steps[{i}].cameraPos 离 target 太近（距离 {d:.1f}，"
                    f"装下整个几何体至少要 {need:.1f}），几何体会被裁出画面。"
                    f"把这个方向的镜头等比拉远到 {need * 1.15:.1f} 左右")

    # 4. 占位符必须都已替换
    blob = json.dumps(data, ensure_ascii=False)
    left = set(re.findall(r"\{\{[a-zA-Z0-9_.]+\}\}", blob))
    if left:
        errs.append(f"仍有未替换的占位符：{sorted(left)}")

    # 5. draggable 的附加要求
    dg = model.get("draggable")
    if dg:
        if not model.get("mathPoints"):
            errs.append("model.draggable 需要同时提供 model.mathPoints")
        if not model.get("scale"):
            errs.append("model.draggable 需要同时提供 model.scale")

    return errs


def _dist(a, b):
    return math.sqrt(sum((float(a[i]) - float(b[i])) ** 2 for i in range(3)))


def bounding_radius(points, target):
    """几何体相对 target 的包围球半径（three 坐标）。"""
    return max(_dist(p, target) for p in points.values())


def fit_camera(points, target, direction, margin=1.15):
    """把镜头沿 direction 放到刚好装得下整个几何体的距离，返回 [x, y, z]。

    几何体尺寸随题目参数变化时，镜头必须跟着算——写死的坐标会让大尺寸的图被裁掉。
    """
    need = CAMERA_FIT * bounding_radius(points, target) * margin
    length = math.sqrt(sum(c * c for c in direction)) or 1.0
    return [target[i] + direction[i] / length * need for i in range(3)]


def _outside_math(text):
    """剥掉 $$…$$ 与 $…$，剩下的就是 MathJax 不会处理的部分。"""
    t = re.sub(r"\$\$.*?\$\$", " ", text, flags=re.S)
    return re.sub(r"\$[^$]*\$", " ", t)


def check_latex(text, where, errs):
    """LaTeX 必须被 $…$ 包住，否则页面上会原样显示源码。"""
    if not isinstance(text, str) or not text:
        return
    if text.count("$") % 2:
        errs.append(f"{where} 里 $ 数量为奇数，公式定界符没配对（整段会显示成原始 LaTeX）")
        return
    bare = sorted(set(LATEX_CMD.findall(_outside_math(text))))
    if bare:
        errs.append(f"{where} 有没被 $…$ 包住的 LaTeX 命令 {bare[:4]}，会原样显示成源码。"
                    f"占位符不自带定界符——要写成 \"${{{{answer}}}}$\" 而不是 \"{{{{answer}}}}\"")


def extract(html: str) -> dict:
    m = re.search(r'<script id="lesson-data" type="application/json">(.*?)</script>',
                  html, re.S)
    if not m:
        raise ValueError("HTML 里找不到 lesson-data 数据岛")
    return json.loads(m.group(1))


def main():
    if len(sys.argv) < 2:
        sys.exit("用法: python3 scripts/validate.py <成品.html>")
    path = Path(sys.argv[1])
    data = extract(path.read_text(encoding="utf-8"))
    errs = validate(data)
    if errs:
        print(f"FAIL ({len(errs)} 个问题):")
        for e in errs:
            print("  -", e)
        sys.exit(1)
    print(f"PASS  {path}  ({len(data.get('steps') or [])} 步)")


if __name__ == "__main__":
    main()
