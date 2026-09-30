#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
solve.py — 通用求解器：problem spec(JSON) -> 精确答案 + 展示用 LaTeX + three 坐标 + 棱拓扑。

目的：绝大多数题目不必再手写 Python 构建脚本。模型只写 spec.json（题目结构）
和 lesson.json（讲解文案 + 占位符），由本模块提供全部数值。

用法:
    python3 scripts/solve.py spec.json        # 打印结果 JSON（自检/取值用）
    from solve import solve; solve(spec_dict) # build.py 内部调用

spec 格式与可用 vals 键见 references/api.md。
"""

import json
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL_DIR / "lib"))

try:
    import sympy as sp
except ImportError:  # 依赖缺失时给出明确指引，而不是一句 traceback
    sys.exit("缺少 sympy。请先征得用户同意再安装：python3 -m pip install sympy")

import geometry_kernel as gk  # noqa: E402
import bodies  # noqa: E402


# ===================== 几何体 =====================
# 固定拓扑的几何体：body 名 -> (坐标构建函数, 棱拓扑构建函数)
SIMPLE_BODIES = {
    "regular_quad_pyramid": (gk.regular_quad_pyramid, lambda: bodies.quad_pyramid()),
    "cuboid": (gk.cuboid, lambda: bodies.cuboid()),
    "cube": (gk.cube, lambda: bodies.cuboid()),
    "regular_tetrahedron": (gk.regular_tetrahedron,
                            lambda: bodies.tri_pyramid("A", ("B", "C", "D"))),
}
# 拓扑随 dims 变化的几何体（n 棱柱/n 棱锥/曲面体/自定义）
PARAM_BODIES = ("regular_prism", "regular_pyramid", "right_prism",
                "cylinder", "cone", "custom")
ALL_BODIES = sorted(SIMPLE_BODIES) + list(PARAM_BODIES)


def _letters(n):
    return [chr(ord("A") + i) for i in range(int(n))]


def build_body(spec):
    """返回 (points, topo, solid)。solid 非 None 时是圆柱/圆锥的曲面，始终可见。"""
    name = spec.get("body")
    dims = dict(spec.get("dims") or {})
    scale = spec.get("scale", 1.5)
    solid = None

    if name in SIMPLE_BODIES:
        make_points, make_topo = SIMPLE_BODIES[name]
        pts, topo = make_points(**dims), make_topo()

    elif name == "regular_prism":
        pts = gk.regular_prism(**dims)
        names = _letters(dims["n"])
        topo = bodies.prism(names, [f"{s}1" for s in names])

    elif name == "regular_pyramid":
        pts = gk.regular_pyramid(**dims)
        topo = bodies.pyramid("P", _letters(dims["n"]))

    elif name == "right_prism":
        pts = gk.right_prism(**dims)
        names = list(dims["base"])
        topo = bodies.prism(names, [f"{s}1" for s in names])

    elif name == "cylinder":
        pts = gk.cylinder(**dims)
        topo = bodies.round_solid("ABCD", top=["A1", "B1", "C1", "D1"], axis=("O", "O1"))
        solid = {"type": "cylinder", "bottom": "O", "top": "O1",
                 "radius": float(sp.sympify(dims["radius"])) * scale}

    elif name == "cone":
        pts = gk.cone(**dims)
        topo = bodies.round_solid("ABCD", apex="P", axis=("O", "P"))
        solid = {"type": "cone", "base": "O", "apex": "P",
                 "radius": float(sp.sympify(dims["radius"])) * scale}

    elif name == "custom":
        if "points" not in spec:
            raise ValueError('body="custom" 需要在 spec 里给 "points": {"A": [0,0,0], …}')
        pts = gk.tetrahedron(spec["points"])
        if not spec.get("topo"):
            raise ValueError('body="custom" 需要在 spec 里给 "topo": '
                             '{"spheres": [...], "edges": [{"a":"A","b":"B"}, …]}，否则画不出骨架')
        topo = spec["topo"]

    else:
        raise ValueError(f"未知 body {name!r}，可选：{ALL_BODIES}"
                         "（表达不了的多面体用 custom + 显式坐标）")

    return pts, spec.get("topo") or topo, solid


# ===================== 构造点（givens） =====================

def apply_givens(pts, givens):
    """按 spec.givens 追加构造点。每项 {name, kind, of, ...}。"""
    for g in givens or []:
        name, kind = g["name"], g["kind"]
        of = g.get("of") or []
        missing = [n for n in of if n not in pts]
        if missing:
            raise ValueError(f"构造点 {name} 引用了不存在的点 {missing}（已有：{sorted(pts)}）")
        if kind == "midpoint":
            pts[name] = gk.midpoint(pts[of[0]], pts[of[1]])
        elif kind == "ratio":
            # P = A + t(B-A)，t 可写 0.75 或 "3/4"
            t = sp.nsimplify(g["t"])
            a, b = pts[of[0]], pts[of[1]]
            pts[name] = sp.simplify(a + t * (b - a))
        elif kind == "centroid":
            acc = pts[of[0]]
            for n in of[1:]:
                acc = acc + pts[n]
            pts[name] = sp.simplify(acc / len(of))
        elif kind == "point":
            pts[name] = gk.V(*[sp.nsimplify(c) for c in g["at"]])
        else:
            raise ValueError(f"未知 givens.kind {kind!r}：可选 midpoint/ratio/centroid/point")
    return pts


# ===================== 求解（query.type -> vals） =====================

def _vec(pts, pair):
    return pts[pair[1]] - pts[pair[0]]


def _normal(pts, names):
    return gk.normal_from_points(pts[names[0]], pts[names[1]], pts[names[2]])


def _norm(v):
    return sp.simplify(sp.sqrt(sum(c ** 2 for c in v)))


def q_line_plane_angle(pts, q):
    v = _vec(pts, q["line"])
    n = _normal(pts, q["plane"])
    n_s = gk.simplify_vec(n)
    ans = gk.line_plane_angle_sin(v, n)
    vals = {
        "v": gk.tex_vec(v), "n": gk.tex_vec(n), "n_simpl": gk.tex_vec(n_s),
        "dot": gk.tex(v.dot(n_s)), "norm_v": gk.tex(_norm(v)), "norm_n": gk.tex(_norm(n_s)),
        "sin": gk.tex(ans),
    }
    return ans, vals


def q_line_line_angle(pts, q):
    d1, d2 = _vec(pts, q["line1"]), _vec(pts, q["line2"])
    ans = gk.line_line_angle_cos(d1, d2)
    vals = {
        "d1": gk.tex_vec(d1), "d2": gk.tex_vec(d2), "dot": gk.tex(d1.dot(d2)),
        "norm_d1": gk.tex(_norm(d1)), "norm_d2": gk.tex(_norm(d2)), "cos": gk.tex(ans),
    }
    return ans, vals


def q_dihedral(pts, q):
    """二面角 C-AB-D：edge 给棱 [A,B]，p1/p2 给两个半平面内各一点。"""
    a, b = q["edge"]
    A, B, C, D = pts[a], pts[b], pts[q["p1"]], pts[q["p2"]]
    ans = gk.dihedral_cos(A, B, C, D)
    u = B - A

    def perp(P):
        w = P - A
        return sp.simplify(w - (w.dot(u) / u.dot(u)) * u)

    v1, v2 = perp(C), perp(D)
    vals = {
        "u": gk.tex_vec(u), "v1": gk.tex_vec(v1), "v2": gk.tex_vec(v2),
        "dot": gk.tex(v1.dot(v2)), "norm_v1": gk.tex(_norm(v1)), "norm_v2": gk.tex(_norm(v2)),
        "cos": gk.tex(ans),
    }
    return ans, vals


def q_point_plane_distance(pts, q):
    P = pts[q["point"]]
    plane = q["plane"]
    P0 = pts[plane[0]]
    n = _normal(pts, plane)
    n_s = gk.simplify_vec(n)
    ans = gk.point_plane_distance(P, P0, n)
    w = sp.simplify(P - P0)
    vals = {
        "n": gk.tex_vec(n), "n_simpl": gk.tex_vec(n_s), "w": gk.tex_vec(w),
        "dot": gk.tex(w.dot(n_s)), "norm_n": gk.tex(_norm(n_s)), "dist": gk.tex(ans),
    }
    return ans, vals


def q_volume(pts, q):
    kind = q.get("kind", "tetra")
    if kind == "tetra":
        p = q["pts"]
        ans = gk.volume_tetra(*[pts[n] for n in p])
    elif kind == "box":
        ans = gk.volume_box(q["lx"], q["ly"], q["lz"])
    elif kind == "prism":
        ans = gk.volume_prism(q["base_area"], q["height"])
    elif kind == "pyramid":
        ans = gk.volume_pyramid(q["base_area"], q["height"])
    else:
        raise ValueError(f"未知 volume.kind {kind!r}：可选 tetra/box/prism/pyramid")
    return ans, {"V": gk.tex(ans)}


QUERIES = {
    "line_plane_angle": q_line_plane_angle,
    "line_line_angle": q_line_line_angle,
    "dihedral": q_dihedral,
    "point_plane_distance": q_point_plane_distance,
    "volume": q_volume,
}


# ===================== 主入口 =====================

def solve(spec: dict) -> dict:
    pts, topo, solid = build_body(spec)
    apply_givens(pts, spec.get("givens"))

    q = spec.get("query") or {}
    qtype = q.get("type")
    if qtype not in QUERIES:
        raise ValueError(f"未知 query.type {qtype!r}，可选：{sorted(QUERIES)}")
    answer, vals = QUERIES[qtype](pts, q)

    # 题面额外需要展示的向量 / 长度（写进 vals 供讲解引用）
    for label, pair in (spec.get("vectors") or {}).items():
        vals[f"vec_{label}"] = gk.tex_vec(_vec(pts, pair))
    for label, pair in (spec.get("lengths") or {}).items():
        vals[f"len_{label}"] = gk.tex(_norm(_vec(pts, pair)))

    scale = spec.get("scale", 1.5)
    return {
        "answer": gk.tex(answer),
        "mp": {k: gk.tex_vec(v) for k, v in pts.items()},          # 数学坐标 LaTeX
        "vals": vals,                                              # 各步骤中间量 LaTeX
        "three_points": gk.to_three(pts, scale=scale),             # three 坐标（渲染用）
        "math_points": {k: [float(c) for c in v] for k, v in pts.items()},  # draggable 用
        "topo": topo,
        "solid": solid,                                             # 圆柱/圆锥曲面（可为 None）
        "scale": scale,
        "_exact": sp.srepr(sp.sympify(answer)),                    # 自检比对用
    }


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if not args:
        sys.exit("用法: python3 scripts/solve.py spec.json [--full]")
    spec = json.loads(Path(args[0]).read_text(encoding="utf-8"))
    sol = solve(spec)
    if "--full" not in sys.argv:
        # 默认只打印讲解要用到的部分；three_points / topo 由 build.py 自动消费，
        # 打印出来纯属浪费上下文。需要完整结果时加 --full。
        sol = {k: sol[k] for k in ("answer", "mp", "vals")}
    print(json.dumps(sol, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
