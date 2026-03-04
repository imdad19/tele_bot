# 🛍️ Istanbul Market Explorer Bot

Track prices across Istanbul stores → auto-logs to Google Sheets.

## You need to do exactly 3 things:

### 1. Enable Google Sheets API (2 min)
1. Go to → https://console.cloud.google.com/apis/library/sheets.googleapis.com
2. Make sure project `656764171061` is selected (top-left dropdown)
3. Click **Enable**

### 2. Add your Google Sheet ID to `.env` (1 min)
1. Create a blank Google Sheet at https://sheets.google.com
2. Copy the ID from the URL:
   `https://docs.google.com/spreadsheets/d/ ← THIS PART → /edit`
3. Open `.env` and replace `PASTE_YOUR_SHEET_ID_HERE` with it

### 3. Run the bot (1 min)
```bash
# Mac / Linux:
bash run.sh

# Windows:
pip install -r requirements.txt
python authorize.py    ← first time only, opens browser
python bot.py
```

The browser will open once for Google login — approve it — then the bot starts. That's it! 🎉

---

## Using the bot

| Action | How |
|--------|-----|
| Log an item | Type: `Nike shoes 1200 TL Grand Bazaar` |
| Photo of price tag | Send any photo (caption optional) |
| Voice note | Send a voice message |
| Compare prices | `/compare Nike` |
| Recent entries | `/list` |
| All stores | `/stores` |

## Input examples
```
Adidas Superstar 950 TL Kapalıçarşı
iPhone 15 Pro 44000 TL Cevahir AVM
saffron 50g 280 TL Mısır Çarşısı
leather jacket 3500 TL Grand Bazaar Beyoğlu
```
