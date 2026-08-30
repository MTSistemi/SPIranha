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

# Tk misura i caratteri in punti, il web in pixel: 96/72.
PX_PER_POINT = 96.0 / 72.0


# ------------------------------------------------------------------ colori

def _tinta(colour):
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
    rgb = _tinta(colour)
    if rgb is None:
        return None
    h, l, s = colorsys.rgb_to_hls(*rgb)
    newer = 1.0 - l
    # ⚠️ The threshold is deliberately high. The theme's grounds are NOT
    # grey: they are very dark blues, and with a low threshold they passed
    # for "colour" and came out
    # printed pale blue instead of white. A real colour (a wire, a
    # avviso) sta ben sopra 0,45 di saturazione; un fondo no.
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


# ------------------------------------------------- dalla tela di Tk all'SVG

def _analizza_carattere(canvas, obj):
    """(famiglia, corpo in px, grassetto) dell'oggetto di testo."""
    description = canvas.itemcget(obj, "font")
    font = tkfont.Font(root=canvas, font=description)
    body = abs(font.actual("size"))
    if body < 40:                      # in punti: si porta in pixel
        body *= PX_PER_POINT
    return (font.actual("family"), body,
            font.actual("weight") == "bold", font)


def _spezza(text, font, width):
    """Manda a capo come fa Tk: avidamente, sugli spazi."""
    if not width:
        return text.split("\n")
    out = []
    for paragrafo in text.split("\n"):
        line = ""
        for word in paragrafo.split(" "):
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
            riempi = for_print(canvas.itemcget(obj, "fill"))
            border = for_print(canvas.itemcget(obj, "outline"))
            dash = canvas.itemcget(obj, "dash")
            chunks.append(
                '<rect x="%.2f" y="%.2f" width="%.2f" height="%.2f" '
                'fill="%s" stroke="%s" stroke-width="%.2f"%s/>'
                % (coords[0], coords[1],
                   coords[2] - coords[0], coords[3] - coords[1],
                   riempi or "none", border or "none",
                   float(canvas.itemcget(obj, "width") or 1),
                   ' stroke-dasharray="2 3"' if dash else ""))
        elif kind in ("oval", "arc"):
            cx = (coords[0] + coords[2]) / 2.0
            cy = (coords[1] + coords[3]) / 2.0
            rx = abs(coords[2] - coords[0]) / 2.0
            ry = abs(coords[3] - coords[1]) / 2.0
            riempi = for_print(canvas.itemcget(obj, "fill")) or "none"
            border = for_print(canvas.itemcget(obj, "outline")) or "none"
            if kind == "oval":
                chunks.append('<ellipse cx="%.2f" cy="%.2f" rx="%.2f" ry="%.2f" '
                             'fill="%s" stroke="%s"/>'
                             % (cx, cy, rx, ry, riempi, border))
            else:
                start = float(canvas.itemcget(obj, "start") or 0)
                amplitude = float(canvas.itemcget(obj, "extent") or 90)
                passi = max(8, int(abs(amplitude) / 8))
                points = []
                for i in range(passi + 1):
                    angolo = math.radians(start + amplitude * i / float(passi))
                    points.append("%.2f,%.2f" % (cx + rx * math.cos(angolo),
                                                cy - ry * math.sin(angolo)))
                chunks.append('<polygon points="%s" fill="%s" stroke="%s"/>'
                             % (" ".join(points), riempi, border))
        elif kind == "text":
            contenuto = canvas.itemcget(obj, "text")
            if not contenuto.strip():
                continue
            family, body, grassetto, font = _analizza_carattere(
                canvas, obj)
            lines = _spezza(contenuto, font,
                            float(canvas.itemcget(obj, "width") or 0))
            anchor = canvas.itemcget(obj, "anchor") or "center"
            allinea = "start"
            x = bounds[0]
            if "e" in anchor and "w" not in anchor:
                allinea, x = "end", bounds[2]
            elif anchor in ("n", "s", "center", ""):
                allinea, x = "middle", (bounds[0] + bounds[2]) / 2.0
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
                       ' font-weight="bold"' if grassetto else "",
                       allinea, _escape(line)))
    # ⚠️ width and height BOTH have to be attributes: with only the
    # larghezza al 100% Chrome, in stampa, calcola altezza zero e la pagina
    # it comes out empty. With both real sizes the CSS can scale it.
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="%.0f %.0f %.0f %.0f" '
        'width="%.0f" height="%.0f" preserveAspectRatio="xMidYMid meet">\n'
        '<rect x="%.0f" y="%.0f" width="%.0f" height="%.0f" fill="%s"/>\n'
        '%s\n</svg>'
        % (x0, y0, x1 - x0, y1 - y0, x1 - x0, y1 - y0,
           x0, y0, x1 - x0, y1 - y0, background, "\n".join(chunks)))


