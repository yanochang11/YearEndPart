import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
from gspread_dataframe import get_as_dataframe, set_with_dataframe
from datetime import datetime, time, timedelta
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
        st.session_state.mock_mode = True
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
    if st.session_state.get('mock_mode', False):
        st.info("Mock mode: Simulating a successful update.")
        return

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

    st.set_page_config(page_title="Event Check-in/out System", initial_sidebar_state="collapsed")
    st.title("Event Check-in/out System")
    cookies = CookieManager()
    if not cookies.ready():
        st.stop()

    # Initialize session state
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'mode' not in st.session_state:
        st.session_state.mode = "Check-in"
    if 'start_time' not in st.session_state:
        st.session_state.start_time = time(9, 0)
    if 'end_time' not in st.session_state:
        st.session_state.end_time = time(17, 0)
    if 'selected_employee_id' not in st.session_state:
        st.session_state.selected_employee_id = None
    if 'search_term' not in st.session_state:
        st.session_state.search_term = ""

    # --- Main App ---
    st.markdown(f"**Current Mode:** `{st.session_state.mode}`")

    GOOGLE_SHEET_NAME = "Event_Check-in"
    WORKSHEET_NAME = "Sheet1"

    with st.sidebar.expander("Admin Panel", expanded=False):
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

    client = get_gsheet()
    df = get_data(client, GOOGLE_SHEET_NAME, WORKSHEET_NAME)

    if df.empty:
        return

    # --- Search and Selection Logic ---
    st.session_state.search_term = st.text_input("請輸入您的員工編號 (EmployeeID) 或中文名字:", value=st.session_state.search_term).strip()

    if st.button("確認"):
        if not st.session_state.search_term:
            st.error("請輸入您的員工編號或名字")
            return

        # Search by both EmployeeID and Name
        id_match = df[df['EmployeeID'] == st.session_state.search_term]
        name_match = df[df['Name'] == st.session_state.search_term]

        if not id_match.empty:
            st.session_state.selected_employee_id = id_match['EmployeeID'].iloc[0]
        elif not name_match.empty:
            if len(name_match) == 1:
                st.session_state.selected_employee_id = name_match['EmployeeID'].iloc[0]
            else:
                # Multiple matches found, prompt user to select
                st.session_state.selected_employee_id = None # Clear previous selection
                st.warning("找到多位同名員工，請選擇一位:")
                for index, row in name_match.iterrows():
                    if st.button(f"{row['Name']} ({row['EmployeeID']})"):
                        st.session_state.selected_employee_id = row['EmployeeID']
                        st.rerun() # Rerun to process the selection
                return # Stop further processing until a selection is made
        else:
            st.error("查無此人，請確認輸入是否正確，或洽詢工作人員。")
            st.session_state.selected_employee_id = None
            return

    if st.session_state.selected_employee_id:
        employee_id = st.session_state.selected_employee_id
        employee_row = df[df['EmployeeID'] == employee_id]
        row_index = employee_row.index[0] + 2

        if st.session_state.mode == "Check-in":
            handle_check_in(employee_id, employee_row, row_index, client, cookies)
        else: # Check-out
            handle_check_out(employee_row, row_index, client)

        # Clear selection after processing
        st.session_state.selected_employee_id = None
        st.session_state.search_term = ""


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
    cookies['event_checked_in'] = employee_id
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
