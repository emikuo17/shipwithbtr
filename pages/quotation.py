import io
import requests
from datetime import date, timedelta

import streamlit as st
import pandas as pd
from PIL import Image as PILImage

from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import Table, TableStyle
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# ----------------------------
# Page config
# ----------------------------
st.set_page_config(page_title="Quotation Generator", layout="wide")

# ----------------------------
# CJK font (fetched at runtime, no manual download needed)
# ----------------------------
FONT_URL = "https://github.com/justfont/open-huninn-font/releases/download/v2.1/jf-openhuninn-2.1.ttf"
FONT_NAME = "CJK"
FONT_NAME_BOLD = "CJK-Bold"  # same file mapped to both slots (font has no separate bold weight)

@st.cache_resource(show_spinner=False)
def load_cjk_font():
    try:
        resp = requests.get(FONT_URL, timeout=15)
        resp.raise_for_status()
        font_bytes = resp.content
        pdfmetrics.registerFont(TTFont(FONT_NAME, io.BytesIO(font_bytes)))
        pdfmetrics.registerFont(TTFont(FONT_NAME_BOLD, io.BytesIO(font_bytes)))
        return True
    except Exception as e:
        st.warning(f"Could not load Chinese font, falling back to Helvetica (Chinese text will not render correctly): {e}")
        return False

_font_ok = load_cjk_font()
BASE_FONT = FONT_NAME if _font_ok else "Helvetica"
BASE_FONT_BOLD = FONT_NAME_BOLD if _font_ok else "Helvetica-Bold"

# ----------------------------
# Company config (MAKK / BTR switch)
# ----------------------------
COMPANIES = {
    "MAKK": {
        "name": "MAKK CROSS-BORDER SOLUTIONS LTD.",
        "address": "14278 VALLEY BLVD UNIT A, CITY OF INDUSTRY, CA 91746, UNITED STATES",
        "phone": "626-601-6131",
        "email": "info@makkcbs.com",  # TODO: confirm real email
        "logo_url": "https://raw.githubusercontent.com/emikuo17/shipwithbtr/main/logo.jpg",
    },
    "BTR": {
        "name": "BEST TRANSPORTATION RESOLUTION",
        "address": "14278 VALLEY BLVD UNIT A, CITY OF INDUSTRY, CA 91746, UNITED STATES",
        "phone": "626-601-6131",
        "email": "info@shipwithbtr.com",  # TODO: confirm real email
        "logo_url": "https://raw.githubusercontent.com/emikuo17/shipwithbtr/main/btr_logo.jpg",  # TODO: confirm real filename
    },
}

# ----------------------------
# Customer directory (reused from invoice tool)
# ----------------------------
CUSTOMERS = {
    "-- Select a customer --": {"address": ""},
    "Falcon Logistics Global Inc.": {
        "address": "667 BREA CANYON RD., STE 20B WALNUT, CA 91789",
    },
    "Shenzhen Baixin International Logistics Co., Ltd. Huangshan Branch": {
        "address": "",
    },
    "Richard Hercoson (Paradigm01)": {
        "address": "",
    },
    "DalnoMo LLC": {
        "address": "",
    },
    "Advantage Transport Solution Inc.": {
        "address": "",
    },
}

# ----------------------------
# Helpers
# ----------------------------
def money(x: float) -> str:
    return f"{x:,.2f}"

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
        [{"Description": "", "Remark": "", "Unit": "", "Qty": 1.0, "Rate": 0.0, "Currency": "USD"}]
    )
if "selected_customer" not in st.session_state:
    st.session_state.selected_customer = "-- Select a customer --"

# ----------------------------
# UI
# ----------------------------
st.title("Quotation Generator")

st.subheader("Company")
company_choice = st.radio("Quoting as", options=list(COMPANIES.keys()), horizontal=True)
company = COMPANIES[company_choice]

st.divider()

st.subheader("Customer")
selected = st.selectbox(
    "Select existing customer (or fill manually below)",
    options=list(CUSTOMERS.keys()),
    index=list(CUSTOMERS.keys()).index(st.session_state.selected_customer),
    key="customer_dropdown",
)
st.session_state.selected_customer = selected
cust = CUSTOMERS[selected]
customer_name = st.text_input("To (Customer name)", value="" if selected.startswith("--") else selected)
customer_address = st.text_area("Customer address", value=cust["address"], height=70)

st.divider()

st.subheader("Quote Info")
col1, col2, col3 = st.columns(3)
with col1:
    quote_no = st.text_input("Quote No.", value="")
    create_date = st.date_input("Create Date", value=date.today())
    created_by = st.text_input("Created By", value="")
with col2:
    sales_person = st.text_input("Sales Person", value="")
    operation = st.text_input("Operation", value="")
    ship_mode = st.selectbox("Ship Mode", ["AIR", "SEA", "TRUCK"], index=0)
