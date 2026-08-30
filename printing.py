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

SENZA_FINESTRA = 0x08000000 if os.name == "nt" else 0

# Tk misura i caratteri in punti, il web in pixel: 96/72.
PX_PER_PUNTO = 96.0 / 72.0


# ------------------------------------------------------------------ colori

def _tinta(colore):
    if not colore:
        return None
    testo = colore.strip()
    if not testo.startswith("#"):
        return (0.0, 0.0, 0.0)
    if len(testo) == 4:
        testo = "#" + "".join(c * 2 for c in testo[1:])
    try:
        return tuple(int(testo[i:i + 2], 16) / 255.0 for i in (1, 3, 5))
    except ValueError:
        return (0.0, 0.0, 0.0)


def per_stampa(colore):
    """Rovescia la luminosita' tenendo tinta e saturazione. None = niente."""
    rgb = _tinta(colore)
    if rgb is None:
        return None
    h, l, s = colorsys.rgb_to_hls(*rgb)
    nuova = 1.0 - l
    # ⚠️ The threshold is deliberately high. The theme's grounds are NOT
    # grey: they are very dark blues, and with a low threshold they passed
    # for "colour" and came out
    # printed pale blue instead of white. A real colour (a wire, a
    # avviso) sta ben sopra 0,45 di saturazione; un fondo no.
    if s > 0.45:
        # solid colours on paper want to be deeper, or
        # diventano pastelli slavati
        s = min(1.0, s * 1.15)
        nuova = min(nuova, 0.44)
    elif nuova < 0.5:
        nuova *= 0.78
    r, g, b = colorsys.hls_to_rgb(h, nuova, s)
    return "#%02X%02X%02X" % (int(r * 255), int(g * 255), int(b * 255))


