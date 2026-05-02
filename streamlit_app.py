import io
import requests
from datetime import date

import streamlit as st
import pandas as pd
from PIL import Image as PILImage

from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import Table, TableStyle
from reportlab.lib.utils import ImageReader

# ----------------------------
# Page config
# ----------------------------
st.set_page_config(page_title="MAKK Invoice Generator", layout="wide")

# ----------------------------
# Company config
# ----------------------------
COMPANY_NAME = "MAKK CROSS BORDER SOLUTIONS LTD."
COMPANY_ADDR = "14278 VALLEY BLVD UNIT A CITY OF INDUSTRY CA 91746"
COMPANY_PHONE = "626-601-6131"
PAYABLE_NOTE = "MAKE ALL CHECKS PAYABLE TO MAKK CROSS BORDER SOLUTIONS LTD."
THANK_YOU = "Thank you for your business!"
LOGO_URL = "https://raw.githubusercontent.com/emikuo17/shipwithbtr/main/logo.jpg"

# ----------------------------
# Payment info
# ----------------------------
PAYMENT_INFO = [
    ("BUSINESS NAME", "MAKK CROSS BORDER SOLUTIONS LTD."),
    ("ACCOUNT NUMBER", "157536489329"),
    ("ACH ROUTING NUMBER", "122235821"),
    ("BANK NAME", "US BANK"),
    ("SWIFT CODE", "USBKUS44IMT"),
    ("BANK ADDRESS", "17501 Colima Rd Suite A, City of Industry, CA 91748"),
    ("BANK PHONE NUMBER", "(626) 923-5259"),
    ("ZELLE", "626-601-6131 (MAKK CROSS BORDER SOLUTIONS LTD)"),
]

# ----------------------------
# Customer directory
# ----------------------------
CUSTOMERS = {
    "-- Select a customer --": {
        "customer_id": "", "receiver": "", "phone": "", "address": ""
    },
    "Falcon01 — Falcon Logistics Global Inc.": {
        "customer_id": "Falcon01",
        "receiver": "FALCON LOGISTICS GLOBAL INC.",
        "phone": "",
        "address": "667 BREA CANYON RD., STE 20B WALNUT, CA 91789",
    },
    "Baixin 01 — Shenzhen Baixin International Logistics": {
        "customer_id": "Baixin 01",
        "receiver": "Shenzhen Baixin International Logistics Co., Ltd. Huangshan Branch",
        "phone": "",
        "address": "",
    },
    "Paradigm01 — Richard Hercoson": {
        "customer_id": "Paradigm01",
        "receiver": "Richard Hercoson",
        "phone": "",
        "address": "",
    },
    "DalnoMo LLC": {
        "customer_id": "DalnoMo LLC",
        "receiver": "DalnoMo LLC",
        "phone": "",
        "address": "",
    },
    "Advantage Transport Solution Inc.": {
        "customer_id": "Advantage transport solution inc",
        "receiver": "Advantage transport solution inc",
        "phone": "",
        "address": "",
    },
}

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
# Init session state
# ----------------------------
if "items_df" not in st.session_state:
    st.session_state.items_df = pd.DataFrame(
        [{"Qty": 1, "Description": "", "Weight": "", "Unit": "LB", "Line Total (USD)": 0.0}]
    )
if "selected_customer" not in st.session_state:
    st.session_state.selected_customer = "-- Select a customer --"

# ----------------------------
# UI
# ----------------------------
st.title("MAKK Invoice Generator")

st.subheader("Customer")
selected = st.selectbox(
    "Select existing customer (or fill manually below)",
    options=list(CUSTOMERS.keys()),
    index=list(CUSTOMERS.keys()).index(st.session_state.selected_customer),
    key="customer_dropdown",
)
st.session_state.selected_customer = selected
cust = CUSTOMERS[selected]

st.divider()

col1, col2 = st.columns(2)
with col1:
    inv_date = st.date_input("Date", value=date.today())
    receiver = st.text_input("To (Receiver name / Company)", value=cust["receiver"])
