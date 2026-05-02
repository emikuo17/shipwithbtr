import io
import requests
from datetime import date

import streamlit as st
from PIL import Image as PILImage

from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader

# ----------------------------
# Page config
# ----------------------------
st.set_page_config(page_title="MAKK Delivery Order Generator", layout="wide")

# ----------------------------
# Company config
# ----------------------------
COMPANY_NAME  = "MAKK CROSS BORDER SOLUTIONS LTD."
COMPANY_ADDR1 = "14278 VALLEY BLVD UNIT A"
COMPANY_ADDR2 = "LA PUENTE, CA 91746, UNITED STATES"
COMPANY_TEL   = "TEL: 626-601-6131"
COMPANY_EMAIL = "EMAIL: mark.chung@bester.com.tw"
LOGO_URL      = "https://raw.githubusercontent.com/emikuo17/shipwithbtr/main/logo.jpg"

def safe_str(v) -> str:
    return "" if v is None else str(v)

@st.cache_data
def fetch_logo():
    try:
        r = requests.get(LOGO_URL, timeout=5)
        r.raise_for_status()
        return r.content
    except Exception:
        return None

logo_bytes = fetch_logo()

# ----------------------------
# UI
# ----------------------------
st.title("MAKK Delivery Order Generator")

# ── Header ──
st.subheader("Header")
h1, h2, h3 = st.columns(3)
with h1:
    issued_at   = st.date_input("Issued At", value=date.today())
with h2:
    issued_by   = st.text_input("Issued By", value="")
with h3:
    prepared_by = st.text_input("Prepared By", value="")

st.divider()

# ── Reference Numbers ──
st.subheader("Reference Numbers")
r1, r2, r3 = st.columns(3)
with r1:
    mawb_no = st.text_input("MAWB No.", value="")
with r2:
    hawb_no = st.text_input("HAWB No.", value="")
with r3:
    our_ref = st.text_input("Our Ref. No.", value="")

st.divider()

# ── Parties ──
st.subheader("Parties")
p1, p2 = st.columns(2)
with p1:
    shipper   = st.text_input("Shipper", value="")
    carrier   = st.text_input("Carrier", value="")
with p2:
    consignee = st.text_input("Consignee", value="")
    flight_no = st.text_input("Flight No.", value="")

st.divider()

# ── Routing ──
st.subheader("Routing")
ro1, ro2, ro3, ro4 = st.columns(4)
with ro1:
    place_of_receipt  = st.text_input("Place of Receipt", value="")
with ro2:
    receipt_etd       = st.text_input("Receipt ETD", value="")
with ro3:
    port_of_loading   = st.text_input("Port of Loading", value="")
with ro4:
    loading_etd       = st.text_input("Loading ETD", value="")

ro5, ro6, ro7, ro8 = st.columns(4)
with ro5:
    port_of_discharge = st.text_input("Port of Discharge", value="")
with ro6:
    discharge_eta     = st.text_input("Discharge ETA", value="")
with ro7:
    place_of_delivery = st.text_input("Place of Delivery", value="")
with ro8:
    delivery_eta      = st.text_input("Delivery ETA", value="")

st.divider()

# ── Cargo Details ──
st.subheader("Cargo Details")
g1, g2, g3 = st.columns(3)
with g1:
    total_packages   = st.text_input("Total Packages", value="")
    package_type     = st.text_input("Package Type (e.g. CRATE, BOX)", value="")
    port_cutoff      = st.text_input("Port Cut-Off", value="")
with g2:
    gross_weight_kg  = st.text_input("Gross Weight (KGS)", value="")
    gross_weight_lbs = st.text_input("Gross Weight (LBS)", value="")
with g3:
    measurement_cbm  = st.text_input("Measurement (CBM)", value="")
    measurement_cft  = st.text_input("Measurement (CFT)", value="")

commodity = st.text_input("Commodity", value="")
po_no     = st.text_input("PO No.", value="")

st.divider()

# ── Trucker ──
st.subheader("Trucker")
trucker_name = st.text_input("Trucker Name", value="")

st.divider()

# ── Empty Pick Up ──
st.subheader("Empty Pick Up Location")
empty_pickup_loc = st.text_area("Empty Pick Up Location", value="", height=80)
ep1, ep2 = st.columns(2)
with ep1:
    empty_ref_no = st.text_input("Empty Pick Up Ref. No.", value="")
with ep2:
    empty_date   = st.text_input("Empty Pick Up Date", value="")

st.divider()

