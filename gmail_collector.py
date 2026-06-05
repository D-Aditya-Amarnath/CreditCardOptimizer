import os
import base64
import httpx
from datetime import datetime
from email.utils import parsedate_tz, mktime_tz
from bs4 import BeautifulSoup
import io
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from models import EmailPayload, BannerResult
from services.banner_extractor import BannerExtractor

INDIAN_FINANCIAL_DOMAINS = [
    # Public Sector Banks
    "sbi.co.in", "sbicard.com", "sbi.bank.in",
    "bankofbaroda.co.in", "bobfinancial.com", "bankofbaroda.bank.in",
    "pnbindia.in", "pnb.bank.in",
    "unionbankofindia.co.in", "unionbank.bank.in",
    "canarabank.com", "canarabank.bank.in",
    "bankofindia.co.in", "bankofindia.bank.in",
    "centralbankofindia.co.in", "centralbank.bank.in",
    "indianbank.in", "indianbank.bank.in",
    "bankofmaharashtra.in", "bankofmaharashtra.bank.in",
    "idbibank.in", "idbi.bank.in",

    # Private Sector Banks
    "hdfcbank.com", "hdfc.bank.in",
    "icicibank.com", "icici.bank.in",
    "axisbank.com", "axis.bank.in",
    "kotak.com", "kotakbank.in",
    "yesbank.in", "yes.bank.in",
    "indusind.com", "indusind.bank.in",
    "idfcfirstbank.com", "idfcfirst.bank.in",
    "rblbank.com", "rbl.bank.in",
    "federalbank.co.in", "federal.bank.in",
    "southindianbank.com",
    "bandhanbank.com",
    "dbs.com", "digibank.in",
    "jkbank.com", "jkbank.bank.in",
    "csb.co.in",
    "dhanbank.com", "dhanlaxmibank.bank.in",
    "karurvysyabank.co.in",
    "cityunionbank.bank.in",
    "dcb.bank.in",

    # Small Finance Banks
    "aubank.in", "au.smallfinancebank.in",
    "equitasbank.com", "equitas.in",
    "ujjivansfb.in", "ujjivan.bank.in",
    "nesfbank.com",
    "fincaresfb.in",
    "utkarsh.bank.in",
    "capitalbank.co.in",
    "esafbank.com",

    # Foreign Banks
    "standardchartered.co.in",
    "hsbc.co.in", "hsbc.in",
    "citibank.co.in",
    "deutschebank.co.in",
    "barclays.in",

    # Card Networks
    "americanexpress.com", "amex.com",
    "dinersclub.in",

    # NBFCs
    "bajajfinserv.in", "bajajfinservmarkets.com",
    "tatacapital.com",
    "hdbfs.com",
    "adityabirlacapital.com",
    "ltfs.com",
    "cholamandalam.com",
    "mahindrafinance.com",
    "muthootfincorp.com",
    "shriramtransport.com",

    # Fintech Card Issuers
    "onecard.in",
    "sliceit.com", "slice.money",
    "uni.cards", "unicards.com",
    "fi.money", "fisdom.com",
    "paytmpay.com",
    "freecharge.com",
    "getsimpl.com",
    "lazypay.in",
    "zestmoney.in",
    "kissht.com",
    "card91.com",

    # Co-branded
    "amazonpay.amazon.in",

    # Aggregators
    "cred.club", "cred.me",
    "paytm.com",
    "phonepe.com",
    "mobikwik.com",
    "rupeeboss.com",
    "tataneu.com",
    "makemytrip.com",
]


class GmailCollector:
    def __init__(self, credentials_dir: str = ".credentials"):
        self.credentials_dir = credentials_dir
        self.scopes = [
            "https://www.googleapis.com/auth/gmail.readonly",
            "https://www.googleapis.com/auth/userinfo.email",
            "openid"
        ]
        self.domains = INDIAN_FINANCIAL_DOMAINS
        self.banner_extractor = BannerExtractor()
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

    def get_configured_accounts(self) -> list:
        if not os.path.exists(self.credentials_dir):
            return []
        return [
            file[6:-5] for file in os.listdir(self.credentials_dir)
            if file.startswith("token_") and file.endswith(".json")
        ]

    def fetch_promotional_emails(self, service, max_results: int = 500,
                                   authenticated_email: str = "",
                                   after_timestamp: datetime = None,
                                   days_back: int = 90) -> list:
        query = " OR ".join([f"from:{domain}" for domain in self.domains])
        if after_timestamp:
            query += f" after:{after_timestamp.strftime('%Y/%m/%d')}"
        else:
            from datetime import timedelta
            lookback_date = datetime.now() - timedelta(days=days_back)
            query += f" after:{lookback_date.strftime('%Y/%m/%d')}"

        try:
            all_message_ids = []
            page_token = None

            while True:
                kwargs = {'userId': 'me', 'q': query, 'maxResults': 100}
                if page_token:
                    kwargs['pageToken'] = page_token

                results = service.users().messages().list(**kwargs).execute()
                messages = results.get('messages', [])
                all_message_ids.extend(messages)

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

    def _extract_banner_urls(self, body_html: str) -> list:
        soup = BeautifulSoup(body_html, "html.parser")
        urls = set()

        for img in soup.find_all('img', src=True):
            src = img['src']
            if src.startswith('http'):
                urls.add(src)

        for a in soup.find_all('a', href=True):
            href = a['href']
            if href.startswith('http') and any(domain in href for domain in self.domains):
                urls.add(href)

        return list(urls)

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
                name = header.get("name", "").lower()
                value = header.get("value", "")
                if name == 'from':
                    sender = value
                if name == 'subject':
                    subject = value
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
                    data = part.get("body", {}).get('data')
                    if not data:
                        if part.get('parts'):
                            for subpart in part['parts']:
                                sub_data = subpart.get('body', {}).get('data')
                                sub_mime = subpart.get("mimeType")
                                if sub_data:
                                    decoded = self._decode_base64url(sub_data)
                                    if sub_mime == "text/plain":
                                        body_text += decoded
                                    elif sub_mime == "text/html":
                                        body_html += decoded
                        continue
                    decoded_data = self._decode_base64url(data)

                    if mime_type == "text/plain":
                        body_text += decoded_data
                    elif mime_type == "text/html":
                        body_html += decoded_data

            if not body_text and body_html:
                soup_body = BeautifulSoup(body_html, "html.parser")
                body_text = soup_body.get_text(separator="\n").strip()

            banner_urls = self._extract_banner_urls(body_html)

            return EmailPayload(
                email_id=email_id,
                sender=sender,
                subject=subject,
                date_received=date_received,
                body_text=body_text,
                body_html=body_html,
                labels=labels,
                account_email=authenticated_email,
                image_urls=banner_urls
            )

        except Exception as error:
            print(f"Error parsing message {msg_id}: {error}")
            return None
