import io
from datetime import date

import streamlit as st
import pandas as pd

from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import Table, TableStyle

# ----------------------------
# Page config
# ----------------------------
st.set_page_config(page_title="MAKK Invoice Generator", layout="centered")

# ----------------------------
# Company config
# ----------------------------
COMPANY_NAME = "MAKK CROSS BORDER SOLUTIONS LTD."
COMPANY_ADDR = "14278 Valley Blvd.\nLa Puente, CA 91746"
COMPANY_PHONE = "626-601-613"
PAYABLE_NOTE = "Make all checks payable to MAKK CROSS BORDER SOLUTIONS LTD."
THANK_YOU = "Thank you for your business!"
LOGO_PATH = "assets/logo.png"  # optional

# ----------------------------
# Helpers
# ----------------------------
def money(x: float) -> str:
    return f"${x:,.2f}"

def safe_float(v) -> float:
    try:
        if v is None or v == "":
            return 0.0
        return float(v)
    except Exception:
        return 0.0

def safe_str(v) -> str:
    return "" if v is None else str(v)

# ----------------------------
# Init session df
# ----------------------------
if "items_df" not in st.session_state:
    st.session_state.items_df = pd.DataFrame(
        [{"Description": "", "Weight": 0.0, "Amount": 0.0}]
    )

# ----------------------------
# UI
# ----------------------------
st.title("MAKK Invoice Generator")

col1, col2 = st.columns(2)
with col1:
    inv_date = st.date_input("Date", value=date.today())
    invoice_no = st.text_input("Invoice # (or Customer ID)", value="")
with col2:
    receiver = st.text_input("To (Receiver name / Company)", value="")
    phone = st.text_input("Phone", value="")

address = st.text_area("Address", value="", height=100)

st.subheader("Line Items")

# Buttons to add/remove rows (so you ALWAYS have a way to add another item)
btn_col1, btn_col2, _ = st.columns([1, 1, 3])
with btn_col1:
    if st.button("➕ Add line item"):
        st.session_state.items_df = pd.concat(
            [st.session_state.items_df, pd.DataFrame([{"Description": "", "Weight": 0.0, "Amount": 0.0}])],
            ignore_index=True
        )

with btn_col2:
    if st.button("🗑️ Remove last item"):
        if len(st.session_state.items_df) > 1:
            st.session_state.items_df = st.session_state.items_df.iloc[:-1].reset_index(drop=True)

# Editable table
edited_df = st.data_editor(
    st.session_state.items_df,
    use_container_width=True,
    num_rows="fixed",  # we control rows via buttons (more reliable)
    column_config={
        "Description": st.column_config.TextColumn("Description", width="large"),
        "Weight": st.column_config.NumberColumn("Total Weight", min_value=0.0, step=0.1, format="%.2f"),
        "Amount": st.column_config.NumberColumn("Line Total (USD)", min_value=0.0, step=1.0, format="%.2f"),
    },
    hide_index=True,
    key="items_editor",
)

# Normalize + store back
items_df = edited_df.copy()
items_df["Description"] = items_df["Description"].map(safe_str)
items_df["Weight"] = items_df["Weight"].map(safe_float)
items_df["Amount"] = items_df["Amount"].map(safe_float)
st.session_state.items_df = items_df

# ✅ Subtotal auto from Amount column
subtotal = float(items_df["Amount"].sum())

# Sales tax manual
sales_tax = st.number_input("Sales Tax (USD) - manual", min_value=0.0, step=1.0, value=0.0)

# Total auto
total = round(subtotal + float(sales_tax), 2)

st.markdown(f"**Subtotal (auto): {money(subtotal)}**")
st.markdown(f"**Total (auto): {money(total)}**")

st.divider()

note_default = f"Note: {PAYABLE_NOTE}\n{THANK_YOU}"
note = st.text_area("Note (shown on invoice)", value=note_default, height=80)

