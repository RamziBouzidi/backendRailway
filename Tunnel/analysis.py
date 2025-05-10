from sqlalchemy import func, desc
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import desc, text
import numpy as np
from typing import Dict, List, Any, Optional
from . import models
from datetime import datetime,timedelta



def analyze_speed_patterns(model_id: int, db_session: Session) -> Dict[str, Any]:
    """
    Analyze how forces change with wind speed for a car model
    
    Args:
        model_id: ID of the car model
        db_session: Database session
        
    Returns:
        Dictionary with speed pattern analysis results
    """
    # Get all tests for this model
    tests = db_session.query(models.testCases).filter(
        models.testCases.Model_id == model_id
    ).all()
    
    if not tests:
        return {"error": "No test data found for this model"}
    
    # Group test data by wind speed
    speed_groups = {}
    for test in tests:
        speed = round(test.Wind_Speed, 1)  # Round to nearest 0.1
        if speed not in speed_groups:
            speed_groups[speed] = []
        
        speed_groups[speed].append({
            "drag_force": test.Drag_Force,
            "down_force": test.Down_Force,
            "date": test.created_at.isoformat() if hasattr(test, 'created_at') else datetime.now().isoformat()
        })
    
    # Calculate statistics for each speed
    results = {}
    for speed, tests in speed_groups.items():
        if len(tests) < 1:
            continue
            
        drag_values = [t["drag_force"] for t in tests]
        down_values = [t["down_force"] for t in tests]
        
        # Basic statistics
        results[speed] = {
            "test_count": len(tests),
            "avg_drag": sum(drag_values) / len(drag_values),
            "avg_downforce": sum(down_values) / len(down_values),
            "max_drag": max(drag_values),
            "max_downforce": max(down_values),
            "efficiency": sum(down_values) / sum(drag_values) if sum(drag_values) > 0 else 0
        }
    
    # Find the relationship between speed and forces
    speeds = sorted(results.keys())
    if len(speeds) > 1:
        # Check if drag increases with square of velocity (theoretical)
        drag_values = [results[s]["avg_drag"] for s in speeds]
        
        # Calculate squared relationship (should be linear if drag ~ v²)
        squared_correlation = calculate_correlation(
            [s**2 for s in speeds], 
            drag_values
        )
        
        # Calculate linear relationship
        linear_correlation = calculate_correlation(
            speeds, 
            drag_values
        )
        
        # Determine which model fits better
        drag_model = "squared" if squared_correlation > linear_correlation else "linear"
        
        # Same for downforce
        down_values = [results[s]["avg_downforce"] for s in speeds]
        down_squared_correlation = calculate_correlation(
            [s**2 for s in speeds], 
            down_values
        )
        down_linear_correlation = calculate_correlation(
            speeds, 
            down_values
        )
        down_model = "squared" if down_squared_correlation > down_linear_correlation else "linear"
    else:
        drag_model = "unknown"
        down_model = "unknown"
    
    return {
        "speed_data": results,
        "pattern_analysis": {
            "drag_force_model": drag_model,
            "downforce_model": down_model,
            "speed_points": len(speeds),
            "speed_range": {
                "min": min(speeds) if speeds else 0,
                "max": max(speeds) if speeds else 0
            }
        }
    }


def calculate_correlation(x, y):
    """Calculate Pearson correlation coefficient"""
    n = len(x)
    if n != len(y) or n < 2:
        return 0
        
    sum_x = sum(x)
    sum_y = sum(y)
    sum_xy = sum(xi*yi for xi, yi in zip(x, y))
    sum_x2 = sum(xi*xi for xi in x)
    sum_y2 = sum(yi*yi for yi in y)
    
    numerator = n * sum_xy - sum_x * sum_y
    denominator = ((n * sum_x2 - sum_x**2) * (n * sum_y2 - sum_y**2))**0.5
    
    if denominator == 0:
        return 0
    
    return abs(numerator / denominator)  # We just want strength, not direction