with col2:
    invoice_no = st.text_input("Invoice #", value="")
    customer_id = st.text_input("Customer ID", value=cust["customer_id"])

phone = st.text_input("Phone", value=cust["phone"])
address = st.text_area("Address", value=cust["address"], height=80)

st.subheader("Line Items")

btn_col1, btn_col2, _ = st.columns([1, 1, 3])
with btn_col1:
    if st.button("➕ Add line item"):
        base = st.session_state.items_df.copy()
        editor_state = st.session_state.get("items_editor", {})
        for idx, changes in editor_state.get("edited_rows", {}).items():
            for col, val in changes.items():
                base.at[idx, col] = val
        st.session_state.items_df = pd.concat(
            [base, pd.DataFrame([{"Qty": 1, "Description": "", "Weight": "", "Unit": "LB", "Line Total (USD)": 0.0}])],
            ignore_index=True
        )

with btn_col2:
    if st.button("🗑️ Remove last item"):
        if len(st.session_state.items_df) > 1:
            st.session_state.items_df = st.session_state.items_df.iloc[:-1].reset_index(drop=True)

edited_df = st.data_editor(
    st.session_state.items_df,
    use_container_width=True,
    num_rows="fixed",
    column_config={
        "Qty": st.column_config.NumberColumn("Qty", min_value=0, step=1, format="%d", width="small"),
        "Description": st.column_config.TextColumn("Description", width="large"),
        "Weight": st.column_config.TextColumn("Weight", width="small"),
        "Unit": st.column_config.SelectboxColumn("Unit", options=["LB", "KG", "NA"], width="small"),
        "Line Total (USD)": st.column_config.NumberColumn("Line Total (USD)", min_value=0.0, step=0.01, format="%.2f", width="medium"),
    },
    hide_index=True,
    key="items_editor",
)

items_df = edited_df.copy()
items_df["Description"] = items_df["Description"].map(safe_str)
items_df["Weight"] = items_df["Weight"].map(safe_str)
items_df["Unit"] = items_df["Unit"].map(safe_str)
items_df["Line Total (USD)"] = items_df["Line Total (USD)"].map(safe_float)

subtotal = float(items_df["Line Total (USD)"].sum())
sales_tax = st.number_input("Sales Tax (USD)", min_value=0.0, step=1.0, value=0.0)
total = round(subtotal + float(sales_tax), 2)

st.markdown(f"**Subtotal: {money(subtotal)}**")
st.markdown(f"**Total: {money(total)}**")

st.divider()
note_default = f"{PAYABLE_NOTE}\n{THANK_YOU}"
note = st.text_area("Note (shown on invoice)", value=note_default, height=80)