def _fuggi(testo):
    return (testo.replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


# ------------------------------------------------- dalla tela di Tk all'SVG

def _analizza_carattere(tela, oggetto):
    """(famiglia, corpo in px, grassetto) dell'oggetto di testo."""
    descrizione = tela.itemcget(oggetto, "font")
    carattere = tkfont.Font(root=tela, font=descrizione)
    corpo = abs(carattere.actual("size"))
    if corpo < 40:                      # in punti: si porta in pixel
        corpo *= PX_PER_PUNTO
    return (carattere.actual("family"), corpo,
            carattere.actual("weight") == "bold", carattere)


def _spezza(testo, carattere, larghezza):
    """Manda a capo come fa Tk: avidamente, sugli spazi."""
    if not larghezza:
        return testo.split("\n")
    fuori = []
    for paragrafo in testo.split("\n"):
        riga = ""
        for parola in paragrafo.split(" "):
            prova = (riga + " " + parola).strip()
            if riga and carattere.measure(prova) > larghezza:
                fuori.append(riga)
                riga = parola
            else:
                riga = prova
        fuori.append(riga)
    return fuori


def svg_da_tela(tela, area, fondo="#FFFFFF"):
    """The piece of canvas inside `area` (x0, y0, x1, y1) becomes an SVG."""
    x0, y0, x1, y1 = area
    pezzi = []
    for oggetto in tela.find_all():
        tipo = tela.type(oggetto)
        limiti = tela.bbox(oggetto)
        if not limiti:
            continue
        if (limiti[2] < x0 or limiti[0] > x1 or limiti[3] < y0
                or limiti[1] > y1):
            continue
        coordinate = tela.coords(oggetto)
        if tipo in ("line", "polygon"):
            punti = " ".join(
                "%.2f,%.2f" % (coordinate[i], coordinate[i + 1])
                for i in range(0, len(coordinate) - 1, 2))
            larghezza = float(tela.itemcget(oggetto, "width") or 1)
            if tipo == "line":
                tratteggio = tela.itemcget(oggetto, "dash")
                pezzi.append(
                    '<polyline points="%s" fill="none" stroke="%s" '
                    'stroke-width="%.2f" stroke-linecap="round" '
                    'stroke-linejoin="round"%s/>'
                    % (punti, per_stampa(tela.itemcget(oggetto, "fill"))
                       or "#000", larghezza,
                       ' stroke-dasharray="2 3"' if tratteggio else ""))
            else:
                pezzi.append(
                    '<polygon points="%s" fill="%s" stroke="%s" '
                    'stroke-width="%.2f"/>'
                    % (punti, per_stampa(tela.itemcget(oggetto, "fill"))
                       or "none",
                       per_stampa(tela.itemcget(oggetto, "outline")) or "none",
                       larghezza))
        elif tipo == "rectangle":
            riempi = per_stampa(tela.itemcget(oggetto, "fill"))
            bordo = per_stampa(tela.itemcget(oggetto, "outline"))
            tratteggio = tela.itemcget(oggetto, "dash")
            pezzi.append(
                '<rect x="%.2f" y="%.2f" width="%.2f" height="%.2f" '
                'fill="%s" stroke="%s" stroke-width="%.2f"%s/>'
                % (coordinate[0], coordinate[1],
                   coordinate[2] - coordinate[0], coordinate[3] - coordinate[1],
                   riempi or "none", bordo or "none",
                   float(tela.itemcget(oggetto, "width") or 1),
                   ' stroke-dasharray="2 3"' if tratteggio else ""))
        elif tipo in ("oval", "arc"):
            cx = (coordinate[0] + coordinate[2]) / 2.0
            cy = (coordinate[1] + coordinate[3]) / 2.0
            rx = abs(coordinate[2] - coordinate[0]) / 2.0
            ry = abs(coordinate[3] - coordinate[1]) / 2.0
            riempi = per_stampa(tela.itemcget(oggetto, "fill")) or "none"
            bordo = per_stampa(tela.itemcget(oggetto, "outline")) or "none"
            if tipo == "oval":
                pezzi.append('<ellipse cx="%.2f" cy="%.2f" rx="%.2f" ry="%.2f" '
                             'fill="%s" stroke="%s"/>'
                             % (cx, cy, rx, ry, riempi, bordo))
            else:
                inizio = float(tela.itemcget(oggetto, "start") or 0)
                ampiezza = float(tela.itemcget(oggetto, "extent") or 90)
                passi = max(8, int(abs(ampiezza) / 8))
                punti = []
                for i in range(passi + 1):
                    angolo = math.radians(inizio + ampiezza * i / float(passi))
                    punti.append("%.2f,%.2f" % (cx + rx * math.cos(angolo),
                                                cy - ry * math.sin(angolo)))
                pezzi.append('<polygon points="%s" fill="%s" stroke="%s"/>'
                             % (" ".join(punti), riempi, bordo))
        elif tipo == "text":
            contenuto = tela.itemcget(oggetto, "text")
            if not contenuto.strip():
                continue
            famiglia, corpo, grassetto, carattere = _analizza_carattere(
                tela, oggetto)
            righe = _spezza(contenuto, carattere,
                            float(tela.itemcget(oggetto, "width") or 0))
            ancora = tela.itemcget(oggetto, "anchor") or "center"
            allinea = "start"
            x = limiti[0]
            if "e" in ancora and "w" not in ancora:
                allinea, x = "end", limiti[2]
            elif ancora in ("n", "s", "center", ""):
                allinea, x = "middle", (limiti[0] + limiti[2]) / 2.0
            alta = carattere.metrics("linespace")
            base = limiti[1] + carattere.metrics("ascent")
            for indice, riga in enumerate(righe):
                if not riga.strip():
                    continue
                pezzi.append(
                    '<text x="%.2f" y="%.2f" fill="%s" font-family="%s" '
                    'font-size="%.1fpx"%s text-anchor="%s" '
                    'xml:space="preserve">%s</text>'
                    % (x, base + indice * alta,
                       per_stampa(tela.itemcget(oggetto, "fill")) or "#000",
                       _fuggi(famiglia), corpo,
                       ' font-weight="bold"' if grassetto else "",
                       allinea, _fuggi(riga)))
    # ⚠️ width and height BOTH have to be attributes: with only the
    # larghezza al 100% Chrome, in stampa, calcola altezza zero e la pagina
    # it comes out empty. With both real sizes the CSS can scale it.
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="%.0f %.0f %.0f %.0f" '
        'width="%.0f" height="%.0f" preserveAspectRatio="xMidYMid meet">\n'
        '<rect x="%.0f" y="%.0f" width="%.0f" height="%.0f" fill="%s"/>\n'
        '%s\n</svg>'
        % (x0, y0, x1 - x0, y1 - y0, x1 - x0, y1 - y0,
           x0, y0, x1 - x0, y1 - y0, fondo, "\n".join(pezzi)))


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
    marca = "th" if intestazione else "td"
    return "<tr>%s</tr>" % "".join(
        "<%s%s>%s</%s>" % (marca, (' class="%s"' % c[1]) if len(c) > 1 else "",
                           c[0], marca) for c in celle)


