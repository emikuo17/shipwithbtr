 import streamlit as st
  import pandas as pd
  from pathlib import Path
  from datetime import datetime

  DATA_FILE = Path(__file__).resolve().parent / "btr_customers.csv"
  COLUMNS = [
      "customer_id",
      "sender_name",
      "sender_phone",
      "recipient_requirements_ack",
      "recipient_name_zh",
      "recipient_id_number",
      "recipient_address_zh",
      "recipient_phone",
      "preferred_contact_method",
      "created_at",
  ]


  def ensure_data_file() -> None:
      if not DATA_FILE.exists():
          df = pd.DataFrame(columns=COLUMNS)
          df.to_csv(DATA_FILE, index=False)


  def read_customer_data() -> pd.DataFrame:
      ensure_data_file()
      if DATA_FILE.stat().st_size == 0:
          return pd.DataFrame(columns=COLUMNS)
      return pd.read_csv(DATA_FILE, dtype=str).fillna("")


  def write_customer_data(df: pd.DataFrame) -> None:
      df.to_csv(DATA_FILE, index=False)


  def generate_customer_id(df: pd.DataFrame) -> str:
      if df.empty:
          return "BTR000001"
      numbers = (
          df["customer_id"]
          .fillna("")
          .str.extract(r"BTR(\d{6})", expand=False)
          .dropna()
      )
      if numbers.empty:
          next_number = 1
      else:
          next_number = numbers.astype(int).max() + 1
      return f"BTR{next_number:06d}"


  def render_dropoff_info() -> None:
      st.subheader("Drop-Off Information | 包裹交件資訊")
      st.markdown(
          """
  **Chinese:** 請將包裹交件至以下地址
  **English:** Please drop off your packages at the following address.

  **地址 | Address:** 14278 Valley Blvd. Unit A, La Puente, CA 91746

  **Chinese:** 若需要幫助配送到此地址，請聯繫我們。會額外收取運費。
  **English:** If you need assistance delivering your package to this address,
  please contact us. Additional delivery fees will apply.
          """
      )


  def main() -> None:
      st.title("BTR Shipping Service: USA to Taiwan")
      st.markdown(
          """
  **Chinese:** 感謝您使用 BTR 飛斯特運通，請填寫以下資料以完成寄送申請。
  **English:** Thank you for using BTR. Please complete the form below to
  finalize your shipment details.
          """
      )

      tabs = st.tabs(["Application Form", "Lookup"])

      with tabs[0]:
          st.subheader("Application Form | 申請表")

          with st.form("application_form", clear_on_submit=True):
              sender_name = st.text_input("Sender's Name (寄件人姓名)",
  max_chars=100)
              sender_phone = st.text_input("Sender's Phone Number (寄件人電
  話)", max_chars=25)
              st.markdown(
                  "**Chinese:** 貨物到台灣後，收件人必須擁有 EZWAY 並完成以下手
  續：\n"
                  "1. 實名認證\n"
                  "2. 委任通關\n\n"
                  "**English:** The recipient must complete Real-Name
  Authentication and authorize Customs Clearance on EZWAY after the package
  arrives in Taiwan."
              )
              recipient_requirements_ack = st.checkbox(
                  "Yes, the recipient acknowledges the required steps.",
  value=False
              )
              recipient_name_zh = st.text_input("Recipient's Name (中文)",
  max_chars=100)
              recipient_id_number = st.text_input("Recipient's ID Number",
  max_chars=20)
              recipient_address_zh = st.text_area("Recipient's Address (中文)",
  max_chars=200)
              recipient_phone = st.text_input("Recipient's Phone Number",
  max_chars=25)
              preferred_contact_method = st.selectbox(
                  "Preferred Contact Method", ["Line", "WeChat", "Instagram",
  "Email", "Phone", "Other"]
              )

              submitted = st.form_submit_button("Submit Application")

              if submitted:
                  required_fields = {
                      "Sender's Name": sender_name,
                      "Sender's Phone": sender_phone,
                      "Recipient's Name": recipient_name_zh,
                      "Recipient's ID": recipient_id_number,
                      "Recipient's Address": recipient_address_zh,
                      "Recipient's Phone": recipient_phone,
                  }
                  missing = [label for label, value in required_fields.items()
  if not value.strip()]
                  if missing:
                      st.error("Please complete all required fields: " + ",
  ".join(missing))
                  elif not recipient_requirements_ack:
                      st.error("Recipient must acknowledge the EZWAY
  requirements before submission.")
                  else:
                      df = read_customer_data()
                      customer_id = generate_customer_id(df)
                      created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                      new_row = {
                          "customer_id": customer_id,
                          "sender_name": sender_name.strip(),
                          "sender_phone": sender_phone.strip(),
                          "recipient_requirements_ack": "Yes",
                          "recipient_name_zh": recipient_name_zh.strip(),
                          "recipient_id_number": recipient_id_number.strip(),
                          "recipient_address_zh": recipient_address_zh.strip(),
                          "recipient_phone": recipient_phone.strip(),
                          "preferred_contact_method": preferred_contact_method,
                          "created_at": created_at,
                      }
                      updated_df = pd.concat([df, pd.DataFrame([new_row])],
  ignore_index=True)
                      write_customer_data(updated_df)

                      st.success(
                          f"Registration complete! Your Customer ID is
  {customer_id}. Please save this ID for future shipments."
                      )
                      st.json(new_row)

          render_dropoff_info()

      with tabs[1]:
          st.subheader("Lookup | 客戶查詢")
          df = read_customer_data()

          st.markdown("### Search by Customer ID")
          id_query = st.text_input("Customer ID (e.g., BTR000123)",
  key="id_search")
          if st.button("Search by ID"):
              if id_query.strip():
                  results = df[df["customer_id"].str.fullmatch(id_query.strip(),
  case=False, na=False)]
                  if results.empty:
                      st.error("No records found.")
                  else:
                      st.dataframe(results)
              else:
                  st.error("Please enter a Customer ID to search.")

          st.markdown("### Search by Phone Number")
          phone_query = st.text_input("Phone number (sender or recipient)",
  key="phone_search")
          if st.button("Search by phone"):
              if phone_query.strip():
                  pattern = phone_query.strip()
                  results = df[
                      df["sender_phone"].str.contains(pattern, case=False,
  na=False)
                      | df["recipient_phone"].str.contains(pattern, case=False,
  na=False)
                  ]
                  if results.empty:
                      st.error("No records found.")
                  else:
                      st.dataframe(results)
              else:
                  st.error("Please enter a phone number to search.")


  if __name__ == "__main__":
      ensure_data_file()
      main()
