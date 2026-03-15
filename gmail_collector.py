import os
import base64
from datetime import datetime
from email.utils import parsedate_tz, mktime_tz
from bs4 import BeautifulSoup
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from models import EmailPayload

# Indian Banks (RBI regulated), NBFCs, and licensed Card Issuers
# Includes both legacy domains and new RBI-mandated .bank.in domains
INDIAN_FINANCIAL_DOMAINS = [
    # ── Public Sector Banks (legacy + .bank.in) ──
    "sbi.co.in", "sbicard.com", "sbi.bank.in",               # State Bank of India
    "bankofbaroda.co.in", "bobfinancial.com", "bankofbaroda.bank.in",  # Bank of Baroda
    "pnbindia.in", "pnb.bank.in",                             # Punjab National Bank
    "unionbankofindia.co.in",                                  # Union Bank of India
    "canarabank.com", "canarabank.bank.in",                    # Canara Bank
    "bankofindia.co.in", "bankofindia.bank.in",                # Bank of India
    "centralbankofindia.co.in",                                # Central Bank of India
    "indianbank.in",                                           # Indian Bank
    "bankofmaharashtra.in",                                    # Bank of Maharashtra
    "idbibank.in", "idbi.bank.in",                             # IDBI Bank

    # ── Private Sector Banks (legacy + .bank.in) ──
    "hdfcbank.com", "hdfc.bank.in",                            # HDFC Bank
    "icicibank.com", "icici.bank.in",                          # ICICI Bank
    "axisbank.com", "axis.bank.in",                            # Axis Bank
    "kotak.com", "kotakbank.in",                               # Kotak Mahindra Bank
    "yesbank.in",                                              # Yes Bank
    "indusind.com", "indusind.bank.in",                        # IndusInd Bank
    "idfcfirstbank.com", "idfcfirst.bank.in",                  # IDFC First Bank
    "rblbank.com", "rbl.bank.in",                              # RBL Bank
    "federalbank.co.in", "federal.bank.in",                    # Federal Bank
    "southindianbank.com",                                     # South Indian Bank
    "karurvysyabank.co.in",                                    # Karur Vysya Bank
    "dhanbank.com", "dhan.bank.in",                            # Dhanlaxmi Bank
    "bandhanbank.com",                                         # Bandhan Bank
    "cityunionbank.bank.in",                                   # City Union Bank
    "dcb.bank.in",                                             # DCB Bank

    # ── Small Finance Banks ──
    "aubank.in",                                               # AU Small Finance Bank
    "equitasbank.com",                                         # Equitas SFB
    "ujjivansfb.in",                                           # Ujjivan SFB

    # ── Foreign Banks operating in India ──
    "standardchartered.co.in",                                 # Standard Chartered
    "hsbc.co.in",                                              # HSBC India
    "citibank.co.in",                                          # Citibank India
    "deutschebank.co.in",                                      # Deutsche Bank India

    # ── Card Networks & Issuers ──
    "americanexpress.com", "amex.com",                         # American Express
    "sbicard.com",                                             # SBI Card
    "hdfcbankdinersclub.com",                                  # HDFC Diners Club

    # ── Licensed NBFCs & Fintechs (Card Issuers) ──
    "bajajfinserv.in",                                         # Bajaj Finserv
    "tatacapital.com",                                         # Tata Capital
    "onecard.in",                                              # OneCard
    "sliceit.com",                                             # Slice
    "uni.cards",                                               # Uni Cards

    # ── Rewards / Offer Aggregators ──
    "cred.club",                                               # CRED
]

