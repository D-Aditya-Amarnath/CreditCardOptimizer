import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models import Base, RawEmailModel, OfferModel

class DatabaseManager:
    """Handles all database connections and queries through an OOP abstraction."""
    
    def __init__(self, db_url: str = None):
        if db_url is None:
             db_url = os.getenv("DATABASE_URL", "sqlite:///offers.db")
        self.engine = create_engine(
            db_url, 
            connect_args={"check_same_thread": False} if db_url.startswith("sqlite") else {}
        )
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        
    def initialize_schema(self):
        """Creates tables if they don't exist."""
        Base.metadata.create_all(bind=self.engine)
        
    def get_session(self):
        return self.SessionLocal()
        
    def raw_email_exists(self, email_id: str) -> bool:
        with self.get_session() as session:
            return session.query(RawEmailModel).filter(RawEmailModel.email_id == email_id).first() is not None

    def insert_raw_email(self, payload) -> RawEmailModel:
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
                processed_status="PENDING"
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
                session.commit()

    def offer_exists(self, unique_hash: str) -> bool:
        with self.get_session() as session:
            return session.query(OfferModel).filter(OfferModel.unique_hash == unique_hash).first() is not None

    def insert_offer(self, offer) -> OfferModel:
        with self.get_session() as session:
            session.add(offer)
            session.commit()
            session.refresh(offer)
            return offer

    def get_latest_email_date(self, account_email: str):
        """Returns the most recent email date strictly to limit API calls on sync."""
        with self.get_session() as session:
             latest = session.query(RawEmailModel).filter(RawEmailModel.account_email == account_email).order_by(RawEmailModel.date_received.desc()).first()
             return latest.date_received if latest else None

    def search_raw_emails(self, query: str, limit: int = 5) -> list[RawEmailModel]:
        """Searches raw emails by splitting the query into individual words 
        and matching any word against subject or body."""
        from sqlalchemy import or_
        
        with self.get_session() as session:
            words = [w.strip() for w in query.split() if len(w.strip()) >= 2]
            if not words:
                # If no valid words, return most recent emails
                return session.query(RawEmailModel).order_by(
                    RawEmailModel.date_received.desc()
                ).limit(limit).all()
            
            conditions = []
            for word in words:
                pattern = f"%{word}%"
                conditions.append(RawEmailModel.subject.ilike(pattern))
                conditions.append(RawEmailModel.body_text.ilike(pattern))
            
            return session.query(RawEmailModel).filter(
                or_(*conditions)
            ).order_by(RawEmailModel.date_received.desc()).limit(limit).all()

    def get_all_active_offers_for_merchant(self, merchant: str) -> list[OfferModel]:
        """Returns all offers for a specific merchant."""
        with self.get_session() as session:
            return session.query(OfferModel).filter(OfferModel.merchant == merchant.lower().strip()).all()

    def get_all_offers(self) -> list[OfferModel]:
        with self.get_session() as session:
            return session.query(OfferModel).all()
