import os
import re
import sys
import requests
from pypdf import PdfReader

# --- CONFIGURATION ---
PDF_FILE_PATH = "document.pdf" 
KEYWORDS_TO_TRACK = ["python", "automation", "telegram"]

# Read sensitive tokens from GitHub Secrets
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
    print("Error: Missing Telegram Environment Variables.")
    sys.exit(1)


def scan_local_pdf(file_path, keywords):
    """Reads the PDF file locally and finds matching paragraphs for each keyword."""
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
            
    # Clean up inconsistent spaces or line breaks often caused by PDF extractions
    # This splits text neatly into paragraphs separated by double line-breaks
    paragraphs = [p.strip() for p in re.split(r'\n\s*\n', full_text) if p.strip()]
        
    keyword_matches = {}
    
    for keyword in keywords:
        keyword_matches[keyword] = {
            "count": 0,
            "paragraphs": []
        }
        
        # Compile a case-insensitive search pattern for the keyword
        pattern = re.compile(re.escape(keyword), re.IGNORECASE)
        
        for para in paragraphs:
            matches = pattern.findall(para)
            if matches:
                keyword_matches[keyword]["count"] += len(matches)
                # Keep the paragraph, but clean up inner single-newlines so it looks good on Telegram
                clean_para = re.sub(r'\n+', ' ', para)
                if clean_para not in keyword_matches[keyword]["paragraphs"]:
                    keyword_matches[keyword]["paragraphs"].append(clean_para)
        
    return keyword_matches


def send_telegram_alert(token, chat_id, results):
    """Sends a summary message along with matching paragraphs to Telegram."""
    # Filter out keywords that weren't found
    found_items = {k: v for k, v in results.items() if v["count"] > 0}
    
    if not found_items:
        print("No matching keywords found in the document. Skipping Telegram alert.")
        return

    # 1. Create the Summary Header
    message = "🔔 **Keyword Alert from GitHub Actions!**\n\n"
    message += "**Matches Found:**\n"
    for kw, data in found_items.items():
        message += f"• `{kw}`: found **{data['count']}** time(s)\n"
    
    message += "\n" + "─" * 15 + "\n\n"
    
    # 2. Append the Surrounding Paragraphs
    message += "📄 **Surrounding Paragraphs:**\n\n"
    for kw, data in found_items.items():
        message += f"🔑 **Keyword: `{kw}`**\n"
        for i, para in enumerate(data["paragraphs"], 1):
            # Truncate paragraphs if they are massive so Telegram doesn't hit a character limit
            if len(para) > 600:
                para = para[:597] + "..."
            
            message += f"_*Paragraph {i}:*_\n> {para}\n\n"
            
    # Telegram messages have a strict 4096 character limit
    if len(message) > 4000:
        message = message[:3990] + "\n\n...[Message Truncated due to length]"
        
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
