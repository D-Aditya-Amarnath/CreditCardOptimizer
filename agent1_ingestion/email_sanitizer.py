import re
from dataclasses import asdict, dataclass
from email.utils import parseaddr
from typing import Optional

from bs4 import BeautifulSoup


BANK_NAME_HINTS = {
    "hdfc": "HDFC Bank",
    "sbi": "SBI",
    "sbicard": "SBI Card",
    "icici": "ICICI Bank",
    "axis": "Axis Bank",
    "bajaj": "Bajaj Finserv",
    "amex": "American Express India",
    "americanexpress": "American Express India",
    "kotak": "Kotak Mahindra Bank",
    "yesbank": "YES Bank",
    "idfc": "IDFC FIRST Bank",
    "rbl": "RBL Bank",
    "indusind": "IndusInd Bank",
    "stanchart": "Standard Chartered Bank India",
    "standardchartered": "Standard Chartered Bank India",
    "bob": "BOB Financial",
    "bobfinancial": "BOB Financial",
    "unionbank": "Union Bank of India",
    "pnb": "Punjab National Bank",
    "canara": "Canara Bank",
    "hsbc": "HSBC India",
    "au": "AU Small Finance Bank",
    "aubank": "AU Small Finance Bank",
    "federal": "Federal Bank",
    "southindian": "South Indian Bank",
    "csb": "CSB Bank",
    "dbs": "DBS Bank India",
    "boi": "Bank of India",
    "indianbank": "Indian Bank",
    "mahabank": "Bank of Maharashtra",
    "centralbank": "Central Bank of India",
    "iob": "Indian Overseas Bank",
    "uco": "UCO Bank",
    "psb": "Punjab & Sind Bank",
    "kvb": "Karur Vysya Bank",
    "karnatakabank": "Karnataka Bank",
    "cub": "City Union Bank",
    "tmb": "Tamilnad Mercantile Bank",
    "dhanlaxmi": "Dhanlaxmi Bank",
    "jkbank": "J&K Bank",
    "sbm": "SBM Bank India",
    "onecard": "OneCard",
    "slice": "Slice",
    "jupiter": "Jupiter",
    "uni": "Uni Cards",
    "unicards": "Uni Cards",
    "scapia": "Scapia",
    "fi": "Fi Money",
    "fimoney": "Fi Money",
    "tatacapital": "Tata Capital",
    "adityabirla": "Aditya Birla Finance",
}


@dataclass(frozen=True)
class SanitizedEmail:
    bank_name: str
    subject: str
    clean_body: str
    sender: str = ""
    account_email: str = ""
    message_id: str = ""
    date_received: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


