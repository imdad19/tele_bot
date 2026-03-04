import os
from dotenv import load_dotenv
load_dotenv()
import json
import logging
import asyncio
import tempfile
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes, CallbackQueryHandler
)
from ai_parser import parse_product_entry
from sheets_handler import SheetsHandler


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Initialize handlers
sheets = SheetsHandler()



# ── /start ──────────────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🛍️ *Istanbul Market Explorer Bot*\n\n"
        "Track prices across stores while you explore!\n\n"
        "*How to log an item:*\n"
        "• 📝 Type: `Nike shoes 850 TL Grand Bazaar`\n"
        "• 📸 Send a photo of the price tag\n"
        "• 🎤 Send a voice message describing it\n\n"
        "*Commands:*\n"
        "/compare `<product>` — Compare prices for an item\n"
        "/list — Show recent entries\n"
        "/stores — List all tracked stores\n"
        "/help — Show this message\n\n"
        "Just start sending items! 🚀",
        parse_mode="Markdown"
    )


# ── /help ────────────────────────────────────────────────────────────────────
async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start(update, context)


# ── Text messages ─────────────────────────────────────────────────────────────
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    # Skip if it's a command
    if text.startswith("/"):
        return

    msg = await update.message.reply_text("⏳ Parsing your entry...")
    await _process_entry(update, context, text, msg)


# ── Photos ────────────────────────────────────────────────────────────────────
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("📸 Reading price tag...")

    caption = update.message.caption or ""
    photo = update.message.photo[-1]  # highest resolution
    file = await context.bot.get_file(photo.file_id)

    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        await file.download_to_drive(tmp.name)
        tmp_path = tmp.name

    # Pass image path + caption to AI parser
    combined = f"[IMAGE:{tmp_path}] {caption}".strip()
    await _process_entry(update, context, combined, msg)

    try:
        os.unlink(tmp_path)
    except Exception:
        pass


# ── Voice messages ────────────────────────────────────────────────────────────
async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("🎤 Transcribing your voice note...")

    voice = update.message.voice
    file = await context.bot.get_file(voice.file_id)

    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
        await file.download_to_drive(tmp.name)
        tmp_path = tmp.name

    combined = f"[VOICE:{tmp_path}]"
    await _process_entry(update, context, combined, msg)

    try:
        os.unlink(tmp_path)
    except Exception:
        pass


# ── Core processing ───────────────────────────────────────────────────────────
async def _process_entry(update: Update, context: ContextTypes.DEFAULT_TYPE, raw_input: str, status_msg):
    try:
        parsed = await parse_product_entry(raw_input)

        if not parsed or not parsed.get("product"):
            await status_msg.edit_text(
                "❌ Couldn't parse that. Try: `Product name  Price  Store`\n"
                "Example: `Adidas sneakers 1200 TL Taksim`",
                parse_mode="Markdown"
            )
            return

        # Build record
        record = {
            "product": parsed.get("product", "Unknown"),
            "price": parsed.get("price", ""),
            "currency": parsed.get("currency", "TL"),
            "store": parsed.get("store", "Unknown"),
            "location": parsed.get("location", ""),
            "category": parsed.get("category", "General"),
            "notes": parsed.get("notes", ""),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "user": update.effective_user.first_name or "User"
        }

        # Save to Google Sheets
        try:
            await sheets.add_entry(record)
            sheets_status = "📊 Google Sheets ✅"
        except Exception as e:
            sheets_status = f"📊 Google Sheets ❌ ({str(e)[:50]})"

        # Build confirmation message
        price_str = f"{record['price']} {record['currency']}" if record['price'] else "price not detected"
        store_str = record['store'] if record['store'] != "Unknown" else "store not detected"

        await status_msg.edit_text(
            f"✅ *Logged!*\n\n"
            f"🏷️ *{record['product']}*\n"
            f"💰 {price_str}\n"
            f"🏪 {store_str}\n"
            f"📁 {record['category']}\n"
            f"🕐 {record['timestamp']}\n\n"
            f"{sheets_status}",
            parse_mode="Markdown"
        )

    except Exception as e:
        logger.exception("Error processing entry")
        await status_msg.edit_text(f"❌ Error: {str(e)[:100]}\n\nTry again or use /help")


# ── /compare ──────────────────────────────────────────────────────────────────
async def compare(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /compare Nike shoes")
        return

    query = " ".join(context.args)
    msg = await update.message.reply_text(f"🔍 Searching for *{query}*...", parse_mode="Markdown")

    results = await sheets.search_product(query)

    if not results:
        await msg.edit_text(f"No entries found for *{query}*. Start logging prices!", parse_mode="Markdown")
        return

    # Sort by price
    try:
        results.sort(key=lambda x: float(str(x.get("price", "0")).replace(",", ".")))
    except Exception:
        pass

    lines = [f"🔍 *Price comparison: {query}*\n"]
    for i, r in enumerate(results[:10], 1):
        medal = ["🥇", "🥈", "🥉"][i - 1] if i <= 3 else f"{i}."
        price_str = f"{r.get('price', '?')} {r.get('currency', 'TL')}"
        lines.append(f"{medal} *{r.get('store', 'Unknown')}* — {price_str}")
        if r.get("location"):
            lines[-1] += f" _({r['location']})_"

    if len(results) > 1:
        try:
            prices = [float(str(r.get("price", 0)).replace(",", ".")) for r in results if r.get("price")]
            if prices:
                diff = max(prices) - min(prices)
                currency = results[0].get("currency", "TL")
                lines.append(f"\n💡 Price range: *{diff:.0f} {currency}* difference")
        except Exception:
            pass

    await msg.edit_text("\n".join(lines), parse_mode="Markdown")


# ── /list ─────────────────────────────────────────────────────────────────────
async def list_entries(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("📋 Fetching recent entries...")
    entries = await sheets.get_recent(10)

    if not entries:
        await msg.edit_text("No entries yet! Start logging prices 🛍️")
        return

    lines = ["📋 *Last 10 entries:*\n"]
    for e in entries:
        price_str = f"{e.get('price', '?')} {e.get('currency', 'TL')}"
        lines.append(f"• *{e.get('product', '?')}* — {price_str} @ {e.get('store', '?')}")

    await msg.edit_text("\n".join(lines), parse_mode="Markdown")


# ── /stores ───────────────────────────────────────────────────────────────────
async def stores(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("🏪 Fetching stores...")
    store_list = await sheets.get_stores()

    if not store_list:
        await msg.edit_text("No stores logged yet!")
        return

    lines = ["🏪 *Tracked stores:*\n"] + [f"• {s}" for s in sorted(store_list)]
    await msg.edit_text("\n".join(lines), parse_mode="Markdown")


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("compare", compare))
    app.add_handler(CommandHandler("list", list_entries))
    app.add_handler(CommandHandler("stores", stores))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))

    logger.info("Bot started...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