# ----------------------------
# PDF generation
# ----------------------------
def build_pdf() -> io.BytesIO:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=LETTER)
    w, h = LETTER

    margin_x = 0.75 * inch
    top_y = h - 0.75 * inch

    # Logo (optional)
    try:
        c.drawImage(LOGO_PATH, margin_x, top_y - 1.05 * inch, width=1.0 * inch, height=1.0 * inch, mask="auto")
    except Exception:
        pass

    # Company block (CENTER)
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(w / 2, top_y, COMPANY_NAME)

    c.setFont("Helvetica", 10)
    y_company = top_y - 0.22 * inch
    for line in COMPANY_ADDR.split("\n"):
        c.drawCentredString(w / 2, y_company, line)
        y_company -= 0.18 * inch
    c.drawCentredString(w / 2, y_company, COMPANY_PHONE)

    # Invoice meta (RIGHT)
    right_x = w - margin_x
    meta_y = top_y - 0.10 * inch

    c.setFont("Helvetica-Bold", 18)
    c.drawRightString(right_x, meta_y - 0.25 * inch, "INVOICE")

    c.setFont("Helvetica-Bold", 10)
    c.drawRightString(right_x, meta_y - 0.55 * inch, "Invoice #")
    c.setFont("Helvetica", 10)
    c.drawRightString(right_x, meta_y - 0.71 * inch, safe_str(invoice_no))

    c.setFont("Helvetica-Bold", 10)
    c.drawRightString(right_x, meta_y - 0.91 * inch, "Date")
    c.setFont("Helvetica", 10)
    c.drawRightString(right_x, meta_y - 1.07 * inch, inv_date.strftime("%Y/%m/%d"))

    # BILL TO (LEFT)
    y = top_y - 1.55 * inch
    c.setFont("Helvetica-Bold", 11)
    c.drawString(margin_x, y, "BILL TO")
    y -= 0.22 * inch

    c.setFont("Helvetica", 10)
    if receiver.strip():
        c.drawString(margin_x, y, receiver); y -= 0.18 * inch
    if phone.strip():
        c.drawString(margin_x, y, phone); y -= 0.18 * inch
    if address.strip():
        for line in address.split("\n"):
            c.drawString(margin_x, y, line)
            y -= 0.18 * inch

    # Items table
    y_table_top = y - 0.25 * inch
    data = [["DESCRIPTION", "WEIGHT", "AMOUNT"]]
    for _, r in items_df.iterrows():
        desc = (r["Description"].strip() or "-")
        wt = float(r["Weight"])
        amt = float(r["Amount"])
        data.append([desc, f"{wt:,.2f}", money(amt)])

    table_w = w - 2 * margin_x
    col_widths = [table_w * 0.64, table_w * 0.18, table_w * 0.18]
    tbl = Table(data, colWidths=col_widths)
    tbl.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 10),
        ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
        ("LINEBELOW", (0, 0), (-1, 0), 1, colors.black),

        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, -1), 10),

        ("ALIGN", (1, 1), (2, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
    ]))

    table_x = margin_x
    table_y = y_table_top - 0.2 * inch
    _, table_h = tbl.wrapOn(c, table_w, h)
    tbl.drawOn(c, table_x, table_y - table_h)

    # Totals (RIGHT)
    y_totals = table_y - table_h - 0.35 * inch
    label_x = w - margin_x - 2.2 * inch
    value_x = w - margin_x

    c.setFont("Helvetica", 10)
    c.drawRightString(label_x, y_totals, "Subtotal")
    c.drawRightString(value_x, y_totals, money(subtotal))
    y_totals -= 0.22 * inch

    c.drawRightString(label_x, y_totals, "Sales Tax")
    c.drawRightString(value_x, y_totals, money(float(sales_tax)))
    y_totals -= 0.22 * inch

    c.setFont("Helvetica-Bold", 11)
    c.drawRightString(label_x, y_totals, "Total")
    c.drawRightString(value_x, y_totals, money(total))

    # Note box
    box_x = margin_x
    box_w = w - 2 * margin_x
    box_h = 0.95 * inch
    box_y = 0.85 * inch

    c.setStrokeColor(colors.black)
    c.rect(box_x, box_y, box_w, box_h, stroke=1, fill=0)

    c.setFont("Helvetica", 10)
    text = c.beginText(box_x + 0.2 * inch, box_y + box_h - 0.28 * inch)
    for line in (note or "").split("\n"):
        text.textLine(line.strip())
    c.drawText(text)

    c.showPage()
    c.save()
    buf.seek(0)
    return buf

st.download_button(
    "Download PDF",
    data=build_pdf(),
    file_name=f"MAKK_Invoice_{invoice_no or 'draft'}.pdf",
    mime="application/pdf",
)
