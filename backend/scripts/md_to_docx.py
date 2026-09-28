"""
md_to_docx.py
=============
Lightweight Markdown -> DOCX converter tuned for the AquaWatch manuscript.
Reads a .md file (single source of truth) and renders headings, paragraphs,
bold/italic/code inline spans, blockquotes, bullet/numbered lists, pipe tables,
and image embeds (resolved relative to the .md file).

Usage:
  python scripts/md_to_docx.py <input.md> <output.docx>
"""
import os
import re
import sys
from docx import Document
from docx.shared import Pt, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH

INLINE = re.compile(r'(\*\*.+?\*\*|`.+?`|\*.+?\*)')
IMG = re.compile(r'^!\[(.*?)\]\((.*?)\)\s*$')


def add_runs(par, text):
    for part in INLINE.split(text):
        if not part:
            continue
        if part.startswith("**") and part.endswith("**"):
            par.add_run(part[2:-2]).bold = True
        elif part.startswith("`") and part.endswith("`"):
            r = par.add_run(part[1:-1]); r.font.name = "Consolas"; r.font.size = Pt(9)
        elif part.startswith("*") and part.endswith("*"):
            par.add_run(part[1:-1]).italic = True
        else:
            par.add_run(part)


def main():
    src, out = sys.argv[1], sys.argv[2]
    md_dir = os.path.dirname(os.path.abspath(src))
    lines = open(src, encoding="utf-8").read().splitlines()

    doc = Document()
    doc.styles["Normal"].font.name = "Times New Roman"
    doc.styles["Normal"].font.size = Pt(10)

    front = True   # centre title/authors until first "## "
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            i += 1; continue

        # image
        m = IMG.match(stripped)
        if m:
            path = os.path.normpath(os.path.join(md_dir, m.group(2)))
            if os.path.exists(path):
                doc.add_picture(path, width=Inches(6.0))
                doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
            i += 1; continue

        # horizontal rule
        if stripped == "---":
            i += 1; continue

        # headings
        if stripped.startswith("# "):
            p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            r = p.add_run(stripped[2:]); r.bold = True; r.font.size = Pt(15)
            i += 1; continue
        if stripped.startswith("## "):
            front = False
            doc.add_heading(stripped[3:], level=1); i += 1; continue
        if stripped.startswith("### "):
            doc.add_heading(stripped[4:], level=2); i += 1; continue

        # blockquote
        if stripped.startswith(">"):
            p = doc.add_paragraph()
            txt = stripped.lstrip(">").strip()
            # render inline but force italic look via a leading style
            add_runs(p, txt)
            for r in p.runs:
                r.italic = True
            i += 1; continue

        # table block
        if stripped.startswith("|"):
            block = []
            while i < n and lines[i].strip().startswith("|"):
                block.append(lines[i].strip()); i += 1
            rows = []
            for r in block:
                if re.match(r'^\|[\s:\-\|]+\|?$', r):  # separator row
                    continue
                cells = [c.strip() for c in r.strip().strip("|").split("|")]
                rows.append(cells)
            if rows:
                ncol = len(rows[0])
                tbl = doc.add_table(rows=0, cols=ncol)
                tbl.style = "Light Grid Accent 1"
                for ridx, cells in enumerate(rows):
                    cs = tbl.add_row().cells
                    for c in range(ncol):
                        cell = cs[c]; cell.text = ""
                        run = cell.paragraphs[0].add_run(cells[c] if c < len(cells) else "")
                        if ridx == 0:
                            run.bold = True
            continue

        # bullet list
        if stripped.startswith("- "):
            p = doc.add_paragraph(style="List Bullet"); add_runs(p, stripped[2:]); i += 1; continue
        # numbered list
        mnum = re.match(r'^(\d+)\.\s+(.*)$', stripped)
        if mnum:
            p = doc.add_paragraph(style="List Number"); add_runs(p, mnum.group(2)); i += 1; continue

        # normal paragraph
        p = doc.add_paragraph()
        if front:
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        add_runs(p, stripped)
        i += 1

    doc.save(out)
    print(f"Wrote {out}  ({os.path.getsize(out)} bytes)")


if __name__ == "__main__":
    main()
