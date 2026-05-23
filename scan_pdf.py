import os
import re
import sys
import html
import requests
from pypdf import PdfReader

# --- CONFIGURATION ---
PDF_FILE_PATH = "document.pdf" 
KEYWORDS_TO_TRACK = ["intention", "automation", "telegram"]

# Read sensitive tokens from GitHub Secrets
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
    print("Error: Missing Telegram Environment Variables.")
    sys.exit(1)


def scan_local_pdf(file_path, keywords):
    """Reads PDF, cleans line breaks, and extracts the full contextual sentence block."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Could not find the file: '{file_path}'")
        
    print(f"Processing: {file_path}...")
    reader = PdfReader(file_path)
    
    raw_lines = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            raw_lines.append(text)
            
    # Combine text and replace single hard line breaks with a regular space
    # This turns broken PDF lines into a natural continuous flow of text
    full_text = " ".join(raw_lines)
    full_text = re.sub(r'\s+', ' ', full_text).strip()
    
    # Split the clean text into actual punctuation-based sentences
    # Matches periods, exclamation marks, or question marks followed by a space
    sentences = re.split(r'(?<=[.!?])\s+', full_text)
    
    keyword_matches = {}
    
    for keyword in keywords:
        keyword_matches[keyword] = {
            "count": 0,
            "snippets": []
        }
        
        # Count total occurrences globally in the document
        global_matches = re.findall(re.escape(keyword), full_text, flags=re.IGNORECASE)
        keyword_matches[keyword]["count"] = len(global_matches)
        
        if keyword_matches[keyword]["count"] > 0:
            # Look through sentences to pull relevant context windows
            for idx, sentence in enumerate(sentences):
                if re.search(re.escape(keyword), sentence, re.IGNORECASE):
                    # Grab a window: 2 sentences before, the current sentence, and 2 sentences after
                    start_idx = max(0, idx - 2)
                    end_idx = min(len(sentences), idx + 3)
                    
                    context_block = " ".join(sentences[start_idx:end_idx])
                    
                    # Avoid duplicates if a keyword appears multiple times in the same area
                    if context_block not in keyword_matches[keyword]["snippets"]:
                        keyword_matches[keyword]["snippets"].append(context_block)
                        
    return keyword_matches


def send_telegram_alert(token, chat_id, results):
    """Sends a summary alert to Telegram using HTML parsing for absolute safety."""
    found_items = {k: v for k, v in results.items() if v["count"] > 0}
    
    if not found_items:
        print("No tracking matches found. Exiting.")
        return

    # Build response with clean HTML tags
    message_segments = [
        "🔔 <b>Keyword Alert from GitHub Actions!</b>\n",
        "<b>Matches Found:</b>"
    ]
    
    for kw, data in found_items.items():
        message_segments.append(f"• <code>{html.escape(kw)}</code>: found <b>{data['count']}</b> time(s)")
        
    message_segments.append("\n" + "─" * 20 + "\n")
    message_segments.append("📄 <b>Extracted Context Blocks:</b>\n")
    
    for kw, data in found_items.items():
        message_segments.append(f"🔑 <b>Keyword: <code>{html.escape(kw)}</code></b>")
        for i, snippet in enumerate(data["snippets"], 1):
            # Safe text encoding for Telegram HTML mode
            safe_snippet = html.escape(snippet)
            
            # Visually bold the targeted keyword inside the context paragraph block
            insensitive_keyword = re.compile(re.escape(kw), re.IGNORECASE)
            highlighted_snippet = insensitive_keyword.sub(f"<u><b>{kw.upper()}</b></u>", safe_snippet)
            
            if len(highlighted_snippet) > 700:
                highlighted_snippet = highlighted_snippet[:697] + "..."
                
            message_segments.append(f"<i>Block {i}:</i>\n<blockquote>{highlighted_snippet}</blockquote>\n")
            
    final_message = "\n".join(message_segments)
    
    # Enforce safe upper message limits
    if len(final_message) > 4000:
        final_message = final_message[:3950] + "\n\n<b>[Message truncated due to length limits]</b>"
        
    telegram_url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": final_message,
        "parse_mode": "HTML"
    }
    
    res = requests.post(telegram_url, json=payload)
    if res.status_code == 200:
        print("Alert successfully pushed to Telegram!")
    else:
        print(f"Telegram API Error Details: {res.text}")


if __name__ == "__main__":
    try:
        results = scan_local_pdf(PDF_FILE_PATH, KEYWORDS_TO_TRACK)
        send_telegram_alert(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, results)
    except Exception as e:
        print(f"An error execution occurred: {e}")
        sys.exit(1)