# ----------------------------
# PDF generation
# ----------------------------
def build_pdf() -> io.BytesIO:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=LETTER)
    w, h = LETTER

    margin_x = 0.65 * inch
    margin_r = w - 0.65 * inch
    top_y = h - 0.55 * inch

    # Fetch logo once
    image_bytes = None
    try:
        response = requests.get(LOGO_URL, timeout=5)
        response.raise_for_status()
        image_bytes = response.content
    except Exception:
        pass

    # ── Logo ──
    if image_bytes:
        try:
            pil_img = PILImage.open(io.BytesIO(image_bytes))
            img_w, img_h = pil_img.size
            aspect = img_h / img_w
            logo_display_w = 1.3 * inch
            logo_display_h = logo_display_w * aspect
            logo_buf = io.BytesIO(image_bytes)
            c.drawImage(ImageReader(logo_buf), margin_x, top_y - logo_display_h,
                        width=logo_display_w, height=logo_display_h, mask="auto")
        except Exception:
            pass

    # ── INVOICE title ──
    c.setFont("Helvetica", 36)
    c.setFillColor(colors.HexColor("#4A6FA5"))
    c.drawCentredString(w / 2, top_y - 0.5 * inch, "INVOICE")
    c.setFillColor(colors.black)

    # ── Horizontal rule ──
    rule_y = top_y - 0.75 * inch
    c.setStrokeColor(colors.HexColor("#4A6FA5"))
    c.setLineWidth(1.5)
    c.line(margin_x, rule_y, margin_r, rule_y)
    c.setLineWidth(1)
    c.setStrokeColor(colors.black)

    # ── Meta block ──
    meta_y = rule_y - 0.28 * inch

    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(colors.HexColor("#4A6FA5"))
    c.drawString(margin_x, meta_y, "DATE:")
    c.setFillColor(colors.black)
    c.setFont("Helvetica", 9)
    c.drawString(margin_x, meta_y - 0.17 * inch, inv_date.strftime("%m/%d/%y"))

    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(colors.HexColor("#4A6FA5"))
    c.drawString(margin_x, meta_y - 0.38 * inch, "INVOICE #")
    c.setFillColor(colors.black)
    c.setFont("Helvetica", 9)
    c.drawString(margin_x, meta_y - 0.55 * inch, safe_str(invoice_no))

    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(colors.HexColor("#4A6FA5"))
    c.drawString(margin_x, meta_y - 0.76 * inch, "CUSTOMER ID:")
    c.setFillColor(colors.black)
    c.setFont("Helvetica", 9)
    c.drawString(margin_x, meta_y - 0.93 * inch, safe_str(customer_id))

    # ── TO block ──
    to_x = w / 2 + 0.5 * inch
    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(colors.HexColor("#4A6FA5"))
    c.drawString(to_x, meta_y, "TO:")
    c.setFillColor(colors.black)
    c.setFont("Helvetica", 9)
    to_y = meta_y - 0.17 * inch
    if receiver.strip():
        words = receiver.strip().split()
        line = ""
        for word in words:
            test = (line + " " + word).strip()
            if c.stringWidth(test, "Helvetica", 9) > (margin_r - to_x):
                c.drawRightString(margin_r, to_y, line)
                to_y -= 0.17 * inch
                line = word
            else:
                line = test
        if line:
            c.drawRightString(margin_r, to_y, line)
            to_y -= 0.17 * inch
    if phone.strip():
        c.drawRightString(margin_r, to_y, phone); to_y -= 0.17 * inch
    if address.strip():
        for addr_line in address.split("\n"):
            if addr_line.strip():
                c.drawRightString(margin_r, to_y, addr_line.strip())
                to_y -= 0.17 * inch

    # ── Line items table ──
    table_top = meta_y - 1.15 * inch
    table_w = margin_r - margin_x
    col_widths = [table_w * 0.07, table_w * 0.53, table_w * 0.20, table_w * 0.20]

    data = [["QTY", "DESCRIPTION", "WEIGHT", "LINE\nTOTAL(USD)"]]
    for _, r in items_df.iterrows():
        qty_val = safe_float(r["Qty"])
        qty = str(int(qty_val)) if qty_val > 0 else ""
        desc = safe_str(r["Description"]).strip()
        wt = safe_str(r["Weight"]).strip()
        unit = safe_str(r["Unit"]).strip()
        wt_display = "NA" if unit == "NA" else (f"{wt} {unit}".strip() if wt else "")
        amt = safe_float(r["Line Total (USD)"])
        amt_str = money(amt) if amt > 0 else ""
        data.append([qty, desc, wt_display, amt_str])

    data.append(["", "", "Subtotal", money(subtotal)])
    data.append(["", "", "Sales Tax", money(float(sales_tax))])
    data.append(["", "", "Total", money(total)])

    n_items = len(items_df)
    n_rows = len(data)

    tbl = Table(data, colWidths=col_widths, repeatRows=1)
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F2F2F2")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("VALIGN", (0, 0), (-1, 0), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, 0), 6),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
        ("GRID", (0, 0), (-1, n_items), 0.5, colors.HexColor("#CCCCCC")),
        ("FONTNAME", (0, 1), (-1, n_items), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, n_items), 9),
        ("ALIGN", (0, 1), (0, n_items), "CENTER"),
        ("ALIGN", (2, 1), (2, n_items), "CENTER"),
        ("ALIGN", (3, 1), (3, n_items), "RIGHT"),
        ("VALIGN", (0, 1), (-1, n_items), "MIDDLE"),
        ("TOPPADDING", (0, 1), (-1, n_items), 5),
        ("BOTTOMPADDING", (0, 1), (-1, n_items), 5),
        ("FONTNAME", (0, n_items + 1), (-1, n_items + 2), "Helvetica"),
        ("FONTSIZE", (0, n_items + 1), (-1, n_rows - 1), 9),
        ("ALIGN", (2, n_items + 1), (3, n_rows - 1), "RIGHT"),
        ("TOPPADDING", (0, n_items + 1), (-1, n_rows - 1), 4),
        ("BOTTOMPADDING", (0, n_items + 1), (-1, n_rows - 1), 4),
        ("LINEABOVE", (2, n_items + 1), (3, n_items + 1), 0.5, colors.HexColor("#CCCCCC")),
        ("FONTNAME", (2, n_rows - 1), (3, n_rows - 1), "Helvetica-Bold"),
        ("FONTSIZE", (2, n_rows - 1), (3, n_rows - 1), 10),
        ("LINEABOVE", (2, n_rows - 1), (3, n_rows - 1), 0.5, colors.HexColor("#CCCCCC")),
        ("LINEBELOW", (2, n_rows - 1), (3, n_rows - 1), 0.5, colors.HexColor("#CCCCCC")),
    ]))

    _, table_h = tbl.wrapOn(c, table_w, h)
    tbl.drawOn(c, margin_x, table_top - table_h)

    # ── Footer note (checks payable + thank you) ──
    footer_y = table_top - table_h - 0.4 * inch
    c.setFont("Helvetica-Bold", 8)
    c.setFillColor(colors.HexColor("#4A6FA5"))
    c.drawCentredString(w / 2, footer_y, PAYABLE_NOTE)
    c.setFont("Helvetica", 8)
    c.setFillColor(colors.black)
    c.drawCentredString(w / 2, footer_y - 0.18 * inch, THANK_YOU)

    # ── Payment Information block (in the blank space) ──
    pay_y = footer_y - 0.55 * inch

    # Section title
    c.setFont("Helvetica-Bold", 11)
    c.setFillColor(colors.HexColor("#4A6FA5"))
    c.drawString(margin_x, pay_y, "PAYMENT INFORMATION")
    pay_y -= 0.08 * inch

    # Teal underline
    c.setStrokeColor(colors.HexColor("#2E8B8B"))
    c.setLineWidth(1)
    c.line(margin_x, pay_y, margin_r, pay_y)
    pay_y -= 0.25 * inch
    c.setStrokeColor(colors.black)

    # Payment rows
    for label, value in PAYMENT_INFO:
        c.setFont("Helvetica-Bold", 8.5)
        c.setFillColor(colors.HexColor("#2C3E6B"))
        label_str = f"{label}: "
        label_w = c.stringWidth(label_str, "Helvetica-Bold", 8.5)
        c.drawString(margin_x, pay_y, label_str)
        c.setFont("Helvetica", 8.5)
        c.drawString(margin_x + label_w, pay_y, value)
        pay_y -= 0.23 * inch

    # ── Bottom company block ──
    bottom_y = 0.55 * inch
    c.setStrokeColor(colors.HexColor("#4A6FA5"))
    c.setLineWidth(1)
    c.line(margin_x, bottom_y + 0.32 * inch, margin_r, bottom_y + 0.32 * inch)
    c.setFont("Helvetica-Bold", 8)
    c.setFillColor(colors.HexColor("#4A6FA5"))
    c.drawCentredString(w / 2, bottom_y + 0.15 * inch, COMPANY_NAME)
    c.setFont("Helvetica", 8)
    c.setFillColor(colors.black)
    c.drawCentredString(w / 2, bottom_y, f"{COMPANY_ADDR}  |  {COMPANY_PHONE}")

    c.showPage()
    c.save()
    buf.seek(0)
    return buf

st.download_button(
    "⬇️ Download PDF",
    data=build_pdf(),
    file_name=f"MAKK_Invoice_{invoice_no or 'draft'}.pdf",
    mime="application/pdf",
)
