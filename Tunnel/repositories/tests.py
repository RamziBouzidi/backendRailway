from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import desc
from .. import models
from fastapi import HTTPException
from .. import schema
from typing import List, Optional, Dict, Any
from datetime import datetime


async def get_all(db: AsyncSession, response_model=List[schema.testCases]):
    result = await db.execute(select(models.testCases))
    return result.scalars().all()


async def post_test(request: schema.testCases, db: AsyncSession):
    new_test = models.testCases(Down_Force=request.Down_Force, Drag_Force=request.Drag_Force, Wind_Speed=request.WindSpeed, User_Id=request.user_id, Model_id=request.Model_Id)
    db.add(new_test)
    await db.commit()
    await db.refresh(new_test)
    return new_test


async def get_test(id: int, db: AsyncSession):
    result = await db.execute(select(models.testCases).filter(models.testCases.Test_id == id))
    new_test = result.scalars().first()
    if not new_test:
        raise HTTPException(status_code=404, detail=f"Test with id {id} is not available")
    return new_test
    

async def delete(id: int, db: AsyncSession):
    result = await db.execute(select(models.testCases).filter(models.testCases.Test_id == id))
    test = result.scalars().first()
    if not test:
        raise HTTPException(status_code=404, detail=f"test with id {id} is not available")
    await db.delete(test)
    await db.commit()
    return {"message": "test deleted successfully"}


async def get_tests_by_model_name(model_name: str, limit: int = 50, db: AsyncSession = None):
    """
    Get the most recent tests for a specific car model by name
    
    Args:
        model_name: Name of the car model
        limit: Maximum number of test results to return (default: 50)
        db: Database session
        
    Returns:
        List of testCases for the specified model, ordered by most recent first
    """
    # Find the model ID first
    result = await db.execute(select(models.CarModels).filter(models.CarModels.car_name == model_name))
    car_model = result.scalars().first()
    
    if not car_model:
        raise HTTPException(status_code=404, detail=f"Car model with name '{model_name}' not found")
    
    # Get tests for this model, ordered by most recent first
    query = select(models.testCases)\
        .filter(models.testCases.Model_id == car_model.id)\
        .order_by(desc(models.testCases.Test_id))\
        .limit(limit)
    
    result = await db.execute(query)
    return result.scalars().all()


async def save_test_data(test_data: Dict[str, Any], db: AsyncSession):
    """
    Automatically save test data received from microcontroller to database
    
    Args:
        test_data: Dictionary containing test measurements
        db: Database session
    
    Returns:
        The newly created test case
    """
    # Create new test case
    new_test = models.testCases(
        Drag_Force=float(test_data.get('drag_force', 0)),
        Down_Force=float(test_data.get('down_force', 0)),
        Wind_Speed=float(test_data.get('wind_speed', 0)),
        Model_id=test_data.get('model_id', 1),
        User_Id=test_data.get('user_id', 1),
    )
    
    db.add(new_test)
    await db.commit()
    await db.refresh(new_test)
    
    return new_test


async def register_test_manually(test_data: Dict[str, Any], description: Optional[str], user_id: int, db: AsyncSession):
    """
    Manually register a test with optional description
    
    Args:
        test_data: Dictionary containing test measurements
        description: Optional description for the test
        user_id: ID of the user registering the test
        db: Database session
    
    Returns:
        The newly created test case
    """
    # Create new test case
    new_test = models.testCases(
        Drag_Force=float(test_data.get('drag_force', 0)),
        Down_Force=float(test_data.get('down_force', 0)),
        Wind_Speed=float(test_data.get('wind_speed', 0)),
        Model_id=test_data.get('model_id', 1),
        User_Id=user_id,
    )
    
    # Add description if provided (would need to add this field to your model)
    # if description:
    #     new_test.description = description
    
    db.add(new_test)
    await db.commit()
    await db.refresh(new_test)
    
    return new_test


async def get_test_with_car_model(id: int, db: AsyncSession):
    """
    Get a test case with its associated car model information
    
    Args:
        id: Test ID
        db: Database session
        
    Returns:
        Test case with car model fields
    """
    # Get the test case
    result = await db.execute(select(models.testCases).filter(models.testCases.Test_id == id))
    test = result.scalars().first()
    
    if not test:
        raise HTTPException(status_code=404, detail=f"Test with id {id} is not available")
    
    # Get the associated car model
    car_result = await db.execute(select(models.CarModels).filter(models.CarModels.id == test.Model_id))
    car_model = car_result.scalars().first()
    
    if not car_model:
        raise HTTPException(status_code=404, detail=f"Car model with id {test.Model_id} not found")
    
    # Create a dictionary with all the required fields
    test_with_model = {
        "Test_id": test.Test_id,
        "Drag_Force": test.Drag_Force,
        "Down_Force": test.Down_Force,
        "Wind_Speed": test.Wind_Speed,
        "created_at": test.created_at,
        "Model_id": test.Model_id,
        "car_name": car_model.car_name,
        "Manufacturer": car_model.Manufacturer,
        "Type_car": car_model.Type_car
    }
    
    return test_with_model


async def get_tests_by_model_with_car_info(model_id: int, limit: int = 50, db: AsyncSession = None):
    """
    Get tests for a specific car model with car model information included
    
    Args:
        model_id: ID of the car model
        limit: Maximum number of test results to return (default: 50)
        db: Database session
        
    Returns:
        List of tests with car model information for the specified model
    """
    # Get the car model
    car_result = await db.execute(select(models.CarModels).filter(models.CarModels.id == model_id))
    car_model = car_result.scalars().first()
    
    if not car_model:
        raise HTTPException(status_code=404, detail=f"Car model with id {model_id} not found")
    
    # Get tests for this model, ordered by most recent first
    query = select(models.testCases)\
        .filter(models.testCases.Model_id == model_id)\
        .order_by(desc(models.testCases.Test_id))\
        .limit(limit)
    
    result = await db.execute(query)
    tests = result.scalars().all()
    
    # Create a list of tests with car model information
    tests_with_model = []
    for test in tests:
        test_with_model = {
            "Test_id": test.Test_id,
            "Drag_Force": test.Drag_Force,
            "Down_Force": test.Down_Force,
            "Wind_Speed": test.Wind_Speed,
            "created_at": test.created_at,
            "Model_id": test.Model_id,
            "car_name": car_model.car_name,
            "Manufacturer": car_model.Manufacturer,
            "Type_car": car_model.Type_car
        }
        tests_with_model.append(test_with_model)
    
    return tests_with_model