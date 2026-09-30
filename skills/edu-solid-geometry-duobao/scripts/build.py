#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build.py — 一条命令走完：spec 求解 -> 占位符替换 -> 补默认值 -> 注入模板 -> 静态自检。

    python3 scripts/build.py spec.json lesson.json out.html

lesson.json 只写"讲解"部分（题面、步骤文字、highlight、镜头），
所有数值用占位符引用 kernel 的计算结果，例如 {{answer}}、{{vals.sin}}、{{mp.A}}。
model.points / spheres / edges / target / initialCamera 可全部省略，由本脚本补齐。

格式细节见 references/api.md。
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from solve import solve  # noqa: E402
from generate import render_html  # noqa: E402
from validate import validate, fit_camera  # noqa: E402

PLACEHOLDER_RE = re.compile(r"\{\{([a-zA-Z0-9_.]+)\}\}")


def lookup(ctx, dotted):
    cur = ctx
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            avail = sorted(cur) if isinstance(cur, dict) else "(非字典)"
            raise KeyError(f"占位符 {{{{{dotted}}}}} 里的 {part!r} 不存在。该层可用键：{avail}")
        cur = cur[part]
    return cur


def substitute(node, ctx):
    """递归替换占位符。整串就是一个占位符时，直接换成原始对象（可为 dict/list）。"""
    if isinstance(node, str):
        whole = PLACEHOLDER_RE.fullmatch(node.strip())
        if whole:
            return lookup(ctx, whole.group(1))
        return PLACEHOLDER_RE.sub(lambda m: str(lookup(ctx, m.group(1))), node)
    if isinstance(node, list):
        return [substitute(x, ctx) for x in node]
    if isinstance(node, dict):
        return {k: substitute(v, ctx) for k, v in node.items()}
    return node


def fill_defaults(data, sol, spec):
    """把能自动推出来的东西补上，模型就不必手写这些字段。"""
    model = data.setdefault("model", {})
    model.setdefault("points", sol["three_points"])
    model.setdefault("spheres", sol["topo"]["spheres"])
    model.setdefault("edges", sol["topo"]["edges"])
    if sol.get("solid"):
        model.setdefault("solid", sol["solid"])   # 圆柱/圆锥曲面，和骨架一样常驻

    pts = model["points"]
    if pts:
        names = list(pts)
        center = [sum(pts[k][i] for k in names) / len(names) for i in range(3)]
        model.setdefault("target", center)
        # 距离按包围球算，保证整个几何体在画面内（写死的距离会让大尺寸的图被裁掉）
        model.setdefault("initialCamera",
                         [round(c, 2) for c in fit_camera(pts, model["target"], [5, 4, 6])])

    # scale 总是补上：地平面用它把网格格宽对齐到数学坐标 1 个单位
    model.setdefault("scale", sol["scale"])
    if model.get("draggable"):
        model.setdefault("mathPoints", sol["math_points"])

    lesson = data.setdefault("lesson", {})
    lesson.setdefault("language", spec.get("language", "zh-CN"))
    # 多问题目自带 lesson.answers，这时不要再塞一个单值 answerValue
    if not lesson.get("answers"):
        lesson.setdefault("answerValue", f"${sol['answer']}$")
    return data


def build(spec: dict, lesson_data: dict, out_path: Path) -> Path:
    sol = solve(spec)
    ctx = {
        "answer": sol["answer"],
        "mp": sol["mp"],
        "vals": sol["vals"],
        "three_points": sol["three_points"],
        "math_points": sol["math_points"],
        "topo": sol["topo"],
        "scale": sol["scale"],
    }
    data = fill_defaults(substitute(lesson_data, ctx), sol, spec)

    errs = validate(data, answer=sol["answer"])
    if errs:
        print(f"FAIL ({len(errs)} 个问题)，未写出文件:", file=sys.stderr)
        for e in errs:
            print("  -", e, file=sys.stderr)
        sys.exit(1)

    render_html(data, out_path)
    print(f"PASS  已生成: {out_path}  (答案 {sol['answer']}, {len(data['steps'])} 步)")
    return out_path


def main():
    args = sys.argv[1:]
    if len(args) == 2:
        # 单文件形式：一个 JSON 里同时含 spec 和 lesson/steps/model（少写一个文件）
        doc = json.loads(Path(args[0]).read_text(encoding="utf-8"))
        if "spec" not in doc:
            sys.exit(f"{args[0]} 缺少顶层 \"spec\" 字段（单文件形式要求 spec 与 lesson/steps/model 同级）")
        spec = doc.pop("spec")
        lesson_data, out = doc, Path(args[1])
    elif len(args) == 3:
        spec = json.loads(Path(args[0]).read_text(encoding="utf-8"))
        lesson_data, out = json.loads(Path(args[1]).read_text(encoding="utf-8")), Path(args[2])
    else:
        sys.exit("用法: python3 scripts/build.py problem.json out.html\n"
                 "  或: python3 scripts/build.py spec.json lesson.json out.html")
    out = out.resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    build(spec, lesson_data, out)


if __name__ == "__main__":
    main()
