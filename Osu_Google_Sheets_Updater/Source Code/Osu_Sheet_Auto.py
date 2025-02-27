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
    print(f"🔍 DEBUG: Raw Beatmap Info -> {beatmap_info}")
    if not beatmap_info:
        return "Unknown Beatmap"

    beatmap_title = (
        beatmap_info.get('title') or
        beatmap_info.get('title_unicode') or
        beatmap_info.get('beatmapset', {}).get('title') or
        beatmap_info.get('version') or
        'Unknown Beatmap'
    )

    return re.sub(r'\[.*?\]', '', beatmap_title).strip().lower()

def format_accuracy(accuracy):
    return round(accuracy * 100, 2)

def load_column_d_values(sheet):
    data = sheet.get_all_values()
    return list(set(row[3].strip().lower() for row in data if len(row) > 3 and row[3].strip()))

def build_beatmap_rows(data):
    beatmap_rows = {}
    starting_row = 8  

    print("\n🔍 DEBUG: Building Beatmap Rows Mapping:")
    for row_idx in range(starting_row, len(data), 3):
        if len(data[row_idx]) > 4:
            beatmap_title = str(data[row_idx][4]).split(" - ", 1)[-1].strip()
            beatmap_rows[re.sub(r'\[.*?\]', '', beatmap_title).strip().lower()] = row_idx + 1

    print("🎵 DEBUG: Final Beatmap Rows Mapping:", beatmap_rows)
    return beatmap_rows

def get_osu_username(user_id, access_token):
    user_url = f'https://osu.ppy.sh/api/v2/users/{user_id}'
    headers = {'Authorization': f'Bearer {access_token}'}
    response = requests.get(user_url, headers=headers)

    if response.status_code == 200:
        user_data = response.json()
        return user_data.get('username', f'Unknown_{user_id}')
    else:
        print(f"⚠️ WARNING: Failed to fetch username for User ID {user_id}. Response: {response.text}")
        return f'Unknown_{user_id}'

def update_google_sheet_with_match_data_gui(sheet, match_data, access_token, col_d_mapping):
    data = sheet.get_all_values()
    player_columns = {str(data[3][i]).strip().lower(): i for i in range(6, len(data[3])) if str(data[3][i]).strip()}
    beatmap_rows = build_beatmap_rows(data)

    for event in match_data.get('events', []):
        game = event.get('game')
        if not game:
            continue

        beatmap_name = extract_beatmap_title(game.get('beatmap', {}))
        print(f"🎯 Processing Beatmap: {beatmap_name}")

        if beatmap_name not in beatmap_rows:
            print(f"⚠️ WARNING: Beatmap '{beatmap_name}' not found in sheet. Skipping...")
            continue

        beatmap_row_index = beatmap_rows[beatmap_name]
        print(f"✅ Found '{beatmap_name}' in row {beatmap_row_index + 1}")

        method = col_d_mapping.get(str(data[beatmap_row_index - 1][3]).strip().lower(), "score")
        print(f"📊 Using '{method}' method for '{beatmap_name}'")

        for score_entry in game.get('scores', []):
            user_id = score_entry.get('user_id')
            if not user_id:
                continue

            username = get_osu_username(user_id, access_token).lower()
            print(f"🏅 Checking score for {username}")

            if username not in player_columns:
                print(f"⚠️ Player '{username}' not found in sheet. Skipping...")
                continue  

            player_col_start = player_columns[username]
            print(f"Player score column start: {player_col_start}")
            score_columns = [player_col_start + i for i in range(4)]  # The 4 score columns for this player

            score_value = (
                format_accuracy(score_entry.get('accuracy', 0)) if method == "accuracy" else
                score_entry.get('max_combo', 0) if method == "combo" else
                score_entry.get('score', 0)
            )

            print(f"📥 Score to insert: {score_value}")

            # Extract current scores, treating empty cells as 0
            current_scores = []
            for col in score_columns:
                try:
                    cell_value = str(data[beatmap_row_index][col])
                except IndexError:
                    cell_value = ''

                if cell_value.replace('.', '', 1).isdigit():
                    current_scores.append(int(cell_value))
                else:
                    current_scores.append(0)  # Empty slots are treated as 0

            print(f"🔍 Current score list: {current_scores}")

            # Step 1: Insert score in the first available empty slot (0)
            if 0 in current_scores:
                first_empty_index = current_scores.index(0)
                current_scores[first_empty_index] = score_value
                print(f"✅ Inserted '{score_value}' into first available slot at index {first_empty_index}")
            else:
                # Step 2: If all slots are full, replace the lowest score if the new score is higher
                min_score = min(current_scores)
                if score_value > min_score:
                    min_index = current_scores.index(min_score)
                    current_scores[min_index] = score_value
                    print(f"✅ Replaced lowest score {min_score} → {score_value} at index {min_index}")
                else:
                    print(f"ℹ️ No update needed. Score '{score_value}' is not higher than existing scores.")

            print(f"🔄 Updated score list: {current_scores}")

            # Step 3: Write updated scores back to the sheet **after each score update**
            for i, new_score in enumerate(current_scores):
                cell_value = new_score if new_score != 0 else ''
                sheet.update_cell(beatmap_row_index + 1, score_columns[i] + 1, cell_value)
                print(f"🔃 Updated cell ({beatmap_row_index + 1}, {score_columns[i] + 1}) → {cell_value}")

            # **After every score update, refresh the sheet data for accurate processing of next scores**
            data = sheet.get_all_values()



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
            print(f"✅ DEBUG: JSON File Uploaded -> {self.credentials_path}")  # Debugging print
            messagebox.showinfo("Success", f"Google API Credentials uploaded: {os.path.basename(file_path)}")
        else:
            messagebox.showerror("Error", "Invalid file selected.")

    def authenticate_google_sheets(self):
        """ Authenticate Google Sheets API using the uploaded JSON file """
        if not self.credentials_path:
            messagebox.showerror("Error", "Please upload Google API credentials JSON first.")
            return None
        try:
            print(f"🔍 DEBUG: Using JSON Path -> {self.credentials_path}")  # Debugging print
            creds = ServiceAccountCredentials.from_json_keyfile_name(self.credentials_path, SCOPE)
            client = gspread.authorize(creds)
            return client
        except Exception as e:
            messagebox.showerror("Error", f"Failed to authenticate: {e}")
            return None

    def load_mappings(self):
        """ Loads Column D values and creates dropdown mappings """
        if not self.credentials_path:
            messagebox.showerror("Error", "Please upload Google API credentials JSON first.")
            return

        client = self.authenticate_google_sheets()
        if not client:
            return

        try:
            sheet = client.open_by_url(self.spreadsheet_url_var.get().strip()).worksheet(self.sheet_selection_var.get())
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open spreadsheet: {e}")
            return

        col_d_values = load_column_d_values(sheet)

        # Clear previous mapping widgets
        for widget in self.mapping_frame.winfo_children():
            widget.destroy()

        tk.Label(self.mapping_frame, text="Mapping for Column D values:").pack()

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
