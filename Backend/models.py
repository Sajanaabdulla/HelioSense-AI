from sqlalchemy import Column, Integer, String, Float, Text, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    name = Column(String(128))
    email = Column(String(256), unique=True, index=True)
    phone = Column(String(32))
    location = Column(String(256))
    password_hash = Column(String(256))
    created_at = Column(DateTime, default=datetime.utcnow)

class Assessment(Base):
    __tablename__ = 'assessments'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    latitude = Column(Float)
    longitude = Column(Float)
    monthly_bill = Column(Float)
    roof_type = Column(String(64))
    roof_area = Column(Float)
    roof_orientation = Column(String(64))
    roof_tilt = Column(Float)
    shading_percent = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)
    user = relationship('User')

class Prediction(Base):
    __tablename__ = 'predictions'
    id = Column(Integer, primary_key=True)
    assessment_id = Column(Integer, ForeignKey('assessments.id'))
    solar_score = Column(Integer)
    peak_sun_hours = Column(Float)
    annual_generation_kwh = Column(Float)
    recommended_capacity_kw = Column(Float)
    recommended_panels = Column(Integer)
    roof_suitability = Column(String(64))
    created_at = Column(DateTime, default=datetime.utcnow)
    assessment = relationship('Assessment')

class ROIAnalysis(Base):
    __tablename__ = 'roi_analysis'
    id = Column(Integer, primary_key=True)
    prediction_id = Column(Integer, ForeignKey('predictions.id'))
    system_cost = Column(Float)
    electricity_tariff = Column(Float)
    subsidy = Column(Float)
    panel_efficiency = Column(Float)
    annual_savings = Column(Float)
    monthly_savings = Column(Float)
    payback_years = Column(Float)
    roi_percent = Column(Float)
    lifetime_savings = Column(Float)
    co2_reduction_kg = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)
    prediction = relationship('Prediction')

class ChatHistory(Base):
    __tablename__ = 'chat_history'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    question = Column(Text)
    answer = Column(Text)
    metadata = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

class KnowledgeDocument(Base):
    __tablename__ = 'knowledge_documents'
    id = Column(Integer, primary_key=True)
    title = Column(String(256))
    path = Column(String(512))
    uploaded_at = Column(DateTime, default=datetime.utcnow)

class Report(Base):
    __tablename__ = 'reports'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    assessment_id = Column(Integer, ForeignKey('assessments.id'))
    path = Column(String(512))
    created_at = Column(DateTime, default=datetime.utcnow)