def detect_anomalies(model_id: int, db_session: Session) -> Dict[str, Any]:
    """
    Detect anomalies in test data for a specific car model
    
    Args:
        model_id: ID of the car model
        db_session: Database session
        
    Returns:
        Dictionary with anomaly detection results
    """
    # Get test data
    tests = db_session.query(models.testCases).filter(
        models.testCases.Model_id == model_id
    ).all()
    
    if not tests or len(tests) < 5:  # Need sufficient data for statistical analysis
        return {"error": "Insufficient test data for anomaly detection"}
    analyze_speed_patterns_async
    # Get car details
    car = db_session.query(models.CarModels).filter(
        models.CarModels.id == model_id
    ).first()
    
    # Extract data series
    drag_forces = [t.Drag_Force for t in tests]
    down_forces = [t.Down_Force for t in tests]
    wind_speeds = [t.Wind_Speed for t in tests]
    
    # Calculate statistical properties
    drag_mean = sum(drag_forces) / len(drag_forces)
    drag_std = (sum((x - drag_mean) ** 2 for x in drag_forces) / len(drag_forces)) ** 0.5
    
    down_mean = sum(down_forces) / len(down_forces)
    down_std = (sum((x - down_mean) ** 2 for x in down_forces) / len(down_forces)) ** 0.5
    
    speed_mean = sum(wind_speeds) / len(wind_speeds)
    speed_std = (sum((x - speed_mean) ** 2 for x in wind_speeds) / len(wind_speeds)) ** 0.5
    
    # Define threshold for anomalies (Z-score > 3)
    threshold = 3.0
    
    # Find anomalies
    anomalies = []
    for i, test in enumerate(tests):
        drag_z = abs(test.Drag_Force - drag_mean) / drag_std if drag_std > 0 else 0
        down_z = abs(test.Down_Force - down_mean) / down_std if down_std > 0 else 0
        speed_z = abs(test.Wind_Speed - speed_mean) / speed_std if speed_std > 0 else 0
        
        # Check for physically impossible measurements
        physics_violation = False
        # Example: Negative drag at positive wind speed
        if test.Wind_Speed > 1.0 and test.Drag_Force < 0:
            physics_violation = True
            
        # Example: Extremely high efficiency ratio
        if test.Drag_Force > 0 and test.Down_Force / test.Drag_Force > 5.0:
            physics_violation = True
            
        # Check if any value is an outlier
        is_anomaly = drag_z > threshold or down_z > threshold or speed_z > threshold or physics_violation
        
        if is_anomaly:
            anomalies.append({
                "test_id": test.Test_id,
                "timestamp": test.created_at.isoformat() if hasattr(test, 'created_at') else "",
                "wind_speed": test.Wind_Speed,
                "drag_force": test.Drag_Force,
                "down_force": test.Down_Force,
                "drag_z_score": drag_z,
                "down_z_score": down_z,
                "speed_z_score": speed_z,
                "physics_violation": physics_violation,
                "anomaly_type": determine_anomaly_type(test, drag_z, down_z, speed_z, physics_violation)
            })
    
    return {
        "car_details": {
            "name": car.car_name,
            "manufacturer": car.Manufacturer,
            "type": car.Type_car
        },
        "total_tests": len(tests),
        "anomalies_found": len(anomalies),
        "anomaly_percentage": (len(anomalies) / len(tests)) * 100 if tests else 0,
        "data_quality_score": 100 - ((len(anomalies) / len(tests)) * 100) if tests else 0,
        "anomalies": anomalies
    }


