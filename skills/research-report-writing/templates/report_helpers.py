# -*- coding: utf-8 -*-
"""生成单个自包含 HTML 研究报告的小工具：内嵌 SVG 图（条形图、折线图、时间轴）、阶段卡片、MathML 公式。
用法：改下面 main() 里的数据，运行 python report_helpers.py，得到 report.html。只使用 Python 标准库。
"""
import base64
import html

C = dict(ink='#1d2430', muted='#5c6878', line='#dde2e8', blue='#2f5bb7', lblue='#8fb0e6', grey='#8e99a8',
         dgrey='#4d5866', orange='#c9772b', green='#1f7a4c', red='#c0473f', purple='#7b4bb7')


def bars(rows, maxv, unit='', aria='条形图'):
    """rows: [(名称, 数值, 颜色, 右侧备注)]。同一做法在全文用同一颜色。"""
    W, rh, L = 780, 34, 220
    H = rh * len(rows) + 10
    g = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="{html.escape(aria)}" style="width:100%;height:auto">']
    for i, (name, v, col, note) in enumerate(rows):
        y = i * rh + 6
        w = (W - L - 170) * v / maxv
        g.append(f'<text x="{L-10}" y="{y+17}" text-anchor="end" font-size="12.5" fill="{col}" font-weight="600">{html.escape(name)}</text>')
        g.append(f'<rect x="{L}" y="{y+4}" width="{w:.1f}" height="18" rx="4" fill="{col}"/>')
        g.append(f'<text x="{L+w+8:.1f}" y="{y+17}" font-size="12" fill="{C["ink"]}"><tspan font-weight="700">{v}</tspan> {html.escape(unit)}'
                 f'<tspan dx="10" fill="{C["muted"]}">{html.escape(note)}</tspan></text>')
    g.append('</svg>')
    return '\n'.join(g)


def line_chart(series, xmax, ymin, ymax, xlabel, ylabel, aria='折线图'):
    """series: [(名称, 颜色, [(x, y), ...])]，图例放右侧，末端标数值。"""
    W, H = 780, 360
    L, R, T, B = 64, 200, 24, 52
    X = lambda v: L + (W - L - R) * v / xmax
    Y = lambda v: T + (H - T - B) * (1 - (v - ymin) / (ymax - ymin))
    g = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="{html.escape(aria)}" style="width:100%;height:auto">']
    step_y = max(1, round((ymax - ymin) / 5))
    for yv in range(int(ymin), int(ymax) + 1, step_y):
        g.append(f'<line x1="{L}" x2="{W-R}" y1="{Y(yv):.1f}" y2="{Y(yv):.1f}" stroke="{C["line"]}"/>'
                 f'<text x="{L-8}" y="{Y(yv)+4:.1f}" text-anchor="end" font-size="11" fill="{C["muted"]}">{yv}</text>')
    step_x = max(1, round(xmax / 5))
    for xv in range(0, int(xmax) + 1, step_x):
        g.append(f'<text x="{X(xv):.1f}" y="{H-B+18}" text-anchor="middle" font-size="11" fill="{C["muted"]}">{xv}</text>')
    g.append(f'<text x="{(L+W-R)/2:.0f}" y="{H-10}" text-anchor="middle" font-size="12" fill="{C["muted"]}">{html.escape(xlabel)}</text>')
    cy = T + (H - T - B) / 2
    g.append(f'<text x="16" y="{cy:.0f}" font-size="12" fill="{C["muted"]}" transform="rotate(-90 16 {cy:.0f})" text-anchor="middle">{html.escape(ylabel)}</text>')
    for name, col, pts in series:
        g.append('<polyline points="' + ' '.join(f'{X(a):.1f},{Y(b):.1f}' for a, b in pts) + f'" fill="none" stroke="{col}" stroke-width="2.5"/>')
        for a, b in pts:
            g.append(f'<circle cx="{X(a):.1f}" cy="{Y(b):.1f}" r="4" fill="{col}"/>')
        a, b = pts[-1]
        g.append(f'<text x="{X(a)+8:.1f}" y="{Y(b)+4:.1f}" font-size="11.5" font-weight="700" fill="{col}">{b}</text>')
    ly = T + 8
    for name, col, _ in series:
        g.append(f'<rect x="{W-R+28}" y="{ly}" width="14" height="5" rx="2" fill="{col}"/>'
                 f'<text x="{W-R+48}" y="{ly+7}" font-size="12" font-weight="600" fill="{col}">{html.escape(name)}</text>')
        ly += 26
    g.append('</svg>')
    return '\n'.join(g)


def timeline(phases, aria='时间轴'):
    """phases: [(日期, 标题, 一句说明, 颜色)]，上下交错排列。"""
    W, H = 800, 250
    L, R = 52, 52
    step = (W - L - R) / max(1, len(phases) - 1)
    g = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="{html.escape(aria)}" style="width:100%;height:auto">',
         f'<line x1="{L}" x2="{W-R}" y1="120" y2="120" stroke="{C["line"]}" stroke-width="3"/>']
    for i, (d, t, s, col) in enumerate(phases):
        x = L + i * step
        up = i % 2 == 0
        ty = 44 if up else 178
        g.append(f'<circle cx="{x:.1f}" cy="120" r="7" fill="{col}"/>')
        g.append(f'<text x="{x:.1f}" y="{143 if up else 106}" text-anchor="middle" font-size="11" fill="{C["muted"]}">{html.escape(d)}</text>')
        g.append(f'<text x="{x:.1f}" y="{ty}" text-anchor="middle" font-size="12.5" font-weight="700" fill="{col}">{html.escape(t)}</text>')
        g.append(f'<text x="{x:.1f}" y="{ty+17}" text-anchor="middle" font-size="11" fill="{C["muted"]}">{html.escape(s)}</text>')
    g.append('</svg>')
    return '\n'.join(g)