class EmailSanitizer:
    """Sanitize promotional email HTML into local-only text context."""

    BLOCKED_TAGS = {
        "script",
        "style",
        "noscript",
        "iframe",
        "object",
        "embed",
        "form",
        "input",
        "button",
        "meta",
        "link",
        "svg",
    }

    SAFE_TEXT_ATTRS = {"alt", "title"}

    def sanitize(
        self,
        body_html: Optional[str],
        *,
        subject: str = "",
        sender: str = "",
        account_email: str = "",
        message_id: str = "",
        date_received: str = "",
        fallback_text: str = "",
    ) -> SanitizedEmail:
        html = body_html or fallback_text or ""
        soup = BeautifulSoup(html, "html.parser")

        self._remove_blocked_nodes(soup)
        self._remove_hidden_nodes(soup)
        self._replace_images(soup)
        self._preserve_tables(soup)
        self._add_layout_breaks(soup)

        clean_body = self._normalize_text(soup.get_text("\n"))
        return SanitizedEmail(
            bank_name=self.infer_bank_name(sender),
            subject=self._normalize_inline(subject),
            clean_body=clean_body,
            sender=sender,
            account_email=account_email,
            message_id=message_id,
            date_received=date_received,
        )

    def infer_bank_name(self, sender: str) -> str:
        _, address = parseaddr(sender or "")
        haystack = f"{sender} {address}".lower()
        for hint, bank_name in BANK_NAME_HINTS.items():
            if hint in haystack:
                return bank_name
        domain = address.split("@")[-1] if "@" in address else ""
        if domain:
            first_label = domain.split(".")[0]
            return first_label.replace("-", " ").replace("_", " ").title()
        return ""

    def _remove_blocked_nodes(self, soup: BeautifulSoup) -> None:
        for tag in soup.find_all(self.BLOCKED_TAGS):
            tag.decompose()

        for tag in soup.find_all(True):
            for attr in list(tag.attrs):
                lowered = attr.lower()
                if lowered.startswith("on") or lowered in {"srcset", "ping"}:
                    tag.attrs.pop(attr, None)
                    continue
                if lowered not in self.SAFE_TEXT_ATTRS and lowered in {"href", "src"}:
                    tag.attrs.pop(attr, None)

    def _remove_hidden_nodes(self, soup: BeautifulSoup) -> None:
        for tag in list(soup.find_all(True)):
            if tag.has_attr("hidden") or str(tag.get("aria-hidden", "")).lower() == "true":
                tag.decompose()
                continue

            style = self._style_map(tag.get("style", ""))
            if style.get("display") == "none" or style.get("visibility") == "hidden":
                tag.decompose()
                continue
            if style.get("opacity") == "0":
                tag.decompose()
                continue
            if style.get("font-size") in {"0", "0px"}:
                tag.decompose()

    def _replace_images(self, soup: BeautifulSoup) -> None:
        for img in list(soup.find_all("img")):
            if self._is_tracking_pixel(img):
                img.decompose()
                continue
            alt_text = self._normalize_inline(img.get("alt") or img.get("title") or "")
            if alt_text:
                img.replace_with(f" [Image: {alt_text}] ")
            else:
                img.decompose()

    def _is_tracking_pixel(self, img) -> bool:
        width = self._dimension(img.get("width"))
        height = self._dimension(img.get("height"))
        style = self._style_map(img.get("style", ""))
        style_width = self._dimension(style.get("width"))
        style_height = self._dimension(style.get("height"))

        known_small = (
            (width is not None and width <= 1)
            or (height is not None and height <= 1)
            or (style_width is not None and style_width <= 1)
            or (style_height is not None and style_height <= 1)
        )
        src = str(img.get("src", "")).lower()
        beaconish = any(token in src for token in ("track", "pixel", "beacon", "openrate"))
        return known_small or beaconish

    def _preserve_tables(self, soup: BeautifulSoup) -> None:
        for table in list(soup.find_all("table")):
            rows = []
            for row in table.find_all("tr"):
                cells = [
                    self._normalize_inline(cell.get_text(" "))
                    for cell in row.find_all(["th", "td"])
                ]
                cells = [cell for cell in cells if cell]
                if cells:
                    rows.append(" | ".join(cells))
            table_text = "\n".join(rows)
            table.replace_with(f"\n{table_text}\n" if table_text else "\n")

    def _add_layout_breaks(self, soup: BeautifulSoup) -> None:
        for tag_name in ("br", "p", "div", "li", "section", "article", "header", "footer"):
            for tag in soup.find_all(tag_name):
                tag.append("\n")

    def _style_map(self, style: str) -> dict:
        pairs = {}
        for declaration in str(style or "").split(";"):
            if ":" not in declaration:
                continue
            key, value = declaration.split(":", 1)
            pairs[key.strip().lower()] = value.strip().lower()
        return pairs

    def _dimension(self, raw) -> Optional[int]:
        if raw is None:
            return None
        match = re.search(r"\d+", str(raw))
        return int(match.group(0)) if match else None

    def _normalize_inline(self, text: str) -> str:
        return re.sub(r"\s+", " ", text or "").strip()

    def _normalize_text(self, text: str) -> str:
        lines = [self._normalize_inline(line) for line in (text or "").splitlines()]
        lines = [line for line in lines if line]
        return "\n".join(lines)
