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
DEFAULT_KEYWORDS = ["insc", "scc", "unconstitutional", "fundamental", "shock", "surprise", "religion"]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Welcome! Send me a PDF link, then either click one of the keyword buttons or type the keyword directly."
    )

async def process_pdf_search(chat_id: int, context: ContextTypes.DEFAULT_TYPE, pdf_url: str, keyword: str, status_msg_id: int = None) -> None:
    # Update status or send a new one
    if status_msg_id:
        try:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=status_msg_id,
                text=f"⏳ Downloading and searching for '{keyword}'... Please wait.",
                reply_markup=None  # Erase buttons immediately upon engagement
            )
        except Exception:
            new_msg = await context.bot.send_message(chat_id=chat_id, text=f"⏳ Downloading and searching for '{keyword}'... Please wait.")
            status_msg_id = new_msg.message_id
    else:
        new_msg = await context.bot.send_message(chat_id=chat_id, text=f"⏳ Downloading and searching for '{keyword}'... Please wait.")
        status_msg_id = new_msg.message_id
    
    keyword_lower = keyword.lower()

    try:
        response = requests.get(pdf_url, timeout=15)
        response.raise_for_status()
        
        pdf_file = BytesIO(response.content)
        reader = PdfReader(pdf_file)
        
        message_blocks = []
        match_counter = 1

        for page_num, page in enumerate(reader.pages, start=1):
            text = page.extract_text()
            if not text:
                continue
                
            # Splitting text into separate paragraphs
            paragraphs = text.split("\n\n")
            for para in paragraphs:
                para_clean = para.strip()
                if keyword_lower in para_clean.lower():
                    # Formatted to replicate the targeted interface layout exactly
                    formatted_match = (
                        f"📄 *Context Match #{match_counter}*\n"
                        f"🔑 Keyword: {keyword}\n"
                        f"> {para_clean}"
                    )
                    message_blocks.append(formatted_match)
