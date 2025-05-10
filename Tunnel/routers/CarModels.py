from fastapi import APIRouter, Depends, Response, status, HTTPException, Body
from typing import Optional, List
from ..repositories import carmodels
from .. import schema, models
from ..database import get_db
from .oauth2 import get_current_user
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(tags=['CarModels'])

@router.get("/getCarModels", status_code=status.HTTP_202_ACCEPTED, response_model=List[schema.carmodels])
async def get_blogs(db: AsyncSession = Depends(get_db), current_user: schema.TokenData = Depends(get_current_user)):
    return await carmodels.get_all(db)

@router.post("/registerCarModel", status_code=status.HTTP_201_CREATED, response_model=schema.carmodels)
async def create_car_model(request: schema.CarModelCreate, db: AsyncSession = Depends(get_db), current_user: schema.TokenData = Depends(get_current_user)):
    return await carmodels.post_Car(request, db)

@router.get("/getCarById/{id}", status_code=status.HTTP_200_OK, response_model=schema.carmodels)
async def get_blog(id: int, response: Response, db: AsyncSession = Depends(get_db), current_user: schema.TokenData = Depends(get_current_user)):
    return await carmodels.get_car(id, db)

@router.post("/getCarByName", status_code=status.HTTP_200_OK, response_model=schema.carmodels)
async def get_car_by_name(
    request: dict = Body(..., example={"car_name": "Ferrari"}),
    db: AsyncSession = Depends(get_db), 
    current_user: schema.TokenData = Depends(get_current_user)
):
    """
    Get a car model by its name (case-insensitive partial match search)
    
    Request body:
    - **car_name**: Name to search for (case-insensitive partial match)
    
    The search is partial and case-insensitive, so searching for "ferr" would match "Ferrari F40"
    """
    car_name = request.get("car_name")
    if not car_name:
        raise HTTPException(status_code=400, detail="car_name is required")
    
    return await carmodels.get_car_by_name(car_name, db)

@router.delete("/deleteCar/{id}", status_code=status.HTTP_200_OK)
async def delete(id: int, db: AsyncSession = Depends(get_db), current_user: schema.TokenData = Depends(get_current_user)):
    return await carmodels.delete(id, db)