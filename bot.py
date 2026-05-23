import logging
import requests
from io import BytesIO
from pypdf import PdfReader
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Welcome! Use the following format to search a PDF:\n\n"
        "/search <PDF_URL> <KEYWORD>\n\n"
        "Example:\n"
        "/search https://example.com/report.pdf revenue"
    )

async def search_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Check if the user supplied enough arguments
    if len(context.args) < 2:
        await update.message.reply_text("❌ Please provide both a PDF link and a keyword.\nFormat: `/search <url> <keyword>`")
        return

    pdf_url = context.args[0]
    # Rejoin keyword parts in case it contains spaces (e.g., "supreme court")
    keyword = " ".join(context.args[1:]).lower()

    await update.message.reply_text("⏳ Downloading and searching the PDF... Please wait.")

    try:
        # Download PDF into memory
        response = requests.get(pdf_url, timeout=15)
        response.raise_for_status()
        
        # Open PDF from bytes stream
        pdf_file = BytesIO(response.content)
        reader = PdfReader(pdf_file)
        
        found_paragraphs = []

        # Iterate through pages and find paragraphs
        for page_num, page in enumerate(reader.pages, start=1):
            text = page.extract_text()
            if not text:
                continue
                
            # Split text into paragraphs (double newlines are common separators)
            paragraphs = text.split("\n\n")
            
            for para in paragraphs:
                para_clean = para.strip()
                if keyword in para_clean.lower():
                    # Keep track of where we found it
                    found_paragraphs.append(f"📄 *[Page {page_num}]*\n{para_clean}")

        # Respond to user
        if found_paragraphs:
            # Join findings, keeping chunks within Telegram's 4096 character limit
            output = "\n\n---\n\n".join(found_paragraphs)
            if len(output) > 4000:
                output = output[:4000] + "\n\n...(truncated due to length limit)"
            await update.message.reply_text(output, parse_mode="Markdown")
        else:
            await update.message.reply_text(f"🔍 Finished searching. Keyword '{keyword}' not found in the text.")

    except requests.exceptions.RequestException as e:
        logger.error(f"Network error: {e}")
        await update.message.reply_text("❌ Failed to download the PDF. Please verify the URL.")
    except Exception as e:
        logger.error(f"Processing error: {e}")
        await update.message.reply_text("❌ An error occurred while parsing the PDF.")

def main() -> None:
    import os
    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    
    if not TOKEN:
        logger.error("No TELEGRAM_BOT_TOKEN found in environment variables.")
        return

    # Build the application using the token
    application = Application.builder().token(TOKEN).build()

    # Register handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("search", search_pdf))

    # Start the Bot
    logger.info("Bot started polling...")
    application.run_polling()

if __name__ == "__main__":
    main()
