# -*- coding: utf-8 -*-
"""The printable PDF of the diagram, with its bill of materials.

HOW. The drawing is not redone: it is READ off the Tk canvas, which can say
what objects it holds, where they sit, in what colour and in what font. That
becomes an SVG, which goes into an HTML page with print CSS, and Chrome in
headless mode turns the page into a PDF. It is the house method for PDFs: the
layout is done by an engine that already knows how to lay out, and the result
stays vector -- it scales without going fuzzy and the text can be selected.

That way there are never two versions of the same diagram to keep in step:
the PDF is what is on screen, in different colours.

⚠️ THE COLOURS ARE INVERTED. The screen is dark; a page with a black
background eats a cartridge and cannot be read. Here the lightness is flipped
while hue and saturation are kept (per_stampa): the ground turns white, light
text turns dark, and the wires keep their own colours, a little deeper as
paper wants. It is not a negative -- a negative would turn red into green.

⚠️ CHROME WANTS A PROFILE OF ITS OWN (an isolated --user-data-dir): without
one it attaches to an already-open window and does not even write the PDF,
saying nothing.
"""
from __future__ import unicode_literals

import colorsys
import math
import os
import subprocess
import tempfile

import tkinter.font as tkfont

CHROME = (
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
)

NO_WINDOW = 0x08000000 if os.name == "nt" else 0

# Tk measures fonts in points, the web in pixels: 96/72.
PX_PER_POINT = 96.0 / 72.0


# ------------------------------------------------------------------ colori

def _tint(colour):
    if not colour:
        return None
    text = colour.strip()
    if not text.startswith("#"):
        return (0.0, 0.0, 0.0)
    if len(text) == 4:
        text = "#" + "".join(c * 2 for c in text[1:])
    try:
        return tuple(int(text[i:i + 2], 16) / 255.0 for i in (1, 3, 5))
    except ValueError:
        return (0.0, 0.0, 0.0)


def for_print(colour):
    """Rovescia la luminosita' tenendo tinta e saturazione. None = niente."""
    rgb = _tint(colour)
    if rgb is None:
        return None
    h, l, s = colorsys.rgb_to_hls(*rgb)
    newer = 1.0 - l
    # ⚠️ The threshold is deliberately high. The theme's grounds are NOT
    # grey: they are very dark blues, and with a low threshold they passed
    # for "colour" and came out
    # printed pale blue instead of white. A real colour (a wire, a
    # warning) sits well above 0.45 saturation; a ground does not.
    if s > 0.45:
        # solid colours on paper want to be deeper, or
        # diventano pastelli slavati
        s = min(1.0, s * 1.15)
        newer = min(newer, 0.44)
    elif newer < 0.5:
        newer *= 0.78
    r, g, b = colorsys.hls_to_rgb(h, newer, s)
    return "#%02X%02X%02X" % (int(r * 255), int(g * 255), int(b * 255))


