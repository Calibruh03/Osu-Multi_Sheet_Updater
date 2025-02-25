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

# Google Sheets credentials and scope
SCOPE = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]
CREDS_FILE = "D:\\Python Code\\Osu_Sheets\\osu-sheet-automation.json"

# List of valid sheet names
VALID_SHEETS = [
    "Qualifiers", "Group Stage", "Round of 128", "Round of 64", "Round of 32",
    "Round of 16", "Quarterfinals", "Semifinals", "Finals", "Grand Finals"
]

# -------------------- Helper Functions (from your original code) --------------------

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

def get_osu_username(user_id, access_token, username_cache={}):
    if user_id in username_cache:
        return username_cache[user_id]
    
    url = f'https://osu.ppy.sh/api/v2/users/{user_id}'
    headers = {'Authorization': f'Bearer {access_token}'}
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        user_data = response.json()
        username = user_data.get('username', f"Unknown User ({user_id})")
        username_cache[user_id] = username
        return username
    else:
        print(f"⚠️ Failed to fetch username for user_id {user_id}: {response.text}")
        return f"Unknown User ({user_id})"

def extract_beatmap_title(beatmap_info):
    beatmap_title = (beatmap_info.get('title') or
                     beatmap_info.get('title_unicode') or
                     beatmap_info.get('beatmapset', {}).get('title') or
                     beatmap_info.get('version') or
                     'Unknown Beatmap')
    beatmap_title_clean = re.sub(r'\[.*?\]', '', beatmap_title).strip().lower()
    return beatmap_title_clean

def format_accuracy(accuracy):
    return round(accuracy * 100, 2)

def build_beatmap_rows(data):
    beatmap_rows = {}
    starting_row = 8  # Assuming row 9 in the sheet (0-indexed)
    print("\n🔍 Building Beatmap Rows Mapping:")
    for row_idx in range(starting_row, len(data), 3):  # Each beatmap block spans 3 rows
        beatmap_name_row = row_idx
        if len(data[beatmap_name_row]) > 4:
            beatmap_full_name = str(data[beatmap_name_row][4]).strip()
            if beatmap_full_name:
                beatmap_title = beatmap_full_name.split(" - ", 1)[-1].strip()
                beatmap_title_clean = re.sub(r'\[.*?\]', '', beatmap_title).strip().lower()
                beatmap_rows[beatmap_title_clean] = beatmap_name_row + 1
            else:
                print(f"⚠️ No beatmap name found in Row {row_idx + 1}")
        else:
            print(f"⚠️ Row {row_idx + 1} does not have enough columns.")
    print("🎵 Final Beatmap Rows Mapping:", beatmap_rows)
    return beatmap_rows

