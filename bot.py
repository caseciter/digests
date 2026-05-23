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
async def process_pdf_search(update_or_query, context: ContextTypes.DEFAULT_TYPE, pdf_url: str, keyword: str) -> None:
    # This handles both direct text messages and button clicks smoothly
    is_callback = hasattr(update_or_query, "message") == False
    send_message_func = update_or_query.edit_message_text if is_callback else update_or_query.reply_text

    await send_message_func(f"⏳ Downloading and searching for '{keyword}'... Please wait.")
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
            
            # Send message back (handling formatting correctly)
            if is_callback:
                await update_or_query.message.reply_text(output, parse_mode="Markdown")
            else:
                await update_or_query.reply_text(output, parse_mode="Markdown")
        else:
            final_text = f"🔍 Finished searching. Keyword '{keyword}' not found in the text."
            if is_callback:
                await update_or_query.message.reply_text(final_text)
            else:
                await update_or_query.reply_text(final_text)

    except Exception as e:
        logger.error(f"Error processing PDF: {e}")
        error_text = "❌ Failed to complete the search. Verify the URL is a direct path to a valid PDF."
        if is_callback:
            await update_or_query.message.reply_text(error_text)
        else:
            await update_or_query.reply_text(error_text)

# Handle explicitly typed command: /search URL keyword
async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if len(context.args) < 2:
        await update.message.reply_text("❌ Missing arguments. Use: `/search <url> <keyword>`")
        return
    pdf_url = context.args[0]
    keyword = " ".join(context.args[1:])
    await process_pdf_search(update.message, context, pdf_url, keyword)

# Handle a raw text link sent without a command
async def handle_raw_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text.strip()
    
    # Basic structural check to see if it looks like a URL
    if text.startswith("http://") or text.startswith("https://"):
        # Build button matrix dynamically
        keyboard = []
        for kw in DEFAULT_KEYWORDS:
            # Storing target url and chosen keyword in callback_data payload
            keyboard.append([InlineKeyboardButton(text=kw.upper(), callback_data=f"kw|{kw}")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Save the URL temporarily in user data context so we can access it on button click
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
    await query.answer() # Acknowledge interaction quickly

    data_parts = query.data.split("|")
    if data_parts[0] == "kw":
        selected_keyword = data_parts[1]
        pdf_url = context.user_data.get("current_pdf_url")

        if not pdf_url:
            await query.edit_message_text("❌ Session expired. Please paste the PDF link again.")
            return

        # Execute search
        await process_pdf_search(query, context, pdf_url, selected_keyword)

def main() -> None:
    import os
    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    if not TOKEN:
        logger.error("No TELEGRAM_BOT_TOKEN found in environment variables.")
        return

    application = Application.builder().token(TOKEN).build()

    # Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("search", search_command))
    
    # Catch-all text messages that look like URLs
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_raw_link))
    
    # Handle button inputs
    application.add_handler(CallbackQueryHandler(handle_button_click))

    logger.info("Bot is polling with instant keyword menus...")
    application.run_polling()

if __name__ == "__main__":
    main()
