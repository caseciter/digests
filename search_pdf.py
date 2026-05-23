import os
import re
import html
import urllib.request
import urllib.parse
import requests
import pypdf

def _post_to_telegram(token, chat_id, text):
    """Helper tool to send HTML-formatted messages to Telegram."""
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    
    # Payload configured for HTML rendering
    payload = {
        'chat_id': chat_id, 
        'text': text,
        'parse_mode': 'HTML'
    }
    
    data = urllib.parse.urlencode(payload).encode('utf-8')
    try:
        req = urllib.request.Request(url, data=data)
        with urllib.request.urlopen(req) as response:
            return response.read().decode('utf-8')
    except Exception as e:
        print(f"Error sending message to Telegram: {e}")
        return None

def send_summary_and_details(token, chat_id, pdf_url, match_mode, keywords_list, matches):
    """Sends a summary card followed by beautifully quoted detailed paragraphs."""
    keywords_display = ", ".join(keywords_list)
    
    # 1. Generate and Send the Summary Card (Using basic HTML tags instead of Markdown)
    summary_lines = [
        f"📋 <b>Context Matches Summary</b>",
        f"🌐 <b>URL:</b> {pdf_url}",
        f"⚙️ <b>Strategy:</b> {match_mode.upper()}",
        f"🔑 <b>Keywords:</b> <code>{html.escape(keywords_display)}</code>",
        f"📈 <b>Total Matches Found:</b> {len(matches)}",
        f"\n🔍 <b>Match Breakdown by Page:</b>"
    ]
    
    for m in matches:
        triggered_escaped = html.escape(", ".join(m['triggered']))
        summary_lines.append(f"• Page {m['page']} (Keywords: {triggered_escaped})")
        
    summary_text = "\n".join(summary_lines)
    print("Sending search summary card...")
    _post_to_telegram(token, chat_id, summary_text)
    
    # 2. Package and Send Paragraph Details Consecutively inside Blockquotes
    current_message = "📝 <b>DETAILED MATCHING PARAGRAPHS:</b>"
    message_count = 1
    
    for idx, m in enumerate(matches, start=1):
        escaped_text = html.escape(m['text'])
        escaped_keywords = html.escape(", ".join(m['triggered']))
        
        # Build the structured, quoted block using <blockquote> tags
        block = (
            f"\n\n📄 <b>Context Match #{idx}</b>\n"
            f"🔑 Keyword: {escaped_keywords}\n"
            f"<blockquote>{escaped_text}</blockquote>"
        )
        
        # Split chunks cleanly if they step over Telegram's character limits
        if len(current_message) + len(block) > 4000:
            print(f"Sending detailed block chunk #{message_count}...")
            _post_to_telegram(token, chat_id, current_message)
            
            message_count += 1
            current_message = f"📦 <b>Detailed Paragraphs (Part {message_count}):</b>{block}"
        else:
            current_message += block
            
    if current_message:
        print(f"Sending final detailed chunk #{message_count}...")
        _post_to_telegram(token, chat_id, current_message)

def extract_paragraphs_with_keywords(pdf_path, keywords_list, match_mode):
    """Extracts structured dictionaries containing metadata and matching text."""
    matched_data = []
    
    try:
        reader = pypdf.PdfReader(pdf_path)
        for page_num, page in enumerate(reader.pages, start=1):
            text = page.extract_text()
            if not text:
                continue
            
            paragraphs = re.split(r'\n\s*\n', text)
            
            for para in paragraphs:
                cleaned_para = para.strip()
                if not cleaned_para:
                    continue
                
                # Case-insensitive lookup tracking matches
                caught_keywords = [kw for kw in keywords_list if kw.lower() in cleaned_para.lower()]
                
                should_append = False
                if match_mode == "all":
                    if len(caught_keywords) == len(keywords_list):
                        should_append = True
                else:
                    if len(caught_keywords) > 0:
                        should_append = True
                
                if should_append:
                    matched_data.append({
                        "page": page_num,
                        "triggered": caught_keywords,
                        "text": cleaned_para
                    })
                    
    except Exception as e:
        print(f"Error processing PDF file: {e}")
        
    return matched_data

def main():
    pdf_url = os.environ.get("PDF_URL")
    keywords_raw = os.environ.get("KEYWORDS")
    match_mode = os.environ.get("MATCH_MODE", "any").strip().lower()
    tg_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    tg_chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    
    if not all([pdf_url, keywords_raw, tg_token, tg_chat_id]):
        print("Missing required environment variables.")
        return

    keywords_list = [kw.strip() for kw in keywords_raw.split(",") if kw.strip()]
    if not keywords_list:
        print("No valid keywords found to search.")
        return

    local_pdf = "temp_downloaded.pdf"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,application/pdf,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5"
    }
    
    print(f"Downloading PDF from: {pdf_url}")
    try:
        with requests.get(pdf_url, headers=headers, stream=True) as response:
            response.raise_for_status()
            with open(local_pdf, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
    except Exception as e:
        print(f"Failed to download PDF: {e}")
        return

    print(f"Searching mode: '{match_mode.upper()}' for keywords: {keywords_list}")
    matches = extract_paragraphs_with_keywords(local_pdf, keywords_list, match_mode)
    
    if matches:
        print(f"Found {len(matches)} match(es). Dispatching UI layout to Telegram...")
        send_summary_and_details(tg_token, tg_chat_id, pdf_url, match_mode, keywords_list, matches)
    else:
        print("No matching paragraphs found based on your keyword criteria.")
        _post_to_telegram(
            tg_token, 
            tg_chat_id, 
            f"🔍 <b>PDF Search Completed</b>\nNo matches found for <code>{html.escape(', '.join(keywords_list))}</code> inside:\n{pdf_url}"
        )
        
    if os.path.exists(local_pdf):
        os.remove(local_pdf)

if __name__ == "__main__":
    main()
