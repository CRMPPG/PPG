"""Database models for property and assessor data."""

import os
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, relationship, sessionmaker


class Base(DeclarativeBase):
    pass


class Property(Base):
    """A property record combining listing and assessor data."""

    __tablename__ = "properties"

    id = Column(Integer, primary_key=True)
    # Address fields
    address = Column(String(500), nullable=False)
    city = Column(String(100))
    state = Column(String(2))
    zip_code = Column(String(10))
    county = Column(String(100))
    parcel_number = Column(String(50), unique=True, index=True)

    # Property characteristics
    property_type = Column(String(50))  # SFR, Multi, Condo, Land, Commercial
    bedrooms = Column(Integer)
    bathrooms = Column(Float)
    sqft = Column(Integer)
    lot_size_sqft = Column(Integer)
    year_built = Column(Integer)

    # Listing data
    list_price = Column(Float)
    list_date = Column(Date)
    days_on_market = Column(Integer)
    listing_status = Column(String(50))  # Active, Pending, Sold, Withdrawn
    listing_source = Column(String(100))

    # Assessor data
    assessed_value = Column(Float)
    assessed_land_value = Column(Float)
    assessed_improvement_value = Column(Float)
    market_value = Column(Float)
    last_assessment_date = Column(Date)

    # Tax data
    annual_tax_amount = Column(Float)
    tax_year = Column(Integer)
    tax_delinquent = Column(Boolean, default=False)
    tax_delinquent_amount = Column(Float)
    tax_delinquent_years = Column(Integer)

    # Distress indicators
    has_liens = Column(Boolean, default=False)
    lien_amount = Column(Float)
    in_foreclosure = Column(Boolean, default=False)
    is_bank_owned = Column(Boolean, default=False)
    is_vacant = Column(Boolean, default=False)
    code_violations = Column(Integer, default=0)
    owner_occupied = Column(Boolean)

    # Recorder-derived distress indicators
    notice_of_default = Column(Boolean, default=False)
    lis_pendens = Column(Boolean, default=False)
    trustee_sale_scheduled = Column(Boolean, default=False)
    nod_date = Column(Date)
    recorder_document_count = Column(Integer, default=0)

    # Calculated fields
    distress_score = Column(Float)  # 0-100, higher = more distressed
    price_to_assessed_ratio = Column(Float)
    estimated_equity = Column(Float)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    data_source = Column(String(100))
    notes = Column(Text)

    # Relationships
    tax_history = relationship("TaxHistory", back_populates="property")
    sale_history = relationship("SaleHistory", back_populates="property")
    recorded_documents = relationship("RecordedDocument", back_populates="property")

    def __repr__(self):
        return f"<Property {self.address}, score={self.distress_score}>"


class TaxHistory(Base):
    """Historical tax records for a property."""

    __tablename__ = "tax_history"

    id = Column(Integer, primary_key=True)
    property_id = Column(Integer, ForeignKey("properties.id"), nullable=False)
    tax_year = Column(Integer)
    assessed_value = Column(Float)
    tax_amount = Column(Float)
    paid = Column(Boolean)
    delinquent_amount = Column(Float)

    property = relationship("Property", back_populates="tax_history")


class SaleHistory(Base):
    """Historical sale records for a property."""

    __tablename__ = "sale_history"

    id = Column(Integer, primary_key=True)
    property_id = Column(Integer, ForeignKey("properties.id"), nullable=False)
    sale_date = Column(Date)
    sale_price = Column(Float)
    buyer = Column(String(200))
    seller = Column(String(200))
    sale_type = Column(String(50))  # Regular, Foreclosure, Short Sale, Auction

    property = relationship("Property", back_populates="sale_history")


class RecordedDocument(Base):
    """A recorded document from the county recorder (NOD, lien, lis pendens, etc.)."""

    __tablename__ = "recorded_documents"

    id = Column(Integer, primary_key=True)
    property_id = Column(Integer, ForeignKey("properties.id"), nullable=False)
    parcel_number = Column(String(50), index=True)

    document_type = Column(String(100))
    instrument_number = Column(String(50))
    recording_date = Column(Date)
    grantor = Column(String(300))
    grantee = Column(String(300))
    document_amount = Column(Float)
    book = Column(String(20))
    page = Column(String(20))

    data_source = Column(String(100), default="clark_county_recorder")
    created_at = Column(DateTime, default=datetime.utcnow)

    property = relationship("Property", back_populates="recorded_documents")

    def __repr__(self):
        return f"<RecordedDocument {self.document_type} {self.recording_date}>"


def get_engine(database_url=None):
    url = database_url or os.getenv("DATABASE_URL", "sqlite:///ppg.db")
    return create_engine(url, echo=False)


def get_session(database_url=None):
    engine = get_engine(database_url)
    Session = sessionmaker(bind=engine)
    return Session()


def init_db(database_url=None):
    engine = get_engine(database_url)
    Base.metadata.create_all(engine)
    return engine
