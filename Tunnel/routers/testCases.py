from fastapi import APIRouter, Depends, Response, status, HTTPException, Query, Body
from fastapi import APIRouter, Depends, Response, status, HTTPException, Query, Body
from typing import Optional, List
from ..repositories import tests
from .oauth2 import get_current_user
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import desc
from datetime import datetime

from .. import schema, models, analysis
from ..database import get_db

router = APIRouter(tags=['TestCases'])

@router.get("/getTests", status_code=status.HTTP_202_ACCEPTED, response_model=List[schema.TestCasesWithCarModel])
async def get_tests(db: AsyncSession = Depends(get_db), current_user: schema.TokenData = Depends(get_current_user)):
    """
    Get all test cases with associated car model information
    """
    try:
        # Get all test cases
        result = await db.execute(
            select(models.testCases)
            .order_by(desc(models.testCases.Test_id))
             # Limit to recent 100 tests
        )
        tests_data = result.scalars().all()
        
        # Create a list to store tests with car model information
        tests_with_car_info = []
        
        # Add car model information to each test
        for test in tests_data:
            # Get the associated car model
            car_result = await db.execute(
                select(models.CarModels).filter(models.CarModels.id == test.Model_id)
            )
            car_model = car_result.scalars().first()
            
            if car_model:
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
                tests_with_car_info.append(test_with_model)
        
        if not tests_with_car_info:
            raise HTTPException(status_code=404, detail=f"Test cases are not available")
        
        return tests_with_car_info
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving test cases: {str(e)}")


@router.post("/registerTests", status_code=status.HTTP_201_CREATED)
async def create_tests(request: schema.testCases, db: AsyncSession = Depends(get_db), current_user: schema.TokenData = Depends(get_current_user)):
    return await tests.post_test(request, db)


@router.post("/getTestCaseById", status_code=status.HTTP_200_OK, response_model=schema.TestCasesWithCarModel)
async def get_test_by_id(
    request: dict = Body(..., example={"id": 1}),
    db: AsyncSession = Depends(get_db), 
    current_user: schema.TokenData = Depends(get_current_user)
):
    """
    Get a specific test case by its ID with car model information
    
    Request body:
    - **id**: ID of the test case to retrieve
    """
    test_id = request.get("id")
    if not test_id:
        raise HTTPException(status_code=400, detail="id is required")
    
    return await tests.get_test_with_car_model(test_id, db)


@router.post("/getTestsByModel", status_code=status.HTTP_200_OK, response_model=List[schema.TestCasesWithCarModel])
async def get_tests_by_model(
    request: dict = Body(..., example={"model_name": "Ferrari F40", "limit": 50}),
    db: AsyncSession = Depends(get_db), 
    current_user: schema.TokenData = Depends(get_current_user)
):
    """
    Get recent tests for a specific car model by name with car model information
    
    Request body:
    - **model_name**: Name of the car model to retrieve tests for
    - **limit**: Number of recent test results to return (default: 50)
    """
    model_name = request.get("model_name")
    if not model_name:
        raise HTTPException(status_code=400, detail="model_name is required")
    
    limit = request.get("limit", 50)
    
    # First find the model ID
    result = await db.execute(select(models.CarModels).filter(models.CarModels.car_name == model_name))
    car_model = result.scalars().first()
    
    if not car_model:
        raise HTTPException(status_code=404, detail=f"Car model with name '{model_name}' not found")
    
    # Get tests with car model information
    return await tests.get_tests_by_model_with_car_info(car_model.id, limit, db)


@router.post("/getTestsByModelId", status_code=status.HTTP_200_OK, response_model=List[schema.TestCasesWithCarModel])
async def get_tests_by_model_id(
    request: dict = Body(..., example={"model_id": 1, "limit": 50}),
    db: AsyncSession = Depends(get_db), 
    current_user: schema.TokenData = Depends(get_current_user)
):
    """
    Get recent tests for a specific car model by ID with car model information
    
    Request body:
    - **model_id**: ID of the car model to retrieve tests for
    - **limit**: Number of recent test results to return (default: 50)
    """
    model_id = request.get("model_id")
    if not model_id:
        raise HTTPException(status_code=400, detail="model_id is required")
    
    limit = request.get("limit", 50)
    
    # Get tests with car model information
    return await tests.get_tests_by_model_with_car_info(model_id, limit, db)


@router.post("/analysis/speed-patterns/{model_id}", status_code=status.HTTP_200_OK)
async def analyze_speed_patterns(
    model_id: int,
    db: AsyncSession = Depends(get_db), 
    current_user: schema.TokenData = Depends(get_current_user)
):
    """
    Analyze how forces change with wind speed for a specific car model
    
    Path parameters:
    - **model_id**: ID of the car model to analyze
    
    Returns:
    - Speed pattern analysis including statistics for each wind speed and force-speed relationships
    """
    results = await analysis.analyze_speed_patterns_async(model_id, db)
    
    # Always return 200 OK, even with insufficient data
    # The frontend will check the "insufficient_data" flag
    return results