def html_adattatore(svg, L, pezzi, canali, note, gia_pronti, titolo, sotto):
    """La pagina: il disegno su un foglio, la distinta sull'altro."""
    righe_pezzi = [_riga_tabella([(L("ad_col_sigla"),), (L("ad_col_valore"),),
                                  (L("ad_col_modelli"),)], True)]
    for sigla, valore, modelli in pezzi:
        righe_pezzi.append(_riga_tabella([
            (_fuggi(sigla), "sigla"), (_fuggi(valore),),
            (_fuggi(modelli), "modelli")]))


    righe_canali = [_riga_tabella([(L("ad_col_segnale"),), (L("sch_col_pico"),),
                                   ("",), (L("sch_col_chip"),)], True)]
    for segnale, pico, chip, verso in canali:
        righe_canali.append(_riga_tabella([
            (segnale, "sigla"), (pico,), ("&rarr;" if verso == "verso"
                                          else "&larr;",), (_fuggi(chip),)]))

    blocchi_note = "\n".join(
        '<p class="nota%s">%s</p>' % (" grave" if indice == 0 else "",
                                      _fuggi(L(chiave)))
        for indice, chiave in enumerate(note))

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
        "titolo": _fuggi(titolo), "sotto": _fuggi(sotto), "css": CSS,
        "svg": svg,
        "tit_distinta": _fuggi(L("ad_distinta")),
        "pezzi": "\n".join(righe_pezzi),
        "gia_pronti": _fuggi(L("ad_gia_pronti")),
        "tit_canali": _fuggi(L("ad_tabella")),
        "canali": "\n".join(righe_canali),
        "tit_note": _fuggi(L("ad_note_titolo")), "note": blocchi_note,
        "piede": _fuggi(L("ad_piede")),
    }


# ------------------------------------------------------------------ Chrome

def trova_chrome():
    for percorso in CHROME:
        if os.path.isfile(percorso):
            return percorso
    return None


def in_pdf(html, percorso_pdf, chrome=None):
    """Scrive l'HTML e lo fa stampare in PDF da Chrome. (fatto, motivo)."""
    eseguibile = chrome or trova_chrome()
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
    cartella = tempfile.mkdtemp(prefix="spiranha-stampa-")
    percorso_html = os.path.join(cartella, "schema.html")
    with open(percorso_html, "wb") as f:
        f.write(html.encode("utf-8"))
    profilo = os.path.join(cartella, "profilo")
    comando = [
        eseguibile, "--headless=new", "--disable-gpu", "--no-first-run",
        "--no-pdf-header-footer", "--user-data-dir=%s" % profilo,
        "--print-to-pdf=%s" % percorso_pdf,
        "file:///" + percorso_html.replace("\\", "/"),
    ]
    try:
        esito = subprocess.run(comando, capture_output=True, timeout=120,
                               creationflags=SENZA_FINESTRA)
    except Exception as e:                                 # noqa: BLE001
        return False, "%s" % e
    if not os.path.isfile(percorso_pdf) or os.path.getsize(percorso_pdf) < 1000:
        return False, (esito.stderr.decode("utf-8", "replace").strip()[-300:]
                       or "il PDF non e' stato scritto")
    return True, percorso_html