# ── Freight Pick Up ──
st.subheader("Freight Pick Up Location")
freight_pickup_loc = st.text_area("Freight Pick Up Location", value="", height=100)
fp1, fp2 = st.columns(2)
with fp1:
    freight_ref_no = st.text_input("Freight Pick Up Ref. No.", value="")
with fp2:
    freight_date   = st.text_input("Freight Pick Up Date/Time", value="")

st.divider()

# ── Loaded Return / Delivery To ──
st.subheader("Loaded Return / Delivery To")
delivery_to = st.text_area("Delivery To", value="", height=100)
dl1, dl2 = st.columns(2)
with dl1:
    delivery_ref_no = st.text_input("Delivery Ref. No.", value="")
with dl2:
    delivery_date   = st.text_input("Delivery Date", value="")

st.divider()

# ── Bill To ──
st.subheader("Bill To")
bill_to     = st.text_area("Bill To", value="", height=80)
bill_ref_no = st.text_input("Bill To Ref. No.", value="")

st.divider()

# ── Bottom Boxes ──
st.subheader("P.O.D Notice & Instruction")
b1, b2 = st.columns(2)
with b1:
    pod_notice = st.text_area("P.O.D Notice", value=(
        "P.O.D REQUIRED WITH BILLING INVOICE\n"
        "PLEASE FAX PROOF OF DELIVERY TO 909-895-7579\n\n"
        "NOTICE: BAD ORDER PACKAGES MUST BE SIGNED FOR AS IN "
        "CONDITION RECEIVED.\n\n"
        "ALL PIER CHARGES FOR ACCOUNT OF RECEIVER UNLESS "
        "OTHERWISE SPECIFIED."
    ), height=150)
with b2:
    instruction = st.text_area("Instruction", value="", height=150)

footer_note = st.text_input("Footer Note (bottom left)", value="DO NOT BREAK DOWN PALLET")

