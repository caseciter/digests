import os
import re
import urllib.request
import urllib.parse
import requests
import pypdf

def send_telegram_message(token, chat_id, text):
    """Sends a text message to a Telegram chat."""
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    
    if len(text) > 4000:
        text = text[:4000] + "\n... (Truncated)"
        
    data = urllib.parse.urlencode({'chat_id': chat_id, 'text': text}).encode('utf-8')
    try:
        req = urllib.request.Request(url, data=data)
        with urllib.request.urlopen(req) as response:
            return response.read().decode('utf-8')
    except Exception as e:
        print(f"Error sending to Telegram: {e}")
        return None

def extract_paragraphs_with_keyword(pdf_path, keyword):
    """Extracts paragraphs containing the specified keyword from the PDF."""
    matched_paragraphs = []
    
    try:
        reader = pypdf.PdfReader(pdf_path)
        for page_num, page in enumerate(reader.pages, start=1):
            text = page.extract_text()
            if not text:
                continue
            
            # Split text by paragraph line breaks
            paragraphs = re.split(r'\n\s*\n', text)
            
            for para in paragraphs:
                cleaned_para = para.strip()
                if keyword.lower() in cleaned_para.lower():
                    matched_paragraphs.append(f"[Page {page_num}]\n{cleaned_para}")
                    
    except Exception as e:
        print(f"Error processing PDF file: {e}")
        
    return matched_paragraphs

def main():
    pdf_url = os.environ.get("PDF_URL")
    keyword = os.environ.get("KEYWORD")
    tg_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    tg_chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    
    if not all([pdf_url, keyword, tg_token, tg_chat_id]):
        print("Missing required environment variables.")
        return

    local_pdf = "temp_downloaded.pdf"
    
    # Masquerade as a real desktop web browser to bypass anti-bot blocks
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,application/pdf,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5"
    }
    
    print(f"Downloading PDF from: {pdf_url}")
    try:
        with requests.get(pdf_url, headers=headers, stream=True) as response:
            response.raise_for_status() # Raises an error if the site rejects the request
            with open(local_pdf, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
    except Exception as e:
        print(f"Failed to download PDF: {e}")
        return

    print(f"Searching for keyword: '{keyword}'")
    matches = extract_paragraphs_with_keyword(local_pdf, keyword)
    
    if matches:
        print(f"Found {len(matches)} match(es). Sending to Telegram...")
        header = f"🔔 *Keyword Match Found* 🔔\nURL: {pdf_url}\nKeyword: '{keyword}'\n\n"
        full_message = header + "\n\n---\n\n".join(matches)
        send_telegram_message(tg_token, tg_chat_id, full_message)
    else:
        print("No matching paragraphs found.")
        
    if os.path.exists(local_pdf):
        os.remove(local_pdf)

if __name__ == "__main__":
    main()