def determine_anomaly_type(test, drag_z, down_z, speed_z, physics_violation):
    """Determine the type of anomaly based on the measurements"""
    if physics_violation:
        if test.Wind_Speed > 1.0 and test.Drag_Force < 0:
            return "PHYSICS_VIOLATION: Negative drag at positive wind speed"
        if test.Drag_Force > 0 and test.Down_Force / test.Drag_Force > 5.0:
            return "PHYSICS_VIOLATION: Unrealistic downforce/drag ratio"
        return "PHYSICS_VIOLATION: General violation"
        
    # New check for identical drag and downforce values
    if abs(test.Drag_Force - test.Down_Force) < 0.001 and test.Drag_Force != 0:
        return "DATA_ANOMALY: Identical drag and downforce values"
        
    if drag_z > 3.0 and down_z > 3.0:
        return "FORCE_ANOMALY: Both drag and downforce are outliers"
    elif drag_z > 3.0:
        return "FORCE_ANOMALY: Drag force is an outlier"
    elif down_z > 3.0:
        return "FORCE_ANOMALY: Downforce is an outlier"
    elif speed_z > 3.0:
        return "SPEED_ANOMALY: Wind speed is an outlier"
    
    return "UNKNOWN_ANOMALY"


# Async version of the anomaly detection function
async def detect_anomalies_async(model_id: int, db: AsyncSession) -> Dict[str, Any]:
    """
    Detect anomalies in test data for a specific car model (async version)
    
    Args:
        model_id: ID of the car model
        db: Async database session
        
    Returns:
        Dictionary with anomaly detection results
    """
    # Get test data using async query
    result = await db.execute(
        select(models.testCases).filter(models.testCases.Model_id == model_id)
    )
    tests = result.scalars().all()
    
    if not tests or len(tests) < 5:  # Need sufficient data for statistical analysis
        return {"error": "Insufficient test data for anomaly detection"}
    
    # Get car details
    car_result = await db.execute(
        select(models.CarModels).filter(models.CarModels.id == model_id)
    )
    car = car_result.scalar_one_or_none()
    
    # Extract data series
    drag_forces = [t.Drag_Force for t in tests]
    down_forces = [t.Down_Force for t in tests]
    wind_speeds = [t.Wind_Speed for t in tests]
    
    # Calculate statistical properties
    drag_mean = sum(drag_forces) / len(drag_forces)
    drag_std = (sum((x - drag_mean) ** 2 for x in drag_forces) / len(drag_forces)) ** 0.5
    
    down_mean = sum(down_forces) / len(down_forces)
    down_std = (sum((x - down_mean) ** 2 for x in down_forces) / len(down_forces)) ** 0.5
    
    speed_mean = sum(wind_speeds) / len(wind_speeds)
    speed_std = (sum((x - speed_mean) ** 2 for x in wind_speeds) / len(wind_speeds)) ** 0.5
    
    # Define threshold for anomalies (Z-score > 3)
    threshold = 3.0
    
    # Find anomalies
    anomalies = []
    for i, test in enumerate(tests):
        drag_z = abs(test.Drag_Force - drag_mean) / drag_std if drag_std > 0 else 0
        down_z = abs(test.Down_Force - down_mean) / down_std if down_std > 0 else 0
        speed_z = abs(test.Wind_Speed - speed_mean) / speed_std if speed_std > 0 else 0
        
        # Check for physically impossible measurements
        physics_violation = False
        # Example: Negative drag at positive wind speed
        if test.Wind_Speed > 1.0 and test.Drag_Force < 0:
            physics_violation = True
            
        # Example: Extremely high efficiency ratio
        if test.Drag_Force > 0 and test.Down_Force / test.Drag_Force > 5.0:
            physics_violation = True
            
        # Add check for identical drag and downforce values (physically suspicious)
        identical_forces = abs(test.Drag_Force - test.Down_Force) < 0.001 and test.Drag_Force != 0
        
        # Check if any value is an outlier or any specific anomaly is detected
        is_anomaly = (drag_z > threshold or 
                      down_z > threshold or 
                      speed_z > threshold or 
                      physics_violation or
                      identical_forces)
        
        if is_anomaly:
            anomalies.append({
                "test_id": test.Test_id,
                "timestamp": test.created_at.isoformat() if hasattr(test, 'created_at') else "",
                "wind_speed": test.Wind_Speed,
                "drag_force": test.Drag_Force,
                "down_force": test.Down_Force,
                "drag_z_score": drag_z,
                "down_z_score": down_z,
                "speed_z_score": speed_z,
                "physics_violation": physics_violation,
                "identical_forces": identical_forces,
                "anomaly_type": determine_anomaly_type(test, drag_z, down_z, speed_z, physics_violation)
            })
    
    return {
        "car_details": {
            "name": car.car_name,
            "manufacturer": car.Manufacturer,
            "type": car.Type_car
        },
        "total_tests": len(tests),
        "anomalies_found": len(anomalies),
        "anomaly_percentage": (len(anomalies) / len(tests)) * 100 if tests else 0,
        "data_quality_score": 100 - ((len(anomalies) / len(tests)) * 100) if tests else 0,
        "anomalies": anomalies
    }