# Updated update function that uses a mapping for column D values.
def update_google_sheet_with_match_data_gui(sheet, match_data, access_token, col_d_mapping):
    data = sheet.get_all_values()

    # Build player columns mapping (starting from column G which is index 6)
    player_columns = {}
    for col_idx in range(6, len(data[3])):
        player_name = str(data[3][col_idx]).strip().lower()
        if player_name:
            player_columns[player_name] = col_idx

    print("👥 Player columns mapping:", player_columns)
    beatmap_rows = build_beatmap_rows(data)

    events = match_data.get('events', [])
    for event in events:
        game = event.get('game', None)
        if not game:
            continue

        beatmap_info = game.get('beatmap', {})
        beatmap_name = extract_beatmap_title(beatmap_info)
        print(f"🎯 Processing Beatmap: {beatmap_name}")

        if beatmap_name not in beatmap_rows:
            print(f"⚠️ Beatmap '{beatmap_name}' not found in sheet. Skipping...")
            continue

        beatmap_row_index = beatmap_rows[beatmap_name]
        # Retrieve the value from column D (index 3) from the row above the beatmap row
        try:
            col_d_value = str(data[beatmap_row_index - 1][3]).strip().lower()
        except IndexError:
            col_d_value = ""
        # Get the chosen method from the mapping; default to "score" if not set
        method = col_d_mapping.get(col_d_value, "score")
        print(f"Column D value '{col_d_value}' will use method: {method}")

        scores = game.get('scores', [])
        for score_entry in scores:
            user_id = score_entry.get('user_id')
            if not user_id:
                continue

            username = get_osu_username(user_id, access_token).strip().lower()
            print(f"🏅 Processing Score for Player: {username}")

            if username not in player_columns:
                print(f"⚠️ Player '{username}' not found in sheet headers. Skipping...")
                continue

            player_col_start = player_columns[username]
            # Choose which value to use based on the mapping selection
            if method == "accuracy":
                raw_accuracy = score_entry.get('accuracy', 0)
                score_value = format_accuracy(raw_accuracy)
                print(f"🎯 Using Accuracy: {score_value}%")
            elif method == "combo":
                # Assuming the API returns 'max_combo' (adjust if necessary)
                score_value = score_entry.get('max_combo', 0)
                print(f"🎯 Using Combo: {score_value}")
            else:  # Default: use score
                score_value = score_entry.get('score', 0)
                print(f"🎯 Using Score: {score_value}")

            max_score_slots = 4  # Limit to 4 scores per player per map
            for slot in range(max_score_slots):
                current_col = player_col_start + slot
                try:
                    cell_value = str(data[beatmap_row_index][current_col])
                except IndexError:
                    cell_value = ''
                existing_score = float(cell_value) if cell_value.replace('.', '', 1).isdigit() else 0
                if existing_score == 0:
                    sheet.update_cell(beatmap_row_index + 1, current_col + 1, score_value)
                    print(f"➕ Inserted new value for {username} on '{beatmap_name}': {score_value}")
                    break
            else:
                # All slots filled; replace the lowest if the new score is higher
                existing_scores = []
                for slot in range(max_score_slots):
                    current_col = player_col_start + slot
                    cell_value = str(data[beatmap_row_index][current_col])
                    existing_score = float(cell_value) if cell_value.replace('.', '', 1).isdigit() else 0
                    existing_scores.append((existing_score, current_col))
                min_score, min_col = min(existing_scores, key=lambda x: x[0])
                if score_value > min_score:
                    sheet.update_cell(beatmap_row_index + 1, min_col + 1, score_value)
                    print(f"✅ Updated {username}'s value on '{beatmap_name}': {min_score} → {score_value}")
                else:
                    print(f"ℹ️ No update needed for {username} on '{beatmap_name}' (Value: {score_value})")

# Utility to authenticate and get a Google Sheets client.
def authenticate_google_sheets():
    creds = ServiceAccountCredentials.from_json_keyfile_name(CREDS_FILE, SCOPE)
    client = gspread.authorize(creds)
    return client

