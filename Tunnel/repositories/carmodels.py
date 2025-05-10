from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from .. import models
from fastapi import HTTPException
from .. import schema
from typing import List


async def get_all(db: AsyncSession, response_model=List[schema.carmodels]):
    result = await db.execute(select(models.CarModels))
    return result.scalars().all()


async def update_Car(id: int, request: schema.CarModelCreate, db: AsyncSession):
    # Update the car model with the given ID
    result = await db.execute(select(models.CarModels).filter(models.CarModels.id == id))
    car = result.scalars().first()
    if not car:
        raise HTTPException(status_code=404, detail=f"Car with id {id} is not available")
    
    # Update the fields of the car model
    car.car_name = request


async def post_Car(request: schema.CarModelCreate, db: AsyncSession):
    # Create a new car model without requiring an ID
    new_car = models.CarModels(
        car_name=request.car_name, 
        Manufacturer=request.Manufacturer, 
        Type_car=request.Type_car
    )
    db.add(new_car)
    await db.commit()
    await db.refresh(new_car)
    return new_car


async def get_car(id: int, db: AsyncSession):
    result = await db.execute(select(models.CarModels).filter(models.CarModels.id == id))
    new_test = result.scalars().first()
    if not new_test:
        raise HTTPException(status_code=404, detail=f"Car with id {id} is not available")
    return new_test
    
    
async def get_car_by_name(name: str, db: AsyncSession):
    result = await db.execute(select(models.CarModels).filter(models.CarModels.car_name == name))
    new_test = result.scalars().first()
    if not new_test:
        raise HTTPException(status_code=404, detail=f"Car with name {name} is not available")
    return new_test
    

async def delete(id: int, db: AsyncSession):
    result = await db.execute(select(models.CarModels).filter(models.CarModels.id == id))
    car = result.scalars().first()
    if not car:
        raise HTTPException(status_code=404, detail=f"car with id {id} is not available")
    await db.delete(car)
    await db.commit()
    return {"message": "Model deleted successfully"}
