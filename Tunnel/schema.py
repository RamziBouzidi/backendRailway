from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime


class user(BaseModel):
    name:str
    surname:str
    age:int
    email:str
    password:str
    phone_number:str




class LoginCredentials(BaseModel):
    email: str
    password: str


class VerifyLogin(BaseModel):
    email: str
    verification_code: str


class testCases(BaseModel):
    Drag_Force:int
    WindSpeed:int
    Test_id:int
    Down_Force:int
    Model_Id:int
    user_id:int
    created_at: datetime
    class Config:
        orm_mode = True


class showuser(BaseModel):
    name: Optional[str] = None  # Made name optional with default None
    age: Optional[int] = None   # Made age optional as well since it could be None
    email: str
    phone_number: Optional[str] = None  # Made phone_number optional 
    surname: Optional[str] = None  # Made surname optional
    class Config:
        orm_mode = True


class showTestcasesByUser(BaseModel):
    Drag_Force:int
    WindSpeed:int
    Test_Date:str
    Down_Force:int
    Owner: showuser | None = None
    class Config:
        orm_mode = True


# Create separate models for different operations
# For creating a car model (no id required)
class CarModelCreate(BaseModel):
    Manufacturer: str
    car_name: str
    Type_car: str
    
    class Config:
        orm_mode = True

# For displaying car model (includes id)
class carmodels(BaseModel):
    Manufacturer: str
    car_name: str
    Type_car: str
    id: int
    
    class Config:
        orm_mode = True


# New schema for showing test cases with car model info
class TestCasesWithCarModel(BaseModel):
    Test_id: int
    Drag_Force: int
    Down_Force: int
    Wind_Speed: int
    created_at: datetime
    # Car model fields
    car_name: str
    Manufacturer: str
    Type_car: str
    Model_id: int
    class Config:
        orm_mode = True


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenResponse(BaseModel):
    """Extended token response that includes user ID"""
    access_token: str
    token_type: str
    user_id: int


class TokenData(BaseModel):
    email: str


# Models for microcontroller API
class TestData(BaseModel):
    """Data sent from microcontroller for test results"""
    drag_force: int
    down_force: int
    wind_speed: int
    model_id: int
    user_id: int


class SpeedUpdate(BaseModel):
    """Used to update the wind speed"""
    wind_speed: int


class DeviceControl(BaseModel):
    """Used to turn device on/off"""
    device_on: bool


class ModelUpdate(BaseModel):
    """Used to update the current model being tested"""
    model_id: int


class CurrentTestSettingsResponse(BaseModel):
    """Response model for current test settings"""
    model_id: int
    user_id: int
    device_on: bool
    wind_speed: int
    last_updated: Optional[datetime] = None
    car_name: Optional[str] = None
    
    class Config:
        orm_mode = True


class RegisterTestRequest(BaseModel):
    """Request to register a test with optional description"""
    description: Optional[str] = None


class TestDataResponse(BaseModel):
    """Response with live test data"""
    drag_force: float
    down_force: float
    wind_speed: int
    model_id: int
    user_id: int
    timestamp: datetime


class AnalysisFilterRequest(BaseModel):
    """Schema for filtered analysis requests"""
    from_date: Optional[str] = None
    to_date: Optional[str] = None
    limit: Optional[int] = None
    
    class Config:
        orm_mode = True
