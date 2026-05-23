import logging
import requests
from io import BytesIO
from pypdf import PdfReader
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

# Enable logging to track bot activity and errors
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Predefined keywords to show as quick-select options
DEFAULT_KEYWORDS = ["insc", "scc", "fundamental", "religion"]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Welcome! Send me a PDF link, then either click one of the keyword buttons (including 'ALL') or type your own keyword directly."
    )

async def process_pdf_search(chat_id: int, context: ContextTypes.DEFAULT_TYPE, pdf_url: str, target_keywords: list, status_msg_id: int = None) -> None:
    # Build a clean display string of what we are searching for
    display_keywords = ", ".join([kw.upper() for kw in target_keywords])
    
    # Update status or send a new one
    if status_msg_id:
        try:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=status_msg_id,
                text=f"⏳ Downloading and searching for '{display_keywords}'... Please wait.",
                reply_markup=None  # Erase buttons immediately upon engagement
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

        # Parse page by page
        for page_num, page in enumerate(reader.pages, start=1):
            text = page.extract_text()
            if not text:
                continue
                
            # Splitting text into separate paragraphs
            paragraphs = text.split("\n\n")
            for para in paragraphs:
                para_clean = para.strip()
                if not para_clean:
                    continue
                
                # Check if this paragraph contains any of our target keywords
                matched_keywords_in_para = []
                for kw in target_keywords:
                    if kw.lower() in para_clean.lower():
                        matched_keywords_in_para.append(kw)

                if matched_keywords_in_para:
                    found_any_match = True
                    # Format matching keywords string nicely for the block header
                    found_kw_str = ", ".join(matched_keywords_in_para)
                    
                    # Construct individual, blockquoted message payload
                    formatted_match = (
                        f"📄 *Context Match #{match_counter}*\n"
                        f"🔑 Keyword: {found_kw_str}\n"
                        f"> {para_clean}"
                    )
                    
                    # Delete the original operational status message right before sending the first match
                    if match_counter == 1:
                        try:
                            await context.bot.delete_message(chat_id=chat_id, message_id=status_msg_id)
                        except Exception:
                            pass

                    # Send EACH match as its own completely separate message
                    await context.bot.send_message(chat_id=chat_id, text=formatted_match, parse_mode="Markdown")
                    match_counter += 1

        # Handling scenarios where zero hits were encountered across pages
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
            await context.bot.edit_message_text(chat_id=chat_id, message_id=status_msg_id, text="❌ Failed to complete the search. Verify the URL is valid.")
        except Exception:
            await context.bot.send_message(chat_id=chat_id, text="❌ Failed to complete the search. Verify the URL is valid.")

async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if len(context.args) < 2:
        await update.message.reply_text("❌ Use format: `/search <url> <keyword>`")
        return
    pdf_url = context.args[0]
    keyword = " ".join(context.args[1:])
    # Convert typed command keyword to single-item list
    await process_pdf_search(update.effective_chat.id, context, pdf_url, [keyword])

async def handle_text_messages(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text.strip()
    
    # Check if incoming text is a link
    if text.startswith("http://") or text.startswith("https://"):
        keyboard = []
        
        # Build keyword rows
        for kw in DEFAULT_KEYWORDS:
            keyboard.append([InlineKeyboardButton(text=kw.upper(), callback_data=f"kw|{kw}")])
        
        # Append "ALL" button at the very bottom as its own distinct action row
        keyboard.append([InlineKeyboardButton(text="🚨 SEARCH ALL KEYWORDS", callback_data="kw|all_keywords")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        context.user_data["current_pdf_url"] = text
        
        await update.message.reply_text(
            "📋 I detected a PDF link! Select a keyword to search below:",
            reply_markup=reply_markup
        )
        return

    # Treat text input as a direct keyword search if a link was stored previously
    saved_url = context.user_data.
