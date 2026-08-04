"""
report_builder.py — STEP 4 of the pipeline: assemble the finished PDF.

ONE JOB: take the narrative sections (from the LLM) and the chart PNGs (from
matplotlib) and lay them out as a single finished document.

The key thing this step demonstrates: by the time this function returns, the report
is DONE. The charts are already baked into the PDF as images. Nothing about
charting is left for a frontend to do later — there is no client-side rendering
step, no chart config shipped to a browser, no "the app draws it". The backend
produced a complete artifact.

Every report follows the same eight sections in the same order, whatever the type:

  1. Opening Snapshot     5. Reflection Questions
  2. Highlights           6. Recognition Received
  3. Work That Doesn't    7. Data Visualization
     Usually Get Counted  8. Forward Frame
  4. Strengths & Growth

Uses reportlab's "platypus" layer, which flows a list of elements down the page and
breaks pages automatically — so we never have to think about coordinates.
"""

import os

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    HRFlowable,
    Image,
    KeepTogether,
    ListFlowable,
    ListItem,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
)

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")

# Same ink colours the charts use, so the document reads as one piece.
INK = colors.HexColor("#0b0b0b")
INK_SECONDARY = colors.HexColor("#52514e")
INK_MUTED = colors.HexColor("#898781")
RULE = colors.HexColor("#c3c2b7")
ACCENT = colors.HexColor("#2a78d6")

PAGE_WIDTH, _ = LETTER
CONTENT_WIDTH = PAGE_WIDTH - 2 * inch  # 1" margins each side => 6.5" of usable width


def _styles():
    """Build the paragraph styles once, up front."""
    base = getSampleStyleSheet()

    return {
        "title": ParagraphStyle(
            "NotchTitle", parent=base["Title"],
            fontName="Helvetica-Bold", fontSize=21, leading=25,
            textColor=INK, alignment=TA_LEFT, spaceAfter=2,
        ),
        "subtitle": ParagraphStyle(
            "NotchSubtitle", parent=base["Normal"],
            fontName="Helvetica", fontSize=10.5, leading=14,
            textColor=INK_SECONDARY, spaceAfter=2,
        ),
        "meta": ParagraphStyle(
            "NotchMeta", parent=base["Normal"],
            fontName="Helvetica", fontSize=9, leading=12,
            textColor=INK_MUTED, spaceAfter=10,
        ),
        "section": ParagraphStyle(
            "NotchSection", parent=base["Heading2"],
            fontName="Helvetica-Bold", fontSize=13, leading=16,
            textColor=INK, spaceBefore=16, spaceAfter=6,
        ),
        "subsection": ParagraphStyle(
            "NotchSubsection", parent=base["Heading3"],
            fontName="Helvetica-Bold", fontSize=10.5, leading=13,
            textColor=ACCENT, spaceBefore=9, spaceAfter=3,
        ),
        "body": ParagraphStyle(
            "NotchBody", parent=base["Normal"],
            fontName="Helvetica", fontSize=10, leading=14.5,
            textColor=INK, spaceAfter=6,
        ),
        "bullet": ParagraphStyle(
            "NotchBullet", parent=base["Normal"],
            fontName="Helvetica", fontSize=10, leading=14.5,
            textColor=INK, spaceAfter=4,
        ),
        "stat": ParagraphStyle(
            "NotchStat", parent=base["Normal"],
            fontName="Helvetica-Oblique", fontSize=9.5, leading=13,
            textColor=INK_SECONDARY, spaceBefore=4, spaceAfter=4,
        ),
        "caption": ParagraphStyle(
            "NotchCaption", parent=base["Normal"],
            fontName="Helvetica", fontSize=8.5, leading=11,
            textColor=INK_MUTED, spaceBefore=3, spaceAfter=12,
        ),
    }


def _escape(text):
    """
    reportlab's Paragraph parses a mini-HTML dialect, so raw & < > in the model's
    prose would break the parser. Escape them.
    """
    if text is None:
        return ""
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _scaled_image(path, max_width=CONTENT_WIDTH):
    """
    Embed a PNG at its natural aspect ratio, capped to the content width.

    matplotlib writes at 150 DPI, so we divide the pixel dimensions back down to
    get real inches before scaling.
    """
    reader = ImageReader(path)
    px_w, px_h = reader.getSize()
    width = min(max_width, px_w / 150.0 * inch)
    height = width * (px_h / px_w)
    return Image(path, width=width, height=height)


def _bullets(items, style):
    """A plain bulleted list of already-escaped strings."""
    return ListFlowable(
        [ListItem(Paragraph(item, style), leftIndent=14) for item in items],
        bulletType="bullet", start="•", bulletColor=INK_MUTED,
        bulletFontName="Helvetica", bulletFontSize=10, bulletOffsetY=-1,
        leftIndent=16, spaceBefore=2, spaceAfter=6,
    )


