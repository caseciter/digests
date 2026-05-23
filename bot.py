import logging
import requests
from io import BytesIO
from pypdf import PdfReader
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

DEFAULT_KEYWORDS = ["insc", "scc", "fundamental", "religion"]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Welcome! Send me a PDF link, then either click one of the keyword buttons or type the keyword directly."
    )

async def process_pdf_search(chat_id: int, context: ContextTypes.DEFAULT_TYPE, pdf_url: str, keyword: str, status_msg_id: int = None) -> None:
    if status_msg_id:
        try:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=status_msg_id,
                text=f"⏳ Downloading and searching for '{keyword}'... Please wait.",
                reply_markup=None # Remove buttons immediately
            )
        except Exception:
            # Fallback if the message can't be edited
            new_msg = await context.bot.send_message(chat_id=chat_id, text=f"⏳ Downloading and searching for '{keyword}'... Please wait.")
            status_msg_id = new_msg.message_id
    else:
        new_msg = await context.bot.send_message(chat_id=chat_id, text=f"⏳ Downloading and searching for '{keyword}'... Please wait.")
        status_msg_id = new_msg.message_id
    
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
            
            try:
                await context.bot.delete_message(chat_id=chat_id, message_id=status_msg_id)
            except Exception:
                pass
            await context.bot.send_message(chat_id=chat_id, text=output, parse_mode="Markdown")
        else:
            await context.bot.send_message(chat_id=chat_id, text=f"🔍 Finished searching. Keyword '{keyword}' not found.")

    except Exception as e:
        logger.error(f"Error processing PDF: {e}")
        await context.bot.send_message(chat_id=chat_id, text="❌ Failed to complete the search. Verify the URL is valid.")

async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if len(context.args) < 2:
        await update.message.reply_text("❌ Use: `/search <url> <keyword>`")
        return
    pdf_url = context.args[0]
    keyword = " ".join(context.args[1:])
    await process_pdf_search(update.effective_chat.id, context, pdf_url, keyword)

# Smart handler that deals with BOTH links and typed words
async def handle_text_messages(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text.strip()
    
    # 1. If it's a link, offer the menu
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
        return

    # 2. If it's a word, check if we have a saved PDF link in active memory
    saved_url = context.user_data.get("current_pdf_url")
    if saved_url:
        # User typed the keyword instead of clicking (Exactly what happened in your screenshot!)
        await process_pdf_search(update.effective_chat.id, context, saved_url, text)
    else:
        await update.message.reply_text("Please send a valid PDF link first.")

async def handle_button_click(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    data_parts = query.data.split("|")
    if data_parts[0] == "kw":
        selected_keyword = data_parts[1]
        pdf_url = context.user_data.get("current_pdf_url")

        if not pdf_url:
            await query.edit_message_text("❌ Session expired. Please paste the PDF link again.")
            return

        await process_pdf_search(
            chat_id=query.message.chat_id,
            context=context,
            pdf_url=pdf_url,
            keyword=selected_keyword,
            status_msg_id=query.message.message_id
        )

def main() -> None:
    import os
    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    if not TOKEN:
        logger.error("No TELEGRAM_BOT_TOKEN found.")
        return

    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("search", search_command))
    
    # Unified text handler catches links AND fallback text entries
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_messages))
    application.add_handler(CallbackQueryHandler(handle_button_click))

    logger.info("Bot is polling with fallback parsing engine active...")
    application.run_polling()

if __name__ == "__main__":
    main()