class GmailCollector:
    """Object-Oriented handler for Gmail connections and message retrieval."""
    
    def __init__(self, credentials_dir: str = ".credentials"):
        self.credentials_dir = credentials_dir
        self.scopes = [
            "https://www.googleapis.com/auth/gmail.readonly",
            "https://www.googleapis.com/auth/userinfo.email", 
            "openid"
        ]
        self.domains = INDIAN_FINANCIAL_DOMAINS
        os.makedirs(self.credentials_dir, exist_ok=True)
        
    def _decode_base64url(self, data: str) -> str:
        data = data.replace("-", "+").replace("_", "/")
        padding = len(data) % 4
        if padding:
            data += "=" * (4 - padding)
        return base64.b64decode(data).decode('utf-8', errors='ignore')

    def authenticate(self, email_address: str = None, force_new: bool = False):
        creds = None
        token_path = f"{self.credentials_dir}/token_{email_address}.json" if email_address else None
        
        if token_path and os.path.exists(token_path) and not force_new:
            creds = Credentials.from_authorized_user_file(token_path, self.scopes)
            
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file("credentials.json", self.scopes)
                creds = flow.run_local_server(port=0)
                
            service = build("oauth2", "v2", credentials=creds)
            user_info = service.userinfo().get().execute()
            authenticated_email = user_info.get("email")
            
            token_path = f"{self.credentials_dir}/token_{authenticated_email}.json"
            with open(token_path, "w") as token:
                token.write(creds.to_json())
                
            return build("gmail", "v1", credentials=creds), authenticated_email
            
        return build("gmail", "v1", credentials=creds), email_address

    def get_configured_accounts(self) -> list[str]:
        if not os.path.exists(self.credentials_dir):
            return []
        return [file[6:-5] for file in os.listdir(self.credentials_dir) if file.startswith("token_") and file.endswith(".json")]

    def fetch_promotional_emails(self, service, max_results: int = 500, authenticated_email: str = "", after_timestamp: datetime = None, days_back: int = 90) -> list[EmailPayload]:
        query = " OR ".join([f"from:{domain}" for domain in self.domains])
        if after_timestamp:
            query += f" after:{after_timestamp.strftime('%Y/%m/%d')}"
        else:
            from datetime import timedelta
            lookback_date = datetime.now() - timedelta(days=days_back)
            query += f" after:{lookback_date.strftime('%Y/%m/%d')}"
            
        try:
            # Paginate through ALL results (Gmail returns max 100 per page)
            all_message_ids = []
            page_token = None
            
            while True:
                kwargs = {'userId': 'me', 'q': query, 'maxResults': 100}
                if page_token:
                    kwargs['pageToken'] = page_token
                    
                results = service.users().messages().list(**kwargs).execute()
                messages = results.get('messages', [])
                all_message_ids.extend(messages)
                
                # Stop if we have enough or there are no more pages
                if len(all_message_ids) >= max_results:
                    all_message_ids = all_message_ids[:max_results]
                    break
                    
                page_token = results.get('nextPageToken')
                if not page_token:
                    break
            
            print(f"  Found {len(all_message_ids)} matching emails for {authenticated_email}")
            
            parsed_emails = []
            for msg in all_message_ids:
                payload = self._get_message_details(service, msg['id'], authenticated_email)
                if payload:
                    parsed_emails.append(payload)
                    
            return parsed_emails
        except Exception as error:
            print(f"An error occurred fetching emails: {error}")
            return []

    def _get_message_details(self, service, msg_id: str, authenticated_email: str) -> EmailPayload:
        try:
            message = service.users().messages().get(userId='me', id=msg_id, format='full').execute()
            payload = message.get('payload', {})
            headers = payload.get('headers', [])
            
            email_id = msg_id
            sender = ""
            subject = ""
            date_received = None
            labels = message.get("labelIds", [])
            body_text = ""
            body_html = ""
            
            for header in headers:
                name = header.get("name").lower()
                value = header.get("value")
                if name == 'from': sender = value
                if name == 'subject': subject = value
                if name == 'date':
                    tt = parsedate_tz(value)
                    if tt:
                        timestamp = mktime_tz(tt)
                        date_received = datetime.fromtimestamp(timestamp)
                        
            parts = payload.get('parts', [])
            if not parts:
                data = payload.get('body', {}).get('data')
                if data:
                    body_text = self._decode_base64url(data)
            else:
                for part in parts:
                    mime_type = part.get("mimeType")
                    data = part.get("body", {}).get("data")
                    if not data: continue
                    decoded_data = self._decode_base64url(data)
                    
                    if mime_type == "text/plain": body_text += decoded_data
                    elif mime_type == "text/html": body_html += decoded_data
                        
            if not body_text and body_html:
                soup = BeautifulSoup(body_html, "html.parser")
                body_text = soup.get_text(separator="\n").strip()
                
            return EmailPayload(
                email_id=email_id,
                sender=sender,
                subject=subject,
                date_received=date_received,
                body_text=body_text,
                body_html=body_html,
                labels=labels,
                account_email=authenticated_email
            )
            
        except Exception as error:
            print(f"Error parsing message {msg_id}: {error}")
            return None