# ------------------------------------------------------------------- pagina

CSS = """
@page { size: A4 landscape; margin: 12mm 12mm 12mm 12mm; }
* { -webkit-print-color-adjust: exact; print-color-adjust: exact;
    box-sizing: border-box; }
body { margin: 0; color: #12202B;
       font-family: "Segoe UI", system-ui, sans-serif; font-size: 10pt; }
h1 { font-size: 15pt; margin: 0 0 1mm 0; }
h2 { font-size: 11pt; margin: 6mm 0 2mm 0; break-after: avoid; }
.sotto { color: #5A6B7A; font-size: 9pt; margin: 0 0 4mm 0; }
.foglio { break-after: page; }
.foglio:last-child { break-after: auto; }
/* ⚠️ Il disegno va CONTENUTO nel foglio, non solo largo quanto il foglio:
   con la sola larghezza al 100% diventa piu' alto della pagina, non si puo'
   spezzare, e Chrome lo butta sulla pagina dopo lasciando la prima vuota.
   Con max-width e max-height insieme (e misure automatiche) si comporta
   come una figura «contenuta», in proporzione. */
svg { display: block; margin: 0 auto; width: auto; height: auto;
      max-width: 100%; max-height: 152mm; }
table { border-collapse: collapse; width: 100%; break-inside: avoid;
        font-size: 9pt; margin-bottom: 4mm; }
th { background: #0B3D66; color: #fff; text-align: left;
     padding: 2mm 2.5mm; font-size: 8.5pt; font-weight: 600; }
td { border: 1px solid #C8D2DA; padding: 1.8mm 2.5mm; vertical-align: top; }
tr { break-inside: avoid; }
.sigla { font-family: Consolas, monospace; font-weight: 700; width: 22mm; }
.modelli { color: #46586A; font-size: 8.5pt; }
.nota { break-inside: avoid; margin: 0 0 2.5mm 0; padding-left: 5mm;
        position: relative; font-size: 9pt; line-height: 1.35; }
.nota::before { content: "•"; position: absolute; left: 0; color: #B57708;
                font-weight: 700; }
.nota.grave::before { color: #C42126; }
.piede { margin-top: 5mm; color: #6B7B89; font-size: 8pt;
         border-top: 1px solid #C8D2DA; padding-top: 2mm; }
.due { display: flex; gap: 8mm; }
.due > * { flex: 1; }
"""


def _riga_tabella(celle, intestazione=False):
    stamp = "th" if intestazione else "td"
    return "<tr>%s</tr>" % "".join(
        "<%s%s>%s</%s>" % (stamp, (' class="%s"' % c[1]) if len(c) > 1 else "",
                           c[0], stamp) for c in celle)


