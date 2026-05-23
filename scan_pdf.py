import io
import os
import re
import sys
import requests
from pypdf import PdfReader

# --- CONFIGURATION FROM ENVIRONMENT VARIABLES ---
GITHUB_PDF_URL = "https://raw.githubusercontent.com/username/repository/main/document.pdf"
KEYWORDS_TO_TRACK = ["python", "automation", "telegram"]

# Read sensitive tokens from GitHub Secrets environment
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
    print("Error: Missing Telegram Environment Variables.")
    sys.exit(1)


def scan_github_pdf(url, keywords):
    print("Downloading PDF from GitHub...")
    response = requests.get(url)
    if response.status_code != 200:
        raise Exception(f"Failed to download PDF. Status code: {response.status_code}")
    
    pdf_file = io.BytesIO(response.content)
    reader = PdfReader(pdf_file)
    
    full_text = ""
    for page in reader.pages:
        extracted_text = page.extract_text()
        if extracted_text:
            full_text += extracted_text + "\n"
            
    keyword_counts = {}
    for keyword in keywords:
        matches = re.findall(re.escape(keyword), full_text, flags=re.IGNORECASE)
        keyword_counts[keyword] = len(matches)
        
    return keyword_counts


def send_telegram_alert(token, chat_id, counts):
    found_keywords = {k: v for k, v in counts.items() if v > 0}
    if not found_keywords:
        print("No matching keywords found. Skipping Telegram notification.")
        return

    message = "🔔 **Keyword Alert from GitHub Actions!**\n\n"
    message += "The following tracked words were discovered in the PDF:\n"
    for kw, count in found_keywords.items():
        message += f"• `{kw}`: found **{count}** time(s)\n"
        
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
        results = scan_github_pdf(GITHUB_PDF_URL, KEYWORDS_TO_TRACK)
        send_telegram_alert(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, results)
    except Exception as e:
        print(f"An error occurred: {e}")
        sys.exit(1)
