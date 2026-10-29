#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
convert_arena.py - 把 v50+ (v53) 的 arena.txt 中的某个竞技场，转换成 v0.47 的
arena.txt 格式（144x144，9 个 Z 层，Z=-4..Z=4）。

用法:
    python convert_arena.py --src 53_arena.txt --arena SMALL --out 47_small_arena.txt
    python convert_arena.py --src 53_arena.txt --list          # 列出所有竞技场
    python convert_arena.py --selftest                          # 自检

说明:
  * v50+ 格式:  [ARENA:NAME] [DIMX:..] [DIMY:..] [START_CENTER:x:y:z]
                后接 [MAP_LEVEL] + 该层每行，[REPEAT_LAST_MAP_LEVEL] 表示复制上一层。
  * v0.47 格式: 固定的 9 层，从 "Z=-4, Lowest Level (must leave this line here)"
                到 "Z=4 (must leave this line here)"，每层 144 行、每行 144 个字符。
  * 两种格式的瓦片字符含义相同（# 空 . 地板 P 墙 R 坡道 F 城垛 C 深渊
    + 水源 W 水 w 水+坡 L 岩浆 l 岩浆+坡 g 草 T 树 ~ 沙 , 土），
    但是地图尺寸/层数/语法不同，因此必须重排，不能直接复制。