def _escape(text):
    return (text.replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


# ------------------------------------------------- from the Tk canvas to SVG

def _measure_font(canvas, obj):
    """(famiglia, corpo in px, grassetto) dell'oggetto di testo."""
    description = canvas.itemcget(obj, "font")
    font = tkfont.Font(root=canvas, font=description)
    body = abs(font.actual("size"))
    if body < 40:                      # in punti: si porta in pixel
        body *= PX_PER_POINT
    return (font.actual("family"), body,
            font.actual("weight") == "bold", font)


def _split(text, font, width):
    """Wraps the way Tk does: greedily, on spaces."""
    if not width:
        return text.split("\n")
    out = []
    for paragraph in text.split("\n"):
        line = ""
        for word in paragraph.split(" "):
            checks = (line + " " + word).strip()
            if line and font.measure(checks) > width:
                out.append(line)
                line = word
            else:
                line = checks
        out.append(line)
    return out


def svg_from_canvas(canvas, area, background="#FFFFFF"):
    """The piece of canvas inside `area` (x0, y0, x1, y1) becomes an SVG."""
    x0, y0, x1, y1 = area
    chunks = []
    for obj in canvas.find_all():
        kind = canvas.type(obj)
        bounds = canvas.bbox(obj)
        if not bounds:
            continue
        if (bounds[2] < x0 or bounds[0] > x1 or bounds[3] < y0
                or bounds[1] > y1):
            continue
        coords = canvas.coords(obj)
        if kind in ("line", "polygon"):
            points = " ".join(
                "%.2f,%.2f" % (coords[i], coords[i + 1])
                for i in range(0, len(coords) - 1, 2))
            width = float(canvas.itemcget(obj, "width") or 1)
            if kind == "line":
                dash = canvas.itemcget(obj, "dash")
                chunks.append(
                    '<polyline points="%s" fill="none" stroke="%s" '
                    'stroke-width="%.2f" stroke-linecap="round" '
                    'stroke-linejoin="round"%s/>'
                    % (points, for_print(canvas.itemcget(obj, "fill"))
                       or "#000", width,
                       ' stroke-dasharray="2 3"' if dash else ""))
            else:
                chunks.append(
                    '<polygon points="%s" fill="%s" stroke="%s" '
                    'stroke-width="%.2f"/>'
                    % (points, for_print(canvas.itemcget(obj, "fill"))
                       or "none",
                       for_print(canvas.itemcget(obj, "outline")) or "none",
                       width))
        elif kind == "rectangle":
            fill_to = for_print(canvas.itemcget(obj, "fill"))
            border = for_print(canvas.itemcget(obj, "outline"))
            dash = canvas.itemcget(obj, "dash")
            chunks.append(
                '<rect x="%.2f" y="%.2f" width="%.2f" height="%.2f" '
                'fill="%s" stroke="%s" stroke-width="%.2f"%s/>'
                % (coords[0], coords[1],
                   coords[2] - coords[0], coords[3] - coords[1],
                   fill_to or "none", border or "none",
                   float(canvas.itemcget(obj, "width") or 1),
                   ' stroke-dasharray="2 3"' if dash else ""))
        elif kind in ("oval", "arc"):
            cx = (coords[0] + coords[2]) / 2.0
            cy = (coords[1] + coords[3]) / 2.0
            rx = abs(coords[2] - coords[0]) / 2.0
            ry = abs(coords[3] - coords[1]) / 2.0
            fill_to = for_print(canvas.itemcget(obj, "fill")) or "none"
            border = for_print(canvas.itemcget(obj, "outline")) or "none"
            if kind == "oval":
                chunks.append('<ellipse cx="%.2f" cy="%.2f" rx="%.2f" ry="%.2f" '
                             'fill="%s" stroke="%s"/>'
                             % (cx, cy, rx, ry, fill_to, border))
            else:
                start = float(canvas.itemcget(obj, "start") or 0)
                amplitude = float(canvas.itemcget(obj, "extent") or 90)
                steps = max(8, int(abs(amplitude) / 8))
                points = []
                for i in range(steps + 1):
                    angolo = math.radians(start + amplitude * i / float(steps))
                    points.append("%.2f,%.2f" % (cx + rx * math.cos(angolo),
                                                cy - ry * math.sin(angolo)))
                chunks.append('<polygon points="%s" fill="%s" stroke="%s"/>'
                             % (" ".join(points), fill_to, border))
        elif kind == "text":
            content = canvas.itemcget(obj, "text")
            if not content.strip():
                continue
            family, body, bold, font = _measure_font(
                canvas, obj)
            lines = _split(content, font,
                            float(canvas.itemcget(obj, "width") or 0))
            anchor = canvas.itemcget(obj, "anchor") or "center"
            align = "start"
            x = bounds[0]
            if "e" in anchor and "w" not in anchor:
                align, x = "end", bounds[2]
            elif anchor in ("n", "s", "center", ""):
                align, x = "middle", (bounds[0] + bounds[2]) / 2.0
            top = font.metrics("linespace")
            base = bounds[1] + font.metrics("ascent")
            for index, line in enumerate(lines):
                if not line.strip():
                    continue
                chunks.append(
                    '<text x="%.2f" y="%.2f" fill="%s" font-family="%s" '
                    'font-size="%.1fpx"%s text-anchor="%s" '
                    'xml:space="preserve">%s</text>'
                    % (x, base + index * top,
                       for_print(canvas.itemcget(obj, "fill")) or "#000",
                       _escape(family), body,
                       ' font-weight="bold"' if bold else "",
                       align, _escape(line)))
    # ⚠️ width and height BOTH have to be attributes: with only the
    # width alone at 100%, Chrome works out a height of zero when printing
    # it comes out empty. With both real sizes the CSS can scale it.
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="%.0f %.0f %.0f %.0f" '
        'width="%.0f" height="%.0f" preserveAspectRatio="xMidYMid meet">\n'
        '<rect x="%.0f" y="%.0f" width="%.0f" height="%.0f" fill="%s"/>\n'
        '%s\n</svg>'
        % (x0, y0, x1 - x0, y1 - y0, x1 - x0, y1 - y0,
           x0, y0, x1 - x0, y1 - y0, background, "\n".join(chunks)))


