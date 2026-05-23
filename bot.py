import logging
import requests
from io import BytesIO
from pypdf import PdfReader
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Predefined keywords to show as options
DEFAULT_KEYWORDS = ["insc", "scc", "fundamental", "religion"]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Welcome! You can search a PDF by doing one of the following:\n\n"
        "1. Send just the PDF link, and I will let you choose a quick keyword.\n"
        "2. Type: `/search <PDF_URL> <KEYWORD>`"
    )

# Core logic to download and search the PDF
async def process_pdf_search(update: Update, context: ContextTypes.DEFAULT_TYPE, pdf_url: str, keyword: str, status_msg=None) -> None:
    # Send a fresh status message if one wasn't passed from the button click
    if not status_msg:
        status_msg = await update.message.reply_text(f"⏳ Downloading and searching for '{keyword}'... Please wait.")
    
    keyword = keyword.lower()

    try:
        response = requests.get(pdf_url, timeout=15)
        response.raise_for_status()
        
        pdf_file = BytesIO(response.content)
        reader = PdfReader(pdf_file)
        found_paragraphs = []

        for page_num, page in enumerate(reader.pages, start=1):
            text = page.extract_text()
            if not text:
                continue
                
            paragraphs = text.split("\n\n")
            for para in paragraphs:
                para_clean = para.strip()
                if keyword in para_clean.lower():
                    found_paragraphs.append(f"📄 *[Page {page_num}]*\n{para_clean}")

        if found_paragraphs:
            output = "\n\n---\n\n".join(found_paragraphs)
            if len(output) > 4000:
                output = output[:4000] + "\n\n...(truncated due to length limit)"
            
            # Delete the status message and send the markdown payload cleanly
            await status_msg.delete()
            await context.bot.send_message(chat_id=status_msg.chat_id, text=output, parse_mode="Markdown")
        else:
            await status_msg.edit_text(f"🔍 Finished searching. Keyword '{keyword}' not found in the text.")

    except Exception as e:
        logger.error(f"Error processing PDF: {e}")
        await status_msg.edit_text("❌ Failed to complete the search. Verify the URL is a direct path to a valid PDF.")

# Handle explicitly typed command: /search URL keyword
async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if len(context.args) < 2:
        await update.message.reply_text("❌ Missing arguments. Use: `/search <url> <keyword>`")
        return
    pdf_url = context.args[0]
    keyword = " ".join(context.args[1:])
    await process_pdf_search(update, context, pdf_url, keyword)

# Handle a raw text link sent without a command
async def handle_raw_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text.strip()
    
    if text.startswith("http://") or text.startswith("https://"):
        keyboard = []
        for kw in DEFAULT_KEYWORDS:
            keyboard.append([InlineKeyboardButton(text=kw.upper(), callback_data=f"kw|{kw}")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        context.user_data["current_pdf_url"] = text
        
        await update.message.reply_text(
            "📋 I detected a PDF link! Select a keyword to search below:",
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text("Please send a valid HTTP/HTTPS link to a PDF document.")

# Handle button interactions
async def handle_button_click(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()  # Tell Telegram the click was registered immediately

    data_parts = query.data.split("|")
    if data_parts[0] == "kw":
        selected_keyword = data_parts[1]
        pdf_url = context.user_data.get("current_pdf_url")

        if not pdf_url:
            await query.edit_message_text("❌ Session expired. Please paste the PDF link again.")
            return

        # CRITICAL FIX: Erase the buttons and alter text to state progress to avoid UI lock
        status_msg = await query.edit_message_text(
            text=f"⏳ Downloading and searching for '{selected_keyword}'... Please wait.", 
            reply_markup=None  # This explicitly deletes the keyboard block
        )

        # Execute search passing the clean status message handle
        await process_pdf_search(update, context, pdf_url, selected_keyword, status_msg=status_msg)

def main() -> None:
    import os
    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    if not TOKEN:
        logger.error("No TELEGRAM_BOT_TOKEN found in environment variables.")
        return

    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("search", search_command))
    application.add_handler(filters.TEXT & ~filters.COMMAND, handle_raw_link))
    application.add_handler(CallbackQueryHandler(handle_button_click))

    logger.info("Bot is polling with fixed keyboard execution...")
    application.run_polling()

if __name__ == "__main__":
    main()
