import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import requests
import re
import os

# -------------------- Configuration & Credentials --------------------
# Osu! API Credentials
CLIENT_ID = '38538'
CLIENT_SECRET = '1Eoq9oBjODYkT3VFfwDcJZq4iLkD76dEP1QCUDge'

# Google Sheets API scope
SCOPE = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

# List of valid sheet names
VALID_SHEETS = [
    "Qualifiers", "Group Stage", "Round of 128", "Round of 64", "Round of 32",
    "Round of 16", "Quarterfinals", "Semifinals", "Finals", "Grand Finals"
]

# -------------------- Helper Functions --------------------

def get_osu_access_token(client_id, client_secret):
    token_url = 'https://osu.ppy.sh/oauth/token'
    payload = {
        'client_id': client_id,
        'client_secret': client_secret,
        'grant_type': 'client_credentials',
        'scope': 'public'
    }
    response = requests.post(token_url, json=payload)
    if response.status_code == 200:
        print("✅ Successfully authenticated with osu! API.")
        return response.json()['access_token']
    else:
        raise Exception(f"Failed to get access token: {response.text}")

def get_osu_match_data(match_id, access_token):
    match_url = f'https://osu.ppy.sh/api/v2/matches/{match_id}'
    headers = {'Authorization': f'Bearer {access_token}'}
    response = requests.get(match_url, headers=headers)
    if response.status_code == 200:
        print("📋 Fetched Match Data.")
        return response.json()
    else:
        raise Exception(f"Failed to get match data: {response.text}")

def extract_beatmap_title(beatmap_info):
    beatmap_title = beatmap_info.get('title') or beatmap_info.get('title_unicode') or 'Unknown Beatmap'
    return re.sub(r'\[.*?\]', '', beatmap_title).strip().lower()

def format_accuracy(accuracy):
    return round(accuracy * 100, 2)

def load_column_d_values(sheet):
    """ Load unique values from Column D in the Google Sheet. """
    data = sheet.get_all_values()
    col_d_values = set()
    for row in data:
        if len(row) > 3:
            val = str(row[3]).strip().lower()
            if val:
                col_d_values.add(val)
    return list(col_d_values)

# -------------------- GUI Application --------------------

class OsuSheetGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Osu! Sheet Updater")
        self.geometry("600x700")
        
        self.lobby_id_var = tk.StringVar()
        self.spreadsheet_url_var = tk.StringVar()
        self.sheet_selection_var = tk.StringVar(value=VALID_SHEETS[0])
        self.col_d_mapping = {}
        self.credentials_path = None  # Stores uploaded JSON credentials path
        
        self.create_widgets()

    def create_widgets(self):
        tk.Label(self, text="Upload Google API Credentials JSON:").pack(pady=5)
        tk.Button(self, text="Upload JSON", command=self.upload_credentials).pack(pady=5)

        tk.Label(self, text="Lobby ID (Match ID):").pack(pady=5)
        tk.Entry(self, textvariable=self.lobby_id_var).pack(pady=5)

        tk.Label(self, text="Spreadsheet URL:").pack(pady=5)
        tk.Entry(self, textvariable=self.spreadsheet_url_var, width=80).pack(pady=5)

        tk.Label(self, text="Select Sheet:").pack(pady=5)
        sheet_dropdown = ttk.Combobox(self, textvariable=self.sheet_selection_var, 
                                      values=VALID_SHEETS, state="readonly")
        sheet_dropdown.pack(pady=5)

        tk.Button(self, text="Load Column D Mappings", command=self.load_mappings).pack(pady=10)

        self.mapping_frame = tk.Frame(self)
        self.mapping_frame.pack(pady=10, fill="x")

        tk.Button(self, text="Run Update", command=self.run_update).pack(pady=20)

    def upload_credentials(self):
        """ Allow user to upload Google API credentials JSON file """
        file_path = filedialog.askopenfilename(filetypes=[("JSON files", "*.json")])
        if file_path and os.path.isfile(file_path):
            self.credentials_path = file_path  # Store uploaded file path dynamically
            print(f"✅ JSON File Uploaded: {self.credentials_path}")  # Debugging print
            messagebox.showinfo("Success", f"Google API Credentials uploaded: {os.path.basename(file_path)}")
        else:
            messagebox.showerror("Error", "Invalid file selected.")

    def authenticate_google_sheets(self):
        """ Authenticate Google Sheets API using the uploaded JSON file """
        if not self.credentials_path:
            messagebox.showerror("Error", "Please upload Google API credentials JSON first.")
            return None
        try:
            print(f"🔍 Using JSON Path: {self.credentials_path}")  # Debugging print
            creds = ServiceAccountCredentials.from_json_keyfile_name(self.credentials_path, SCOPE)
            client = gspread.authorize(creds)
            return client
        except Exception as e:
            messagebox.showerror("Error", f"Failed to authenticate: {e}")
            return None

    def run_update(self):
        lobby_id = self.lobby_id_var.get().strip()
        spreadsheet_url = self.spreadsheet_url_var.get().strip()
        sheet_name = self.sheet_selection_var.get().strip()

        if not self.credentials_path:
            messagebox.showerror("Error", "Please upload Google API credentials JSON first.")
            return
        
        client = self.authenticate_google_sheets()
        if not client:
            return

        try:
            sheet = client.open_by_url(spreadsheet_url).worksheet(sheet_name)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open spreadsheet: {e}")
            return

        access_token = get_osu_access_token(CLIENT_ID, CLIENT_SECRET)
        match_data = get_osu_match_data(lobby_id, access_token)

        update_google_sheet_with_match_data_gui(sheet, match_data, access_token, self.col_d_mapping)
        messagebox.showinfo("Success", f"Google Sheet '{sheet_name}' updated successfully.")

if __name__ == "__main__":
    app = OsuSheetGUI()
    app.mainloop()