@router.post("/analysis/speed-patterns-filtered/{model_id}", status_code=status.HTTP_200_OK)
async def analyze_speed_patterns_with_filter(
    model_id: int,
    request: schema.AnalysisFilterRequest,
    db: AsyncSession = Depends(get_db), 
    current_user: schema.TokenData = Depends(get_current_user)
):
    """
    Analyze how forces change with wind speed for a specific car model with time-based filtering
    
    Path parameters:
    - **model_id**: ID of the car model to analyze
    
    Request body:
    - **from_date**: Optional start date for filtering tests
    - **to_date**: Optional end date for filtering tests
    - **limit**: Optional maximum number of tests to analyze
    
    Returns:
    - Speed pattern analysis including statistics for each wind speed and force-speed relationships
    """
    results = await analysis.analyze_speed_patterns_async(
        model_id, 
        db, 
        from_date=request.from_date, 
        to_date=request.to_date,
        limit=request.limit
    )
    
    # Always return 200 OK, even with insufficient data
    return results


@router.post("/analysis/anomalies/{model_id}", status_code=status.HTTP_200_OK)
async def detect_anomalies(
    model_id: int,
    db: AsyncSession = Depends(get_db), 
    current_user: schema.TokenData = Depends(get_current_user)
):
    """
    Detect anomalies in test data for a specific car model
    
    Path parameters:
    - **model_id**: ID of the car model to analyze
    
    Returns:
    - List of detected anomalies, data quality score, and other anomaly statistics
    """
    results = await analysis.detect_anomalies_async(model_id, db)
    
    if "error" in results:
        raise HTTPException(status_code=404, detail=results["error"])
        
    return results

@router.post("/analysis/speed-patterns-filtered/{model_id}", status_code=status.HTTP_200_OK)
async def analyze_speed_patterns_filtered(
    model_id: int,
    request: schema.AnalysisFilterRequest = Body(...),
    db: AsyncSession = Depends(get_db), 
    current_user: schema.TokenData = Depends(get_current_user)
):
    """
    Analyze how forces change with wind speed for a specific car model with date filtering
    
    Path parameters:
    - **model_id**: ID of the car model to analyze
    
    Request body:
    - **from_date**: Optional start date for filtering tests (ISO format)
    - **to_date**: Optional end date for filtering tests (ISO format)
    - **limit**: Optional maximum number of tests to analyze
    
    Returns:
    - Speed pattern analysis including statistics for each wind speed and force-speed relationships
    """    # Convert string dates to datetime objects if provided
    from_date = None
    to_date = None
    
    if request.from_date:
        try:
            # Handle different ISO format variations
            date_str = request.from_date
            # Remove 'Z' and replace with +00:00 for UTC if needed
            if date_str.endswith('Z'):
                date_str = date_str[:-1] + '+00:00'
            # Add timezone info if missing
            elif not ('+' in date_str or '-' in date_str[-6:]):
                date_str += '+00:00'
            
            from_date = datetime.fromisoformat(date_str)
        except ValueError:
            # Try parsing with different formats
            try:
                from_date = datetime.strptime(request.from_date, '%Y-%m-%dT%H:%M:%S')
            except ValueError:
                try:
                    from_date = datetime.strptime(request.from_date, '%Y-%m-%d')
                except ValueError:
                    raise HTTPException(status_code=400, detail="Invalid from_date format. Use ISO format (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS).")
    
    if request.to_date:
        try:
            # Handle different ISO format variations
            date_str = request.to_date
            # Remove 'Z' and replace with +00:00 for UTC if needed
            if date_str.endswith('Z'):
                date_str = date_str[:-1] + '+00:00'
            # Add timezone info if missing
            elif not ('+' in date_str or '-' in date_str[-6:]):
                date_str += '+00:00'
                
            to_date = datetime.fromisoformat(date_str)
        except ValueError:
            # Try parsing with different formats
            try:
                to_date = datetime.strptime(request.to_date, '%Y-%m-%dT%H:%M:%S')
            except ValueError:
                try:
                    to_date = datetime.strptime(request.to_date, '%Y-%m-%d')
                except ValueError:
                    raise HTTPException(status_code=400, detail="Invalid to_date format. Use ISO format (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS).")
      # Call the analysis function with filters
    try:
        results = await analysis.analyze_speed_patterns_async(
            model_id=model_id,
            db=db,
            from_date=from_date,
            to_date=to_date,
            limit=request.limit
        )
        
        # Always return 200 OK, even with insufficient data
        # The frontend will check the "insufficient_data" flag
        return results
    except Exception as e:
        # Log the error for debugging
        print(f"Error in analyze_speed_patterns_filtered: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"Error processing filtered analysis: {str(e)}"
        )