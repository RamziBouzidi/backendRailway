from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean, Float
from sqlalchemy import Column, Integer, String, ForeignKey, Float, Boolean, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime

from .database import Base

class User(Base):
    __tablename__ = "Users"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    surname = Column(String)
    phone_number = Column(String)
    age = Column(Integer)
    email = Column(String, unique=True)
    password = Column(String)
    is_verified = Column(Boolean, default=False)
    verification_code = Column(String, nullable=True)
    code_expiry = Column(DateTime, nullable=True)
    testCasesS = relationship("testCases", back_populates="Owner", lazy='joined')


class testCases(Base):
    __tablename__ = "testCases"
    Test_id = Column(Integer, primary_key=True, index=True)
    Down_Force = Column(Float)
    Drag_Force = Column(Float)
    User_Id = Column(Integer, ForeignKey("Users.id"))
    Owner = relationship("User", back_populates="testCasesS")
    Wind_Speed = Column(Float)
    Model_id = Column(Integer, ForeignKey("CarModels.id"))
    CarModel = relationship("CarModels", back_populates="testCasesS")
    created_at = Column(DateTime, default=datetime.now)


class CarModels(Base):
    __tablename__ = "CarModels"
    id = Column(Integer, primary_key=True, index=True)
    Manufacturer = Column(String)
    car_name = Column(String)
    Type_car = Column(String)
    testCasesS = relationship("testCases", back_populates="CarModel")


class WindSpeed(Base):
    """Stores the current wind speed setting for the wind tunnel"""
    __tablename__ = "WindSpeed"
    id = Column(Integer, primary_key=True, index=True)
    speed = Column(Float, default=0.0)
    last_updated = Column(DateTime, nullable=True)
    updated_by = Column(Integer, ForeignKey("Users.id"))


class CurrentModelSettings(Base):
    """Tracks the currently selected model and the user who selected it"""
    __tablename__ = "CurrentModelSettings"
    id = Column(Integer, primary_key=True, index=True)
    model_id = Column(Integer, ForeignKey("CarModels.id"))
    user_id = Column(Integer, ForeignKey("Users.id"))
    last_updated = Column(DateTime, default=datetime.now)
    
    # Relationships for easy access to related data
    model = relationship("CarModels")
    user = relationship("User")


class CurrentTestSettings(Base):
    """Tracks the current test settings including model, user, and device state"""
    __tablename__ = "CurrentTestSettings"
    id = Column(Integer, primary_key=True, index=True)
    model_id = Column(Integer, ForeignKey("CarModels.id"))
    user_id = Column(Integer, ForeignKey("Users.id"))
    device_on = Column(Boolean, default=False)
    wind_speed = Column(Float, default=0.0)
    last_updated = Column(DateTime, default=datetime.now)

