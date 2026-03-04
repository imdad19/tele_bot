from dotenv import load_dotenv
load_dotenv()
import os
from sheets_handler import _load_credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

print("Loading credentials...")
creds = _load_credentials()
print(f"Token valid: {creds.valid}")
print(f"Token expired: {creds.expired}")
print(f"Token value: {creds.token[:20]}...")

sheet_id = os.environ['GOOGLE_SHEET_ID']
print(f"Sheet ID: {sheet_id}")

service = build("sheets", "v4", credentials=creds)

print("\nTesting sheet access...")
try:
    info = service.spreadsheets().get(spreadsheetId=sheet_id).execute()
    print(f"Sheet title: {info['properties']['title']}")
except HttpError as e:
    print(f"GET error: {e.status_code} - {e.error_details}")

print("\nTesting write...")
try:
    result = service.spreadsheets().values().append(
        spreadsheetId=sheet_id,
        range="Sheet1!A:I",
        valueInputOption="RAW",
        insertDataOption="INSERT_ROWS",
        body={"values": [["test","test","10","TL","store","","General","","me"]]}
    ).execute()
    print(f"Write success: {result}")
except HttpError as e:
    print(f"WRITE error: {e.status_code} - {e.error_details}")
    print(f"Full error: {e}")
