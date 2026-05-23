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

# Predefined keywords to show as quick-select options
DEFAULT_KEYWORDS = ["insc", "scc", "fundamental", "religion"]

# The core base domain path parsed from your custom system link
BASE_URL_PREFIX = "https://cdn.sci-notifier.codechips.in/orders/"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Welcome! Send me a PDF link, then either click one of the keyword buttons (including 'ALL') or type your own keyword directly."
    )

async def process_pdf_search(chat_id: int, context: ContextTypes.DEFAULT_TYPE, pdf_url: str, target_keywords: list, status_msg_id: int = None) -> None:
    display_keywords = ", ".join([kw.upper() for kw in target_keywords])
    
    # Send or edit status message
    if status_msg_id:
        try:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=status_msg_id,
                text=f"⏳ Downloading and searching for '{display_keywords}'... Please wait.",
                reply_markup=None  # Clears buttons immediately
            )
        except Exception:
            new_msg = await context.bot.send_message(chat_id=chat_id, text=f"⏳ Downloading and searching for '{display_keywords}'... Please wait.")
            status_msg_id = new_msg.message_id
    else:
        new_msg = await context.bot.send_message(chat_id=chat_id, text=f"⏳ Downloading and searching for '{display_keywords}'... Please wait.")
        status_msg_id = new_msg.message_id

    try:
        response = requests.get(pdf_url, timeout=15)
        response.raise_for_status()
        
        pdf_file = BytesIO(response.content)
        reader = PdfReader(pdf_file)
        
        match_counter = 1
        found_any_match = False

        for page_num, page in enumerate(reader.pages, start=1):
            text = page.extract_text()
            if not text:
                continue
                
            paragraphs = text.split("\n\n")
            for para in paragraphs:
                para_clean = para.strip()
                if not para_clean:
                    continue
                
                matched_keywords_in_para = []
                for kw in target_keywords:
                    if kw.lower() in para_clean.lower():
                        matched_keywords_in_para.append(kw)

                if matched_keywords_in_para:
                    found_any_match = True
                    found_kw_str = ", ".join(matched_keywords_in_para)
                    
                    # Markdown blockquote style format (Precise Quote Visual Match)
                    formatted_match = (
                        f"📄 *Context Match #{match_counter}*\n"
                        f"🔑 Keyword: {found_kw_str}\n"
                        f"> {para_clean}"
                    )
                    
                    # Delete the "Please wait" status message right before sending results
                    if match_counter == 1:
                        try:
                            await context.bot.delete_message(chat_id=chat_id, message_id=status_msg_id)
                        except Exception:
                            pass

                    # Send EACH match as its own separate message
                    await context.bot.send_message(chat_id=chat_id, text=formatted_match, parse_mode="Markdown")
                    match_counter += 1

        if not found_any_match:
            try:
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=status_msg_id,
                    text=f"🔍 Finished searching. Keywords [{display_keywords}] not found."
                )
            except Exception:
                await context.bot.send_message(chat_id=chat_id, text=f"🔍 Finished searching. Keywords [{display_keywords}] not found.")

    except Exception as e:
        logger.error(f"Error processing PDF: {e}")
        try:
            await context.bot.edit_message_text(chat_id=chat_id, message_id=status_msg_id, text="❌ Failed to complete the search. Verify the PDF is accessible.")
        except Exception:
            await context.bot.send_message(chat_id=chat_id, text="❌ Failed to complete the search. Verify the PDF is accessible.")

async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if len(context.args) < 2:
        await update.message.reply_text("❌ Use format: `/search <url> <keyword>`")
        return
    pdf_url = context.args[0]
    keyword = " ".join(context.args[1:])
    await process_pdf_search(update.effective_chat.id, context, pdf_url, [keyword])

async def handle_text_messages(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text.strip()
    
    # If the user sends a link
    if text.startswith("http://") or text.startswith("https://"):
        keyboard = []
        
        # Save full link as runtime fallback for manual keyword typers
        context.user_data["last_link"] = text
        
        # Compress the URL payload: Strip out the known base prefix to easily stay inside the 64-byte callback limit
        # Example: 'https://cdn.sci-notifier.codechips.in/orders/2026-05-23/abc.pdf' becomes '2026-05-23/abc.pdf'
        short_url_path = text.replace(BASE_URL_PREFIX, "")
        
        for kw in DEFAULT_KEYWORDS:
            # We pass both the keyword name and the specific short URL directly into the button data!
            keyboard.append([InlineKeyboardButton(text=kw.upper(), callback_data=f"k|{kw}|{short_url_path}")])
        
        keyboard.append([InlineKeyboardButton(text="🚨 SEARCH ALL KEYWORDS", callback_data=f"k|all|{short_url_path}")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "📋 I detected a PDF link! Select a keyword to search below:",
            reply_markup=reply_markup
        )
        return

    # Fallback context loop: User types a manual keyword directly into chat window right after dropping a link
    saved_url = context.user_data.get("last_link")
    if saved_url:
        await process_pdf_search(update.effective_chat.id, context, saved_url, [text])
    else:
        await update.message.reply_text("Please send a valid PDF link first.")

async def handle_button_click(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    data_parts = query.data.split("|")
    if data_parts[0] == "k":
        action_keyword = data_parts[1]
        short_url_path = data_parts[2]
        
        # Reconstruct the absolute path instantly from the button data payload itself
        if short_url_path.startswith("http"):
            pdf_url = short_url_path
        else:
            pdf_url = BASE_URL_PREFIX + short_url_path

        if action_keyword == "all":
            target_list = DEFAULT_KEYWORDS
        else:
            target_list = [action_keyword]

        await process_pdf_search(
            chat_id=query.message.chat_id,
            context=context,
            pdf_url=pdf_url,
            target_keywords=target_list,
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
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_messages))
    application.add_handler(CallbackQueryHandler(handle_button_click))

    logger.info("Zero-Memory Dependency Engine Active. Polling...")
    application.run_polling()

if __name__ == "__main__":
    main()
