import re
from datetime import datetime
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text, JSON
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()

class RawEmailModel(Base):
    __tablename__ = 'raw_emails'

    id = Column(Integer, primary_key=True, autoincrement=True)
    email_id = Column(String, unique=True, index=True, nullable=False)
    sender = Column(String, nullable=False)
    subject = Column(String, nullable=False)
    date_received = Column(DateTime, nullable=False)
    body_text = Column(Text, nullable=True)
    body_html = Column(Text, nullable=True)
    labels = Column(JSON, nullable=True)
    account_email = Column(String, nullable=False, default="unknown")
    processed_status = Column(String, default="PENDING")

class OfferModel(Base):
    __tablename__ = 'offers'

    id = Column(Integer, primary_key=True, autoincrement=True)
    merchant = Column(String, index=True, nullable=False)
    card_name = Column(String, index=True, nullable=False)
    offer_type = Column(String, nullable=False)
    discount_percent = Column(Float, nullable=True)
    min_spend = Column(Float, nullable=True)
    max_cashback = Column(Float, nullable=True)
    valid_from = Column(DateTime, nullable=True)
    valid_until = Column(DateTime, nullable=True)
    source_email_id = Column(String, nullable=False)
    account_email = Column(String, nullable=False, default="unknown")
    unique_hash = Column(String, unique=True, index=True, nullable=False)

def _clean_currency(value):
    """Strips ₹, Rs., commas, asterisks, and parenthetical cruft from LLM output."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    cleaned = re.sub(r'[₹,*()a-zA-Z\s]', '', str(value))
    try:
        return float(cleaned) if cleaned else None
    except ValueError:
        return None

# Pydantic Output Schema for LLM Extraction
class OfferExtraction(BaseModel):
    merchant: Optional[str] = Field(default=None, description="Normalized name of merchant (e.g., 'amazon', 'zomato')")
    card_name: Optional[str] = Field(default=None, description="Credit card or bank name (e.g., 'SBI Card', 'HDFC Bank')")
    offer_type: Optional[str] = Field(default=None, description="Type: 'cashback', 'discount', or 'reward points'")
    discount_percent: Optional[float] = Field(default=None, description="Discount/cashback percentage, e.g. 5 for 5%")
    min_spend: Optional[float] = Field(default=None, description="Minimum spend required")
    max_cashback: Optional[float] = Field(default=None, description="Maximum cap on discount/cashback")
    valid_from: Optional[str] = Field(default=None, description="Start date format YYYY-MM-DD")
    valid_until: Optional[str] = Field(default=None, description="End date format YYYY-MM-DD")

    @field_validator('discount_percent', 'min_spend', 'max_cashback', mode='before')
    @classmethod
    def clean_currency_fields(cls, v):
        return _clean_currency(v)
    
class EmailPayload(BaseModel):
    email_id: str
    sender: str
    subject: str
    date_received: datetime
    body_text: str
    body_html: str
    labels: List[str]
    account_email: str
