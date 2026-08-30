# -*- coding: utf-8 -*-
"""What is inside a BIOS image, and what changes between two of them.

No chip is touched here: this reads, compares and counts. It serves three
things that used to be done by hand:

  1. the DRY RUN: work out how the flash will end up BEFORE writing it, and
     check that every changing byte falls inside the chosen region;
  2. the COMPARISON of two images, with the ranges aligned to sectors;
  3. the COHERENCE CHECK after writing: not only "the bytes match", but
     "there is still a sensible structure in there".

⚠️ The comparison works in 4 KB blocks because that is the granularity the
chip erases at: a range that is not sector-aligned cannot be written without
dragging along whatever sits around it.
"""
from __future__ import unicode_literals

import os

SECTOR = 4096
ERASED = b"\xff"
ZERO = b"\x00"

# Signatures we can recognise in this flash, verified on the real dump
# of a real BC-250 (BIOS P3.00): _FVH x7, NVAR x958, APCB at
# 0xAB1000, $PSP at 0x8E0000.
SIGNATURES = (
    (b"_FVH", "fv", "volume UEFI", "UEFI firmware volume"),
    (b"NVAR", "nvar", "variabili UEFI", "UEFI variables"),
    (b"APCB", "apcb", "configurazione memoria (APCB)", "memory config (APCB)"),
    (b"$PSP", "psp", "direttorio PSP", "PSP directory"),
)


def read(path):
    with open(path, "rb") as f:
        return f.read()


# --------------------------------------------------------------- confronto