# Function to load unique values from column D of the sheet.
def load_column_d_values(sheet):
    data = sheet.get_all_values()
    col_d_values = set()
    # Scan every row – adjust range if needed
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
        
        # Variables for inputs
        self.lobby_id_var = tk.StringVar()
        self.spreadsheet_url_var = tk.StringVar()
        self.sheet_selection_var = tk.StringVar(value=VALID_SHEETS[0])
        self.col_d_mapping = {}  # To hold the mapping from column D values to stat method
        
        self.credentials_path = None
        self.create_widgets()
    
    def create_widgets(self):
        # Upload Credentials JSON
        tk.Label(self, text="Upload Google API Credeneitals JSON:").pack(pady=5)
        tk.Button(self, text="UPLOAD JSON", command=self.upload_credentials).pack(pady=5)

        # Lobby ID (match ID)
        tk.Label(self, text="Lobby ID (Match ID):").pack(pady=5)
        tk.Entry(self, textvariable=self.lobby_id_var).pack(pady=5)

        # Spreadsheet URL
        tk.Label(self, text="Spreadsheet URL:").pack(pady=5)
        tk.Entry(self, textvariable=self.spreadsheet_url_var, width=80).pack(pady=5)

        # Sheet selection dropdown
        tk.Label(self, text="Select Sheet:").pack(pady=5)
        sheet_dropdown = ttk.Combobox(self, textvariable=self.sheet_selection_var, 
                                      values=VALID_SHEETS, state="readonly")
        sheet_dropdown.pack(pady=5)

        # Button to load Column D mappings
        tk.Button(self, text="Load Column D Mappings", command=self.load_mappings).pack(pady=10)

        # Frame to hold dynamic dropdowns for each unique Column D value
        self.mapping_frame = tk.Frame(self)
        self.mapping_frame.pack(pady=10, fill="x")

        # Run button to start the update process
        tk.Button(self, text="Run Update", command=self.run_update).pack(pady=20)

    def upload_credentials(self):
        # Open file dialog for JSON upload
        file_path = filedialog.askopenfilename(filetypes=[("JSON files", "*.json")])
        if file_path and os.path.isfile(file_path):
            self.credentials_path = file_path
            messagebox.showinfo("Success", "Google API Credentials uploaded successfully.")
        else:
            messagebox.showerror("Error", "Invalid file selected.")
    
    def authenticate_google_sheets(self):
        if not self.credentials_path:
            messagebox.showerror("Error", "Please upload Google API credentials JSON.")
            return None
        try:
            creds = ServiceAccountCredentials.from_json_keyfile_name(self.credentials_path, SCOPE)
            client = gspread.authorize(creds)
            return client
        except Exception as e:
            messagebox.showerror("Error", f"Failed to authenticate: {e}")
            return None
    
    def load_mappings(self):
        spreadsheet_url = self.spreadsheet_url_var.get().strip()
        sheet_name = self.sheet_selection_var.get().strip()
        if not spreadsheet_url:
            messagebox.showerror("Error", "Please enter a Spreadsheet URL.")
            return

        client = self.authenticate_google_sheets()
        if not client:
            return
        
        try:
            client = authenticate_google_sheets()
            spreadsheet = client.open_by_url(spreadsheet_url)
            sheet = spreadsheet.worksheet(sheet_name)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open spreadsheet: {e}")
            return
        
        # Get unique values from column D
        col_d_values = load_column_d_values(sheet)
        # Clear previous mapping widgets, if any
        for widget in self.mapping_frame.winfo_children():
            widget.destroy()
        
        tk.Label(self.mapping_frame, text="Mapping for Column D values:").pack()
        # Create a dropdown for each unique value with options: score, accuracy, combo
        self.dropdown_vars = {}
        options = ["score", "accuracy", "combo"]
        for val in col_d_values:
            frame = tk.Frame(self.mapping_frame)
            frame.pack(pady=2, anchor="w")
            tk.Label(frame, text=f"'{val}': ").pack(side="left")
            var = tk.StringVar(value="score")
            dropdown = ttk.Combobox(frame, textvariable=var, values=options, state="readonly", width=10)
            dropdown.pack(side="left")
            self.dropdown_vars[val] = var
        
        messagebox.showinfo("Info", "Column D mappings loaded. Select your options for each value.")
    
    def run_update(self):
        lobby_id = self.lobby_id_var.get().strip()
        spreadsheet_url = self.spreadsheet_url_var.get().strip()
        sheet_name = self.sheet_selection_var.get().strip()
        if not lobby_id or not spreadsheet_url:
            messagebox.showerror("Error", "Please enter all required fields.")
            return
        
        # Build the mapping dictionary from the dropdown selections.
        col_d_mapping = {}
        if hasattr(self, "dropdown_vars"):
            for key, var in self.dropdown_vars.items():
                col_d_mapping[key.lower()] = var.get()
        else:
            messagebox.showerror("Error", "Please load Column D mappings first.")
            return
        
        client = self.authenticate_google_sheets()
        if not client:
            return
        
        try:
            spreadsheet = client.open_by_url(spreadsheet_url)
            sheet = spreadsheet.worksheet(sheet_name)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open spreadsheet: {e}")
            return

        try:
            access_token = get_osu_access_token(CLIENT_ID, CLIENT_SECRET)
        except Exception as e:
            messagebox.showerror("Error", f"Osu! API authentication failed: {e}")
            return

        try:
            match_data = get_osu_match_data(lobby_id, access_token)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to fetch match data: {e}")
            return

        try:
            update_google_sheet_with_match_data_gui(sheet, match_data, access_token, col_d_mapping)
            messagebox.showinfo("Success", f"Google Sheet '{sheet_name}' updated successfully.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to update sheet: {e}")

if __name__ == "__main__":
    app = OsuSheetGUI()
    app.mainloop()
