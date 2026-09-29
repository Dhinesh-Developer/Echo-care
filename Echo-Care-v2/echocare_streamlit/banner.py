"""
Animated hero slideshow generated entirely offline with PIL (no image APIs):
soft white-to-blue gradients, blue accent shapes, bundled fonts. Rendered as a
self-contained auto-fading carousel through st.components.v1.html.
"""
import base64
import io
import os
import streamlit as st
from PIL import Image, ImageDraw, ImageFont, ImageFilter

HERE = os.path.dirname(__file__)
FONT_BOLD = os.path.join(HERE, "assets", "fonts", "DejaVuSans-Bold.ttf")
FONT_REG = os.path.join(HERE, "assets", "fonts", "DejaVuSans.ttf")

W, H = 1200, 340
BG_TOP = (255, 255, 255)
BG_BOTTOM = (219, 234, 254)
BLUE = (37, 99, 235)
BLUE_LIGHT = (96, 165, 250)
INK = (15, 23, 42)
SLATE = (71, 85, 105)


def _gradient_bg():
    img = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(img)
    for y in range(H):
        t = y / H
        c = tuple(int(BG_TOP[i] + (BG_BOTTOM[i] - BG_TOP[i]) * t) for i in range(3))
        draw.line([(0, y), (W, y)], fill=c)
    return img


def _glow(img, spots):
    overlay = Image.new("RGBA", img.size, (*BLUE_LIGHT, 0))  # same hue as glow => no gray fringe
    d = ImageDraw.Draw(overlay)
    for cx, cy, r, color, alpha in spots:
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(*color, alpha))
    overlay = overlay.filter(ImageFilter.GaussianBlur(50))
    return Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")


def _pulse(draw, y_base):
    pts, x = [], 0
    while x < W:
        pts += [(x, y_base), (x + 22, y_base - 26), (x + 36, y_base + 34), (x + 50, y_base)]
        x += 90
    draw.line(pts, fill=(*BLUE, 70), width=2, joint="curve")


