"""
Build the hardware layout figure from existing part graphics.

The part drawings are unmodified breadboard-view SVGs from the Fritzing parts
library (CC-BY-SA 3.0) and SparkFun's Fritzing parts (CC-BY-SA 4.0), plus the
Tabler Icons camera (MIT); see parts/ and ../../ATTRIBUTION.md. This script
only positions them, draws schematic wires and labels, and renders the result
with a headless Chromium-based browser (Edge or Chrome).

    python build_hardware_figure.py
"""

import os
import shutil
import subprocess
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
OUT_HTML = HERE / "hardware_layout.html"
OUT_PNG = HERE.parents[1] / "assets" / "images" / "hardware_layout.png"
W, H = 1900, 1120

# SparkFun ESP32 Thing graphic (1 x 2.36 in) drawn at 170 x 401 px, header
# pins along both long edges.
ESP_W, ESP_H = 170, 401
ESP_PIN_X = {"L": 12.0, "R": 158.0}
ESP_PIN_Y0, ESP_PIN_PITCH = 62.0, 17.0


def esp_pin(side, idx, ox, oy):
    return ox + ESP_PIN_X[side], oy + ESP_PIN_Y0 + idx * ESP_PIN_PITCH


# nRF24L01 module drawn at 185 x 92 px; its labelled pins are on the right.
NRF_W, NRF_H = 185, 92
NRF_PINS = {"MISO": (177, 23), "MOSI": (169, 36), "SCK": (177, 36),
            "CSN": (169, 49), "CE": (177, 49), "VCC": (169, 62), "GND": (177, 62)}
# nRF pin -> (ESP32 header side, position along it), colour. Schematic only.
NRF_TO_ESP = [("VCC", ("L", 1), "#d62728"), ("GND", ("L", 0), "#222222"), ("CE", ("R", 13), "#ff7f0e"),
              ("CSN", ("R", 12), "#e3c800"), ("SCK", ("R", 10), "#2ca02c"), ("MOSI", ("R", 7), "#1f77b4"),
              ("MISO", ("R", 9), "#9467bd")]

# Receiver LEDs: approach -> (GPIO for red, GPIO for green) as in Reciver.ino,
# and the header position used for the schematic wire.
LED_GROUPS = [("North", ("13", "12"), [("L", 14), ("L", 15)]),
              ("East", ("26", "25"), [("L", 8), ("L", 9)]),
              ("South", ("14", "27"), [("L", 12), ("L", 11)]),
              ("West", ("33", "32"), [("L", 6), ("L", 5)])]
WIRE_FOR = {"red": "#c0392b", "green": "#1e8449"}


def wire(x1, y1, x2, y2, colour, width=3, dash=None, bend=0.5):
    my = y1 + (y2 - y1) * bend
    d = f"M{x1:.1f},{y1:.1f} C{x1:.1f},{my:.1f} {x2:.1f},{my:.1f} {x2:.1f},{y2:.1f}"
    da = f' stroke-dasharray="{dash}"' if dash else ""
    return (f'<path d="{d}" fill="none" stroke="{colour}" stroke-width="{width}" '
            f'stroke-linecap="round"{da}/>')


def hwire(x1, y1, x2, y2, colour, width=3):
    """Wire that leaves horizontally (for side headers)."""
    mx = (x1 + x2) / 2
    d = f"M{x1:.1f},{y1:.1f} C{mx:.1f},{y1:.1f} {mx:.1f},{y2:.1f} {x2:.1f},{y2:.1f}"
    return f'<path d="{d}" fill="none" stroke="{colour}" stroke-width="{width}" stroke-linecap="round"/>'


def label(x, y, text, size=17, weight="normal", anchor="start", colour="#1a1a1a"):
    lines = text.split("\n")
    out = [f'<text x="{x}" y="{y}" font-family="Segoe UI, Arial, sans-serif" font-size="{size}" '
           f'font-weight="{weight}" fill="{colour}" text-anchor="{anchor}">']
    for i, line in enumerate(lines):
        out.append(f'<tspan x="{x}" dy="{0 if i == 0 else size * 1.25}">{line}</tspan>')
    out.append("</text>")
    return "".join(out)


def image(name, x, y, w, h, extra=""):
    return f'<image href="parts/{name}" x="{x}" y="{y}" width="{w}" height="{h}"{extra}/>'


def esp_with_radio(s, ex, ey, nx, ny):
    s.append(image("sparkfun_esp32_thing_breadboard.svg", ex, ey, ESP_W, ESP_H))
    s.append(image("NRF24L01_fix_breadboard.svg", nx, ny, NRF_W, NRF_H))
    for name, (side, idx), col in NRF_TO_ESP:
        px, py = NRF_PINS[name]
        hx, hy = esp_pin(side, idx, ex, ey)
        s.append(wire(nx + px, ny + py, hx, hy, col, bend=0.6))