# -------------------------------------------------------------------- page

CSS = """
@page { size: A4 landscape; margin: 12mm 12mm 12mm 12mm; }
* { -webkit-print-color-adjust: exact; print-color-adjust: exact;
    box-sizing: border-box; }
body { margin: 0; color: #12202B;
       font-family: "Segoe UI", system-ui, sans-serif; font-size: 10pt; }
h1 { font-size: 15pt; margin: 0 0 1mm 0; }
h2 { font-size: 11pt; margin: 6mm 0 2mm 0; break-after: avoid; }
.sub { color: #5A6B7A; font-size: 9pt; margin: 0 0 4mm 0; }
.sheet { break-after: page; }
.sheet:last-child { break-after: auto; }
/* ⚠️ The drawing has to be CONTAINED in the sheet, not merely as wide as
   the sheet: with width alone at 100% it grows taller than the page, it
   cannot be split, and Chrome throws it onto the next page leaving the
   first one empty. With max-width and max-height together (and automatic
   sizes) it behaves like a "contained" figure, in proportion. */
svg { display: block; margin: 0 auto; width: auto; height: auto;
      max-width: 100%; max-height: 152mm; }
table { border-collapse: collapse; width: 100%; break-inside: avoid;
        font-size: 9pt; margin-bottom: 4mm; }
th { background: #0B3D66; color: #fff; text-align: left;
     padding: 2mm 2.5mm; font-size: 8.5pt; font-weight: 600; }
td { border: 1px solid #C8D2DA; padding: 1.8mm 2.5mm; vertical-align: top; }
tr { break-inside: avoid; }
.ref { font-family: Consolas, monospace; font-weight: 700; width: 22mm; }
.parts { color: #46586A; font-size: 8.5pt; }
.note { break-inside: avoid; margin: 0 0 2.5mm 0; padding-left: 5mm;
        position: relative; font-size: 9pt; line-height: 1.35; }
.note::before { content: "•"; position: absolute; left: 0; color: #B57708;
                font-weight: 700; }
.note.grave::before { color: #C42126; }
.footer { margin-top: 5mm; color: #6B7B89; font-size: 8pt;
         border-top: 1px solid #C8D2DA; padding-top: 2mm; }
.pair { display: flex; gap: 8mm; }
.pair > * { flex: 1; }
"""


def _table_row(cells, heading=False):
    stamp = "th" if heading else "td"
    return "<tr>%s</tr>" % "".join(
        "<%s%s>%s</%s>" % (stamp, (' class="%s"' % c[1]) if len(c) > 1 else "",
                           c[0], stamp) for c in cells)


