"""PDF laporan tahunan (reportlab). Hanya karakter Latin-1 agar aman dengan font standar."""
from io import BytesIO

from app.services.alerts import fmt_price
from app.services.tax_report import AnnualReport


def _plain(text: str) -> str:
    return text.encode("latin-1", "replace").decode("latin-1")


def build_annual_pdf(report: AnnualReport, owner: str, demo: bool = False) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import LongTable, Paragraph, SimpleDocTemplate, Spacer, TableStyle

    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=styles["Title"], fontSize=18, alignment=0, spaceAfter=2)
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], fontSize=12, spaceBefore=12, spaceAfter=4, textColor=colors.HexColor("#4338ca"))
    small = ParagraphStyle("small", parent=styles["Normal"], fontSize=8, leading=10.5, textColor=colors.HexColor("#4b5563"))
    body = ParagraphStyle("body", parent=styles["Normal"], fontSize=9, leading=12)
    head_bg, zebra = colors.HexColor("#4f46e5"), colors.HexColor("#f3f4f6")

    def table(header, rows, widths_mm, right_cols):
        if not rows:
            return Paragraph("Tidak ada data pada periode ini.", small)
        t = LongTable([header] + rows, colWidths=[w * mm for w in widths_mm], repeatRows=1)
        style = [
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("BACKGROUND", (0, 0), (-1, 0), head_bg), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, zebra]),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d1d5db")), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ] + [("ALIGN", (c, 0), (c, -1), "RIGHT") for c in right_cols]
        t.setStyle(TableStyle(style))
        return t

    def kv(rows):
        t = LongTable([[k, v] for k, v in rows], colWidths=[90 * mm, 88 * mm])
        t.setStyle(TableStyle([
            ("FONTSIZE", (0, 0), (-1, -1), 9), ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("ALIGN", (1, 0), (1, -1), "RIGHT"), ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#e5e7eb")),
            ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        return t

    t = report.totals
    story = [
        Paragraph(f"Laporan Tahunan Portofolio {report.year}", h1),
        Paragraph(_plain(f"Stockfolio &middot; {owner} &middot; disusun {report.generated_on} &middot; posisi per {report.as_of}"), small),
        Spacer(1, 6),
    ]
    if demo:
        story += [Paragraph("<b>DATA DEMO: seluruh angka adalah simulasi, bukan data investasi nyata.</b>", body), Spacer(1, 4)]

    story += [Paragraph("Ringkasan", h2), kv([
        ("Jumlah transaksi penjualan", str(t.sales_count)),
        ("Hasil penjualan bruto", fmt_price(t.gross_sales)),
        ("Fee penjualan", fmt_price(t.sell_fees)),
        ("Hasil penjualan bersih", fmt_price(t.net_proceeds)),
        ("Harga perolehan saham yang dijual", fmt_price(t.cost_basis)),
        ("Laba/rugi terealisasi", fmt_price(t.realized_pl)),
        ("Dividen diterima", fmt_price(t.dividends)),
    ])]

    story += [Paragraph("Ringkasan per saham", h2), table(
        ["Saham", "Hasil jual bruto", "Harga perolehan", "Laba/rugi", "Dividen"],
        [[_plain(s.symbol), fmt_price(s.gross), fmt_price(s.cost_basis), fmt_price(s.realized), fmt_price(s.dividends)] for s in report.by_stock],
        [34, 36, 36, 36, 36], [1, 2, 3, 4])]

    story += [Paragraph("Rincian penjualan", h2), table(
        ["Tanggal", "Saham", "Lembar", "Nilai bruto", "Fee", "Harga perolehan", "Laba/rugi"],
        [[str(s.day), _plain(s.symbol), f"{s.quantity:,.0f}".replace(",", "."), fmt_price(s.gross), fmt_price(s.fee),
          fmt_price(s.cost_basis), fmt_price(s.realized)] for s in report.sales],
        [20, 26, 18, 28, 18, 32, 36], [2, 3, 4, 5, 6])]

    story += [Paragraph("Dividen diterima", h2), table(
        ["Tanggal", "Saham", "Jumlah (bersih)"],
        [[str(d.day), _plain(d.symbol), fmt_price(d.amount)] for d in report.dividends], [30, 40, 50], [2])]

    story += [Paragraph(f"Posisi per {report.as_of}", h2), table(
        ["Saham", "Lembar", "Harga perolehan", "Harga penutupan", "Nilai pasar"],
        [[_plain(p.symbol), f"{p.quantity:,.0f}".replace(",", "."), fmt_price(p.total_cost),
          fmt_price(p.price) if p.price is not None else "-", fmt_price(p.market_value) if p.market_value is not None else "-"]
         for p in report.positions], [28, 26, 38, 38, 48], [1, 2, 3, 4])]

    story += [Paragraph("Catatan penting", h2)] + [Paragraph(_plain("- " + n), small) for n in report.notes]

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(colors.HexColor("#6b7280"))
        canvas.drawString(16 * mm, 9 * mm, f"Stockfolio - Laporan Tahunan {report.year}" + (" (DEMO)" if demo else ""))
        canvas.drawRightString(A4[0] - 16 * mm, 9 * mm, f"Halaman {doc.page}")
        canvas.restoreState()

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm, topMargin=16 * mm,
                            bottomMargin=16 * mm, title=f"Laporan Tahunan {report.year}", author="Stockfolio")
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buf.getvalue()
