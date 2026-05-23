import os
import re
import sys
import requests
from pypdf import PdfReader

# --- CONFIGURATION ---
# Just put the filename or the relative path to the PDF inside your repository
PDF_FILE_PATH = "document.pdf" 
KEYWORDS_TO_TRACK = ["insc", "criminal", "telegram"]

# Read sensitive tokens from GitHub Secrets
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
    print("Error: Missing Telegram Environment Variables.")
    sys.exit(1)


def scan_local_pdf(file_path, keywords):
    """Reads the PDF file locally from the repository folder."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Could not find the file: '{file_path}' in the repository workspace.")
        
    print(f"Reading local file: {file_path}...")
    reader = PdfReader(file_path)
    
    # Extract all text from the document
    full_text = ""
    for page in reader.pages:
        extracted_text = page.extract_text()
        if extracted_text:
            full_text += extracted_text + "\n"
            
    # Count the matches (case-insensitive scan)
    keyword_counts = {}
    for keyword in keywords:
        matches = re.findall(re.escape(keyword), full_text, flags=re.IGNORECASE)
        keyword_counts[keyword] = len(matches)
        
    return keyword_counts


def send_telegram_alert(token, chat_id, counts):
    """Sends a summary message to your Telegram Bot if keywords are found."""
    found_keywords = {k: v for k, v in counts.items() if v > 0}
    
    if not found_keywords:
        print("No matching keywords found in the document. Skipping Telegram alert.")
        return

    # Construct the alert message
    message = "🔔 **Keyword Alert from GitHub Actions!**\n\n"
    message += "The following tracked words were discovered:\n"
    for kw, count in found_keywords.items():
        message += f"• `{kw}`: found **{count}** time(s)\n"
        
    # Send request to Telegram Bot API
    telegram_url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown"
    }
    
    res = requests.post(telegram_url, json=payload)
    if res.status_code == 200:
        print("Alert successfully sent to Telegram!")
    else:
        print(f"Failed to send Telegram message: {res.text}")


if __name__ == "__main__":
    try:
        # Run the scanning process using the local workspace file
        results = scan_local_pdf(PDF_FILE_PATH, KEYWORDS_TO_TRACK)
        
        # Trigger the alert if anything matches
        send_telegram_alert(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, results)
        
    except Exception as e:
        print(f"An error occurred: {e}")
        sys.exit(1)
