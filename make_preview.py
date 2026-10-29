# -*- coding: utf-8 -*-
"""生成预览图（俯视 Z=0）并校验输出文件。"""
import re
from PIL import Image, ImageDraw

COLORS = {
    'g': (86, 130, 66), 'T': (40, 96, 52), '~': (216, 198, 140), ',': (126, 100, 72),
    'P': (108, 108, 116), 'R': (150, 140, 118), 'F': (92, 92, 100), '.': (74, 74, 80),
    '#': (18, 18, 22), 'C': (8, 8, 10), 'W': (62, 112, 190), 'w': (62, 112, 190),
    'L': (206, 74, 30), 'l': (206, 74, 30), '+': (86, 146, 226),
}
DARK = (28, 28, 30)


def grid_from_47(path):
    g, z = {}, None
    for line in open(path, encoding='utf-8').read().splitlines():
        if line.startswith('Z='):
            z = int(re.match(r'Z=(-?\d+)', line).group(1)); g[z] = []
        elif z is not None and line:
            g[z].append(line)
    return g


def grid_from_53(path, name='SMALL'):
    lines = open(path, encoding='utf-8-sig').read().splitlines()
    cur, mode, levels, props = None, None, [], {}
    for ln in lines:
        s = ln.strip()
        if s.startswith('[ARENA:'):
            if cur == name:
                break
            cur = s[7:-1]; continue
        if cur != name:
            continue
        if s == '[MAP_LEVEL]':
            levels.append([]); mode = 'lv'; continue
        if s == '[REPEAT_LAST_MAP_LEVEL]':
            levels.append(list(levels[-1])); continue
        m = re.match(r'^\[([A-Z_]+):(.*)\]$', s)
        if m:
            props[m.group(1)] = m.group(2); mode = None; continue
        if mode == 'lv' and s:
            levels[-1].append(s)
    return levels, props


def draw(rows, scale):
    h, w = len(rows), len(rows[0])
    im = Image.new('RGB', (w * scale, h * scale), DARK)
    px = im.load()
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            c = COLORS.get(ch, (255, 0, 255))
            for dy in range(scale):
                for dx in range(scale):
                    px[x * scale + dx, y * scale + dy] = c
    return im


def verify(path53, path47):
    levels, props = grid_from_53(path53, 'SMALL')
    g = grid_from_47(path47)
    assert sorted(g) == list(range(-4, 5)), sorted(g)
    for z in g:
        assert len(g[z]) == 144 and all(len(r) == 144 for r in g[z]), z
    src = levels[0]
    inner = [r[48:96] for r in g[0][48:96]]
    diff = sum(1 for y in range(48) for x in range(48) if inner[y][x] != src[y][x])
    outside = {(x, y) for y in range(144) for x in range(144)} - \
              {(x, y) for y in range(48, 96) for x in range(48, 96)}
    bad_out = sum(1 for x, y in outside if g[0][y][x] != 'g')
    other = sum(1 for z in range(-4, 5) if z != 0 for r in g[z] for c in r if c != '#')
    print('校验 %s' % path47)
    print('  层/尺寸: 9 层 144x144  OK')
    print('  Z=0 内部 48x48 与源差异: %d 格' % diff)
    print('  Z=0 外部填充非草地: %d 格' % bad_out)
    print('  其他层非空字符: %d 格' % other)
    return diff == 0 and bad_out == 0 and other == 0


def main():
    ok = verify('53_arena.txt', '47_small_arena.txt')
    levels, props = grid_from_53('53_arena.txt', 'SMALL')
    g = grid_from_47('47_small_arena.txt')

    s48 = draw(levels[0], 8)
    s144 = draw(g[0], 4)
    pad = 16
    canvas = Image.new('RGB', (s48.width + pad + s144.width, max(s48.height, s144.height) + 34), (24, 24, 26))
    canvas.paste(s48, (0, 30))
    canvas.paste(s144, (s48.width + pad, 30))
    d = ImageDraw.Draw(canvas)
    d.text((6, 8), 'v53 Small arena 48x48 (source)', fill=(215, 215, 215))
    d.text((s48.width + pad + 6, 8), 'v47 port 144x144, Z=0 (arena centred, grassland around)', fill=(215, 215, 215))
    canvas.save('preview_z0.png')

    # 裁剪对比：源 48x48  vs  输出 Z=0 中抠出来的 48x48
    crop = draw([r[48:96] for r in g[0][48:96]], 8)
    c2 = Image.new('RGB', (s48.width * 2 + 16, s48.height + 30), (24, 24, 26))
    c2.paste(s48, (0, 30)); c2.paste(crop, (s48.width + 16, 30))
    d2 = ImageDraw.Draw(c2)
    d2.text((6, 8), 'source 48x48', fill=(215, 215, 215))
    d2.text((s48.width + 22, 8), 'cut out of the port at Z=0 (should be identical)', fill=(215, 215, 215))
    c2.save('preview_crop_check.png')
    print('preview_z0.png ->', canvas.size, 'ok' if ok else 'CHECK FAILED')
    print('preview_crop_check.png ->', c2.size)


main()
