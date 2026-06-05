import re
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Text, JSON,
    Boolean, ForeignKey, Index
)
from sqlalchemy.orm import declarative_base

Base = declarative_base()


# ─── Email Models ─────────────────────────────────────────────────────────────

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
    image_urls = Column(JSON, nullable=True, default=list)
    email_type = Column(String, default="promotional")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


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
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_offer_merchant_card', 'merchant', 'card_name'),
        Index('idx_offer_expiry', 'valid_until'),
    )


class BannerOfferModel(Base):
    __tablename__ = 'banner_offers'

    id = Column(Integer, primary_key=True, autoincrement=True)
    raw_email_id = Column(String, ForeignKey('raw_emails.email_id'), nullable=False)
    banner_url = Column(String, nullable=False)
    content_type = Column(String)
    extracted_text = Column(Text)
    extraction_method = Column(String)
    extraction_status = Column(String, default="pending")
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class ChunkModel(Base):
    __tablename__ = 'chunks'

    id = Column(Integer, primary_key=True, autoincrement=True)
    email_id = Column(String, ForeignKey('raw_emails.email_id'), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    chunk_type = Column(String, default="general")
    source = Column(String)
    text = Column(Text, nullable=False)
    weight = Column(Float, default=1.0)
    merchants = Column(JSON, default=list)
    cards = Column(JSON, default=list)
    discount_percent = Column(Float, nullable=True)
    min_spend = Column(Float, nullable=True)
    max_cashback = Column(Float, nullable=True)
    expiry_date = Column(String, nullable=True)
    offer_type = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_chunk_type', 'chunk_type'),
    )


# ─── Transaction Models ────────────────────────────────────────────────────

class TransactionModel(Base):
    __tablename__ = 'transactions'

    id = Column(Integer, primary_key=True, autoincrement=True)
    email_id = Column(String, ForeignKey('raw_emails.email_id'), nullable=True)
    profile_id = Column(Integer, nullable=True)
    account_email = Column(String, nullable=True)

    merchant_raw = Column(String, nullable=True)
    merchant_normalized = Column(String, index=True, nullable=True)
    amount = Column(Float, nullable=True)
    currency = Column(String, default="INR")
    transaction_date = Column(DateTime, nullable=True)

    card_last4 = Column(String, nullable=True)
    card_name = Column(String, nullable=True)
    bank_name = Column(String, nullable=True)

    transaction_type = Column(String, default="debit")
    category = Column(String, nullable=True)
    source = Column(String, default="email_parser")

    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_txn_profile', 'profile_id'),
        Index('idx_txn_merchant', 'merchant_normalized'),
        Index('idx_txn_date', 'transaction_date'),
        Index('idx_txn_category', 'category'),
    )


class MerchantNormalizationModel(Base):
    __tablename__ = 'merchant_normalizations'

    id = Column(Integer, primary_key=True, autoincrement=True)
    raw_name = Column(String, unique=True, nullable=False)
    normalized_name = Column(String, nullable=False)
    category = Column(String, nullable=True)
    aliases = Column(JSON, default=list)

    __table_args__ = (
        Index('idx_merchant_normalized', 'normalized_name'),
    )


class CardNetworkRuleModel(Base):
    __tablename__ = 'card_network_rules'

    id = Column(Integer, primary_key=True, autoincrement=True)
    card_name = Column(String, nullable=False)
    network = Column(String, nullable=True)
    bank_name = Column(String, nullable=True)
    accepted_merchants = Column(JSON, default=list)
    excluded_merchants = Column(JSON, default=list)
    base_earning_percent = Column(Float, default=1.0)
    category_earnings = Column(JSON, default=dict)
    accelerated_merchants = Column(JSON, default=dict)
    max_monthly_points = Column(Float, nullable=True)

    __table_args__ = (
        Index('idx_cardrule_card', 'card_name'),
    )


# ─── User Models ─────────────────────────────────────────────────────────────

class UserProfile(Base):
    __tablename__ = 'user_profiles'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String)
    email = Column(String, unique=True)
    password_hash = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ProfileAccountMapping(Base):
    __tablename__ = 'profile_account_mappings'

    id = Column(Integer, primary_key=True, autoincrement=True)
    profile_id = Column(Integer, ForeignKey('user_profiles.id'), nullable=False)
    account_email = Column(String, nullable=False)
    account_label = Column(String, nullable=True)
    is_primary = Column(Boolean, default=False)
    synced_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_profile_account', 'profile_id', 'account_email', unique=True),
    )