"""

import argparse
import io
import os
import re
import sys

# ---- v0.47 固定尺寸 ----------------------------------------------------------
DF47_W = 144
DF47_H = 144
DF47_ZMIN = -4
DF47_ZMAX = 4
DF47_LEVELS = DF47_ZMAX - DF47_ZMIN + 1  # 9

LEVEL_HEADER_LOWEST = "Z=-4, Lowest Level (must leave this line here)"
LEVEL_HEADER = "Z={} (must leave this line here)"

# ---- 解析 v50+ 格式 ----------------------------------------------------------

class Arena:
    def __init__(self, name):
        self.name = name
        self.props = {}
        self.levels = []


def parse_arena_file(path):
    """返回 [Arena, ...]，按文件中的出现顺序。"""
    with open(path, encoding="utf-8-sig", errors="replace") as fh:
        lines = fh.read().splitlines()

    arenas, cur, in_level = [], None, False
    for raw in lines:
        line = raw.strip()
        if line.startswith("[ARENA:"):
            cur = Arena(line[len("[ARENA:"):-1])
            arenas.append(cur)
            in_level = False
            continue
        if cur is None:
            continue
        if line == "[MAP_LEVEL]":
            cur.levels.append([])
            in_level = True
            continue
        if line == "[REPEAT_LAST_MAP_LEVEL]":
            if not cur.levels:
                raise ValueError("[REPEAT_LAST_MAP_LEVEL] 出现在任何 [MAP_LEVEL] 之前")
            cur.levels.append(list(cur.levels[-1]))
            in_level = True
            continue
        m = re.match(r"^\[([A-Z_]+):(.*)\]$", line)
        if m:
            cur.props[m.group(1)] = m.group(2)
            in_level = False
            continue
        if in_level and line:
            cur.levels[-1].append(line)
    return arenas


def arena_dims(a):
    return int(a.props["DIMX"]), int(a.props["DIMY"])


def check_arena(a):
    """校验每个 MAP_LEVEL 的行数/列数，返回问题列表。"""
    w, h = arena_dims(a)
    problems = []
    for i, lv in enumerate(a.levels):
        if len(lv) != h:
            problems.append("第 %d 层行数 %d != DIMY %d" % (i, len(lv), h))
        bad = [(y, len(r)) for y, r in enumerate(lv) if len(r) != w]
        if bad:
            problems.append("第 %d 层有 %d 行列宽不是 %d（首例：行 %d 宽 %d）"
                            % (i, len(bad), w, bad[0][0], bad[0][1]))
        chars = set("".join(lv))
        problems.extend("第 %d 层出现未知字符 %r" % (i, c)
                        for c in sorted(chars) if c not in TILE_CHARS)
    return problems


TILE_CHARS = set("#.PRFC+WwLl gT~,".replace(" ", ""))


# ---- 生成 v0.47 格式 ---------------------------------------------------------

def convert(arena, anchor_level=0, fill_empty="#", fill_ground="g",
            fill_below="#", center=True, offset=None, verbose=True):
    """
    arena:        Arena 对象
    anchor_level: 竞技场自身第几层放到 v0.47 的 Z=0（地面层）
    fill_empty:   地面层以上的背景字符（默认 '#' 空地 = 天空）
    fill_ground:  地面层的背景字符（默认 'g' 草地，和竞技场外圈无缝衔接）
    fill_below:   地面层以下的背景字符（默认 '#' 空腔；'P' = 实心岩壁）
    center:       True = 居中放置
    offset:       (x, y) 左上角，给定则忽略 center
    """
    w, h = arena_dims(arena)
    if offset is None:
        if center:
            ox = (DF47_W - w) // 2
            oy = (DF47_H - h) // 2
        else:
            ox = oy = 0
    else:
        ox, oy = offset

    # 画布：先填背景。地面层 = 竞技场第 0 层落到的那个 Z
    ground_z = -anchor_level
    grid = {}
    for z in range(DF47_ZMIN, DF47_ZMAX + 1):
        if z == ground_z:
            row = fill_ground
        elif z < ground_z:
            row = fill_below
        else:
            row = fill_empty
        grid[z] = [[row] * DF47_W for _ in range(DF47_H)]

    # 竞技场自身第 i 层 -> Z = i - anchor_level
    dropped = []
    for i, lv in enumerate(arena.levels):
        z = i - anchor_level
        if z < DF47_ZMIN or z > DF47_ZMAX:
            if any(ch != "#" for r in lv for ch in r):
                dropped.append(i)
            continue
        for y in range(h):
            ty = oy + y
            if not (0 <= ty < DF47_H):
                continue
            src = lv[y]
            dst = grid[z][ty]
            for x in range(w):
                tx = ox + x
                if 0 <= tx < DF47_W:
                    dst[tx] = src[x]

    if verbose and dropped:
        print("注意：以下层超出 9 层范围被丢弃（且不是纯空层）：%s" % dropped,
              file=sys.stderr)
    if verbose and (w > DF47_W or h > DF47_H):
        print("注意：源图 %dx%d 大于 144x144，超出部分会被裁掉（FOREST 就是这种）。"
              % (w, h), file=sys.stderr)
    if verbose and ground_z != 0:
        print("注意：地面层在 Z=%d，而 v0.47 进竞技场时固定从 Z=0 开图，"
              "进图后需要手动下降 %d 层才看得到场地。" % (ground_z, abs(ground_z)),
              file=sys.stderr)
    return grid, ox, oy


def render_47(grid, newline="\r\n"):
    out = io.StringIO()
    for z in range(DF47_ZMIN, DF47_ZMAX + 1):
        out.write(LEVEL_HEADER_LOWEST if z == DF47_ZMIN else LEVEL_HEADER.format(z))
        out.write(newline)
        for row in grid[z]:
            out.write("".join(row))
            out.write(newline)
    text = out.getvalue()
    # 原版 v0.47 arena.txt 末尾没有换行
    return text.rstrip(newline)


# ---- 自检：解析回自己生成的文本，和源数据逐格比对 ---------------------------

def parse_47_text(text):
    grid = {}
    z = None
    for line in text.splitlines():
        if line.startswith("Z="):
            z = int(re.match(r"Z=(-?\d+)", line).group(1))
            grid[z] = []
        elif z is not None and line:
            grid[z].append(line)
    return grid


def selftest(src="53_arena.txt"):
    arenas = parse_arena_file(src)
    by_name = {a.name: a for a in arenas}
    ok = True

    # 1) 53 的 CLASSIC 必须和 47 模板逐格相同 -> 证明字符含义一致
    try:
        tpl = parse_47_text(open("47_arena.txt", encoding="utf-8").read())
        cl = by_name["CLASSIC"].levels
        for i, lv in enumerate(cl):
            z = i - 4
            diff = sum(1 for y in range(144) for x in range(144)
                       if lv[y][x] != tpl[z][y][x])
            print("CLASSIC L%d vs Z=%d: %d 处不同" % (i, z, diff))
            ok &= diff == 0
    except (KeyError, FileNotFoundError) as exc:
        print("跳过 CLASSIC 交叉验证：%s" % exc)

    # 2) 每张转换后的地图：外框尺寸、行数、内部 48x48 与源一致
    for name in ("SMALL",):
        a = by_name[name]
        grid, ox, oy = convert(a, verbose=False)
        text = render_47(grid)
        back = parse_47_text(text)
        assert sorted(back) == list(range(-4, 5)), sorted(back)
        for z in range(-4, 5):
            assert len(back[z]) == 144, len(back[z])
            assert all(len(r) == 144 for r in back[z])
        w, h = arena_dims(a)
        bad = 0
        for i, lv in enumerate(a.levels):
            z = i
            if z not in back:
                continue
            for y in range(h):
                for x in range(w):
                    if back[z][oy + y][ox + x] != lv[y][x]:
                        bad += 1
        print("%s: 144x144x9 OK, 内部 %dx%d 与源逐格比对差异 %d 处" % (name, w, h, bad))
        ok &= bad == 0
    print("自检结果：%s" % ("全部通过" if ok else "失败"))
    return ok


# ---- 命令行 ------------------------------------------------------------------

def main(argv=None):
    ap = argparse.ArgumentParser(description="v53 arena.txt -> v0.47 arena.txt")
    ap.add_argument("--src", default="53_arena.txt")
    ap.add_argument("--arena", default="SMALL")
    ap.add_argument("--out", default=None)
    ap.add_argument("--list", action="store_true", help="列出源文件里的竞技场")
    ap.add_argument("--anchor", type=int, default=0,
                    help="竞技场第几层放到 Z=0（默认 0，即带地形的表层）")
    ap.add_argument("--fill", default="g",
                    help="地面层场地以外的填充字符（默认 g 草地）")
    ap.add_argument("--below", default="#",
                    help="地面层以下整层的填充字符（默认 # 空腔；P = 实心岩壁）")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)

    if args.selftest:
        return 0 if selftest(args.src) else 1

    arenas = parse_arena_file(args.src)
    if args.list:
        for a in arenas:
            w, h = arena_dims(a)
            print("%-8s %3dx%-3d  层数=%d  中心=%s"
                  % (a.name, w, h, len(a.levels), a.props.get("START_CENTER", "?")))
        return 0

    by_name = {a.name: a for a in arenas}
    key = args.arena.upper()
    if key not in by_name:
        print("找不到竞技场 %r，可选：%s" % (args.arena, ", ".join(by_name)), file=sys.stderr)
        return 2
    arena = by_name[key]

    problems = check_arena(arena)
    if problems:
        print("源数据有问题：", file=sys.stderr)
        for p in problems:
            print("  " + p, file=sys.stderr)
        return 3

    grid, ox, oy = convert(arena, anchor_level=args.anchor, fill_ground=args.fill,
                           fill_below=args.below)
    text = render_47(grid)

    out = args.out or ("47_%s.txt" % key.lower())
    with open(out, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)

    w, h = arena_dims(arena)
    print("已生成 %s" % out)
    print("  竞技场 %s (%dx%d) 放置在 144x144 的第 %d..%d 列 / 第 %d..%d 行，Z=%d..%d"
          % (key, w, h, ox, ox + w - 1, oy, oy + h - 1, -args.anchor, -args.anchor + len(arena.levels) - 1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
