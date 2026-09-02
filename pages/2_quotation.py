import io
import json
import requests
from datetime import date, timedelta

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
# Company config (MAKK only)
# ----------------------------
COMPANY = {
    "name": "MAKK CROSS-BORDER SOLUTIONS LTD.",
    "address": "14278 VALLEY BLVD UNIT A, CITY OF INDUSTRY, CA 91746, UNITED STATES",
    "phone": "626-601-6131",
    "email": "mark.chung@bester.com.tw",
    "logo_url": "https://raw.githubusercontent.com/emikuo17/shipwithbtr/main/logo.jpg",
}

# ----------------------------
# Google Sheets customer database (shared with the invoice app)
# ----------------------------
@st.cache_resource(show_spinner=False)
def get_sheet():
    """Connect once per session to the shared customer database Google Sheet."""
    creds_dict = json.loads(st.secrets["gcp_service_account_json"])
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(st.secrets["sheet_id"])
    return sh.sheet1

@st.cache_data(ttl=0, show_spinner=False)
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
if "quotation_items_df" not in st.session_state:
    st.session_state.quotation_items_df = pd.DataFrame(
        [{"Description": "", "Remark": "", "Unit": "", "Qty": 1.0, "Rate": 0.0, "Currency": "USD"}]
    )
if "quotation_selected_customer" not in st.session_state:
    st.session_state.quotation_selected_customer = "-- Select a customer --"

# ----------------------------
# UI
# ----------------------------
st.title("Quotation Generator")

company = COMPANY

CUSTOMERS = load_customers()

st.subheader("Customer")
customer_keys = list(CUSTOMERS.keys())
selected = st.selectbox(
    "Select existing customer (or fill manually below)",
    options=customer_keys,
    index=customer_keys.index(st.session_state.quotation_selected_customer)
    if st.session_state.quotation_selected_customer in customer_keys else 0,
    key="customer_dropdown",
)
st.session_state.quotation_selected_customer = selected
cust = CUSTOMERS[selected]
default_name = cust["receiver"] or ("" if selected.startswith("--") else selected)
customer_name = st.text_input("To (Customer name)", value=default_name)
customer_address = st.text_area("Customer address", value=cust["address"], height=70)

with st.expander("➕ Add a new customer to the database"):
    with st.form("quotation_new_customer_form", clear_on_submit=True):
        nc_id = st.text_input("Customer ID")
        nc_company = st.text_input("Company Name")
        nc_receiver = st.text_input("Receiver (name printed on documents)")
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

st.subheader("Quote Info")
col1, col2 = st.columns(2)
with col1:
    quote_no = st.text_input("Quote No.", value="")
    create_date = st.date_input("Create Date", value=date.today())
    created_by = st.text_input("Created By", value="Mark Chung")
with col2:
    ship_mode = st.selectbox("Ship Mode", ["AIR", "SEA", "TRUCK"], index=0)
    service_term = st.text_input("Service Term", value="AIRPORT/AIRPORT")
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
    carrier = st.text_input("Carrier", value="")

st.divider()

st.subheader("Rate Line Items")

btn_col1, btn_col2, _ = st.columns([1, 1, 3])
with btn_col1:
    if st.button("➕ Add line item"):
        base = st.session_state.quotation_items_df.copy()
        editor_state = st.session_state.get("quotation_items_editor", {})
        for idx, changes in editor_state.get("edited_rows", {}).items():
            for col, val in changes.items():
                base.at[idx, col] = val
        st.session_state.quotation_items_df = pd.concat(
            [base, pd.DataFrame([{"Description": "", "Remark": "", "Unit": "", "Qty": 1.0, "Rate": 0.0, "Currency": "USD"}])],
            ignore_index=True
        )

with btn_col2:
    if st.button("🗑️ Remove last item"):
        if len(st.session_state.quotation_items_df) > 1:
            st.session_state.quotation_items_df = st.session_state.quotation_items_df.iloc[:-1].reset_index(drop=True)