class UserCard(Base):
    __tablename__ = 'user_cards'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('user_profiles.id'), nullable=False)
    card_name = Column(String, nullable=False)
    card_last4 = Column(String)
    bank_name = Column(String)
    card_network = Column(String)
    is_primary = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    added_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_usercard_user', 'user_id'),
    )


class UserSettings(Base):
    __tablename__ = 'user_settings'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('user_profiles.id'), unique=True, nullable=False)
    auto_sync_on_open = Column(Boolean, default=True)
    sync_frequency_hours = Column(Integer, default=24)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class UserSession(Base):
    __tablename__ = 'user_sessions'

    id = Column(String, primary_key=True)
    user_id = Column(Integer, ForeignKey('user_profiles.id'), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_active = Column(DateTime, default=datetime.utcnow)


# ─── Notification Models ─────────────────────────────────────────────────────

class NotificationModel(Base):
    __tablename__ = 'notifications'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('user_profiles.id'), nullable=False)
    type = Column(String, nullable=False)
    title = Column(String, nullable=False)
    message = Column(Text)
    read = Column(Boolean, default=False)
    offer_id = Column(Integer, ForeignKey('offers.id'), nullable=True)
    chunk_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_notification_user_unread', 'user_id', 'read'),
    )


# ─── Retrieval Audit Models ──────────────────────────────────────────────────

class RetrievalAuditModel(Base):
    __tablename__ = 'retrieval_audit'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('user_profiles.id'), nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    query = Column(Text)
    intent = Column(String)
    plan_mode = Column(String)
    top_k_requested = Column(Integer)
    raw_candidates_count = Column(Integer)
    final_candidates_count = Column(Integer)
    prefilter_rejected = Column(JSON)
    rerank_applied = Column(Boolean, default=False)
    conflicts_detected = Column(JSON)
    llm_response_length = Column(Integer)
    response_time_ms = Column(Float)
    error = Column(Text, nullable=True)


# ─── Sync History ────────────────────────────────────────────────────────────

class SyncHistory(Base):
    __tablename__ = 'sync_history'

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_email = Column(String, nullable=False)
    status = Column(String)
    new_emails = Column(Integer, default=0)
    new_offers = Column(Integer, default=0)
    new_banners = Column(Integer, default=0)
    new_chunks = Column(Integer, default=0)
    new_transactions = Column(Integer, default=0)
    errors = Column(JSON, default=list)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)


# ─── Pydantic Schemas ────────────────────────────────────────────────────────

def _clean_currency(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    cleaned = re.sub(r'[₹,*()a-zA-Z\s]', '', str(value))
    try:
        return float(cleaned) if cleaned else None
    except ValueError:
        return None


class OfferExtraction(BaseModel):
    merchant: Optional[str] = None
    card_name: Optional[str] = None
    offer_type: Optional[str] = None
    discount_percent: Optional[float] = None
    min_spend: Optional[float] = None
    max_cashback: Optional[float] = None
    valid_from: Optional[str] = None
    valid_until: Optional[str] = None

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
    image_urls: List[str] = Field(default_factory=list)
    email_type: str = "promotional"


class BannerResult(BaseModel):
    banner_url: str
    content_type: Optional[str] = None
    extracted_text: Optional[str] = None
    extraction_method: Optional[str] = None
    extraction_status: str = "pending"
    error_message: Optional[str] = None


class ChunkPayload(BaseModel):
    chunk_id: str
    email_id: str
    text: str
    chunk_type: str = "general"
    source: Optional[str] = None
    weight: float = 1.0
    merchants: List[str] = Field(default_factory=list)
    cards: List[str] = Field(default_factory=list)
    discount_percent: Optional[float] = None
    min_spend: Optional[float] = None
    max_cashback: Optional[float] = None
    expiry_date: Optional[str] = None
    offer_type: Optional[str] = None


class TransactionPayload(BaseModel):
    email_id: Optional[str] = None
    account_email: Optional[str] = None
    merchant_raw: Optional[str] = None
    merchant_normalized: Optional[str] = None
    amount: Optional[float] = None
    transaction_date: Optional[datetime] = None
    card_last4: Optional[str] = None
    card_name: Optional[str] = None
    bank_name: Optional[str] = None
    transaction_type: str = "debit"
    category: Optional[str] = None


class SpendPatternResponse(BaseModel):
    by_category: dict
    monthly: dict
    frequency: dict
    avg_per_category: dict
    top_merchants: list
    trend: str
    total_90d: float
    avg_monthly: float


class AccountAssignmentRequest(BaseModel):
    account_email: str
    profile_id: int
    account_label: Optional[str] = None
    is_primary: bool = False


class UserSettingsPayload(BaseModel):
    auto_sync_on_open: bool = True
    sync_frequency_hours: int = 24