# ----------------------------
# PDF Builder
# ----------------------------
def build_pdf() -> io.BytesIO:
    buf = io.BytesIO()
    c   = canvas.Canvas(buf, pagesize=LETTER)
    W, H = LETTER
    ml  = 0.35 * inch
    mr  = W - 0.35 * inch
    TW  = mr - ml

    # ── Helpers ──────────────────────────────────────────────────
    def hline(yy, x0=ml, x1=mr, lw=0.5):
        c.setLineWidth(lw)
        c.line(x0, yy, x1, yy)

    def vline(xx, y0, y1, lw=0.5):
        c.setLineWidth(lw)
        c.line(xx, y0, xx, y1)

    def box(x, y, w, h, lw=0.5):
        c.setLineWidth(lw)
        c.rect(x, y, w, h)

    def lbl(text, x, yy, size=6):
        c.setFont("Helvetica", size)
        c.setFillColor(colors.black)
        c.drawString(x, yy, safe_str(text))

    def val(text, x, yy, size=8, bold=False):
        c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
        c.setFillColor(colors.black)
        c.drawString(x, yy, safe_str(text))

    def mltext(text, x, yy, max_w, size=7.5, lh=0.145*inch):
        c.setFont("Helvetica", size)
        c.setFillColor(colors.black)
        for raw_line in safe_str(text).split("\n"):
            words = raw_line.split()
            line  = ""
            for w_ in words:
                test = (line + " " + w_).strip()
                if c.stringWidth(test, "Helvetica", size) > max_w:
                    c.drawString(x, yy, line)
                    yy -= lh
                    line = w_
                else:
                    line = test
            if line:
                c.drawString(x, yy, line)
                yy -= lh
        return yy

    PAD  = 0.06 * inch   # inner padding
    y    = H - 0.28 * inch

    # ════════════════════════════════════════════════════════════
    # HEADER
    # ════════════════════════════════════════════════════════════
    hdr_h   = 1.05 * inch
    hdr_bot = y - hdr_h
    mid_hdr = W * 0.52   # left/right split

    # Left: logo + company info
    if logo_bytes:
        try:
            pil  = PILImage.open(io.BytesIO(logo_bytes))
            iw, ih = pil.size
            lw_  = 0.85 * inch
            lh_  = lw_ * (ih / iw)
            c.drawImage(ImageReader(io.BytesIO(logo_bytes)),
                        ml, hdr_bot + (hdr_h - lh_) / 2,
                        width=lw_, height=lh_, mask="auto")
        except Exception:
            pass

    tx = ml + 1.0 * inch
    c.setFont("Helvetica-Bold", 12)
    c.drawString(tx, y - 0.18*inch, COMPANY_NAME)
    c.setFont("Helvetica", 7.5)
    for i, ln in enumerate([COMPANY_ADDR1, COMPANY_ADDR2,
                             COMPANY_TEL, COMPANY_EMAIL]):
        c.drawString(tx, y - 0.35*inch - i*0.145*inch, ln)
    if prepared_by.strip():
        c.setFont("Helvetica-Bold", 7)
        c.drawString(tx, y - 0.35*inch - 4*0.145*inch,
                     f"Prepared by {prepared_by}   "
                     f"{issued_at.strftime('%m-%d-%Y')} (PDT)")

    # Right: title box + issued row
    title_top = y - 0.04*inch
    title_bot = y - 0.60*inch
    box(mid_hdr, title_bot, mr - mid_hdr, title_top - title_bot, lw=1)
    c.setFont("Helvetica-Bold", 15)
    c.drawCentredString((mid_hdr + mr) / 2,
                        (title_top + title_bot) / 2 - 0.07*inch,
                        "PICKUP & DELIVERY ORDER")

    iss_top = title_bot
    iss_bot = iss_top - 0.32*inch
    iss_mid = (mid_hdr + mr) / 2
    box(mid_hdr, iss_bot, mr - mid_hdr, iss_top - iss_bot, lw=0.5)
    vline(iss_mid, iss_bot, iss_top)
    lbl("ISSUED AT :", mid_hdr + PAD, iss_top - 0.10*inch, size=6)
    val(issued_at.strftime("%m-%d-%Y"),
        mid_hdr + PAD, iss_top - 0.22*inch, size=8)
    lbl("ISSUED BY :", iss_mid + PAD, iss_top - 0.10*inch, size=6)
    val(issued_by.upper(), iss_mid + PAD, iss_top - 0.22*inch, size=8)

    hline(hdr_bot, lw=1.2)
    y = hdr_bot

    # ════════════════════════════════════════════════════════════
    # ROW 1 — TRUCKER (left) | MAWB / HAWB / OUR REF (right)
    # ════════════════════════════════════════════════════════════
    R1H   = 0.52 * inch
    r1bot = y - R1H
    LCOL  = ml + TW * 0.44   # left/right column split

    box(ml, r1bot, LCOL - ml, R1H)
    lbl("TRUCKER", ml + PAD, y - 0.10*inch)
    val(trucker_name.upper(), ml + PAD, y - 0.28*inch, size=9, bold=True)

    rw  = mr - LCOL
    box(LCOL, r1bot, rw, R1H)
    h1x = LCOL + rw * 0.45
    h2x = LCOL + rw * 0.45
    vline(h1x, r1bot, y)
    hmid = y - R1H / 2
    hline(hmid, LCOL, mr)

    lbl("MAWB NO.",      LCOL + PAD,   y - 0.10*inch)
    lbl("HAWB NO.",      h1x  + PAD,   y - 0.10*inch)
    val(mawb_no,         LCOL + PAD,   y - 0.24*inch)
    val(hawb_no,         h1x  + PAD,   y - 0.22*inch, size=10, bold=True)
    lbl("OUR REF. NO.",  LCOL + PAD,   hmid - 0.10*inch)
    val(our_ref,         LCOL + PAD,   hmid - 0.24*inch)

    hline(r1bot)
    y = r1bot

    # ════════════════════════════════════════════════════════════
    # ROW 2 — EMPTY PICKUP (left) | SHIPPER/CONSIGNEE/CARRIER/FLIGHT (right)
    # ════════════════════════════════════════════════════════════
    R2H   = 1.05 * inch
    r2bot = y - R2H

    box(ml, r2bot, LCOL - ml, R2H)
    lbl("EMPTY PICK UP LOCATION", ml + PAD, y - 0.10*inch)
    mltext(empty_pickup_loc, ml + PAD, y - 0.22*inch, LCOL - ml - PAD*2)
    lbl("REF. NO. :", ml + PAD,       r2bot + 0.24*inch, size=6)
    val(empty_ref_no,  ml + 0.75*inch, r2bot + 0.24*inch)
    lbl("DATE:",       ml + PAD,       r2bot + 0.10*inch, size=6)
    val(empty_date,    ml + 0.50*inch, r2bot + 0.10*inch)

    rw  = mr - LCOL
    hw  = rw / 2
    rm  = y - R2H / 2
    box(LCOL, r2bot, rw, R2H)
    vline(LCOL + hw, r2bot, y)
    hline(rm, LCOL, mr)
    lbl("SHIPPER",    LCOL     + PAD, y  - 0.10*inch)
    lbl("CONSIGNEE",  LCOL+hw  + PAD, y  - 0.10*inch)
    val(shipper.upper(),   LCOL     + PAD, y  - 0.24*inch, bold=True)
    val(consignee.upper(), LCOL+hw  + PAD, y  - 0.24*inch, bold=True)
    lbl("CARRIER",    LCOL     + PAD, rm - 0.10*inch)
    lbl("FLIGHT NO.", LCOL+hw  + PAD, rm - 0.10*inch)
    val(carrier,      LCOL     + PAD, rm - 0.24*inch)
    val(flight_no,    LCOL+hw  + PAD, rm - 0.24*inch)

    hline(r2bot)
    y = r2bot

    # ════════════════════════════════════════════════════════════
    # ROW 3 — FREIGHT PICKUP (left) | ROUTING top 2 rows (right)
    # ════════════════════════════════════════════════════════════
    R3H   = 1.15 * inch
    r3bot = y - R3H

    box(ml, r3bot, LCOL - ml, R3H)
    lbl("FREIGHT PICK UP LOCATION", ml + PAD, y - 0.10*inch)
    mltext(freight_pickup_loc, ml + PAD, y - 0.22*inch, LCOL - ml - PAD*2)
    lbl("REF. NO. :", ml + PAD,        r3bot + 0.24*inch, size=6)
    val(freight_ref_no, ml + 0.75*inch, r3bot + 0.24*inch)
    lbl("DATE:",        ml + PAD,        r3bot + 0.10*inch, size=6)
    val(freight_date,   ml + 0.50*inch,  r3bot + 0.10*inch)

    rw  = mr - LCOL
    hw  = rw / 2
    rm  = y - R3H / 2
    box(LCOL, r3bot, rw, R3H)
    vline(LCOL + hw, r3bot, y)
    hline(rm, LCOL, mr)
    lbl("PLACE OF RECEIPT", LCOL    + PAD, y  - 0.10*inch)
    lbl("ETD",              LCOL+hw + PAD, y  - 0.10*inch)
    val(place_of_receipt,   LCOL    + PAD, y  - 0.24*inch, bold=True)
    val(receipt_etd,        LCOL+hw + PAD, y  - 0.24*inch)
    lbl("PORT OF LOADING",  LCOL    + PAD, rm - 0.10*inch)
    lbl("ETD",              LCOL+hw + PAD, rm - 0.10*inch)
    val(port_of_loading,    LCOL    + PAD, rm - 0.24*inch, bold=True)
    val(loading_etd,        LCOL+hw + PAD, rm - 0.24*inch)

    hline(r3bot)
    y = r3bot

    # ════════════════════════════════════════════════════════════
    # ROW 4 — DELIVERY TO (left) | PORT OF DISCHARGE / DELIVERY (right)
    # ════════════════════════════════════════════════════════════
    R4H   = 1.15 * inch
    r4bot = y - R4H

    box(ml, r4bot, LCOL - ml, R4H)
    lbl("LOADED RETURN/DELIVERY TO", ml + PAD, y - 0.10*inch)
    mltext(delivery_to, ml + PAD, y - 0.22*inch, LCOL - ml - PAD*2)
    lbl("REF. NO. :", ml + PAD,         r4bot + 0.24*inch, size=6)
    val(delivery_ref_no, ml + 0.75*inch, r4bot + 0.24*inch)
    lbl("DATE:",         ml + PAD,        r4bot + 0.10*inch, size=6)
    val(delivery_date,   ml + 0.50*inch,  r4bot + 0.10*inch)

    rw  = mr - LCOL
    hw  = rw / 2
    rm  = y - R4H / 2
    box(LCOL, r4bot, rw, R4H)
    vline(LCOL + hw, r4bot, y)
    hline(rm, LCOL, mr)
    lbl("PORT OF DISCHARGE", LCOL    + PAD, y  - 0.10*inch)
    lbl("ETA",               LCOL+hw + PAD, y  - 0.10*inch)
    val(port_of_discharge,   LCOL    + PAD, y  - 0.24*inch, bold=True)
    val(discharge_eta,       LCOL+hw + PAD, y  - 0.24*inch)
    lbl("PLACE OF DELIVERY", LCOL    + PAD, rm - 0.10*inch)
    lbl("ETA",               LCOL+hw + PAD, rm - 0.10*inch)
    val(place_of_delivery,   LCOL    + PAD, rm - 0.24*inch, bold=True)
    val(delivery_eta,        LCOL+hw + PAD, rm - 0.24*inch)

    hline(r4bot)
    y = r4bot

    # ════════════════════════════════════════════════════════════
    # ROW 5 — BILL TO (left) | CARGO DETAILS (right)
    # ════════════════════════════════════════════════════════════
    R5H   = 1.1 * inch
    r5bot = y - R5H

    box(ml, r5bot, LCOL - ml, R5H)
    lbl("BILL TO", ml + PAD, y - 0.10*inch)
    mltext(bill_to, ml + PAD, y - 0.22*inch, LCOL - ml - PAD*2)
    lbl("REF. NO. :", ml + PAD,       r5bot + 0.10*inch, size=6)
    val(bill_ref_no,  ml + 0.75*inch,  r5bot + 0.10*inch)

    # Cargo right side — 3 rows
    rw  = mr - LCOL
    hw  = rw / 2
    th  = R5H / 3
    box(LCOL, r5bot, rw, R5H)
    vline(LCOL + hw, r5bot, y)
    hline(y - th,    LCOL, mr)
    hline(y - 2*th,  LCOL, mr)

    # Row a: total packages | port cut-off
    lbl("TOTAL PACKAGES",  LCOL    + PAD, y - 0.10*inch)
    lbl("PORT CUT-OFF",    LCOL+hw + PAD, y - 0.10*inch)
    val(f"{total_packages}  {package_type}".strip(),
        LCOL + PAD, y - 0.26*inch, bold=True)
    val(port_cutoff, LCOL+hw + PAD, y - 0.26*inch)

    # Row b: gross weight
    lbl("GROSS WEIGHT", LCOL + PAD, y - th - 0.10*inch)
    val(f"{gross_weight_kg} KGS" if gross_weight_kg else "",
        LCOL    + PAD, y - th - 0.26*inch)
    val(f"{gross_weight_lbs} LBS" if gross_weight_lbs else "",
        LCOL+hw + PAD, y - th - 0.26*inch)

    # Row c: measurement
    lbl("MEASUREMENT", LCOL + PAD, y - 2*th - 0.10*inch)
    val(f"{measurement_cbm} CBM" if measurement_cbm else "",
        LCOL    + PAD, y - 2*th - 0.26*inch)
    val(f"{measurement_cft} CFT" if measurement_cft else "",
        LCOL+hw + PAD, y - 2*th - 0.26*inch)

    # Commodity / PO at bottom of cargo box
    lbl("COMMODITY", LCOL    + PAD, r5bot + 0.30*inch)
    lbl("PO NO.",    LCOL+hw + PAD, r5bot + 0.30*inch)
    val(commodity.upper(), LCOL    + PAD, r5bot + 0.12*inch, bold=True)
    val(po_no,             LCOL+hw + PAD, r5bot + 0.12*inch)

    hline(r5bot, lw=1.2)
    y = r5bot

    # ════════════════════════════════════════════════════════════
    # BOTTOM — POD box (left) | Instruction (right)
    # ════════════════════════════════════════════════════════════
    BOT_H   = 1.25 * inch
    bot_bot = y - BOT_H
    mid_bot = ml + TW * 0.44

    box(ml,      bot_bot, mid_bot - ml,  BOT_H)
    box(mid_bot, bot_bot, mr - mid_bot,  BOT_H)
    lbl("INSTRUCTION", mid_bot + PAD, y - 0.10*inch)

    mltext(pod_notice,   ml      + PAD, y - 0.10*inch,
           mid_bot - ml - PAD*2, size=7.5)
    mltext(instruction,  mid_bot + PAD, y - 0.22*inch,
           mr - mid_bot - PAD*2, size=8)

    hline(bot_bot, lw=1.2)
    y = bot_bot

    # ════════════════════════════════════════════════════════════
    # FOOTER
    # ════════════════════════════════════════════════════════════
    FT_H    = 0.38 * inch
    ft_bot  = y - FT_H
    mid_ft  = ml + TW * 0.44

    box(ml,     ft_bot, mid_ft - ml,  FT_H)
    box(mid_ft, ft_bot, mr - mid_ft,  FT_H)

    c.setFont("Helvetica-Bold", 11)
    c.drawString(ml + PAD,
                 ft_bot + FT_H/2 - 0.07*inch,
                 safe_str(footer_note))

    c.setFont("Helvetica", 7)
    c.drawRightString(mr - PAD,
                      ft_bot + FT_H/2 + 0.03*inch,
                      "You are requested to inform us immediately of any occurrence.")
    c.drawRightString(mr - PAD,
                      ft_bot + FT_H/2 - 0.12*inch,
                      "Thank You for your service !")

    c.showPage()
    c.save()
    buf.seek(0)
    return buf

# ----------------------------
# Download button
# ----------------------------
ref_label = our_ref or mawb_no or "draft"
st.download_button(
    "⬇️ Download Delivery Order PDF",
    data=build_pdf(),
    file_name=f"MAKK_DO_{ref_label}.pdf",
    mime="application/pdf",
)
