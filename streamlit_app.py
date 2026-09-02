import io
import json
import requests
from datetime import date

import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
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
# CJK font (fetched at runtime, no manual download needed)
# ----------------------------
FONT_URL = "https://github.com/justfont/open-huninn-font/releases/download/v2.1/jf-openhuninn-2.1.ttf"
FONT_NAME = "CJK"
FONT_NAME_BOLD = "CJK-Bold"  # mapped to same file below (font has no separate bold weight)

@st.cache_resource(show_spinner=False)
def load_cjk_font():
    """Fetch the CJK TTF once per app session and register it with ReportLab."""
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
# Google Sheets customer database
# ----------------------------
SHEET_COLUMNS = ["Customer ID", "Company Name", "Receiver", "Phone", "Address"]

@st.cache_resource(show_spinner=False)
def get_sheet():
    """Connect once per session to the customer database Google Sheet."""
    creds_dict = json.loads(st.secrets["gcp_service_account_json"])
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(st.secrets["sheet_id"])
    return sh.sheet1

@st.cache_data(ttl=300, show_spinner=False)
def load_customers():
    """Pull all customer rows from the Sheet, refreshed at most every 5 minutes."""
    default = {
        "-- Select a customer --": {"customer_id": "", "receiver": "", "phone": "", "address": ""}
    }
    try:
        records = get_sheet().get_all_records()
    except Exception as e:
        st.warning(f"Could not load customers from Google Sheets, using blank list: {e}")
        return default

    customers = dict(default)
    for row in records:
        cust_id = safe_str(row.get("Customer ID")).strip()
        company = safe_str(row.get("Company Name")).strip()
        if not cust_id and not company:
            continue
        label = f"{cust_id} — {company}" if cust_id and company else (cust_id or company)
        customers[label] = {
            "customer_id": cust_id,
            "receiver": safe_str(row.get("Receiver")).strip(),
            "phone": safe_str(row.get("Phone")).strip(),
            "address": safe_str(row.get("Address")).strip(),
        }
    return customers

def add_customer(cust_id, company, receiver, phone, address):
    """Append a new customer row to the Sheet, then clear the cache so it shows up immediately."""
    get_sheet().append_row([cust_id, company, receiver, phone, address])
    load_customers.clear()

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

CUSTOMERS = load_customers()

st.subheader("Customer")
selected = st.selectbox(
    "Select existing customer (or fill manually below)",
    options=list(CUSTOMERS.keys()),
    index=list(CUSTOMERS.keys()).index(st.session_state.selected_customer)
    if st.session_state.selected_customer in CUSTOMERS else 0,
    key="customer_dropdown",
)
st.session_state.selected_customer = selected
cust = CUSTOMERS[selected]

