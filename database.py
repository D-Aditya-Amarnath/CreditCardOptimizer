import os
import json
from datetime import datetime, timedelta
from typing import Optional, List
from sqlalchemy import create_engine, text, and_, or_, func
from sqlalchemy.orm import sessionmaker
from models import (
    Base, RawEmailModel, OfferModel, BannerOfferModel, ChunkModel,
    UserProfile, UserCard, UserSession, NotificationModel,
    RetrievalAuditModel, SyncHistory, EmailPayload, BannerResult,
    TransactionModel, MerchantNormalizationModel, CardNetworkRuleModel,
    ProfileAccountMapping, UserSettings, TransactionPayload,
    SpendPatternResponse,
)


class DatabaseManager:
    def __init__(self, db_url: str = None):
        if db_url is None:
            db_url = os.getenv("DATABASE_URL", "sqlite:///offers.db")
        self.engine = create_engine(
            db_url,
            connect_args={"check_same_thread": False} if db_url.startswith("sqlite") else {}
        )
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

    def initialize_schema(self):
        Base.metadata.create_all(bind=self.engine)
        self._run_migrations()
        self._seed_card_network_rules()

    def _run_migrations(self):
        with self.get_session() as session:
            try:
                session.execute(text("ALTER TABLE raw_emails ADD COLUMN email_type TEXT"))
                session.commit()
            except Exception:
                session.rollback()

            try:
                session.execute(text("ALTER TABLE sync_history ADD COLUMN new_transactions INTEGER DEFAULT 0"))
                session.commit()
            except Exception:
                session.rollback()

    def _seed_card_network_rules(self):
        with self.get_session() as session:
            existing = session.query(CardNetworkRuleModel).first()
            if existing:
                return

            rules = [
                CardNetworkRuleModel(
                    card_name="American Express",
                    network="Amex",
                    bank_name="American Express",
                    excluded_merchants=["amazon", "flipkart", "bigbasket", "swiggy", "zomato"],
                    base_earning_percent=1.0,
                    category_earnings={"shopping": 2.0, "travel": 3.0, "dining": 2.0, "fuel": 0.5},
                ),
                CardNetworkRuleModel(
                    card_name="HDFC Regalia Gold",
                    network="Visa",
                    bank_name="HDFC Bank",
                    accepted_merchants=[],
                    excluded_merchants=[],
                    base_earning_percent=1.0,
                    category_earnings={"dining": 2.5, "travel": 3.0, "shopping": 1.5, "groceries": 1.0},
                    accelerated_merchants={"amazon": 0.5, "myntra": 0.5},
                ),
                CardNetworkRuleModel(
                    card_name="HDFC MoneyBack+",
                    network="Visa",
                    bank_name="HDFC Bank",
                    accepted_merchants=[],
                    excluded_merchants=[],
                    base_earning_percent=0.5,
                    category_earnings={"food": 1.0, "groceries": 1.0, "payments": 0.5},
                ),
                CardNetworkRuleModel(
                    card_name="SBI Card PRIME",
                    network="Visa",
                    bank_name="SBI Card",
                    accepted_merchants=[],
                    excluded_merchants=[],
                    base_earning_percent=1.0,
                    category_earnings={"travel": 5.0, "movies": 2.0, "dining": 2.0},
                ),
                CardNetworkRuleModel(
                    card_name="ICICI Amazon Pay",
                    network="Visa",
                    bank_name="ICICI Bank",
                    accepted_merchants=[],
                    excluded_merchants=[],
                    base_earning_percent=1.0,
                    category_earnings={"amazon": 5.0},
                ),
                CardNetworkRuleModel(
                    card_name="Axis Ace",
                    network="Visa",
                    bank_name="Axis Bank",
                    accepted_merchants=[],
                    excluded_merchants=[],
                    base_earning_percent=0.5,
                    category_earnings={"groceries": 1.5, "utilities": 1.0},
                ),
            ]

            for rule in rules:
                session.add(rule)
            session.commit()

    def get_session(self):
        return self.SessionLocal()

    # ─── Raw Email ─────────────────────────────────────────────────────────────

    def raw_email_exists(self, email_id: str) -> bool:
        with self.get_session() as session:
            return session.query(RawEmailModel).filter(RawEmailModel.email_id == email_id).first() is not None

    def insert_raw_email(self, payload: EmailPayload) -> RawEmailModel:
        with self.get_session() as session:
            db_email = RawEmailModel(
                email_id=payload.email_id,
                sender=payload.sender,
                subject=payload.subject,
                date_received=payload.date_received,
                body_text=payload.body_text,
                body_html=payload.body_html,
                labels=payload.labels,
                account_email=payload.account_email,
                processed_status="PENDING",
                image_urls=payload.image_urls,
                email_type=getattr(payload, 'email_type', 'promotional'),
            )
            session.add(db_email)
            session.commit()
            session.refresh(db_email)
            return db_email

    def update_email_status(self, email_id: str, status: str):
        with self.get_session() as session:
            email = session.query(RawEmailModel).filter(RawEmailModel.email_id == email_id).first()
            if email:
                email.processed_status = status
                email.updated_at = datetime.utcnow()
                session.commit()

    def update_email_type(self, email_id: str, email_type: str):
        with self.get_session() as session:
            email = session.query(RawEmailModel).filter(RawEmailModel.email_id == email_id).first()
            if email:
                email.email_type = email_type
                session.commit()

    def get_latest_email_date(self, account_email: str) -> Optional[datetime]:
        with self.get_session() as session:
            latest = session.query(RawEmailModel).filter(
                RawEmailModel.account_email == account_email
            ).order_by(RawEmailModel.date_received.desc()).first()
            return latest.date_received if latest else None

    def get_email_by_id(self, email_id: str) -> Optional[RawEmailModel]:
        with self.get_session() as session:
            return session.query(RawEmailModel).filter(RawEmailModel.email_id == email_id).first()

    def get_emails_paginated(self, limit: int = 20, offset: int = 0, account_email: str = None) -> List[RawEmailModel]:
        with self.get_session() as session:
            q = session.query(RawEmailModel)
            if account_email:
                q = q.filter(RawEmailModel.account_email == account_email)
            return q.order_by(RawEmailModel.date_received.desc()).offset(offset).limit(limit).all()

    def count_emails(self, account_email: str = None) -> int:
        with self.get_session() as session:
            q = session.query(func.count(RawEmailModel.id))
            if account_email:
                q = q.filter(RawEmailModel.account_email == account_email)
            return q.scalar()

    def get_transactions_paginated(self, profile_id: int, limit: int = 20, offset: int = 0) -> List[TransactionModel]:
        with self.get_session() as session:
            return session.query(TransactionModel).filter(
                TransactionModel.profile_id == profile_id
            ).order_by(TransactionModel.transaction_date.desc()).offset(offset).limit(limit).all()

    # ─── Offers ─────────────────────────────────────────────────────────────

    def offer_exists(self, unique_hash: str) -> bool:
        with self.get_session() as session:
            return session.query(OfferModel).filter(OfferModel.unique_hash == unique_hash).first() is not None

    def insert_offer(self, offer) -> OfferModel:
        with self.get_session() as session:
            session.add(offer)
            session.commit()
            session.refresh(offer)
            return offer

    def get_offers_by_merchant(self, merchant: str, user_cards: List[str] = None) -> List[OfferModel]:
        with self.get_session() as session:
            q = session.query(OfferModel).filter(
                func.lower(OfferModel.merchant).like(f"%{merchant.lower()}%")
            )
            if user_cards:
                or_conditions = [func.lower(OfferModel.card_name).like(f"%{card.lower()}%") for card in user_cards]
                q = q.filter(or_(*or_conditions))
            q = q.filter(or_(
                OfferModel.valid_until == None,
                OfferModel.valid_until >= datetime.utcnow()
            ))
            return q.order_by(OfferModel.discount_percent.desc()).all()

    def get_all_offers(self, user_cards: List[str] = None, limit: int = 100) -> List[OfferModel]:
        with self.get_session() as session:
            q = session.query(OfferModel)
            if user_cards:
                or_conditions = [func.lower(OfferModel.card_name).like(f"%{card.lower()}%") for card in user_cards]
                q = q.filter(or_(*or_conditions))
            return q.order_by(OfferModel.discount_percent.desc()).limit(limit).all()

    def get_expiring_offers(self, user_cards: List[str], days: int = 7) -> List[OfferModel]:
        cutoff = datetime.utcnow()
        future = cutoff + timedelta(days=days)
        with self.get_session() as session:
            q = session.query(OfferModel).filter(
                OfferModel.valid_until != None,
                OfferModel.valid_until >= cutoff,
                OfferModel.valid_until <= future
            )
            if user_cards:
                or_conditions = [func.lower(OfferModel.card_name).like(f"%{card.lower()}%") for card in user_cards]
                q = q.filter(or_(*or_conditions))
            return q.order_by(OfferModel.valid_until.asc()).all()

    def count_offers(self) -> int:
        with self.get_session() as session:
            return session.query(func.count(OfferModel.id)).scalar()

    def compare_offers(self, merchant: str, amount: float, user_cards: List[str] = None) -> List[OfferModel]:
        with self.get_session() as session:
            q = session.query(OfferModel).filter(
                func.lower(OfferModel.merchant).like(f"%{merchant.lower()}%"),
                or_(
                    OfferModel.min_spend == None,
                    OfferModel.min_spend <= amount
                ),
                or_(
                    OfferModel.valid_until == None,
                    OfferModel.valid_until >= datetime.utcnow()
                )
            )
            if user_cards:
                or_conditions = [func.lower(OfferModel.card_name).like(f"%{card.lower()}%") for card in user_cards]
                q = q.filter(or_(*or_conditions))
            return q.order_by(OfferModel.discount_percent.desc()).all()

    def get_offers_for_merchant(self, merchant: str, user_cards: List[str] = None) -> List[OfferModel]:
        return self.get_offers_by_merchant(merchant, user_cards)

    # ─── Chunks ───────────────────────────────────────────────────────────────

    def insert_chunk(self, chunk) -> ChunkModel:
        with self.get_session() as session:
            session.add(chunk)
            session.commit()
            session.refresh(chunk)
            return chunk

    def count_chunks(self) -> int:
        with self.get_session() as session:
            return session.query(func.count(ChunkModel.id)).scalar()

    def get_all_chunks(self) -> List[ChunkModel]:
        with self.get_session() as session:
            return session.query(ChunkModel).all()

    # ─── Transactions ───────────────────────────────────────────────────────

    def insert_transaction(self, txn: TransactionPayload, profile_id: int) -> TransactionModel:
        with self.get_session() as session:
            db_txn = TransactionModel(
                email_id=txn.email_id,
                profile_id=profile_id,
                account_email=txn.account_email,
                merchant_raw=txn.merchant_raw,
                merchant_normalized=txn.merchant_normalized,
                amount=txn.amount,
                transaction_date=txn.transaction_date,
                card_last4=txn.card_last4,
                card_name=txn.card_name,
                bank_name=txn.bank_name,
                transaction_type=txn.transaction_type,
                category=txn.category,
            )
            session.add(db_txn)
            session.commit()
            session.refresh(db_txn)
            return db_txn

    def transaction_exists(self, email_id: str) -> bool:
        with self.get_session() as session:
            return session.query(TransactionModel).filter(
                TransactionModel.email_id == email_id
            ).first() is not None

    def get_transactions_by_profile(self, profile_id: int, days: int = 90) -> List[TransactionModel]:
        cutoff = datetime.utcnow() - timedelta(days=days)
        with self.get_session() as session:
            return session.query(TransactionModel).filter(
                TransactionModel.profile_id == profile_id,
                TransactionModel.transaction_date >= cutoff
            ).order_by(TransactionModel.transaction_date.desc()).all()

    def count_transactions(self, profile_id: int = None) -> int:
        with self.get_session() as session:
            q = session.query(func.count(TransactionModel.id))
            if profile_id:
                q = q.filter(TransactionModel.profile_id == profile_id)
            return q.scalar()

    def get_spend_by_category(self, profile_id: int, days: int = 90) -> dict:
        cutoff = datetime.utcnow() - timedelta(days=days)
        with self.get_session() as session:
            txns = session.query(TransactionModel).filter(
                TransactionModel.profile_id == profile_id,
                TransactionModel.transaction_date >= cutoff,
                TransactionModel.transaction_type == 'debit'
            ).all()
            result = {}
            for t in txns:
                cat = t.category or 'other'
                result[cat] = result.get(cat, 0) + (t.amount or 0)
            return dict(sorted(result.items(), key=lambda x: x[1], reverse=True))

    def get_monthly_spend(self, profile_id: int, months: int = 3) -> dict:
        result = {}
        with self.get_session() as session:
            for i in range(months):
                month_start = datetime.utcnow().replace(day=1) - timedelta(days=30 * i)
                month_end = month_start + timedelta(days=32)
                total = session.query(func.sum(TransactionModel.amount)).filter(
                    TransactionModel.profile_id == profile_id,
                    TransactionModel.transaction_type == 'debit',
                    TransactionModel.transaction_date >= month_start,
                    TransactionModel.transaction_date < month_end,
                ).scalar() or 0
                result[month_start.strftime('%b %Y')] = float(total)
        return result

    def get_top_merchants(self, profile_id: int, days: int = 90, limit: int = 10) -> list:
        cutoff = datetime.utcnow() - timedelta(days=days)
        with self.get_session() as session:
            results = session.query(
                TransactionModel.merchant_normalized,
                func.sum(TransactionModel.amount).label('total'),
                func.count(TransactionModel.id).label('count')
            ).filter(
                TransactionModel.profile_id == profile_id,
                TransactionModel.transaction_date >= cutoff,
                TransactionModel.transaction_type == 'debit',
                TransactionModel.merchant_normalized != None
            ).group_by(TransactionModel.merchant_normalized).order_by(
                func.sum(TransactionModel.amount).desc()
            ).limit(limit).all()
            return [
                {"merchant": r.merchant_normalized, "total": float(r.total), "count": r.count}
                for r in results
            ]

    def get_transaction_frequency(self, profile_id: int, days: int = 90) -> dict:
        cutoff = datetime.utcnow() - timedelta(days=days)
        with self.get_session() as session:
            count = session.query(func.count(TransactionModel.id)).filter(
                TransactionModel.profile_id == profile_id,
                TransactionModel.transaction_date >= cutoff,
                TransactionModel.transaction_type == 'debit',
            ).scalar() or 0
            weeks = days / 7
            return {
                "per_week": round(count / weeks, 1),
                "per_month": round(count / (days / 30), 1),
                "total_transactions": count,
            }

    # ─── Merchant Normalization ─────────────────────────────────────────────

    def get_merchant_normalization(self, raw_name: str) -> Optional[MerchantNormalizationModel]:
        with self.get_session() as session:
            return session.query(MerchantNormalizationModel).filter(
                MerchantNormalizationModel.raw_name == raw_name
            ).first()

    def save_merchant_normalization(self, raw_name: str, normalized: str, category: str = None, aliases: list = None):
        with self.get_session() as session:
            existing = session.query(MerchantNormalizationModel).filter(
                MerchantNormalizationModel.raw_name == raw_name
            ).first()
            if not existing:
                mn = MerchantNormalizationModel(
                    raw_name=raw_name,
                    normalized_name=normalized,
                    category=category,
                    aliases=aliases or []
                )
                session.add(mn)
                session.commit()

    def get_all_merchant_normalizations(self) -> List[MerchantNormalizationModel]:
        with self.get_session() as session:
            return session.query(MerchantNormalizationModel).all()

    # ─── Card Network Rules ──────────────────────────────────────────────────

    def get_card_network_rules(self, card_name: str) -> Optional[CardNetworkRuleModel]:
        with self.get_session() as session:
            return session.query(CardNetworkRuleModel).filter(
                func.lower(CardNetworkRuleModel.card_name).like(f"%{card_name.lower()}%")
            ).first()

    def get_all_card_network_rules(self) -> List[CardNetworkRuleModel]:
        with self.get_session() as session:
            return session.query(CardNetworkRuleModel).all()

    def upsert_card_network_rule(self, card_name: str, **kwargs) -> CardNetworkRuleModel:
        with self.get_session() as session:
            rule = session.query(CardNetworkRuleModel).filter(
                func.lower(CardNetworkRuleModel.card_name) == card_name.lower()
            ).first()
            if not rule:
                rule = CardNetworkRuleModel(card_name=card_name, **kwargs)
                session.add(rule)
            else:
                for k, v in kwargs.items():
                    setattr(rule, k, v)
            session.commit()
            session.refresh(rule)
            return rule

    # ─── User ────────────────────────────────────────────────────────────────

    def get_user_by_email(self, email: str) -> Optional[UserProfile]:
        with self.get_session() as session:
            return session.query(UserProfile).filter(UserProfile.email == email).first()

    def get_user_by_id(self, user_id: int) -> Optional[UserProfile]:
        with self.get_session() as session:
            return session.query(UserProfile).filter(UserProfile.id == user_id).first()

    def create_user(self, name: str, email: str, password_hash: str) -> UserProfile:
        with self.get_session() as session:
            user = UserProfile(name=name, email=email, password_hash=password_hash)
            session.add(user)
            session.commit()
            session.refresh(user)
            settings = UserSettings(user_id=user.id, auto_sync_on_open=True, sync_frequency_hours=24)
            session.add(settings)
            session.commit()
            return user

    def get_all_profiles(self) -> List[UserProfile]:
        with self.get_session() as session:
            return session.query(UserProfile).all()

    def get_user_cards(self, user_id: int) -> List[UserCard]:
        with self.get_session() as session:
            return session.query(UserCard).filter(
                UserCard.user_id == user_id,
                UserCard.is_active == True
            ).order_by(UserCard.is_primary.desc()).all()

    def add_user_card(self, user_id: int, card_name: str, bank_name: str = None,
                      card_last4: str = None, card_network: str = None,
                      is_primary: bool = False) -> UserCard:
        with self.get_session() as session:
            if is_primary:
                session.query(UserCard).filter(UserCard.user_id == user_id).update({"is_primary": False})
            card = UserCard(
                user_id=user_id, card_name=card_name, bank_name=bank_name,
                card_last4=card_last4, card_network=card_network, is_primary=is_primary
            )
            session.add(card)
            session.commit()
            session.refresh(card)
            return card

    def remove_user_card(self, user_id: int, card_id: int):
        with self.get_session() as session:
            card = session.query(UserCard).filter(
                UserCard.id == card_id, UserCard.user_id == user_id
            ).first()
            if card:
                card.is_active = False
                session.commit()

    def set_primary_card(self, user_id: int, card_id: int):
        with self.get_session() as session:
            session.query(UserCard).filter(UserCard.user_id == user_id).update({"is_primary": False})
            session.query(UserCard).filter(
                UserCard.id == card_id, UserCard.user_id == user_id
            ).update({"is_primary": True})
            session.commit()

    # ─── Profile-Account Mapping ────────────────────────────────────────────

    def assign_account_to_profile(self, profile_id: int, account_email: str,
                                 label: str = None, is_primary: bool = False) -> ProfileAccountMapping:
        with self.get_session() as session:
            existing = session.query(ProfileAccountMapping).filter(
                ProfileAccountMapping.profile_id == profile_id,
                ProfileAccountMapping.account_email == account_email
            ).first()
            if existing:
                if label:
                    existing.account_label = label
                existing.synced_at = datetime.utcnow()
                session.commit()
                return existing
            mapping = ProfileAccountMapping(
                profile_id=profile_id,
                account_email=account_email,
                account_label=label,
                is_primary=is_primary,
                synced_at=datetime.utcnow()
            )
            session.add(mapping)
            session.commit()
            session.refresh(mapping)
            return mapping

    def get_accounts_for_profile(self, profile_id: int) -> List[ProfileAccountMapping]:
        with self.get_session() as session:
            return session.query(ProfileAccountMapping).filter(
                ProfileAccountMapping.profile_id == profile_id
            ).all()

    def get_profile_by_account(self, account_email: str) -> Optional[UserProfile]:
        with self.get_session() as session:
            mapping = session.query(ProfileAccountMapping).filter(
                ProfileAccountMapping.account_email == account_email
            ).first()
            if mapping:
                return session.query(UserProfile).filter(
                    UserProfile.id == mapping.profile_id
                ).first()
            return None

    def remove_account_mapping(self, account_email: str):
        with self.get_session() as session:
            session.query(ProfileAccountMapping).filter(
                ProfileAccountMapping.account_email == account_email
            ).delete()
            session.commit()

    def get_all_accounts(self) -> List[dict]:
        with self.get_session() as session:
            results = session.query(ProfileAccountMapping, UserProfile).join(
                UserProfile, ProfileAccountMapping.profile_id == UserProfile.id
            ).all()
            return [
                {
                    "account_email": m.account_email,
                    "account_label": m.account_label,
                    "profile_id": m.profile_id,
                    "profile_name": p.name,
                    "is_primary": m.is_primary,
                    "synced_at": m.synced_at.isoformat() if m.synced_at else None,
                }
                for m, p in results
            ]

    # ─── User Settings ──────────────────────────────────────────────────────

    def get_user_settings(self, user_id: int) -> UserSettings:
        with self.get_session() as session:
            settings = session.query(UserSettings).filter(
                UserSettings.user_id == user_id
            ).first()
            if not settings:
                settings = UserSettings(user_id=user_id, auto_sync_on_open=True, sync_frequency_hours=24)
                session.add(settings)
                session.commit()
                session.refresh(settings)
            return settings

    def update_user_settings(self, user_id: int, auto_sync_on_open: bool = None,
                             sync_frequency_hours: int = None) -> UserSettings:
        with self.get_session() as session:
            settings = session.query(UserSettings).filter(
                UserSettings.user_id == user_id
            ).first()
            if not settings:
                settings = UserSettings(user_id=user_id)
                session.add(settings)
            if auto_sync_on_open is not None:
                settings.auto_sync_on_open = auto_sync_on_open
            if sync_frequency_hours is not None:
                settings.sync_frequency_hours = sync_frequency_hours
            session.commit()
            session.refresh(settings)
            return settings

    # ─── Sessions ───────────────────────────────────────────────────────────

    def create_session(self, session_id: str, user_id: int) -> UserSession:
        with self.get_session() as session:
            user_session = UserSession(id=session_id, user_id=user_id)
            session.add(user_session)
            session.commit()
            return user_session

    def get_user_session(self, session_id: str) -> Optional[UserSession]:
        with self.get_session() as session:
            s = session.query(UserSession).filter(UserSession.id == session_id).first()
            if s:
                s.last_active = datetime.utcnow()
                session.commit()
            return s

    def delete_session(self, session_id: str):
        with self.get_session() as session:
            session.query(UserSession).filter(UserSession.id == session_id).delete()
            session.commit()

    def get_user_by_session(self, session_id: str) -> Optional[UserProfile]:
        user_session = self.get_user_session(session_id)
        if not user_session:
            return None
        return self.get_user_by_id(user_session.user_id)

    # ─── Notifications ───────────────────────────────────────────────────────

    def create_notification(self, user_id: int, notif_type: str, title: str,
                            message: str = None, offer_id: int = None) -> NotificationModel:
        with self.get_session() as session:
            notif = NotificationModel(
                user_id=user_id, type=notif_type, title=title, message=message, offer_id=offer_id
            )
            session.add(notif)
            session.commit()
            session.refresh(notif)
            return notif

    def get_unread_notifications(self, user_id: int, limit: int = 20) -> List[NotificationModel]:
        with self.get_session() as session:
            return session.query(NotificationModel).filter(
                NotificationModel.user_id == user_id,
                NotificationModel.read == False
            ).order_by(NotificationModel.created_at.desc()).limit(limit).all()

    def get_all_notifications(self, user_id: int, limit: int = 50) -> List[NotificationModel]:
        with self.get_session() as session:
            return session.query(NotificationModel).filter(
                NotificationModel.user_id == user_id
            ).order_by(NotificationModel.created_at.desc()).limit(limit).all()

    def mark_notification_read(self, user_id: int, notif_id: int):
        with self.get_session() as session:
            session.query(NotificationModel).filter(
                NotificationModel.id == notif_id, NotificationModel.user_id == user_id
            ).update({"read": True})
            session.commit()

    def mark_all_notifications_read(self, user_id: int):
        with self.get_session() as session:
            session.query(NotificationModel).filter(
                NotificationModel.user_id == user_id, NotificationModel.read == False
            ).update({"read": True})
            session.commit()

    def count_unread_notifications(self, user_id: int) -> int:
        with self.get_session() as session:
            return session.query(func.count(NotificationModel.id)).filter(
                NotificationModel.user_id == user_id, NotificationModel.read == False
            ).scalar()

    # ─── Retrieval Audit ────────────────────────────────────────────────────

    def insert_audit_log(self, log_entry: RetrievalAuditModel):
        with self.get_session() as session:
            session.add(log_entry)
            session.commit()

    def get_audit_logs(self, user_id: int = None, limit: int = 100) -> List[RetrievalAuditModel]:
        with self.get_session() as session:
            q = session.query(RetrievalAuditModel)
            if user_id:
                q = q.filter(RetrievalAuditModel.user_id == user_id)
            return q.order_by(RetrievalAuditModel.timestamp.desc()).limit(limit).all()

    # ─── Sync History ───────────────────────────────────────────────────────

    def create_sync_history(self, account_email: str) -> SyncHistory:
        with self.get_session() as session:
            sync = SyncHistory(account_email=account_email, status="running")
            session.add(sync)
            session.commit()
            session.refresh(sync)
            return sync

    def update_sync_history(self, sync_id: int, status: str = None,
                            new_emails: int = None, new_offers: int = None,
                            new_banners: int = None, new_chunks: int = None,
                            new_transactions: int = None, errors: list = None):
        with self.get_session() as session:
            sync = session.query(SyncHistory).filter(SyncHistory.id == sync_id).first()
            if sync:
                if status: sync.status = status
                if new_emails is not None: sync.new_emails = new_emails
                if new_offers is not None: sync.new_offers = new_offers
                if new_banners is not None: sync.new_banners = new_banners
                if new_chunks is not None: sync.new_chunks = new_chunks
                if new_transactions is not None: sync.new_transactions = new_transactions
                if errors is not None: sync.errors = errors
                if status in ("completed", "failed"):
                    sync.completed_at = datetime.utcnow()
                session.commit()

    def get_sync_history(self, limit: int = 20) -> List[SyncHistory]:
        with self.get_session() as session:
            return session.query(SyncHistory).order_by(
                SyncHistory.started_at.desc()
            ).limit(limit).all()

    def get_recent_sync_date(self) -> Optional[datetime]:
        with self.get_session() as session:
            recent = session.query(SyncHistory).filter(
                SyncHistory.status == "completed"
            ).order_by(SyncHistory.completed_at.desc()).first()
            return recent.completed_at if recent else None

    # ─── Banner Offers ──────────────────────────────────────────────────────

    def insert_banner_offer(self, banner: BannerResult, email_id: str) -> BannerOfferModel:
        with self.get_session() as session:
            db_banner = BannerOfferModel(
                raw_email_id=email_id,
                banner_url=banner.banner_url,
                content_type=banner.content_type,
                extracted_text=banner.extracted_text,
                extraction_method=banner.extraction_method,
                extraction_status=banner.extraction_status,
                error_message=banner.error_message
            )
            session.add(db_banner)
            session.commit()
            session.refresh(db_banner)
            return db_banner

    def count_banners(self) -> int:
        with self.get_session() as session:
            return session.query(func.count(BannerOfferModel.id)).scalar()

    # ─── Dashboard Stats ───────────────────────────────────────────────────

    def get_dashboard_stats(self, user_id: int = None) -> dict:
        user_cards = []
        if user_id:
            user_cards = [c.card_name for c in self.get_user_cards(user_id)]

        with self.get_session() as session:
            total_emails = session.query(func.count(RawEmailModel.id)).scalar() or 0
            total_offers = session.query(func.count(OfferModel.id)).scalar() or 0
            total_chunks = session.query(func.count(ChunkModel.id)).scalar() or 0
            total_banners = session.query(func.count(BannerOfferModel.id)).scalar() or 0
            total_txns = self.count_transactions(user_id)

            expiring_cutoff = datetime.utcnow() + timedelta(days=7)
            expiring_offers = session.query(OfferModel).filter(
                OfferModel.valid_until != None,
                OfferModel.valid_until >= datetime.utcnow(),
                OfferModel.valid_until <= expiring_cutoff
            )
            if user_cards:
                or_conditions = [
                    func.lower(OfferModel.card_name).like(f"%{card.lower()}%")
                    for card in user_cards
                ]
                expiring_offers = expiring_offers.filter(or_(*or_conditions))
            expiring_count = expiring_offers.count()

            recent_sync = session.query(SyncHistory).filter(
                SyncHistory.status == "completed"
            ).order_by(SyncHistory.completed_at.desc()).first()

            return {
                "total_emails": total_emails,
                "total_offers": total_offers,
                "total_chunks": total_chunks,
                "total_banners": total_banners,
                "total_transactions": total_txns,
                "expiring_soon": expiring_count or 0,
                "last_sync": recent_sync.completed_at.isoformat() if recent_sync and recent_sync.completed_at else None,
                "user_cards_count": len(user_cards) if user_id else 0,
            }
