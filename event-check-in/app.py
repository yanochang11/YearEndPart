import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
from gspread_dataframe import get_as_dataframe, set_with_dataframe
from datetime import datetime, time
from streamlit_cookies_manager import CookieManager

# --- Google Sheets Connection ---
@st.cache_resource(ttl=600)
def get_gsheet():
    # ... (rest of the function is the same)
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = {
        "type": st.secrets.gcp_service_account.type,
        "project_id": st.secrets.gcp_service_account.project_id,
        "private_key_id": st.secrets.gcp_service_account.private_key_id,
        "private_key": st.secrets.gcp_service_account.private_key,
        "client_email": st.secrets.gcp_service_account.client_email,
        "client_id": st.secrets.gcp_service_account.client_id,
        "auth_uri": st.secrets.gcp_service_account.auth_uri,
        "token_uri": st.secrets.gcp_service_account.token_uri,
        "auth_provider_x509_cert_url": st.secrets.gcp_service_account.auth_provider_x509_cert_url,
        "client_x509_cert_url": st.secrets.gcp_service_account.client_x509_cert_url,
    }
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client

@st.cache_data(ttl=60)
def get_data(_client, sheet_name, worksheet_name):
    # ... (rest of the function is the same)
    try:
        sheet = _client.open(sheet_name).worksheet(worksheet_name)
        data = get_as_dataframe(sheet)
        # Ensure 'EmployeeID' is string type for matching
        if 'EmployeeID' in data.columns:
            data['EmployeeID'] = data['EmployeeID'].astype(str)
        return data
    except gspread.exceptions.SpreadsheetNotFound:
        st.warning(f"Spreadsheet '{sheet_name}' not found. Using mock data instead.")
        return create_mock_data()
    except gspread.exceptions.WorksheetNotFound:
        st.error(f"Worksheet '{worksheet_name}' not found.")
        return pd.DataFrame()

def create_mock_data():
    """Creates a mock DataFrame for demonstration purposes."""
    data = {
        'EmployeeID': ['M4095', 'M4096', 'M4097'],
        'Name': ['John Doe', 'Jane Smith', 'Peter Jones'],
        'TableNo': ['A1', 'B2', 'C3'],
        'CheckInTime': ['', '', ''],
        'CheckOutTime': ['', '', '']
    }
    return pd.DataFrame(data)


def update_cell(client, sheet_name, worksheet_name, row, col, value):
    """Updates a single cell in the Google Sheet."""
    try:
        sheet = client.open(sheet_name).worksheet(worksheet_name)
        sheet.update_cell(row, col, value)
        # Clear the cache to reflect the update
        get_data.clear()
    except Exception as e:
        st.error(f"Failed to update Google Sheet: {e}")

# --- Main App ---
def main():
    if not st.runtime.exists():
        print("---")
        print("This app must be run with `streamlit run`.")
        print("Please run `streamlit run app.py` to view this application.")
        print("---")
        return

    st.set_page_config(page_title="Event Check-in/out System")
    st.title("Event Check-in/out System")
    cookies = CookieManager()

    GOOGLE_SHEET_NAME = "Event_Check-in"
    WORKSHEET_NAME = "Sheet1"

    # Initialize session state
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'mode' not in st.session_state:
        st.session_state.mode = "Check-in"
    if 'start_time' not in st.session_state:
        st.session_state.start_time = time(9, 0)
    if 'end_time' not in st.session_state:
        st.session_state.end_time = time(17, 0)

    with st.expander("Admin Panel"):
        if not st.session_state.authenticated:
            password = st.text_input("Enter password to access admin panel:", type="password", key="password_input")
            if st.button("Login"):
                if password == st.secrets.admin.password:
                    st.session_state.authenticated = True
                    st.rerun()
                else:
                    st.error("Incorrect password")
        else:
            st.success("Authenticated")
            # Update session state directly when admin changes settings
            st.session_state.mode = st.radio("Mode", ["Check-in", "Check-out"], index=["Check-in", "Check-out"].index(st.session_state.mode))
            st.session_state.start_time = st.time_input("Start Time", st.session_state.start_time)
            st.session_state.end_time = st.time_input("End Time", st.session_state.end_time)
            if st.button("Logout"):
                st.session_state.authenticated = False
                st.rerun()

    # Use settings from session state for the check
    now = datetime.now().time()
    if not (st.session_state.start_time <= now <= st.session_state.end_time):
        st.warning("Not currently open for check-in/out.")
        return

    employee_id = st.text_input("請輸入您的員工編號 (EmployeeID):").strip()

    if st.button("確認"):
        if not employee_id:
            st.error("請輸入您的員工編號")
            return

        client = get_gsheet()
        df = get_data(client, GOOGLE_SHEET_NAME, WORKSHEET_NAME)

        if df.empty:
            return

        employee_row = df[df['EmployeeID'] == employee_id]

        if employee_row.empty:
            st.error("查無此人")
            return

        row_index = employee_row.index[0] + 2 # +2 for header and 1-based index

        if st.session_state.mode == "Check-in":
            handle_check_in(employee_id, employee_row, row_index, client, cookies)
        else: # Check-out
            handle_check_out(employee_row, row_index, client)

def handle_check_in(employee_id, employee_row, row_index, client, cookies):
    check_in_time = employee_row['CheckInTime'].iloc[0]
    if pd.notna(check_in_time) and check_in_time != '':
        st.warning("您已報到，無須重複操作")
        return

    if cookies.get('event_checked_in') == employee_id:
        st.warning("您已報到，無須重複操作")
        return

    name = employee_row['Name'].iloc[0]
    table_no = employee_row['TableNo'].iloc[0]
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Assuming 'CheckInTime' is the 4th column (D)
    update_cell(client, "Event_Check-in", "Sheet1", row_index, 4, timestamp)
    cookies.set('event_checked_in', employee_id, expires_in=86400) # 24 hours
    st.success(f"報到成功！{name}，您的桌號在 {table_no}")


def handle_check_out(employee_row, row_index, client):
    check_out_time = employee_row['CheckOutTime'].iloc[0]
    if pd.notna(check_out_time) and check_out_time != '':
        st.warning("您已完成簽退")
        return

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # Assuming 'CheckOutTime' is the 5th column (E)
    update_cell(client, "Event_Check-in", "Sheet1", row_index, 5, timestamp)
    st.success("簽退成功，祝您有個美好的一天！")


if __name__ == "__main__":
    main()