edited_df = st.data_editor(
    st.session_state.quotation_items_df,
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
    key="quotation_items_editor",
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

    def wrap_text(text, font, size, max_width):
        """Word-wrap text to fit max_width, returning a list of lines."""
        text = safe_str(text).strip()
        if not text:
            return []
        words = text.split()
        lines, line = [], ""
        for word in words:
            test = (line + " " + word).strip()
            if c.stringWidth(test, font, size) > max_width and line:
                lines.append(line)
                line = word
            else:
                line = test
        if line:
            lines.append(line)
        return lines

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

    # ── Quotation box (top right, alongside the letterhead) ──
    box_w, box_h = 2.4 * inch, 0.7 * inch
    box_x, box_y = margin_r - box_w, y - box_h

    # ── Company header text (left of the box, ECMS-style) ──
    text_x = margin_x + 1.3 * inch
    text_max_w = box_x - text_x - 0.25 * inch  # stop before the box, wrap instead of overlapping

    # Try to keep the company name on one line by shrinking the font slightly;
    # only wrap to a second line if it still doesn't fit even at the smallest size.
    name_font_size = 13
    for size in (13, 12, 11, 10):
        if c.stringWidth(company["name"], BASE_FONT_BOLD, size) <= text_max_w:
            name_font_size = size
            break
    else:
        name_font_size = 10

    c.setFont(BASE_FONT_BOLD, name_font_size)
    c.setFillColor(colors.HexColor("#1A1A1A"))
    name_lines_list = wrap_text(company["name"], BASE_FONT_BOLD, name_font_size, text_max_w) or [company["name"]]
    line_height = 0.19 * inch if name_font_size >= 12 else 0.16 * inch
    for i, line in enumerate(name_lines_list):
        c.drawString(text_x, y - 0.16 * inch - i * line_height, line)
    name_lines = len(name_lines_list)

    line_y = y - 0.16 * inch - name_lines * line_height - 0.05 * inch
    c.setFont(BASE_FONT, 8)
    c.setFillColor(colors.HexColor("#333333"))
    for addr_line in wrap_text(company["address"], BASE_FONT, 8, text_max_w):
        c.drawString(text_x, line_y, addr_line)
        line_y -= 0.14 * inch
    c.drawString(text_x, line_y, f"TEL: {company['phone']}    EMAIL: {company['email']}")
    line_y -= 0.14 * inch
    c.setFillColor(colors.black)

    header_bottom = min(line_y, y - logo_h, box_y)

    c.setStrokeColor(colors.HexColor("#4A6FA5"))
    c.rect(box_x, box_y, box_w, box_h)
    c.setFont(BASE_FONT_BOLD, 15)
    c.setFillColor(colors.HexColor("#4A6FA5"))
    c.drawCentredString(box_x + box_w / 2, box_y + box_h - 0.3 * inch, "QUOTATION")
    c.setFont(BASE_FONT, 9)
    c.setFillColor(colors.black)
    c.drawCentredString(box_x + box_w / 2, box_y + 0.15 * inch, f"QUOTE NO: {safe_str(quote_no)}")
    c.setStrokeColor(colors.black)

    y = header_bottom - 0.2 * inch
    c.setStrokeColor(colors.HexColor("#CCCCCC"))
    c.line(margin_x, y, margin_r, y)

    # ── TO block (left) / Meta block (right) ──
    y -= 0.22 * inch
    left_x = margin_x
    right_label_x = w / 2 + 0.1 * inch
    to_max_w = right_label_x - left_x - 0.4 * inch  # keep clear of the meta column

    c.setFont(BASE_FONT_BOLD, 8.5)
    c.drawString(left_x, y, "TO:")
    c.setFont(BASE_FONT, 8.5)
    ty = y - 0.16 * inch
    c.setFont(BASE_FONT_BOLD, 8.5)
    for line in wrap_text(customer_name, BASE_FONT_BOLD, 8.5, to_max_w):
        c.drawString(left_x, ty, line)
        ty -= 0.16 * inch
    c.setFont(BASE_FONT, 8.5)
    for addr_para in customer_address.split("\n"):
        for line in wrap_text(addr_para, BASE_FONT, 8.5, to_max_w):
            c.drawString(left_x, ty, line)
            ty -= 0.16 * inch

    meta_rows = [
        ("CREATE DATE", create_date.strftime("%m-%d-%Y")),
        ("CREATED BY", created_by),
        ("SHIP MODE", ship_mode),
        ("SERVICE TERM", service_term),
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
        ("Carrier", carrier, left_x + 5.7 * inch),
    ]
    for label, val, xpos in route_cols:
        c.setFont(BASE_FONT_BOLD, 7.5)
        c.drawString(xpos, y, label)
        c.setFont(BASE_FONT, 8.5)
        c.drawString(xpos, y - 0.15 * inch, safe_str(val))

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
