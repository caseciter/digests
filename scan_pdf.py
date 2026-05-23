import os
import re
import sys
import html
import time
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
    """Reads PDF, cleans line breaks, and extracts structural context blocks."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Could not find the file: '{file_path}'")
        
    print(f"Processing: {file_path}...")
    reader = PdfReader(file_path)
    
    raw_lines = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            raw_lines.append(text)
            
    # Stitches broken lines into a unified continuous flow
    full_text = " ".join(raw_lines)
    full_text = re.sub(r'\s+', ' ', full_text).strip()
    
    # Split text intelligently into actual punctuation-based sentences
    sentences = re.split(r'(?<=[.!?])\s+', full_text)
    
    keyword_matches = {}
    
    for keyword in keywords:
        keyword_matches[keyword] = {
            "count": 0,
            "snippets": []
        }
        
        global_matches = re.findall(re.escape(keyword), full_text, flags=re.IGNORECASE)
        keyword_matches[keyword]["count"] = len(global_matches)
        
        if keyword_matches[keyword]["count"] > 0:
            for idx, sentence in enumerate(sentences):
                if re.search(re.escape(keyword), sentence, re.IGNORECASE):
                    # Gather context window: 2 sentences before, current sentence, 2 sentences after
                    start_idx = max(0, idx - 2)
                    end_idx = min(len(sentences), idx + 3)
                    
                    context_block = " ".join(sentences[start_idx:end_idx])
                    
                    if context_block not in keyword_matches[keyword]["snippets"]:
                        keyword_matches[keyword]["snippets"].append(context_block)
                        
    return keyword_matches


def post_to_telegram(token, chat_id, text):
    """Helper function to send a standalone message to Telegram."""
    telegram_url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    }
    res = requests.post(telegram_url, json=payload)
    if res.status_code != 200:
        print(f"Telegram API Error: {res.text}")
    # Short pause to prevent hitting Telegram's rate limits when blasting multiple messages
    time.sleep(0.5)


def send_telegram_alert(token, chat_id, results):
    """Sends a summary overview followed by individual messages for matches to prevent truncation."""
    found_items = {k: v for k, v in results.items() if v["count"] > 0}
    
    if not found_items:
        print("No tracking matches found. Exiting.")
        return

    # 1. Send the Summary Overview Header First
    summary_msg = [
        "🔔 <b>Keyword Alert from GitHub Actions!</b>\n",
        "<b>Matches Found Overview:</b>"
    ]
    for kw, data in found_items.items():
        summary_msg.append(f"• <code>{html.escape(kw)}</code>: found <b>{data['count']}</b> time(s)")
        
    post_to_telegram(token, chat_id, "\n".join(summary_msg))
    
    # 2. Send each matching context paragraph block as its own dedicated message
    block_number = 1
    for kw, data in found_items.items():
        for snippet in data["snippets"]:
            safe_snippet = html.escape(snippet)
            
            # Highlight target keyword
            insensitive_keyword = re.compile(re.escape(kw), re.IGNORECASE)
            highlighted_snippet = insensitive_keyword.sub(f"<u><b>{kw.upper()}</b></u>", safe_snippet)
            
            # Build individual container message
            block_msg = (
                f"📄 <b>Context Match #{block_number}</b>\n"
                f"🔑 Keyword: <code>{html.escape(kw)}</code>\n\n"
                f"<blockquote>{highlighted_snippet}</blockquote>"
            )
            
            # Absolute safety net: if a single block is somehow longer than 4000 characters, hard slice it
            if len(block_msg) > 4000:
                block_msg = block_msg[:3990] + "..."
                
            post_to_telegram(token, chat_id, block_msg)
            block_number += 1
            
    print(f"Successfully sent summary and {block_number - 1} context blocks to Telegram!")


if __name__ == "__main__":
    try:
        results = scan_local_pdf(PDF_FILE_PATH, KEYWORDS_TO_TRACK)
        send_telegram_alert(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, results)
    except Exception as e:
        print(f"An error execution occurred: {e}")
        sys.exit(1)