def level_shifter_html(svg, L, chunks, canali, note, gia_pronti, title, sotto):
    """La pagina: il disegno su un foglio, la distinta sull'altro."""
    righe_pezzi = [_riga_tabella([(L("ad_col_sigla"),), (L("ad_col_valore"),),
                                  (L("ad_col_modelli"),)], True)]
    for ref, value_for, modelli in chunks:
        righe_pezzi.append(_riga_tabella([
            (_escape(ref), "sigla"), (_escape(value_for),),
            (_escape(modelli), "modelli")]))


    righe_canali = [_riga_tabella([(L("ad_col_segnale"),), (L("sch_col_pico"),),
                                   ("",), (L("sch_col_chip"),)], True)]
    for signal, pico, chip, direction in canali:
        righe_canali.append(_riga_tabella([
            (signal, "sigla"), (pico,), ("&rarr;" if direction == "verso"
                                          else "&larr;",), (_escape(chip),)]))

    blocchi_note = "\n".join(
        '<p class="nota%s">%s</p>' % (" grave" if index == 0 else "",
                                      _escape(L(key)))
        for index, key in enumerate(note))

    return """<!doctype html>
<html lang="it"><head><meta charset="utf-8">
<title>%(titolo)s</title><style>%(css)s</style></head><body>
<div class="foglio">
  <h1>%(titolo)s</h1>
  <p class="sotto">%(sotto)s</p>
  %(svg)s
  <p class="piede">%(piede)s</p>
</div>
<div class="foglio">
  <h1>%(titolo)s</h1>
  <h2>%(tit_distinta)s</h2>
  <table>%(pezzi)s</table>
  <p class="nota">%(gia_pronti)s</p>
  <div class="due">
    <div>
      <h2>%(tit_canali)s</h2>
      <table>%(canali)s</table>
    </div>
    <div>
      <h2>%(tit_note)s</h2>
      %(note)s
    </div>
  </div>
  <p class="piede">%(piede)s</p>
</div>
</body></html>""" % {
        "titolo": _escape(title), "sotto": _escape(sotto), "css": CSS,
        "svg": svg,
        "tit_distinta": _escape(L("ad_distinta")),
        "pezzi": "\n".join(righe_pezzi),
        "gia_pronti": _escape(L("ad_gia_pronti")),
        "tit_canali": _escape(L("ad_tabella")),
        "canali": "\n".join(righe_canali),
        "tit_note": _escape(L("ad_note_titolo")), "note": blocchi_note,
        "piede": _escape(L("ad_piede")),
    }


# ------------------------------------------------------------------ Chrome

def find_chrome():
    for path in CHROME:
        if os.path.isfile(path):
            return path
    return None


def to_pdf(html, percorso_pdf, chrome=None):
    """Scrive l'HTML e lo fa stampare in PDF da Chrome. (fatto, motivo)."""
    eseguibile = chrome or find_chrome()
    if not eseguibile:
        return False, "chrome"
    # ⚠️ The destination file is removed FIRST. If it stays there and
    # Chrome does not write -- because it is open in a reader, because the
    # profile is busy -- finding yesterday's PDF and calling it done is
    # worse than failing: you print the wrong diagram without knowing.
    if os.path.exists(percorso_pdf):
        try:
            os.remove(percorso_pdf)
        except OSError as e:
            return False, "%s" % e
    folder = tempfile.mkdtemp(prefix="spiranha-stampa-")
    percorso_html = os.path.join(folder, "schema.html")
    with open(percorso_html, "wb") as f:
        f.write(html.encode("utf-8"))
    profile = os.path.join(folder, "profilo")
    command = [
        eseguibile, "--headless=new", "--disable-gpu", "--no-first-run",
        "--no-pdf-header-footer", "--user-data-dir=%s" % profile,
        "--print-to-pdf=%s" % percorso_pdf,
        "file:///" + percorso_html.replace("\\", "/"),
    ]
    try:
        result = subprocess.run(command, capture_output=True, timeout=120,
                               creationflags=NO_WINDOW)
    except Exception as e:                                 # noqa: BLE001
        return False, "%s" % e
    if not os.path.isfile(percorso_pdf) or os.path.getsize(percorso_pdf) < 1000:
        return False, (result.stderr.decode("utf-8", "replace").strip()[-300:]
                       or "il PDF non e' stato scritto")
    return True, percorso_html