with col3:
    service_term = st.text_input("Service Term", value="AIRPORT/AIRPORT")
    incoterms = st.text_input("Incoterms", value="")
    valid_from = st.date_input("Valid From", value=date.today())
    valid_to = st.date_input("Valid To", value=date.today() + timedelta(days=7))

st.divider()

st.subheader("Cargo Info")
col1, col2 = st.columns(2)
with col1:
    commodity = st.text_input("Commodity", value="")
    cargo_type = st.text_input("Cargo Type", value="GENERAL CARGO")
    stackable = st.selectbox("Stackable", ["YES", "NO"], index=0)
    package = st.text_input("Package", value="")
with col2:
    gross_weight = st.text_input("Gross Weight", value="", placeholder="e.g. 841.26 KGS / 1,854.66 LBS")
    volume_weight = st.text_input("Volume Weight", value="", placeholder="e.g. 855.00 KGS / 5.13 CBM")
    chargeable_weight = st.text_input("Chargeable Weight", value="", placeholder="e.g. 855.00 KGS / 1,884.95 LBS")

st.divider()

st.subheader("Shipment Route")
col1, col2 = st.columns(2)
with col1:
    departure = st.text_input("Departure", value="")
    destination = st.text_input("Destination", value="")
with col2:
    final_destination = st.text_input("Final Destination", value="")
    via = st.text_input("Via", value="")
col1, col2 = st.columns(2)
with col1:
    carrier = st.text_input("Carrier", value="")
with col2:
    transit_time = st.text_input("T/T", value="")

st.divider()

st.subheader("Rate Line Items")

btn_col1, btn_col2, _ = st.columns([1, 1, 3])
with btn_col1:
    if st.button("➕ Add line item"):
        base = st.session_state.items_df.copy()
        editor_state = st.session_state.get("items_editor", {})
        for idx, changes in editor_state.get("edited_rows", {}).items():
            for col, val in changes.items():
                base.at[idx, col] = val
        st.session_state.items_df = pd.concat(
            [base, pd.DataFrame([{"Description": "", "Remark": "", "Unit": "", "Qty": 1.0, "Rate": 0.0, "Currency": "USD"}])],
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
        "Description": st.column_config.TextColumn("Description", width="large"),
        "Remark": st.column_config.TextColumn("Remark", width="medium"),
        "Unit": st.column_config.TextColumn("Unit", width="small"),
        "Qty": st.column_config.NumberColumn("QTY", min_value=0.0, step=1.0, format="%.2f", width="small"),
        "Rate": st.column_config.NumberColumn("Rate", min_value=0.0, step=0.01, format="%.2f", width="small"),
        "Currency": st.column_config.TextColumn("Cur.", width="small"),
    },
    hide_index=True,
    key="items_editor",
)

items_df = edited_df.copy()
items_df["Description"] = items_df["Description"].map(safe_str)
items_df["Remark"] = items_df["Remark"].map(safe_str)
items_df["Unit"] = items_df["Unit"].map(safe_str)
items_df["Currency"] = items_df["Currency"].map(safe_str)
items_df["Qty"] = items_df["Qty"].map(safe_float)
items_df["Rate"] = items_df["Rate"].map(safe_float)
items_df["Subtotal"] = items_df["Qty"] * items_df["Rate"]

grand_total = float(items_df["Subtotal"].sum())
st.markdown(f"**Grand Total: {money(grand_total)}**")

st.divider()
quotation_remark = st.text_area("Quotation Remark", value="", height=80)
disclaimer = st.text_area(
    "Disclaimer (footer)",
    value="ABOVE RATES ARE SUBJECT TO BE CHANGED WITHOUT PRIOR NOTICE, PLEASE VERIFY THE RATE AGAIN BEFORE MAKING BOOKING.",
    height=60,
)