def _motif(draw, kind, cx, cy):
    c = (*BLUE, 235)
    if kind == "cross":
        t = 30
        draw.rounded_rectangle([cx - t // 2, cy - 62, cx + t // 2, cy + 62], radius=8, fill=c)
        draw.rounded_rectangle([cx - 62, cy - t // 2, cx + 62, cy + t // 2], radius=8, fill=c)
    elif kind == "pin":
        draw.ellipse([cx - 44, cy - 60, cx + 44, cy + 28], fill=c)
        draw.polygon([(cx - 30, cy + 8), (cx + 30, cy + 8), (cx, cy + 74)], fill=c)
        draw.ellipse([cx - 18, cy - 42, cx + 18, cy - 8], fill=(255, 255, 255, 255))
    elif kind == "shield":
        draw.polygon([(cx, cy - 62), (cx + 50, cy - 34), (cx + 50, cy + 22),
                      (cx, cy + 72), (cx - 50, cy + 22), (cx - 50, cy - 34)], fill=c)
        draw.line([(cx - 20, cy), (cx - 4, cy + 18), (cx + 24, cy - 20)], fill=(255, 255, 255), width=7)
    elif kind == "chat":
        draw.rounded_rectangle([cx - 62, cy - 44, cx + 62, cy + 34], radius=22, fill=c)
        draw.polygon([(cx - 22, cy + 32), (cx - 4, cy + 32), (cx - 28, cy + 62)], fill=c)
        for i in (-28, 0, 28):
            draw.ellipse([cx + i - 7, cy - 7, cx + i + 7, cy + 7], fill=(255, 255, 255))
    elif kind == "eye":
        draw.ellipse([cx - 70, cy - 40, cx + 70, cy + 40], fill=c)
        draw.ellipse([cx - 24, cy - 24, cx + 24, cy + 24], fill=(255, 255, 255))
        draw.ellipse([cx - 11, cy - 11, cx + 11, cy + 11], fill=(*INK, 255))
    elif kind == "calendar":
        draw.rounded_rectangle([cx - 60, cy - 52, cx + 60, cy + 58], radius=14, fill=c)
        draw.rectangle([cx - 60, cy - 52, cx + 60, cy - 22], fill=(*INK, 255))
        for r in range(2):
            for k in range(4):
                draw.rounded_rectangle([cx - 44 + k * 26, cy - 6 + r * 30, cx - 28 + k * 26, cy + 10 + r * 30],
                                       radius=4, fill=(255, 255, 255))


def _slide(title, subtitle, tag, motif):
    img = _glow(_gradient_bg(), [(W - 160, 60, 240, BLUE_LIGHT, 90), (80, H, 200, BLUE_LIGHT, 60)])
    draw = ImageDraw.Draw(img, "RGBA")
    _pulse(draw, H - 55)
    _motif(draw, motif, W - 150, 150)

    draw.text((60, 52), tag.upper(), font=ImageFont.truetype(FONT_BOLD, 15), fill=(*BLUE, 255))
    draw.text((60, 84), title, font=ImageFont.truetype(FONT_BOLD, 46), fill=INK)

    font_sub = ImageFont.truetype(FONT_REG, 20)
    lines, cur = [], ""
    for w in subtitle.split():
        trial = (cur + " " + w).strip()
        if len(trial) > 60:
            lines.append(cur)
            cur = w
        else:
            cur = trial
    if cur:
        lines.append(cur)
    y = 152
    for line in lines[:3]:
        draw.text((60, y), line, font=font_sub, fill=SLATE)
        y += 30
    return img


SLIDES_SPEC = [
    ("EchoCare", "One platform for your whole health story: track it, understand it, "
                 "and take it to the right doctor.", "AI healthcare companion", "cross"),
    ("Semantic Evidence Engine", "Gemini embeddings retrieve the exact moments in your history "
                                 "that matter. Every insight shows its evidence.", "LE-RAG · Explainable AI", "eye"),
    ("Vision, Voice & Languages", "Read lab reports and prescriptions from a photo, dictate symptoms, "
                                  "and chat in English, Tamil or Hindi.", "Gemini multimodal", "chat"),
    ("Find the Right Doctor", "District-wise specialist directory with map navigation, "
                              "ranking and live search.", "Doctor & facility finder", "pin"),
    ("Diagnostic Guard", "Catch symptoms that never got resolved and opinions that "
                         "don't agree, then walk in prepared.", "Patient advocacy engine", "shield"),
    ("Care, Coordinated", "Appointments, medicine reminders, family profiles, an emergency "
                          "card and a one-click PDF for your doctor.", "Care coordination", "calendar"),
]


@st.cache_data(show_spinner=False)
def get_slideshow_html() -> str:
    """Self-contained slideshow: JPEG data-URIs + CSS keyframes (no JS, no iframe). The 1200x340 aspect
    ratio is preserved at any width, so text is never cropped."""
    n, secs = len(SLIDES_SPEC), 3.6
    total = round(n * secs, 1)
    b64s = []
    for title, sub, tag, motif in SLIDES_SPEC:
        buf = io.BytesIO()
        _slide(title, sub, tag, motif).save(buf, format="JPEG", quality=86, optimize=True)
        b64s.append(base64.b64encode(buf.getvalue()).decode())

    rules, slides, dots = [], [], []
    for i, b in enumerate(b64s):
        rules.append(f".ec-slide:nth-child({i + 1}){{animation-delay:{round(i * secs, 1)}s}} .ec-dot:nth-child({i + 1}){{animation-delay:{round(i * secs, 1)}s}}")
        slides.append(f'<img class="ec-slide" src="data:image/jpeg;base64,{b}" alt="EchoCare slide {i + 1}"/>')
        dots.append('<span class="ec-dot"></span>')
    peak = 100 / n
    return f"""
    <style>
      .ec-banner {{ position:relative; width:100%; aspect-ratio:{W}/{H}; border-radius:20px; overflow:hidden;
                    border:1px solid #E2E8F0; box-shadow:0 6px 20px rgba(15,23,42,.06); background:#EFF6FF; }}
      .ec-slide {{ position:absolute; inset:0; width:100%; height:100%; opacity:0; animation:ecfade {total}s infinite; }}
      @keyframes ecfade {{ 0% {{opacity:0}} 4% {{opacity:1}} {peak:.2f}% {{opacity:1}} {peak + 4:.2f}% {{opacity:0}} 100% {{opacity:0}} }}
      .ec-dots {{ position:absolute; bottom:3.2%; left:5%; display:flex; gap:6px; z-index:3; }}
      .ec-dot {{ width:22px; height:5px; border-radius:99px; background:rgba(37,99,235,.25); animation:ecdot {total}s infinite; }}
      @keyframes ecdot {{ 0% {{background:#2563EB;width:34px}} {peak:.2f}% {{background:#2563EB;width:34px}} {peak + 1:.2f}% {{background:rgba(37,99,235,.25);width:22px}} 100% {{background:rgba(37,99,235,.25);width:22px}} }}
      {' '.join(rules)}
    </style>
    <div class="ec-banner">{''.join(slides)}<div class="ec-dots">{''.join(dots)}</div></div>
    """
