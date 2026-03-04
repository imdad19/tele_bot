import os
from dotenv import load_dotenv
load_dotenv()
import json
import logging
import asyncio
from datetime import datetime, timezone
from typing import List, Dict
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
TOKEN_FILE = "token.json"
HEADERS = ["Timestamp", "Product", "Price", "Currency", "Store", "Location", "Category", "Notes", "User"]


def _load_credentials():
    if not os.path.exists(TOKEN_FILE):
        raise FileNotFoundError("token.json not found — run authorize.py first")

    with open(TOKEN_FILE) as f:
        data = json.load(f)

    # Parse expiry — token.json stores it as ISO string
    expiry = None
    if data.get("expiry"):
        try:
            expiry = datetime.fromisoformat(data["expiry"].replace("Z", "+00:00")).replace(tzinfo=None)
        except Exception:
            pass

    creds = Credentials(
        token=data["token"],
        refresh_token=data["refresh_token"],
        token_uri=data["token_uri"],
        client_id=data["client_id"],
        client_secret=data["client_secret"],
        scopes=data["scopes"],
        universe_domain=data.get("universe_domain", "googleapis.com")
    )

    # Manually set expiry so google knows it's expired
    if expiry:
        creds.expiry = expiry

    # Always refresh — access tokens expire after 1 hour, refresh token is permanent
    if not creds.valid or creds.expired:
        logger.info("Refreshing expired access token...")
        creds.refresh(Request())
        # Save updated token back to file
        data["token"] = creds.token
        data["expiry"] = creds.expiry.isoformat() if creds.expiry else ""
        with open(TOKEN_FILE, "w") as f:
            json.dump(data, f, indent=2)
        logger.info("Token refreshed and saved.")

    return creds


class SheetsHandler:
    def __init__(self):
        self.spreadsheet_id = os.environ.get("GOOGLE_SHEET_ID")
        self._service = None
        self._creds = None

    def _get_service(self):
        # Rebuild service if credentials expired or not yet created
        if self._service and self._creds and self._creds.valid:
            return self._service
        self._creds = _load_credentials()
        self._service = build("sheets", "v4", credentials=self._creds)
        return self._service

    async def _ensure_headers(self):
        try:
            service = self._get_service()
            result = service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range="Sheet1!A1:Z1"
            ).execute()
            if not result.get("values"):
                service.spreadsheets().values().update(
                    spreadsheetId=self.spreadsheet_id,
                    range="Sheet1!A1",
                    valueInputOption="RAW",
                    body={"values": [HEADERS]}
                ).execute()
        except Exception as e:
            logger.warning(f"Header setup error: {e}")

    async def add_entry(self, record: Dict) -> bool:
        await self._ensure_headers()
        row = [
            record.get("timestamp", ""),
            record.get("product", ""),
            record.get("price", ""),
            record.get("currency", "TL"),
            record.get("store", ""),
            record.get("location", ""),
            record.get("category", ""),
            record.get("notes", ""),
            record.get("user", ""),
        ]
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._append_row, row)
        return True

    def _append_row(self, row: list):
        service = self._get_service()
        service.spreadsheets().values().append(
            spreadsheetId=self.spreadsheet_id,
            range="Sheet1!A:I",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": [row]}
        ).execute()

    async def search_product(self, query: str) -> List[Dict]:
        all_rows = await self._get_all_rows()
        query_lower = query.lower()
        return [
            r for r in all_rows
            if any(word in r.get("product", "").lower() for word in query_lower.split())
        ]

    async def get_recent(self, n: int = 10) -> List[Dict]:
        all_rows = await self._get_all_rows()
        return all_rows[-n:]

    async def get_stores(self) -> List[str]:
        all_rows = await self._get_all_rows()
        return list(set(r.get("store", "") for r in all_rows if r.get("store")))

    async def _get_all_rows(self) -> List[Dict]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._fetch_all_rows)

    def _fetch_all_rows(self) -> List[Dict]:
        try:
            service = self._get_service()
            result = service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range="Sheet1!A:I"
            ).execute()
            values = result.get("values", [])
            if len(values) < 2:
                return []
            headers = [h.lower() for h in values[0]]
            return [
                dict(zip(headers, row + [""] * (len(headers) - len(row))))
                for row in values[1:]
            ]
        except Exception as e:
            logger.error(f"Sheet fetch error: {e}")
            return []