# Async version of the speed pattern analysis function
async def analyze_speed_patterns_async(
    model_id: int, 
    db: AsyncSession,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
    limit: Optional[int] = None
) -> Dict[str, Any]:
    """
    Analyze how forces change with wind speed for a car model (async version)
    
    Args:
        model_id: ID of the car model
        db: Async database session
        from_date: Optional start date for filtering tests
        to_date: Optional end date for filtering tests
        limit: Optional maximum number of tests to analyze
        
    Returns:
        Dictionary with speed pattern analysis results
    """    # Build query with filters
    query = select(models.testCases).filter(models.testCases.Model_id == model_id)
    
# Inside analyze_speed_patterns_async function, replace these lines:

# Add date range filters if provided - using text() to ensure proper SQL typing
    if from_date is None:
        # Use a reasonable default, like 30 days ago
        from_date = datetime.now() - timedelta(days=30)
    if from_date:
    # Make sure from_date is a datetime object, not a string
      if isinstance(from_date, str):
        from_date = datetime.fromisoformat(from_date.replace('Z', '+00:00'))
    # Use a direct text condition to ensure proper date comparison
    date_condition = text(f"created_at >= '{from_date.strftime('%Y-%m-%d %H:%M:%S')}'")
    query = query.filter(date_condition)
    if to_date is None:
        # Default to current time
        to_date = datetime.now()
    if to_date:
    # Make sure to_date is a datetime object, not a string
      if isinstance(to_date, str):
        to_date = datetime.fromisoformat(to_date.replace('Z', '+00:00'))
    date_condition = text(f"created_at <= '{to_date.strftime('%Y-%m-%d %H:%M:%S')}'")
    query = query.filter(date_condition)
        
    # Add ordering by date (newest first)
    query = query.order_by(desc(models.testCases.created_at))
    
    # Add limit if provided
    if limit and limit > 0:
        query = query.limit(limit)
    
    # Execute query
    result = await db.execute(query)
    tests = result.scalars().all()
    
    if not tests:
        # Instead of returning error, return empty analysis structure
        return {
            "speed_data": {},
            "pattern_analysis": {
                "drag_force_model": "unknown",
                "downforce_model": "unknown",
                "speed_points": 0,
                "speed_range": {
                    "min": 0,
                    "max": 0
                },
                "overall_max_drag": 0,
                "overall_max_downforce": 0,
                "insufficient_data": True
            }
        }
    
    if len(tests) < 3:
        # If fewer than 3 tests, still provide basic data but mark as insufficient
        # Track overall max values for all tests
        overall_max_drag = max(test.Drag_Force for test in tests) if tests else 0
        overall_max_downforce = max(test.Down_Force for test in tests) if tests else 0
        
        # Group test data by wind speed
        speed_groups = {}
        for test in tests:
            speed = round(test.Wind_Speed, 1)  # Round to nearest 0.1
            if speed not in speed_groups:
                speed_groups[speed] = []
            
            speed_groups[speed].append({
                "drag_force": test.Drag_Force,
                "down_force": test.Down_Force,
                "date": test.created_at.isoformat() if hasattr(test, 'created_at') else datetime.now().isoformat()
            })
        
        # Calculate basic statistics
        results = {}
        for speed, speed_tests in speed_groups.items():
            if len(speed_tests) < 1:
                continue
                
            drag_values = [t["drag_force"] for t in speed_tests]
            down_values = [t["down_force"] for t in speed_tests]
            
            # Basic statistics
            results[speed] = {
                "test_count": len(speed_tests),
                "avg_drag": sum(drag_values) / len(drag_values),
                "avg_downforce": sum(down_values) / len(down_values),
                "max_drag": max(drag_values),
                "max_downforce": max(down_values),
                "efficiency": sum(down_values) / sum(drag_values) if sum(drag_values) > 0 else 0
            }
        
        return {
            "speed_data": results,
            "pattern_analysis": {
                "drag_force_model": "unknown",
                "downforce_model": "unknown",
                "speed_points": len(speed_groups),
                "speed_range": {
                    "min": min(speed_groups.keys()) if speed_groups else 0,
                    "max": max(speed_groups.keys()) if speed_groups else 0
                },
                "overall_max_drag": overall_max_drag,
                "overall_max_downforce": overall_max_downforce,
                "insufficient_data": True
            }
        }
    
    # Group test data by wind speed
    speed_groups = {}
    
    # Track overall max values for all tests
    overall_max_drag = 0
    overall_max_downforce = 0
    
    for test in tests:
        speed = round(test.Wind_Speed, 1)  # Round to nearest 0.1
        if speed not in speed_groups:
            speed_groups[speed] = []
        
        # Update overall max values
        overall_max_drag = max(overall_max_drag, test.Drag_Force)
        overall_max_downforce = max(overall_max_downforce, test.Down_Force)
        
        speed_groups[speed].append({
            "drag_force": test.Drag_Force,
            "down_force": test.Down_Force,
            "date": test.created_at.isoformat() if hasattr(test, 'created_at') else datetime.now().isoformat()
        })
    
    # Calculate statistics for each speed
    results = {}
    for speed, tests in speed_groups.items():
        if len(tests) < 1:
            continue
            
        drag_values = [t["drag_force"] for t in tests]
        down_values = [t["down_force"] for t in tests]
        
        # Basic statistics
        results[speed] = {
            "test_count": len(tests),
            "avg_drag": sum(drag_values) / len(drag_values),
            "avg_downforce": sum(down_values) / len(down_values),
            "max_drag": max(drag_values),
            "max_downforce": max(down_values),
            "efficiency": sum(down_values) / sum(drag_values) if sum(drag_values) > 0 else 0
        }
    
    # Find the relationship between speed and forces
    speeds = sorted(results.keys())
    if len(speeds) > 1:
        # Check if drag increases with square of velocity (theoretical)
        drag_values = [results[s]["avg_drag"] for s in speeds]
        
        # Calculate squared relationship (should be linear if drag ~ v²)
        squared_correlation = calculate_correlation(
            [s**2 for s in speeds], 
            drag_values
        )
        
        # Calculate linear relationship
        linear_correlation = calculate_correlation(
            speeds, 
            drag_values
        )
        
        # Determine which model fits better
        drag_model = "squared" if squared_correlation > linear_correlation else "linear"
        
        # Same for downforce
        down_values = [results[s]["avg_downforce"] for s in speeds]
        down_squared_correlation = calculate_correlation(
            [s**2 for s in speeds], 
            down_values
        )
        down_linear_correlation = calculate_correlation(
            speeds, 
            down_values
        )
        down_model = "squared" if down_squared_correlation > down_linear_correlation else "linear"
    else:
        drag_model = "unknown"
        down_model = "unknown"
    
    return {
        "speed_data": results,
        "pattern_analysis": {
            "drag_force_model": drag_model,
            "downforce_model": down_model,
            "speed_points": len(speeds),
            "speed_range": {
                "min": min(speeds) if speeds else 0,
                "max": max(speeds) if speeds else 0
            },
            "overall_max_drag": overall_max_drag,
            "overall_max_downforce": overall_max_downforce,
            "insufficient_data": False
        }
    }