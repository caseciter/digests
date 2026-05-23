import os
import re
import urllib.request
import urllib.parse
import requests
import pypdf

def send_telegram_messages_in_chunks(token, chat_id, header, matches):
    """
    Groups matched paragraphs into multiple messages to respect Telegram's 4096 character limit,
    then sends them consecutively.
    """
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    
    current_message = header
    message_count = 1
    
    for match in matches:
        # Format the block with a separator
        block = f"\n\n---\n\n{match}"
        
        # Check if adding this block exceeds a safe limit (e.g., 4000 chars)
        if len(current_message) + len(block) > 4000:
            print(f"Sending message chunk #{message_count}...")
            _post_to_telegram(url, chat_id, current_message)
            
            # Start a new message chunk
            message_count += 1
            current_message = f"📦 *[Part {message_count}]*\n{match}"
        else:
            current_message += block
            
    # Send any remaining content left in the buffer
    if current_message:
        print(f"Sending final message chunk #{message_count}...")
        _post_to_telegram(url, chat_id, current_message)

def _post_to_telegram(url, chat_id, text):
    """Helper tool to make the actual network request to Telegram."""
    data = urllib.parse.urlencode({'chat_id': chat_id, 'text': text}).encode('utf-8')
    try:
        req = urllib.request.Request(url, data=data)
        with urllib.request.urlopen(req) as response:
            return response.read().decode('utf-8')
    except Exception as e:
        print(f"Error sending message chunk to Telegram: {e}")
        return None

def extract_paragraphs_with_keywords(pdf_path, keywords_list, match_mode):
    """Extracts paragraphs matching keywords based on the selected mode ('any' or 'all')."""
    matched_paragraphs = []
    
    try:
        reader = pypdf.PdfReader(pdf_path)
        for page_num, page in enumerate(reader.pages, start=1):
            text = page.extract_text()
            if not text:
                continue
            
            # Split text into paragraphs based on blank lines
            paragraphs = re.split(r'\n\s*\n', text)
            
            for para in paragraphs:
                cleaned_para = para.strip()
                if not cleaned_para:
                    continue
                
                # Check which keywords match this specific paragraph
                caught_keywords = [kw for kw in keywords_list if kw.lower() in cleaned_para.lower()]
                
                # Determine if it meets our matching strategy rule
                should_append = False
                if match_mode == "all":
                    if len(caught_keywords) == len(keywords_list):
                        should_append = True
                else:
                    if len(caught_keywords) > 0:
                        should_append = True
                
                if should_append:
                    triggered_str = ", ".join(caught_keywords)
                    matched_paragraphs.append(
                        f"[Page {page_num} | Matches: {triggered_str}]\n{cleaned_para}"
                    )
                    
    except Exception as e:
        print(f"Error processing PDF file: {e}")
        
    return matched_paragraphs

def main():
    pdf_url = os.environ.get("PDF_URL")
    keywords_raw = os.environ.get("KEYWORDS")
    match_mode = os.environ.get("MATCH_MODE", "any").strip().lower()
    tg_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    tg_chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    
    if not all([pdf_url, keywords_raw, tg_token, tg_chat_id]):
        print("Missing required environment variables.")
        return

    # Turn comma-separated string into a clean list of phrases
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
        print(f"Found {len(matches)} match(es). Dispatching split chunks to Telegram...")
        keywords_display = ", ".join(keywords_list)
        header = f"🔔 *Keyword Matches Found ({match_mode.upper()})* 🔔\nURL: {pdf_url}\nTargets: {keywords_display}"
        
        send_telegram_messages_in_chunks(tg_token, tg_chat_id, header, matches)
    else:
        print("No matching paragraphs found based on your keyword criteria.")
        
    if os.path.exists(local_pdf):
        os.remove(local_pdf)

if __name__ == "__main__":
    main()
