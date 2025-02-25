import tkinter as tk
from tkinter import ttk, messagebox
import threading
from osu_google_sheet_logic import get_osu_access_token, get_osu_match_data, update_google_sheet_with_match_data, client

# ---- Predefined Sheet Names ----
VALID_SHEETS = [
    "Qualifiers", "Group Stage", "Round of 128", "Round of 64", "Round of 32",
    "Round of 16", "Quarterfinals", "Semifinals", "Finals", "Grand Finals"
]

# ---- GUI Application ----
class OsuGoogleSheetApp:
    def __init__(self, root):
        self.root = root
        self.root.title("osu! to Google Sheets")
        self.create_widgets()

    def create_widgets(self):
        # osu! Match ID
        tk.Label(self.root, text="osu! Match ID:").grid(row=0, column=0, padx=10, pady=5, sticky='w')
        self.match_id_entry = tk.Entry(self.root, width=40)
        self.match_id_entry.grid(row=0, column=1, padx=10, pady=5)

        # Google Spreadsheet URL
        tk.Label(self.root, text="Google Spreadsheet URL:").grid(row=1, column=0, padx=10, pady=5, sticky='w')
        self.spreadsheet_url_entry = tk.Entry(self.root, width=60)
        self.spreadsheet_url_entry.grid(row=1, column=1, padx=10, pady=5)

        # Sheet Selection Dropdown (Predefined List)
        tk.Label(self.root, text="Select Sheet:").grid(row=2, column=0, padx=10, pady=5, sticky='w')
        self.sheet_var = tk.StringVar()
        self.sheet_dropdown = ttk.Combobox(self.root, textvariable=self.sheet_var, state="readonly")
        self.sheet_dropdown['values'] = VALID_SHEETS
        self.sheet_dropdown.grid(row=2, column=1, padx=10, pady=5)
        self.sheet_dropdown.set(VALID_SHEETS[0])  # Default to first sheet

        # Run Button
        self.run_button = tk.Button(self.root, text="Run", command=self.run_threaded)
        self.run_button.grid(row=3, column=0, columnspan=2, pady=10)

        # Log/Output Text Box
        self.log_text = tk.Text(self.root, height=15, width=80, state='disabled')
        self.log_text.grid(row=4, column=0, columnspan=2, padx=10, pady=10)

    def log(self, message):
        """Logs messages to the GUI text area."""
        self.log_text.config(state='normal')
        self.log_text.insert(tk.END, message + '\n')
        self.log_text.config(state='disabled')
        self.log_text.see(tk.END)

    def run_threaded(self):
        """Run the main process in a separate thread to avoid UI freezing."""
        thread = threading.Thread(target=self.run)
        thread.start()

    def run(self):
        match_id = self.match_id_entry.get()
        spreadsheet_url = self.spreadsheet_url_entry.get()
        selected_sheet = self.sheet_var.get()

        if not match_id or not spreadsheet_url or not selected_sheet:
            messagebox.showerror("Error", "Please fill in all fields.")
            return

        try:
            # Step 1: Authenticate with osu! API
            self.log("🔑 Authenticating with osu! API...")
            access_token = get_osu_access_token('38538', '1Eoq9oBjODYkT3VFfwDcJZq4iLkD76dEP1QCUDge')
            self.log("✅ Authenticated with osu! API.")

            # Step 2: Fetch Match Data
            self.log(f"📋 Fetching match data for match ID {match_id}...")
            match_data = get_osu_match_data(match_id, access_token)
            self.log("📋 Retrieved match data.")

            # Step 3: Connect to Google Sheet
            self.log(f"📋 Connecting to Google Spreadsheet...")
            spreadsheet = client.open_by_url(spreadsheet_url)
            sheet = spreadsheet.worksheet(selected_sheet)
            self.log(f"✅ Connected to Google Sheet: {selected_sheet}")

            # Step 4: Update Google Sheet
            self.log(f"📋 Updating Google Sheet '{selected_sheet}'...")
            update_google_sheet_with_match_data(sheet, match_data, access_token)
            self.log(f"✅ Google Sheet '{selected_sheet}' updated successfully.")

        except Exception as e:
            self.log(f"❌ Error: {e}")
            messagebox.showerror("Error", f"An error occurred: {e}")

# ---- Run the Application ----
if __name__ == "__main__":
    root = tk.Tk()
    app = OsuGoogleSheetApp(root)
    root.mainloop()