def build():
    s = [f'<rect x="0" y="0" width="{W}" height="{H}" fill="#ffffff"/>']
    s.append(label(W / 2, 42, "Remote-controlled traffic light: fallback hardware prototype",
                   size=28, weight="600", anchor="middle"))
    s.append(label(W / 2, 74, "One four-way junction of the proposed city-wide system "
                   "(illustrative layout; wires are schematic, pin numbers are in hardware/wiring.md)",
                   size=17, anchor="middle", colour="#555555"))
    s.append('<rect x="25" y="100" width="830" height="990" rx="14" fill="#f4f8fb" stroke="#9fb6c8"/>')
    s.append('<rect x="1045" y="100" width="830" height="990" rx="14" fill="#f7f5ef" stroke="#c8bb9f"/>')
    s.append(label(45, 132, "CONTROL STATION (transmitter)", size=20, weight="600", colour="#24557a"))
    s.append(label(1065, 132, "JUNCTION CONTROLLER (receiver)", size=20, weight="600", colour="#7a5a24"))

    # ---------------- Left: ESP32 1 + nRF 1 ----------------
    e1x, e1y, n1x, n1y = 470, 330, 130, 190
    esp_with_radio(s, e1x, e1y, n1x, n1y)
    s.append(label(n1x, n1y + NRF_H + 24, "nRF24L01+ radio 1 (SPI)", size=16, weight="600"))
    s.append(label(e1x + ESP_W + 20, e1y + 40, "ESP32 1", size=19, weight="600"))
    s.append(label(e1x + ESP_W + 20, e1y + 64, "sends NS_EMERGENCY or\nEW_EMERGENCY over the\nradio when the operator\ntypes N or E", size=15, colour="#444"))
    # laptop / serial input
    s.append('<rect x="440" y="790" width="380" height="80" rx="10" fill="#ffffff" stroke="#24557a" stroke-width="2"/>')
    s.append(label(630, 822, "Laptop: serial monitor (USB)", size=16, weight="600", anchor="middle", colour="#24557a"))
    s.append(label(630, 848, "operator types N = N/S green, E = E/W green", size=14, anchor="middle", colour="#333"))
    s.append(wire(e1x + ESP_W / 2, e1y + ESP_H, 630, 790, "#555", width=4, bend=0.5))
    s.append(label(e1x + ESP_W / 2 + 12, e1y + ESP_H + 30, "USB", size=13, colour="#555"))

    # Camera (planned, not assembled)
    cx, cy = 60, 560
    s.append(f'<rect x="{cx}" y="{cy}" width="205" height="175" rx="10" fill="#fafafa" '
             f'stroke="#888" stroke-width="2" stroke-dasharray="8 6"/>')
    s.append(image("tabler-camera.svg", cx + 62, cy + 18, 80, 80, extra=' opacity="0.55"'))
    s.append(label(cx + 102, cy + 122, "Camera: lane counts", size=15, weight="600", anchor="middle", colour="#666"))
    s.append(label(cx + 102, cy + 144, "PLANNED, NOT ASSEMBLED", size=13, weight="700", anchor="middle", colour="#b03a2e"))
    s.append(label(cx + 102, cy + 162, "demo used randomized counts", size=13, anchor="middle", colour="#666"))
    s.append(wire(cx + 205, cy + 88, e1x, e1y + 250, "#888", width=2.5, dash="8 6", bend=0.0))

    s.append('<rect x="60" y="910" width="770" height="150" rx="10" fill="#ffffff" stroke="#9fb6c8"/>')
    s.append(label(80, 942, "Role in the system", size=17, weight="600", colour="#24557a"))
    s.append(label(80, 970, "- Fallback: used when the team's automatic traffic-light algorithm is unavailable\n"
                            "- The operator decides the phase (in the demo, from randomized lane counts)\n"
                            "- Part of a larger city-wide system: one control station per junction or zone",
                   size=15, colour="#333"))

    # ---------------- Radio link ----------------
    n2x, n2y = 1120, 190
    ax1, ay1 = n1x + 30, n1y + 20
    ax2, ay2 = n2x + 30, n2y + 20
    s.append(f'<path d="M{ax1},{ay1} Q{(ax1 + ax2) / 2},{ay1 - 70} {ax2},{ay2}" fill="none" '
             f'stroke="#2e86c1" stroke-width="3" stroke-dasharray="12 9"/>')
    for (x, y, sgn) in [(ax1, ay1, 1), (ax2, ay2, -1)]:
        for r in (22, 36, 50):
            s.append(f'<path d="M{x + sgn * r * 0.5},{y - r} A{r},{r} 0 0 {1 if sgn > 0 else 0} '
                     f'{x + sgn * r * 0.5},{y + r * 0.2}" fill="none" stroke="#2e86c1" stroke-width="2" opacity="0.6"/>')
    s.append(label(950, 300, "2.4 GHz\nwireless link\n(nRF24L01+)", size=18, weight="600", anchor="middle", colour="#1b4f72"))
    s.append(label(950, 390, "phase command\n-->", size=15, anchor="middle", colour="#1b4f72"))

    # ---------------- Right: ESP32 2 + nRF 2 + breadboard with 8 LEDs ----------------
    e2x, e2y = 1560, 230
    esp_with_radio(s, e2x, e2y, n2x, n2y)
    s.append(label(n2x, n2y + NRF_H + 24, "nRF24L01+ radio 2 (SPI)", size=16, weight="600"))
    s.append(label(e2x - 20, e2y + 330, "ESP32 2", size=19, weight="600", anchor="end"))
    s.append(label(e2x - 20, e2y + 354, "drives the 8 LEDs; switches\nphase every 120 s, or at once\nwhen a command arrives", size=15,
                   anchor="end", colour="#444"))

    bbx, bby, bbw, bbh = 1080, 760, 780, 252
    s.append(image("breadboard2.svg", bbx, bby, bbw, bbh))
    led_w, led_h = 26, 90
    group_x0 = [bbx + 90, bbx + 275, bbx + 460, bbx + 645]
    for gi, (approach, gpios, pins) in enumerate(LED_GROUPS):
        gx = group_x0[gi]
        s.append(label(gx + 33, bby - 92, approach, size=17, weight="600", anchor="middle"))
        s.append(label(gx + 33, bby - 72, f"GPIO {gpios[0]} / {gpios[1]}", size=13, anchor="middle", colour="#555"))
        for li, colour in enumerate(("red", "green")):
            lx, ly = gx + li * 46, bby + 18
            s.append(image("resistor_220.svg", lx - 22, bby + 160, 70, 16,
                           extra=f' transform="rotate(90 {lx + 13} {bby + 168})"'))
            hx, hy = esp_pin(*pins[li], e2x, e2y)
            s.append(wire(hx, hy, lx + 13, bby + 130, WIRE_FOR[colour], width=2.5, bend=0.7))
            s.append(image(f"LED-5mm-{colour}.svg", lx, ly - 60, led_w, led_h))
    gx, gy = esp_pin("R", 0, e2x, e2y)
    s.append(wire(gx, gy, bbx + bbw - 30, bby + bbh - 12, "#222222", width=3, bend=0.5))
    s.append(label(bbx + bbw - 30, bby + bbh + 28, "GND rail", size=14, anchor="end", colour="#333"))
    s.append(label(bbx, bby + bbh + 28, "Breadboard: 8 LEDs = 4 approaches x (red, green), no yellow by design,",
                   size=15, colour="#333"))
    s.append(label(bbx, bby + bbh + 48, "each from a GPIO pin through a 220 ohm resistor to ground",
                   size=15, colour="#333"))

    s.append(label(W / 2, H - 8, "Part graphics: Fritzing parts library (CC-BY-SA 3.0), SparkFun Fritzing parts (ESP32 Thing, "
                   "CC-BY-SA 4.0) and Tabler Icons (MIT). ESP32 board drawing is representative. Figure licensed CC-BY-SA 4.0.",
                   size=13, anchor="middle", colour="#666"))

    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
           f'width="{W}" height="{H}" viewBox="0 0 {W} {H}">' + "".join(s) + "</svg>")
    OUT_HTML.write_text("<!doctype html><html><head><meta charset='utf-8'></head>"
                        f"<body style='margin:0;background:#fff'>{svg}</body></html>", encoding="utf-8")


def render():
    candidates = [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                  r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                  shutil.which("chromium") or "", shutil.which("google-chrome") or ""]
    browser = next(c for c in candidates if c and os.path.exists(c))
    OUT_PNG.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([browser, "--headless", "--disable-gpu", "--allow-file-access-from-files",
                    "--hide-scrollbars", f"--window-size={W},{H}",
                    f"--screenshot={OUT_PNG}", OUT_HTML.as_uri()],
                   check=True, capture_output=True)
    print("wrote", OUT_PNG)


if __name__ == "__main__":
    build()
    render()