def phase(col, when, title, rows):
    """阶段卡片：rows = [('假设', '...'), ('实验', '...'), ('结果', '...'), ('调整', '...')]，值可含 <b> 等 HTML。"""
    dl = ''.join(f'<dt>{k}</dt><dd>{v}</dd>' for k, v in rows)
    return (f'<div class="phase" style="--c:{col}"><div class="when">{html.escape(when)}</div>'
            f'<h3 style="margin:2px 0 0">{html.escape(title)}</h3><dl>{dl}</dl></div>')


def embed_jpeg(path, alt, caption, max_width='100%'):
    """把本地 JPEG 嵌进 HTML（先自己压缩到几十 KB）。"""
    data = base64.b64encode(open(path, 'rb').read()).decode()
    return (f'<figure><img alt="{html.escape(alt)}" style="width:100%;max-width:{max_width};border-radius:8px" '
            f'src="data:image/jpeg;base64,{data}"><figcaption>{caption}</figcaption></figure>')


# MathML 示例：样本均值，包含分数、下标、上标与求和。浏览器原生支持，离线可用。
MATH_EXAMPLE = ('<math display="block"><mrow><mover><mi>x</mi><mo>¯</mo></mover><mo>=</mo>'
                '<mfrac><mn>1</mn><mi>n</mi></mfrac><munderover><mo>∑</mo>'
                '<mrow><mi>i</mi><mo>=</mo><mn>1</mn></mrow><mi>n</mi></munderover>'
                '<msub><mi>x</mi><mi>i</mi></msub></mrow></math>')

CSS = '''
body{margin:0;background:#fbfbfa;color:#1d2430;font-family:"Microsoft YaHei","PingFang SC",sans-serif;font-size:15.5px;line-height:1.8}
.wrap{max-width:900px;margin:0 auto;padding:34px 20px 70px}
h1{font-size:28px;line-height:1.35;margin:0 0 6px}h2{font-size:21px;margin:44px 0 10px;padding-top:8px;border-top:2px solid #1d2430}
.note{color:#5c6878;font-size:13.5px}.box{background:#fff;border:1px solid #dde2e8;border-radius:12px;padding:16px 20px;margin:14px 0}
table{border-collapse:collapse;width:100%;font-size:14px}th,td{border-bottom:1px solid #dde2e8;padding:7px 8px;text-align:left;vertical-align:top}th{color:#5c6878;background:#f4f6f8}
.phase{background:#fff;border:1px solid #dde2e8;border-left:5px solid var(--c);border-radius:10px;padding:14px 18px;margin:14px 0}
.phase .when{font-size:13px;color:var(--c);font-weight:700}.phase dl{display:grid;grid-template-columns:78px 1fr;gap:6px 10px;margin:8px 0 0}
.phase dt{color:var(--c);font-weight:700;font-size:13.5px}.phase dd{margin:0}
.ftitle{font-weight:700;font-size:15px;margin:22px 0 4px}figure{margin:14px 0}figcaption{font-size:13.5px;color:#5c6878}
math[display=block]{margin:6px 0 8px;font-size:1.1em}
'''


def main():
    body = f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>方法比较演示</title><style>{CSS}</style></head><body><main class="wrap">
<h1>方法比较演示</h1>
<p>本页数值为演示数据，用于展示图表与公式排版。</p>
<p><b>增加计算量后，方法 A 在演示样本中的正确数增加。</b>同一批 100 题中，基线答对 55 题，方法 A 答对 70 题。计算成本分别为每题 40 次与 63 次。</p>
<h2>一、研究路线总览</h2>
{timeline([('阶段 1', '建立基线', '固定 100 题', C['grey']), ('阶段 2', '评估方法 A', '同批样本对比', C['blue']), ('阶段 3', '比较计算量', '测量正确数变化', C['green'])])}
<h2>二、主要实验证据</h2>
<div class="ftitle">图 1　各方法的正确数（独立判定，100 题）</div>
{bars([('基线', 55, C['grey'], '40 次计算'), ('方法 A', 70, C['blue'], '63 次')], 100, '/ 100')}
<div class="ftitle">图 2　计算量与正确数的关系</div>
{line_chart([('方法 A', C['blue'], [(40, 60), (63, 70), (100, 77)]), ('基线', C['dgrey'], [(40, 55), (80, 66), (120, 74)])], 140, 0, 100, '每题计算次数', '正确题数 / 100')}
<h2>三、理论</h2>{MATH_EXAMPLE}
{phase(C['blue'], '阶段 2 → 阶段 3', '计算量增加时的正确数变化', [('假设', '增加计算量可能提高正确数。'), ('实验', '在同一批 100 题上比较方法 A 与基线。'), ('结果', '演示中方法 A 以每题 63 次计算答对 70 题。'), ('调整', '按相同计算预算继续比较。')])}
</main></body></html>'''
    open('report.html', 'w', encoding='utf-8').write(body)
    print('written report.html')


if __name__ == '__main__':
    main()
