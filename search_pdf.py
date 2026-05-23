import os
import re
import urllib.request
import urllib.parse
import pypdf

def send_telegram_message(token, chat_id, text):
    """Sends a text message to a Telegram chat."""
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    
    # Truncate message if it exceeds Telegram's limit (4096 characters)
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
            
            # Split text by double newlines or standard line breaks that look like paragraph endings
            # Adjust splitting logic depending on the structural layout of your target PDFs
            paragraphs = re.split(r'\n\s*\n', text)
            
            for para in paragraphs:
                cleaned_para = para.strip()
                # Case-insensitive keyword matching
                if keyword.lower() in cleaned_para.lower():
                    # Format found context with page number reference
                    matched_paragraphs.append(f"[Page {page_num}]\n{cleaned_para}")
                    
    except Exception as e:
        print(f"Error processing PDF file: {e}")
        
    return matched_paragraphs

def main():
    # Fetch configurations from Environment Variables
    pdf_url = os.environ.get("PDF_URL")
    keyword = os.environ.get("KEYWORD")
    tg_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    tg_chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    
    if not all([pdf_url, keyword, tg_token, tg_chat_id]):
        print("Missing required environment variables.")
        return

    local_pdf = "temp_downloaded.pdf"
    
    print(f"Downloading PDF from: {pdf_url}")
    try:
        urllib.request.urlretrieve(pdf_url, local_pdf)
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
        
    # Clean up the downloaded file
    if os.path.exists(local_pdf):
        os.remove(local_pdf)

if __name__ == "__main__":
    main()
