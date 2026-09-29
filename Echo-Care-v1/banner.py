"""
Generates the animated hero slideshow entirely offline (no image APIs, no
network) using PIL: gradient dark-navy backgrounds, orange/amber accent
shapes, and bundled fonts (assets/fonts/), matching the takeUforward-style
theme. Images are generated once per process (cached) and rendered as a
self-contained auto-fading HTML/CSS carousel via st.components.v1.html —
fully deployment-safe on Streamlit Community Cloud.
"""
import base64
import io
import math
import os
import streamlit as st
from PIL import Image, ImageDraw, ImageFont, ImageFilter

HERE = os.path.dirname(__file__)
FONT_BOLD = os.path.join(HERE, "assets", "fonts", "DejaVuSans-Bold.ttf")
FONT_REG = os.path.join(HERE, "assets", "fonts", "DejaVuSans.ttf")

W, H = 1200, 380
NAVY_DARK = (11, 15, 25)
NAVY_MID = (20, 26, 42)
ORANGE = (255, 140, 26)
ORANGE_2 = (255, 95, 109)
WHITE = (241, 243, 246)
MUTED = (146, 160, 184)


def _gradient_bg(c1, c2, angle_bias=0.0):
    img = Image.new("RGB", (W, H), c1)
    px = img.load()
    for y in range(H):
        t = y / H
        r = int(c1[0] + (c2[0] - c1[0]) * t)
        g = int(c1[1] + (c2[1] - c1[1]) * t)
        b = int(c1[2] + (c2[2] - c1[2]) * t)
        for x in range(W):
            px[x, y] = (r, g, b)
    return img


def _pulse_line(draw, y_base, color, alpha_img, width=3):
    points = []
    x = 0
    while x < W:
        points.append((x, y_base))
        x += 22
        points.append((x, y_base - 26))
        x += 14
        points.append((x, y_base + 34))
        x += 14
        points.append((x, y_base))
        x += 40
    draw.line(points, fill=color, width=width, joint="curve")