def level_shifter_html(svg, L, chunks, channels, note, ready_made, title, below):
    """The page: the drawing on one sheet, the BOM on the other."""
    part_rows = [_table_row([(L("ls_col_ref"),), (L("ls_col_value"),),
                                  (L("ls_col_parts"),)], True)]
    for ref, value, models in chunks:
        part_rows.append(_table_row([
            (_escape(ref), "ref"), (_escape(value),),
            (_escape(models), "parts")]))


    channel_rows = [_table_row([(L("ls_col_signal"),), (L("sch_col_pico"),),
                                   ("",), (L("sch_col_chip"),)], True)]
    for signal, pico, chip, direction in channels:
        channel_rows.append(_table_row([
            (signal, "ref"), (pico,), ("&rarr;" if direction == "to"
                                          else "&larr;",), (_escape(chip),)]))

    note_blocks = "\n".join(
        '<p class="note%s">%s</p>' % (" severe" if index == 0 else "",
                                      _escape(L(key)))
        for index, key in enumerate(note))

    return """<!doctype html>
<html lang="%(lang)s"><head><meta charset="utf-8">
<title>%(title)s</title><style>%(css)s</style></head><body>
<div class="sheet">
  <h1>%(title)s</h1>
  <p class="sub">%(sub)s</p>
  %(svg)s
  <p class="footer">%(footer)s</p>
</div>
<div class="sheet">
  <h1>%(title)s</h1>
  <h2>%(bom_title)s</h2>
  <table>%(parts)s</table>
  <p class="note">%(ready_made)s</p>
  <div class="pair">
    <div>
      <h2>%(channels_title)s</h2>
      <table>%(channels)s</table>
    </div>
    <div>
      <h2>%(notes_title)s</h2>
      %(note)s
    </div>
  </div>
  <p class="footer">%(footer)s</p>
</div>
</body></html>""" % {
        "lang": getattr(L, "code", "en"),
        "title": _escape(title), "sub": _escape(below), "css": CSS,
        "svg": svg,
        "bom_title": _escape(L("ls_bom")),
        "parts": "\n".join(part_rows),
        "ready_made": _escape(L("ls_ready_made")),
        "channels_title": _escape(L("ls_table")),
        "channels": "\n".join(channel_rows),
        "notes_title": _escape(L("ls_notes_title")), "note": note_blocks,
        "footer": _escape(L("ls_footer")),
    }


# ------------------------------------------------------------------ Chrome

def find_chrome():
    for path in CHROME:
        if os.path.isfile(path):
            return path
    return None


def to_pdf(html, pdf_path, chrome=None):
    """Writes the HTML and has Chrome print it to PDF. (done, reason)."""
    executable_ = chrome or find_chrome()
    if not executable_:
        return False, "chrome"
    # ⚠️ The destination file is removed FIRST. If it stays there and
    # Chrome does not write -- because it is open in a reader, because the
    # profile is busy -- finding yesterday's PDF and calling it done is
    # worse than failing: you print the wrong diagram without knowing.
    if os.path.exists(pdf_path):
        try:
            os.remove(pdf_path)
        except OSError as e:
            return False, "%s" % e
    folder = tempfile.mkdtemp(prefix="spiranha-stampa-")
    html_path = os.path.join(folder, "schema.html")
    with open(html_path, "wb") as f:
        f.write(html.encode("utf-8"))
    profile = os.path.join(folder, "profile")
    command = [
        executable_, "--headless=new", "--disable-gpu", "--no-first-run",
        "--no-pdf-header-footer", "--user-data-dir=%s" % profile,
        "--print-to-pdf=%s" % pdf_path,
        "file:///" + html_path.replace("\\", "/"),
    ]
    try:
        result = subprocess.run(command, capture_output=True, timeout=120,
                               creationflags=NO_WINDOW)
    except Exception as e:                                 # noqa: BLE001
        return False, "%s" % e
    if not os.path.isfile(pdf_path) or os.path.getsize(pdf_path) < 1000:
        return False, (result.stderr.decode("utf-8", "replace").strip()[-300:]
                       or "the PDF was not written")
    return True, html_path