with st.expander("➕ Add a new customer to the database"):
    with st.form("new_customer_form", clear_on_submit=True):
        nc_id = st.text_input("Customer ID")
        nc_company = st.text_input("Company Name")
        nc_receiver = st.text_input("Receiver (name printed on invoice)")
        nc_phone = st.text_input("Phone")
        nc_address = st.text_area("Address", height=70)
        submitted = st.form_submit_button("Save customer")
        if submitted:
            if not nc_id and not nc_company:
                st.error("Enter at least a Customer ID or Company Name.")
            else:
                add_customer(nc_id, nc_company, nc_receiver, nc_phone, nc_address)
                st.success(f"Saved {nc_company or nc_id} — it'll appear in the dropdown above now.")
                st.rerun()

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
    c.setFont(BASE_FONT, 36)
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

    c.setFont(BASE_FONT_BOLD, 9)
    c.setFillColor(colors.HexColor("#4A6FA5"))
    c.drawString(margin_x, meta_y, "DATE:")
    c.setFillColor(colors.black)
    c.setFont(BASE_FONT, 9)
    c.drawString(margin_x, meta_y - 0.17 * inch, inv_date.strftime("%m/%d/%y"))

    c.setFont(BASE_FONT_BOLD, 9)
    c.setFillColor(colors.HexColor("#4A6FA5"))
    c.drawString(margin_x, meta_y - 0.38 * inch, "INVOICE #")
    c.setFillColor(colors.black)
    c.setFont(BASE_FONT, 9)
    c.drawString(margin_x, meta_y - 0.55 * inch, safe_str(invoice_no))

    c.setFont(BASE_FONT_BOLD, 9)
    c.setFillColor(colors.HexColor("#4A6FA5"))
    c.drawString(margin_x, meta_y - 0.76 * inch, "CUSTOMER ID:")
    c.setFillColor(colors.black)
    c.setFont(BASE_FONT, 9)
    c.drawString(margin_x, meta_y - 0.93 * inch, safe_str(customer_id))

    # ── TO block ──
    to_x = w / 2 + 0.5 * inch
    c.setFont(BASE_FONT_BOLD, 9)
    c.setFillColor(colors.HexColor("#4A6FA5"))
    c.drawString(to_x, meta_y, "TO:")
    c.setFillColor(colors.black)
    c.setFont(BASE_FONT, 9)
    to_y = meta_y - 0.17 * inch
    if receiver.strip():
        words = receiver.strip().split()
        line = ""
        for word in words:
            test = (line + " " + word).strip()
            if c.stringWidth(test, BASE_FONT, 9) > (margin_r - to_x):
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
        ("FONTNAME", (0, 0), (-1, 0), BASE_FONT_BOLD),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("VALIGN", (0, 0), (-1, 0), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, 0), 6),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
        ("GRID", (0, 0), (-1, n_items), 0.5, colors.HexColor("#CCCCCC")),
        ("FONTNAME", (0, 1), (-1, n_items), BASE_FONT),
        ("FONTSIZE", (0, 1), (-1, n_items), 9),
        ("ALIGN", (0, 1), (0, n_items), "CENTER"),
        ("ALIGN", (2, 1), (2, n_items), "CENTER"),
        ("ALIGN", (3, 1), (3, n_items), "RIGHT"),
        ("VALIGN", (0, 1), (-1, n_items), "MIDDLE"),
        ("TOPPADDING", (0, 1), (-1, n_items), 5),
        ("BOTTOMPADDING", (0, 1), (-1, n_items), 5),
        ("FONTNAME", (0, n_items + 1), (-1, n_items + 2), BASE_FONT),
        ("FONTSIZE", (0, n_items + 1), (-1, n_rows - 1), 9),
        ("ALIGN", (2, n_items + 1), (3, n_rows - 1), "RIGHT"),
        ("TOPPADDING", (0, n_items + 1), (-1, n_rows - 1), 4),
        ("BOTTOMPADDING", (0, n_items + 1), (-1, n_rows - 1), 4),
        ("LINEABOVE", (2, n_items + 1), (3, n_items + 1), 0.5, colors.HexColor("#CCCCCC")),
        ("FONTNAME", (2, n_rows - 1), (3, n_rows - 1), BASE_FONT_BOLD),
        ("FONTSIZE", (2, n_rows - 1), (3, n_rows - 1), 10),
        ("LINEABOVE", (2, n_rows - 1), (3, n_rows - 1), 0.5, colors.HexColor("#CCCCCC")),
        ("LINEBELOW", (2, n_rows - 1), (3, n_rows - 1), 0.5, colors.HexColor("#CCCCCC")),
    ]))

    _, table_h = tbl.wrapOn(c, table_w, h)
    tbl.drawOn(c, margin_x, table_top - table_h)

    # ── Footer note (checks payable + thank you) ──
    footer_y = table_top - table_h - 0.4 * inch
    c.setFont(BASE_FONT_BOLD, 8)
    c.setFillColor(colors.HexColor("#4A6FA5"))
    c.drawCentredString(w / 2, footer_y, PAYABLE_NOTE)
    c.setFont(BASE_FONT, 8)
    c.setFillColor(colors.black)
    c.drawCentredString(w / 2, footer_y - 0.18 * inch, THANK_YOU)

    # ── Payment Information block (in the blank space) ──
    pay_y = footer_y - 0.55 * inch

    # Section title
    c.setFont(BASE_FONT_BOLD, 11)
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
        c.setFont(BASE_FONT_BOLD, 8.5)
        c.setFillColor(colors.HexColor("#2C3E6B"))
        label_str = f"{label}: "
        label_w = c.stringWidth(label_str, BASE_FONT_BOLD, 8.5)
        c.drawString(margin_x, pay_y, label_str)
        c.setFont(BASE_FONT, 8.5)
        c.drawString(margin_x + label_w, pay_y, value)
        pay_y -= 0.23 * inch

    # ── Bottom company block ──
    bottom_y = 0.55 * inch
    c.setStrokeColor(colors.HexColor("#4A6FA5"))
    c.setLineWidth(1)
    c.line(margin_x, bottom_y + 0.32 * inch, margin_r, bottom_y + 0.32 * inch)
    c.setFont(BASE_FONT_BOLD, 8)
    c.setFillColor(colors.HexColor("#4A6FA5"))
    c.drawCentredString(w / 2, bottom_y + 0.15 * inch, COMPANY_NAME)
    c.setFont(BASE_FONT, 8)
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