def _medical_cross(draw, cx, cy, size, color):
    t = size // 3
    draw.rounded_rectangle([cx - t // 2, cy - size, cx + t // 2, cy + size], radius=6, fill=color)
    draw.rounded_rectangle([cx - size, cy - t // 2, cx + size, cy + t // 2], radius=6, fill=color)


def _add_glow_circles(img, spots):
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)
    for (cx, cy, r, color, alpha) in spots:
        odraw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(*color, alpha))
    overlay = overlay.filter(ImageFilter.GaussianBlur(60))
    return Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")


def _slide(title, subtitle, tag, motif="cross"):
    img = _gradient_bg(NAVY_DARK, NAVY_MID)
    img = _add_glow_circles(img, [
        (W - 160, 80, 220, ORANGE, 70),
        (120, H - 40, 160, ORANGE_2, 50),
    ])
    draw = ImageDraw.Draw(img, "RGBA")

    # faint pulse line motif across the whole banner
    _pulse_line(draw, H - 70, (*ORANGE, 60), img, width=2)

    if motif == "cross":
        _medical_cross(draw, W - 130, 140, 46, (*ORANGE, 200))
    elif motif == "pin":
        cx, cy = W - 130, 140
        draw.ellipse([cx - 40, cy - 55, cx + 40, cy + 25], fill=(*ORANGE, 210))
        draw.polygon([(cx - 28, cy + 5), (cx + 28, cy + 5), (cx, cy + 70)], fill=(*ORANGE, 210))
        draw.ellipse([cx - 16, cy - 40, cx + 16, cy - 8], fill=(*NAVY_DARK, 255))
    elif motif == "shield":
        cx, cy = W - 130, 130
        draw.polygon([(cx, cy - 55), (cx + 45, cy - 30), (cx + 45, cy + 20),
                      (cx, cy + 65), (cx - 45, cy + 20), (cx - 45, cy - 30)], fill=(*ORANGE, 200))
        draw.line([(cx - 18, cy), (cx - 4, cy + 16), (cx + 22, cy - 18)], fill=NAVY_DARK, width=6)
    elif motif == "chat":
        cx, cy = W - 130, 130
        draw.rounded_rectangle([cx - 55, cy - 40, cx + 55, cy + 30], radius=18, fill=(*ORANGE, 200))
        draw.polygon([(cx - 20, cy + 28), (cx - 5, cy + 28), (cx - 25, cy + 55)], fill=(*ORANGE, 200))

    font_title = ImageFont.truetype(FONT_BOLD, 46)
    font_sub = ImageFont.truetype(FONT_REG, 20)
    font_tag = ImageFont.truetype(FONT_BOLD, 15)

    draw.text((60, 60), tag.upper(), font=font_tag, fill=(*ORANGE, 255))
    draw.text((60, 95), title, font=font_title, fill=WHITE)
    # wrap subtitle manually at ~52 chars
    words, lines, cur = subtitle.split(), [], ""
    for w_ in words:
        trial = (cur + " " + w_).strip()
        if len(trial) > 58:
            lines.append(cur)
            cur = w_
        else:
            cur = trial
    if cur:
        lines.append(cur)
    y = 165
    for line in lines[:3]:
        draw.text((60, y), line, font=font_sub, fill=MUTED)
        y += 30

    return img


SLIDES_SPEC = [
    ("EchoCare", "Your longitudinal AI health companion — every symptom, tracked, "
                  "understood, and grounded in your own evidence over time.",
     "AI-Powered Healthcare Platform", "cross"),
    ("Find the Right Doctor", "District-wise specialist directory across 10 departments, "
                               "mapped and ranked so you know exactly where to go.",
     "Doctor & Facility Finder", "pin"),
    ("Diagnostic Guard", "Never let a symptom quietly go unresolved. We track patterns "
                          "across visits and flag contradictions for you to raise.",
     "Patient Advocacy Engine", "shield"),
    ("Echo, Your AI Companion", "A RAG + Gemini + Tavily powered agent that answers using "
                                 "YOUR history first — never a guess, always grounded.",
     "Agentic AI Assistant", "chat"),
]


@st.cache_data(show_spinner=False)
def get_slideshow_html(height: int = 320) -> str:
    b64_slides = []
    for title, sub, tag, motif in SLIDES_SPEC:
        img = _slide(title, sub, tag, motif)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        b64_slides.append(base64.b64encode(buf.getvalue()).decode())

    slides_html = "".join(
        f'<div class="tuf-slide{" active" if i == 0 else ""}">'
        f'<img src="data:image/png;base64,{b64}" />'
        f'</div>'
        for i, b64 in enumerate(b64_slides)
    )
    dots_html = "".join(
        f'<span class="tuf-dot{" active" if i == 0 else ""}" data-i="{i}"></span>'
        for i in range(len(b64_slides))
    )

    return f"""
    <div class="tuf-carousel" style="position:relative;width:100%;height:{height}px;
         border-radius:16px;overflow:hidden;border:1px solid #232B40;">
      <style>
        .tuf-slide {{ position:absolute; inset:0; opacity:0; transition:opacity 1s ease-in-out; }}
        .tuf-slide.active {{ opacity:1; }}
        .tuf-slide img {{ width:100%; height:100%; object-fit:cover; }}
        .tuf-dots {{ position:absolute; bottom:12px; right:18px; z-index:5; }}
        .tuf-dot {{ display:inline-block; width:8px; height:8px; border-radius:50%;
                     background:rgba(255,255,255,.35); margin-left:6px; transition:background .3s; }}
        .tuf-dot.active {{ background:#FF8C1A; }}
      </style>
      {slides_html}
      <div class="tuf-dots">{dots_html}</div>
    </div>
    <script>
      (function() {{
        let idx = 0;
        const root = window.frameElement ? window.frameElement.parentNode : document;
        setInterval(function() {{
          const slides = document.querySelectorAll('.tuf-slide');
          const dots = document.querySelectorAll('.tuf-dot');
          if (!slides.length) return;
          slides[idx].classList.remove('active');
          dots[idx].classList.remove('active');
          idx = (idx + 1) % slides.length;
          slides[idx].classList.add('active');
          dots[idx].classList.add('active');
        }}, 3200);
      }})();
    </script>
    """