# ----------------------------
# PDF generation
# ----------------------------
def build_pdf() -> io.BytesIO:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=LETTER)
    w, h = LETTER

    margin_x = 0.6 * inch
    margin_r = w - 0.6 * inch
    y = h - 0.55 * inch

    # ── Logo ──
    try:
        resp = requests.get(company["logo_url"], timeout=5)
        resp.raise_for_status()
        pil_img = PILImage.open(io.BytesIO(resp.content))
        img_w, img_h = pil_img.size
        aspect = img_h / img_w
        logo_w = 1.1 * inch
        logo_h = logo_w * aspect
        c.drawImage(ImageReader(io.BytesIO(resp.content)), margin_x, y - logo_h,
                    width=logo_w, height=logo_h, mask="auto")
    except Exception:
        logo_h = 0.5 * inch

    # ── Company header text ──
    text_x = margin_x + 1.3 * inch
    c.setFont(BASE_FONT_BOLD, 13)
    c.drawString(text_x, y - 0.15 * inch, company["name"])
    c.setFont(BASE_FONT, 8)
    c.drawString(text_x, y - 0.33 * inch, company["address"])
    c.drawString(text_x, y - 0.46 * inch, f"TEL: {company['phone']}    EMAIL: {company['email']}")

    # ── Quotation box (top right) ──
    box_w, box_h = 2.6 * inch, 0.9 * inch
    box_x, box_y = margin_r - box_w, y - box_h + 0.05 * inch
    c.setStrokeColor(colors.HexColor("#4A6FA5"))
    c.rect(box_x, box_y, box_w, box_h)
    c.setFont(BASE_FONT_BOLD, 16)
    c.setFillColor(colors.HexColor("#4A6FA5"))
    c.drawCentredString(box_x + box_w / 2, box_y + box_h - 0.35 * inch, "QUOTATION")
    c.setFont(BASE_FONT, 9)
    c.setFillColor(colors.black)
    c.drawCentredString(box_x + box_w / 2, box_y + 0.15 * inch, f"QUOTE NO: {safe_str(quote_no)}")
    c.setStrokeColor(colors.black)

    y -= 0.85 * inch
    c.setStrokeColor(colors.HexColor("#CCCCCC"))
    c.line(margin_x, y, margin_r, y)

    # ── TO block (left) / Meta block (right) ──
    y -= 0.22 * inch
    left_x = margin_x
    right_label_x = w / 2 + 0.1 * inch

    c.setFont(BASE_FONT_BOLD, 8.5)
    c.drawString(left_x, y, "TO:")
    c.setFont(BASE_FONT, 8.5)
    ty = y - 0.16 * inch
    if customer_name.strip():
        c.drawString(left_x + 0.35 * inch, y, customer_name)
    for line in customer_address.split("\n"):
        if line.strip():
            c.drawString(left_x, ty, line.strip())
            ty -= 0.16 * inch

    meta_rows = [
        ("CREATE DATE", create_date.strftime("%m-%d-%Y")),
        ("CREATED BY", created_by),
        ("SALES PERSON", sales_person),
        ("OPERATION", operation),
        ("SHIP MODE", ship_mode),
        ("SERVICE TERM", service_term),
        ("INCOTERMS", incoterms),
        ("VALID DATE", f"{valid_from.strftime('%m-%d-%Y')} ~ {valid_to.strftime('%m-%d-%Y')}"),
    ]
    my = y
    for label, val in meta_rows:
        c.setFont(BASE_FONT_BOLD, 8)
        c.drawString(right_label_x, my, f"{label}:")
        c.setFont(BASE_FONT, 8)
        c.drawString(right_label_x + 1.15 * inch, my, safe_str(val))
        my -= 0.15 * inch

    y = min(ty, my) - 0.15 * inch
    c.setStrokeColor(colors.HexColor("#CCCCCC"))
    c.line(margin_x, y, margin_r, y)

    # ── Cargo info block ──
    y -= 0.2 * inch
    cargo_rows = [
        ("COMMODITY", commodity), ("CARGO TYPE", cargo_type),
        ("STACKABLE", stackable), ("PACKAGE", package),
    ]
    cy = y
    for label, val in cargo_rows:
        c.setFont(BASE_FONT_BOLD, 8)
        c.drawString(left_x, cy, f"{label}:")
        c.setFont(BASE_FONT, 8)
        c.drawString(left_x + 1.0 * inch, cy, safe_str(val))
        cy -= 0.16 * inch

    weight_rows = [
        ("Gross Weight", gross_weight), ("Volume Weight", volume_weight),
        ("Chargeable Weight", chargeable_weight),
    ]
    wy = y
    for label, val in weight_rows:
        c.setFont(BASE_FONT_BOLD, 8)
        c.drawString(right_label_x, wy, f"{label}:")
        c.setFont(BASE_FONT, 8)
        c.drawString(right_label_x + 1.3 * inch, wy, safe_str(val))
        wy -= 0.16 * inch

    y = min(cy, wy) - 0.1 * inch
    c.setStrokeColor(colors.HexColor("#CCCCCC"))
    c.line(margin_x, y, margin_r, y)

    # ── Shipment route block ──
    y -= 0.2 * inch
    route_cols = [
        ("Departure", departure, left_x),
        ("Destination", destination, left_x + 2.0 * inch),
        ("Final Destination", final_destination, left_x + 4.0 * inch),
        ("Via", via, left_x + 5.5 * inch),
    ]
    for label, val, xpos in route_cols:
        c.setFont(BASE_FONT_BOLD, 7.5)
        c.drawString(xpos, y, label)
        c.setFont(BASE_FONT, 8.5)
        c.drawString(xpos, y - 0.15 * inch, safe_str(val))

    y -= 0.35 * inch
    c.setFont(BASE_FONT_BOLD, 7.5)
    c.drawString(left_x, y, "Carrier")
    c.setFont(BASE_FONT, 8.5)
    c.drawString(left_x, y - 0.15 * inch, safe_str(carrier))
    c.setFont(BASE_FONT_BOLD, 7.5)
    c.drawString(left_x + 2.0 * inch, y, "T/T")
    c.setFont(BASE_FONT, 8.5)
    c.drawString(left_x + 2.0 * inch, y - 0.15 * inch, safe_str(transit_time))

    y -= 0.35 * inch

    # ── Line items table ──
    table_w = margin_r - margin_x
    col_widths = [table_w * 0.28, table_w * 0.20, table_w * 0.10, table_w * 0.10,
                  table_w * 0.12, table_w * 0.08, table_w * 0.12]

    data = [["Description", "Remark", "Unit", "QTY", "Rate", "Cur.", "Subtotal"]]
    for _, r in items_df.iterrows():
        data.append([
            safe_str(r["Description"]), safe_str(r["Remark"]), safe_str(r["Unit"]),
            money(r["Qty"]) if r["Qty"] else "", money(r["Rate"]) if r["Rate"] else "",
            safe_str(r["Currency"]), money(r["Subtotal"]) if r["Subtotal"] else "",
        ])
    n_items = len(items_df)
    data.append(["", "", "", "", "", "TOTAL", money(grand_total)])
    n_rows = len(data)

    tbl = Table(data, colWidths=col_widths, repeatRows=1)
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F2F2F2")),
        ("FONTNAME", (0, 0), (-1, 0), BASE_FONT_BOLD),
        ("FONTSIZE", (0, 0), (-1, 0), 7.5),
        ("ALIGN", (0, 0), (-1, 0), "LEFT"),
        ("VALIGN", (0, 0), (-1, 0), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, 0), 5),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 5),
        ("GRID", (0, 0), (-1, n_items), 0.5, colors.HexColor("#CCCCCC")),
        ("FONTNAME", (0, 1), (-1, n_items), BASE_FONT),
        ("FONTSIZE", (0, 1), (-1, n_items), 8),
        ("ALIGN", (3, 1), (4, n_items), "RIGHT"),
        ("ALIGN", (6, 1), (6, n_items), "RIGHT"),
        ("VALIGN", (0, 1), (-1, n_items), "MIDDLE"),
        ("TOPPADDING", (0, 1), (-1, n_items), 4),
        ("BOTTOMPADDING", (0, 1), (-1, n_items), 4),
        ("FONTNAME", (5, n_rows - 1), (6, n_rows - 1), BASE_FONT_BOLD),
        ("FONTSIZE", (5, n_rows - 1), (6, n_rows - 1), 9),
        ("ALIGN", (5, n_rows - 1), (6, n_rows - 1), "RIGHT"),
        ("LINEABOVE", (0, n_rows - 1), (-1, n_rows - 1), 0.5, colors.HexColor("#CCCCCC")),
        ("TOPPADDING", (0, n_rows - 1), (-1, n_rows - 1), 5),
    ]))

    _, table_h = tbl.wrapOn(c, table_w, h)
    tbl.drawOn(c, margin_x, y - table_h)
    y = y - table_h - 0.25 * inch

    # ── Quotation remark box ──
    if quotation_remark.strip():
        c.setStrokeColor(colors.HexColor("#CCCCCC"))
        c.rect(margin_x, y - 0.6 * inch, table_w, 0.6 * inch)
        c.setFont(BASE_FONT_BOLD, 7.5)
        c.drawString(margin_x + 0.1 * inch, y - 0.2 * inch, "QUOTATION REMARK")
        c.setFont(BASE_FONT, 8)
        ry = y - 0.35 * inch
        for line in quotation_remark.split("\n"):
            if line.strip():
                c.drawString(margin_x + 2.0 * inch, ry, line.strip())
                ry -= 0.14 * inch
        y -= 0.75 * inch

    # ── Disclaimer ──
    c.setFont(BASE_FONT_BOLD, 7.5)
    for line in disclaimer.split("\n"):
        if line.strip():
            c.drawString(margin_x, y, line.strip())
            y -= 0.14 * inch

    # ── Signature ──
    y -= 0.6 * inch
    c.setStrokeColor(colors.black)
    c.line(margin_r - 2.2 * inch, y + 0.15 * inch, margin_r, y + 0.15 * inch)
    c.setFont(BASE_FONT_BOLD, 8.5)
    c.drawCentredString(margin_r - 1.1 * inch, y, company["name"])

    c.showPage()
    c.save()
    buf.seek(0)
    return buf

st.download_button(
    "⬇️ Download PDF",
    data=build_pdf(),
    file_name=f"Quotation_{quote_no or 'draft'}.pdf",
    mime="application/pdf",
)