def build_pdf(
    output_path,
    title,
    subtitle,
    period_label,
    user,
    content,
    stat_line,
    recognition,
    charts,
):
    """
    Write the finished PDF.

    Arguments:
      content      the LLM's structured narrative (the dict from llm.py)
      stat_line    a Python-computed string, e.g. "5 entries · dominant themes: ..."
      recognition  the acknowledged_by entries, straight from the database
      charts       list of (png_path, caption) tuples, already rendered

    Note that `stat_line`, `recognition` and the chart numbers all came from
    Python, not the model. The model supplied the prose.
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    s = _styles()

    doc = SimpleDocTemplate(
        output_path, pagesize=LETTER,
        leftMargin=inch, rightMargin=inch, topMargin=0.85 * inch, bottomMargin=0.85 * inch,
        title=title, author="Notch",
    )

    story = []

    # ---- Header ----------------------------------------------------------
    story.append(Paragraph(_escape(title), s["title"]))
    story.append(Paragraph(_escape(subtitle), s["subtitle"]))
    story.append(Paragraph(
        f"{_escape(user['name'])} · {_escape(user['role'])} · {_escape(period_label)}",
        s["meta"],
    ))
    story.append(HRFlowable(width="100%", thickness=0.7, color=RULE, spaceAfter=2))

    # ---- 1. Opening Snapshot --------------------------------------------
    story.append(Paragraph("1. Opening Snapshot", s["section"]))
    story.append(Paragraph(_escape(content["opening_snapshot"]), s["body"]))
    story.append(Paragraph(_escape(stat_line), s["stat"]))

    # ---- 2. Highlights ---------------------------------------------------
    story.append(Paragraph("2. Highlights", s["section"]))
    for group in content.get("highlights", []):
        block = [Paragraph(_escape(group.get("theme", "")), s["subsection"])]
        for item in group.get("items", []):
            line = _escape(item.get("what_happened", ""))
            if item.get("impact"):
                line += f" <font color='#52514e'>— {_escape(item['impact'])}</font>"
            if item.get("date"):
                line += f" <font color='#898781'>({_escape(item['date'])})</font>"
            block.append(Paragraph(line, s["bullet"]))
        # KeepTogether stops a theme heading from getting orphaned at a page break.
        story.append(KeepTogether(block))

    # ---- 3. Work That Doesn't Usually Get Counted ------------------------
    story.append(Paragraph("3. Work That Doesn't Usually Get Counted", s["section"]))
    for item in content.get("uncounted_work", []):
        line = f"<b>{_escape(item.get('what', ''))}</b>"
        if item.get("date"):
            line += f" <font color='#898781'>({_escape(item['date'])})</font>"
        story.append(Paragraph(line, s["bullet"]))
        story.append(Paragraph(_escape(item.get("why_it_matters", "")), s["body"]))

    # ---- 4. Strengths & Growth -------------------------------------------
    # Note the framing: "What's working" comes first and "Building on that" is
    # explicitly an extension of it. There is deliberately no "weaknesses" heading
    # here, and no field in the schema that could produce one.
    story.append(Paragraph("4. Strengths &amp; Growth", s["section"]))
    story.append(Paragraph("What's working", s["subsection"]))
    story.append(_bullets([_escape(x) for x in content.get("strengths", [])], s["bullet"]))
    if content.get("building_on"):
        story.append(Paragraph("Building on that", s["subsection"]))
        story.append(_bullets([_escape(x) for x in content["building_on"]], s["bullet"]))

    # ---- 5. Reflection Questions -----------------------------------------
    story.append(Paragraph("5. Reflection Questions", s["section"]))
    story.append(_bullets(
        [_escape(q) for q in content.get("reflection_questions", [])], s["bullet"]
    ))

    # ---- 6. Recognition Received -----------------------------------------
    # Pure database filter — every entry with a populated acknowledged_by. No model
    # involved; this is a fact already recorded on the row.
    story.append(Paragraph("6. Recognition Received", s["section"]))
    if recognition:
        for entry in recognition:
            line = (
                f"<b>{_escape(entry['acknowledged_by'])}</b> "
                f"<font color='#898781'>({_escape(entry['date_display'])})</font><br/>"
                f"{_escape(entry['impact_note'] or entry['raw_text'])}"
            )
            story.append(Paragraph(line, s["bullet"]))
    else:
        story.append(Paragraph(
            "No entries in this period recorded recognition from someone else.",
            s["body"],
        ))

    # ---- 7. Data Visualization -------------------------------------------
    # Charts are embedded as images that were rendered before this function ran.
    # The PDF is complete on save — nothing is deferred to a client.
    story.append(Paragraph("7. Data Visualization", s["section"]))
    for path, caption in charts:
        story.append(_scaled_image(path))
        story.append(Paragraph(_escape(caption), s["caption"]))

    # ---- 8. Forward Frame ------------------------------------------------
    story.append(Paragraph("8. Forward Frame", s["section"]))
    story.append(Paragraph(_escape(content["forward_frame"]), s["body"]))

    story.append(Spacer(1, 14))
    story.append(HRFlowable(width="100%", thickness=0.7, color=RULE, spaceAfter=6))
    story.append(Paragraph(
        "Generated by Notch. Narrative written by Claude Haiku 4.5; "
        "all counts, percentages and charts computed in Python from the source entries.",
        s["caption"],
    ))

    doc.build(story)
    return output_path
