from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean, Text, Index, BigInteger
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime
from .db import Base

class User(Base):
    __tablename__ = 'users'
    
    telegram_id = Column(Integer, primary_key=True)
    username = Column(String, nullable=True)
    phone_number = Column(String, nullable=True)
    balance = Column(Float, default=0.0)
    rating = Column(Float, default=5.0)
    total_reviews = Column(Integer, default=0)
    is_blocked = Column(Boolean, default=False)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Связи с другими таблицами
    listings = relationship("PhoneListing", back_populates="seller")
    reviews_received = relationship("Review", foreign_keys="Review.reviewed_id", back_populates="reviewed")
    reviews_given = relationship("Review", foreign_keys="Review.reviewer_id", back_populates="reviewer")
    # Обновленные связи для споров
    disputes_as_buyer = relationship("Dispute", foreign_keys="Dispute.buyer_id", back_populates="buyer")
    disputes_as_seller = relationship("Dispute", foreign_keys="Dispute.seller_id", back_populates="seller")
    won_disputes = relationship("Dispute", foreign_keys="Dispute.winner_id", back_populates="winner")

class PhoneListing(Base):
    __tablename__ = 'phone_listings'
    
    id = Column(Integer, primary_key=True)
    seller_id = Column(Integer, ForeignKey('users.telegram_id', ondelete='CASCADE'))
    service = Column(String, nullable=False)
    phone_number = Column(String, nullable=False)
    rental_period = Column(Integer, nullable=False)  # в часах
    price = Column(Float, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Связи
    seller = relationship("User", back_populates="listings")
    transactions = relationship("Transaction", back_populates="listing")
    
    # Индексы
    __table_args__ = (
        Index('idx_listing_service', 'service'),
        Index('idx_listing_active', 'is_active'),
        Index('idx_listing_seller', 'seller_id'),
    )

class Transaction(Base):
    __tablename__ = 'transactions'
    
    id = Column(Integer, primary_key=True)
    listing_id = Column(Integer, ForeignKey('phone_listings.id', ondelete='CASCADE'))
    buyer_id = Column(Integer, ForeignKey('users.telegram_id', ondelete='CASCADE'))
    seller_id = Column(Integer, ForeignKey('users.telegram_id', ondelete='CASCADE'))
    amount = Column(Float, nullable=False)
    status = Column(String, default='pending')  # pending, completed, cancelled, disputed
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    
    # Связи
    listing = relationship("PhoneListing", back_populates="transactions")
    disputes = relationship("Dispute", back_populates="transaction")
    
    # Индексы
    __table_args__ = (
        Index('idx_transaction_status', 'status'),
        Index('idx_transaction_buyer', 'buyer_id'),
        Index('idx_transaction_seller', 'seller_id'),
        Index('idx_transaction_listing', 'listing_id'),
    )

class Dispute(Base):
    """Модель для хранения споров"""
    __tablename__ = "disputes"
    
    id = Column(Integer, primary_key=True)
    transaction_id = Column(Integer, ForeignKey("transactions.id"), nullable=False)
    buyer_id = Column(Integer, ForeignKey("users.telegram_id"), nullable=False)
    seller_id = Column(Integer, ForeignKey("users.telegram_id"), nullable=False)
    status = Column(String, default="open")  # open, active, resolved
    winner_id = Column(Integer, ForeignKey("users.telegram_id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)
    
    # Связи
    transaction = relationship("Transaction", back_populates="disputes")
    buyer = relationship("User", foreign_keys=[buyer_id], back_populates="disputes_as_buyer")
    seller = relationship("User", foreign_keys=[seller_id], back_populates="disputes_as_seller")
    winner = relationship("User", foreign_keys=[winner_id], back_populates="won_disputes")

class Review(Base):
    __tablename__ = 'reviews'
    
    id = Column(Integer, primary_key=True)
    transaction_id = Column(Integer, ForeignKey('transactions.id', ondelete='CASCADE'))
    reviewer_id = Column(Integer, ForeignKey('users.telegram_id', ondelete='CASCADE'))
    reviewed_id = Column(Integer, ForeignKey('users.telegram_id', ondelete='CASCADE'))
    rating = Column(Integer, nullable=False)  # 1-5
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Связи
    reviewer = relationship("User", foreign_keys=[reviewer_id], back_populates="reviews_given")
    reviewed = relationship("User", foreign_keys=[reviewed_id], back_populates="reviews_received")
    
    # Индексы
    __table_args__ = (
        Index('idx_review_transaction', 'transaction_id'),
        Index('idx_review_reviewer', 'reviewer_id'),
        Index('idx_review_reviewed', 'reviewed_id'),
    )

class PromoCode(Base):
    __tablename__ = 'promo_codes'
    
    id = Column(Integer, primary_key=True)
    code = Column(String, unique=True, nullable=False)
    amount = Column(Float, nullable=False)  # Сумма в ROXY
    max_uses = Column(Integer, default=1)  # Максимальное количество использований
    current_uses = Column(Integer, default=0)  # Текущее количество использований
    is_active = Column(Boolean, default=True)  # Активен ли промокод
    used_by = Column(BigInteger, nullable=True)  # telegram_id пользователя, использовавшего промокод
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)
    created_by = Column(BigInteger, nullable=False)  # telegram_id админа, создавшего промокод 