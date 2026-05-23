import os
import re
import urllib.request
import urllib.parse
import requests
import pypdf

def _post_to_telegram(token, chat_id, text):
    """Helper tool to make the actual network request to Telegram."""
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode({'chat_id': chat_id, 'text': text}).encode('utf-8')
    try:
        req = urllib.request.Request(url, data=data)
        with urllib.request.urlopen(req) as response:
            return response.read().decode('utf-8')
    except Exception as e:
        print(f"Error sending message to Telegram: {e}")
        return None

def send_summary_and_details(token, chat_id, pdf_url, match_mode, keywords_list, matches):
    """
    Sends an initial summary breakdown of matches, followed by the individual 
    paragraphs split cleanly across consecutive messages.
    """
    # 1. Generate and Send the Summary Card
    keywords_display = ", ".join(keywords_list)
    summary_lines = [
        f"📊 *PDF SEARCH SUMMARY*",
        f"🌐 *URL:* {pdf_url}",
        f"⚙️ *Mode:* {match_mode.upper()}",
        f"🎯 *Keywords:* `{keywords_display}`",
        f"📈 *Total Matches Found:* {len(matches)}",
        f"\n🔍 *Match Breakdown by Page:*"
    ]
    
    for m in matches:
        summary_lines.append(f"• Page {m['page']} (Matches: {', '.join(m['triggered'])})")
        
    summary_text = "\n".join(summary_lines)
    print("Sending search summary card...")
    _post_to_telegram(token, chat_id, summary_text)
    
    # 2. Package and Send Paragraph Details Consecutively
    current_message = "📝 *DETAILED MATCHING PARAGRAPHS:*"
    message_count = 1
    
    for m in matches:
        block = f"\n\n---\n📄 *[Page {m['page']} | Matches: {', '.join(m['triggered'])}]*\n{m['text']}"
        
        # Split text safely if it risks exceeding Telegram's 4096 character limit
        if len(current_message) + len(block) > 4000:
            print(f"Sending detailed chunk #{message_count}...")
            _post_to_telegram(token, chat_id, current_message)
            
            message_count += 1
            current_message = f"📦 *Detailed Paragraphs (Part {message_count}):*{block}"
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
        print(f"Found {len(matches)} match(es). Triggering Telegram sequence...")
        send_summary_and_details(tg_token, tg_chat_id, pdf_url, match_mode, keywords_list, matches)
    else:
        print("No matching paragraphs found based on your keyword criteria.")
        _post_to_telegram(
            tg_token, 
            tg_chat_id, 
            f"🔍 *PDF Search Completed*\nNo matches found for `{', '.join(keywords_list)}` inside:\n{pdf_url}"
        )
        
    if os.path.exists(local_pdf):
        os.remove(local_pdf)

if __name__ == "__main__":
    main()