def differing_blocks(a, b, grain=SECTOR):
    """Indices of the `grana`-byte blocks where the two images differ.

    Whole slices are compared rather than byte by byte: over 16 MiB that is
    the difference between an instant and half a minute.
    """
    if len(a) != len(b):
        raise ValueError("immagini di dimensione diversa: %d e %d" % (len(a), len(b)))
    different = []
    for index in range(0, (len(a) + grain - 1) // grain):
        start = index * grain
        if a[start:start + grain] != b[start:start + grain]:
            different.append(index)
    return different


def merge_runs(indices, grain=SECTOR, limit=None):
    """Blocchi contigui -> intervalli (inizio, fine_inclusa)."""
    spans = []
    for index in indices:
        start, end = index * grain, (index + 1) * grain - 1
        if limit is not None:
            end = min(end, limit - 1)
        if spans and spans[-1][1] + 1 == start:
            spans[-1] = (spans[-1][0], end)
        else:
            spans.append((start, end))
    return spans


def exact_spans(a, b, spans):
    """Inside the differing blocks, the true bounds, byte by byte."""
    exact = []
    for start, end in spans:
        first = last = None
        for position in range(start, end + 1):
            if a[position] != b[position]:
                if first is None:
                    first = position
                last = position
        if first is not None:
            exact.append((first, last))
    return exact


def compare_images(a, b, grain=SECTOR):
    """The whole comparison: blocks, aligned spans, true bounds."""
    indices = differing_blocks(a, b, grain)
    aligned = merge_runs(indices, grain, limit=len(a))
    exact = exact_spans(a, b, aligned)
    return {
        "blocchi": indices,
        "grana": grain,
        "allineati": aligned,
        "esatti": exact,
        "byte_diversi": sum(f - i + 1 for i, f in exact),
        "uguali": not indices,
    }


# ---------------------------------------------------------------- struttura

def signatures(data, biggest=4000):
    """Where the known structures sit. Only the first `massimo` per signature:
    NVAR alone shows up nearly a thousand times and listing them all helps
    nobody."""
    found = {}
    for sig, key, _it, _en in SIGNATURES:
        positions = []
        position = data.find(sig)
        while position != -1 and len(positions) < biggest:
            positions.append(position)
            position = data.find(sig, position + 1)
        if positions:
            found[key] = positions
    return found


def describe(start, end, signature_map, language="it"):
    """What sits in this range, in words."""
    inside = []
    for sig, key, text_it, text_en in SIGNATURES:
        positions = signature_map.get(key, ())
        count = sum(1 for p in positions if start <= p <= end)
        if count:
            name = text_it if language == "it" else text_en
            inside.append("%s%s" % (name, " ×%d" % count if count > 1 else ""))
    return ", ".join(inside)


def coherence(data, start, end, signature_map=None):
    """Does the written region still have a sensible structure?

    This is not a formal validation of the firmware -- nobody can do that
    from outside -- but it catches the two states a failed write leaves the
    chip in: all 0xFF (erased and never rewritten) or all 0x00.
    """
    chunk = data[start:end + 1]
    results = {
        "vuoto": chunk == ERASED * len(chunk),
        "azzerato": chunk == ZERO * len(chunk),
        "byte": len(chunk),
    }
    signature_map = signature_map if signature_map is not None else signatures(data)
    results["firme"] = {key: sum(1 for p in positions if start <= p <= end)
                      for key, positions in signature_map.items()}
    results["ok"] = not results["vuoto"] and not results["azzerato"]
    return results


# ----------------------------------------------------------------- dry run

class DryRun(object):
    """The result of working out how the flash will look after the write."""

    def __init__(self):
        self.outcome = None        # bytes: l'immagine attesa
        self.md5 = None
        self.changes = []             # the (aligned) spans that change
        self.changes_exact = []
        self.outside = []              # ⚠️ spans that fall OUTSIDE the region
        self.bytes_changed = 0
        self.nothing_to_do = False
        self.error = None


def dry_run(current, source_image, region=None, md5=None):
    """Works out the image the write will produce, without writing anything.

    `current` = what is on the chip right now (the verified read)
    `source`  = the image to be written
    `region`  = (start, end) when writing a single region, None for all

    The check that matters is `fuori`: if the source image differs from the
    current one ALSO outside the chosen region, those differences will NOT be
    written. That is not an error in itself -- it is the whole reason for
    writing by region -- but it has to be said, because someone who believes
    they are transferring the whole BIOS while only part of it goes across
    needs to know.
    """
    result = DryRun()
    if len(current) != len(source_image):
        result.error = "dimensioni diverse: %d e %d" % (len(current), len(source_image))
        return result

    if region is None:
        outcome = bytes(source_image)
    else:
        start, end = region
        outcome = bytes(current[:start]) + bytes(source_image[start:end + 1]) \
            + bytes(current[end + 1:])

    result.outcome = outcome
    if md5 is not None:
        result.md5 = md5(outcome)

    indices = differing_blocks(current, outcome)
    result.changes = merge_runs(indices, SECTOR, limit=len(current))
    result.changes_exact = exact_spans(current, outcome, result.changes)
    result.bytes_changed = sum(f - i + 1 for i, f in result.changes_exact)
    result.nothing_to_do = not indices

    # what would be left out: differences between current and source outside
    # the region, which the write would not carry over
    if region is not None:
        start, end = region
        every = merge_runs(differing_blocks(current, source_image), SECTOR,
                       limit=len(current))
        result.outside = [(a, b) for a, b in every if b < start or a > end]
    return result


# --------------------------------------------------------- layout generato

def make_layout(spans, total_size, name="modificata"):
    """A flashrom layout file that isolates the given ranges.

    It covers the whole flash: flashrom accepts partial layouts too, but a
    complete one makes it obvious what is NOT being written.
    ⚠️ No comments in the file: flashrom's parser rejects them.
    """
    lines = []
    position = 0
    counter = 0
    for start, end in sorted(spans):
        if start > position:
            lines.append((position, start - 1, "skip%d" % counter))
            counter += 1
        label = name if len(spans) == 1 else "%s%d" % (name, counter)
        lines.append((start, end, label))
        counter += 1
        position = end + 1
    if position < total_size:
        lines.append((position, total_size - 1, "skip%d" % counter))
    return "".join("%08x:%08x %s\n" % (a, b, n) for a, b, n in lines)


def is_aligned(start, end, grain=SECTOR):
    return start % grain == 0 and (end + 1) % grain == 0


# ------------------------------------------------------------------ comodo

def human_size(size):
    """Dimensione a misura d'uomo."""
    for drive, threshold in (("MiB", 1024 * 1024), ("KiB", 1024)):
        if size >= threshold:
            value = size / float(threshold)
            return ("%.0f %s" if value >= 100 else "%.1f %s") % (value, drive)
    return "%d B" % size


def file_name(path):
    return os.path.basename(path) if path else ""
