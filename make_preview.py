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


def verify(path53, path47, ground_z=0, below='#'):
    levels, props = grid_from_53(path53, 'SMALL')
    g = grid_from_47(path47)
    assert sorted(g) == list(range(-4, 5)), sorted(g)
    for z in g:
        assert len(g[z]) == 144 and all(len(r) == 144 for r in g[z]), z
    src = levels[0]
    inner = [r[48:96] for r in g[ground_z][48:96]]
    diff = sum(1 for y in range(48) for x in range(48) if inner[y][x] != src[y][x])
    outside = {(x, y) for y in range(144) for x in range(144)} - \
              {(x, y) for y in range(48, 96) for x in range(48, 96)}
    bad_out = sum(1 for x, y in outside if g[ground_z][y][x] != 'g')
    above = sum(1 for z in range(ground_z + 1, 5) for r in g[z] for c in r if c != '#')
    below_bad = sum(1 for z in range(-4, ground_z) for r in g[z] for c in r if c != below)
    print('校验 %s  (地面层 Z=%d, 以下填充 %r)' % (path47, ground_z, below))
    print('  层/尺寸: 9 层 144x144  OK')
    print('  Z=%d 内部 48x48 与源差异: %d 格' % (ground_z, diff))
    print('  Z=%d 外部填充非草地: %d 格' % (ground_z, bad_out))
    print('  地面层以上非空字符: %d 格' % above)
    print('  地面层以下非 %r 字符: %d 格' % (below, below_bad))
    return diff == 0 and bad_out == 0 and above == 0 and below_bad == 0


def sheet(rows, scale, title_left, title_right, out, show_full=None):
    s48 = draw(rows, scale)
    s144 = draw(show_full, 4)
    pad = 16
    canvas = Image.new('RGB', (s48.width + pad + s144.width,
                               max(s48.height, s144.height) + 34), (24, 24, 26))
    canvas.paste(s48, (0, 30))
    canvas.paste(s144, (s48.width + pad, 30))
    d = ImageDraw.Draw(canvas)
    d.text((6, 8), title_left, fill=(215, 215, 215))
    d.text((s48.width + pad + 6, 8), title_right, fill=(215, 215, 215))
    canvas.save(out)
    print(out, '->', canvas.size)
    return s48


def main():
    ok1 = verify('53_arena.txt', '47_small_arena.txt', 0, below='P')
    ok2 = verify('53_arena.txt', '47_small_arena_z-4.txt', -4, below='#')

    levels, props = grid_from_53('53_arena.txt', 'SMALL')
    src = levels[0]

    g0 = grid_from_47('47_small_arena.txt')
    sheet(src, 8, 'v53 Small arena 48x48 (source)',
          'port: 144x144, arena at Z=0, solid rock below',
          'preview_z0.png', g0[0])

    g4 = grid_from_47('47_small_arena_z-4.txt')
    sheet(src, 8, 'v53 Small arena 48x48 (source)',
          'literal variant: arena at Z=-4, nothing below',
          'preview_zm4.png', g4[-4])

    # 逐格对照：源 48x48 vs 成品抠出来的 48x48
    for tag, g, z in (('z0', g0, 0), ('zm4', g4, -4)):
        crop = draw([r[48:96] for r in g[z][48:96]], 8)
        c2 = Image.new('RGB', (len(src[0]) * 8 * 2 + 16, len(src) * 8 + 30), (24, 24, 26))
        c2.paste(draw(src, 8), (0, 30))
        c2.paste(crop, (len(src[0]) * 8 + 16, 30))
        d2 = ImageDraw.Draw(c2)
        d2.text((6, 8), 'source 48x48', fill=(215, 215, 215))
        d2.text((len(src[0]) * 8 + 22, 8),
                'cut out of the port at Z=%d (should be identical)' % z, fill=(215, 215, 215))
        c2.save('preview_crop_check_%s.png' % tag)
        print('preview_crop_check_%s.png ->' % tag, c2.size)

    # 九层剖面网格：Z=4 -> Z=-4
    layers(g0, 'preview_layers.png')

    ok3 = verify_flat('47_grass_only.txt', -4)
    layers(grid_from_47('47_grass_only.txt'), 'preview_layers_grass.png')

    print('结果：', 'ok' if (ok1 and ok2 and ok3) else 'CHECK FAILED')


def verify_flat(path, ground_z=-4, ground='g', above='#'):
    g = grid_from_47(path)
    assert sorted(g) == list(range(-4, 5)), sorted(g)
    for z in g:
        assert len(g[z]) == 144 and all(len(r) == 144 for r in g[z]), z
    ground_bad = sum(1 for r in g[ground_z] for c in r if c != ground)
    above_bad = sum(1 for z in range(ground_z + 1, 5) for r in g[z] for c in r if c != above)
    below_bad = sum(1 for z in range(-4, ground_z) for r in g[z] for c in r if c != '#')
    print('校验 %s  (纯色层 Z=%d)' % (path, ground_z))
    print('  层/尺寸: 9 层 144x144  OK')
    print('  Z=%d 非 %r 字符: %d 格' % (ground_z, ground, ground_bad))
    print('  上方非 %r 字符: %d 格' % (above, above_bad))
    print('  下方非空字符: %d 格' % below_bad)
    return ground_bad == 0 and above_bad == 0 and below_bad == 0


def layers(g, out, cell=104, pad=10):
    zs = list(range(4, -5, -1))
    cols, rows = 3, 3
    W = cols * (cell + pad) + pad
    H = rows * (cell + pad + 14) + pad
    im = Image.new('RGB', (W, H), (24, 24, 26))
    d = ImageDraw.Draw(im)
    for i, z in enumerate(zs):
        r, c = divmod(i, cols)
        x = pad + c * (cell + pad)
        y = pad + r * (cell + pad + 14)
        thumb = draw(g[z], 1).resize((cell, cell), Image.NEAREST)
        im.paste(thumb, (x, y + 14))
        d.text((x, y), 'Z=%d' % z, fill=(220, 220, 220))
        d.rectangle([x, y + 14, x + cell - 1, y + 14 + cell - 1], outline=(60, 60, 64))
    im.save(out)
    print(out, '->', im.size)


main()
