import gspread
import traceback
from google.oauth2.service_account import Credentials

# --- CONFIGURATION ---
SHEET_NAME = "test" 
CREDENTIALS_FILE = "credentials.json"

def debug_connection():
    print(f"--- DIAGNOSTIC START (gspread v{gspread.__version__}) ---")
    
    # 1. Load Credentials
    try:
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        creds = Credentials.from_service_account_file(
            CREDENTIALS_FILE, scopes=scopes
        )
        client = gspread.authorize(creds)
        print("✅ Credentials loaded.")
        print(f"   - Service Account Email: {creds.service_account_email}")
    except Exception:
        print("❌ Failed to load credentials.")
        traceback.print_exc()
        return

    # 2. List all visible sheets
    # This proves if the Service Account has permission to see ANY files
    print("\n--- CHECKING VISIBILITY ---")
    try:
        files = client.list_spreadsheet_files()
        print(f"Service Account can see {len(files)} file(s):")
        for f in files:
            print(f"   - Found: '{f['name']}' (ID: {f['id']})")
            
        # Check if our target is in the list
        target_found = any(f['name'] == SHEET_NAME for f in files)
        if target_found:
            print(f"✅ Target sheet '{SHEET_NAME}' found in list.")
        else:
            print(f"❌ Target sheet '{SHEET_NAME}' NOT found in the list above.")
            print("   (Did you share the sheet with the email printed above?)")
    except Exception:
        print("⚠️ Could not list files (might be a permission scope issue, skipping).")

    # 3. Attempt to Open and Write
    print(f"\n--- ATTEMPTING WRITE TO '{SHEET_NAME}' ---")
    try:
        sheet = client.open(SHEET_NAME).sheet1
        print(f"✅ Opened tab: {sheet.title}")
        
        print("   Attempting append_row...")
        result = sheet.append_row(["Debug", "Test", "123", "Success"])
        print(f"✅ Success! Result: {result}")
        
    except Exception as e:
        print(f"❌ OPERATION FAILED.")
        print(f"   Error Type: {type(e).__name__}")
        print(f"   Error Message: {e}")
        print("\nFull Traceback:")
        traceback.print_exc()

if __name__ == "__main__":
    debug_connection()