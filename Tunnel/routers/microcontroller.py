from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from .. import models, schema, database
from ..routers.oauth2 import get_current_user
from ..repositories import device
from ..routers.websockets import broadcast_to_all

router = APIRouter(tags=['Device Control'])

# API endpoint to get current test settings
@router.post("/test-settings", status_code=status.HTTP_200_OK, response_model=schema.CurrentTestSettingsResponse)
async def get_test_settings(
    request: dict = Body({}, example={}),
    db: AsyncSession = Depends(database.get_db),
    current_user: schema.TokenData = Depends(get_current_user)
):
    """Get current test settings including model, user, device state"""
    settings = await device.get_or_create_test_settings(db)
    
    # Get car model name if available
    result = await db.execute(select(models.CarModels).filter(models.CarModels.id == settings.model_id))
    car_model = result.scalars().first()
    
    response = schema.CurrentTestSettingsResponse(
        model_id=settings.model_id,
        user_id=settings.user_id,
        device_on=settings.device_on,
        wind_speed=settings.wind_speed,
        last_updated=settings.last_updated,
        car_name=car_model.car_name if car_model else None
    )
    return response

# API endpoint to update current model
@router.post("/update-model", status_code=status.HTTP_200_OK)
async def update_model(
    model_update: schema.ModelUpdate,
    db: AsyncSession = Depends(database.get_db),
    current_user: schema.TokenData = Depends(get_current_user)
):
    """Update the current model being tested"""
    # Get user ID from email
    result = await db.execute(select(models.User).filter(models.User.email == current_user.email))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Update settings using repository function
    settings, model = await device.update_model_setting(model_update.model_id, user.id, db)
    
    # Broadcast update to all connected clients
    await broadcast_to_all({
        "type": "model_update",
        "model_id": settings.model_id,
        "user_id": settings.user_id,
        "device_on": settings.device_on,
        "wind_speed": settings.wind_speed,
        "car_name": model.car_name
    })
    
    return {
        "message": "Model updated successfully", 
        "model_id": model_update.model_id,
        "car_name": model.car_name
    }

# API endpoint to turn device on/off
@router.post("/device-control", status_code=status.HTTP_200_OK)
async def control_device(
    control: schema.DeviceControl, 
    db: AsyncSession = Depends(database.get_db),
    current_user: schema.TokenData = Depends(get_current_user)
):
    """Turn wind tunnel device on or off"""
    # Get user ID from email
    result = await db.execute(select(models.User).filter(models.User.email == current_user.email))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Update settings using repository function
    settings = await device.update_device_control(control.device_on, user.id, db)
    
    # Broadcast update to all connected clients
    await broadcast_to_all({
        "type": "device_update",
        "model_id": settings.model_id,
        "user_id": settings.user_id,
        "device_on": settings.device_on,
        "wind_speed": settings.wind_speed
    })
    
    return {
        "message": f"Device {'turned on' if control.device_on else 'turned off'} successfully",
        "device_on": control.device_on
    }

# API endpoint to update wind speed
@router.post("/wind-speed", status_code=status.HTTP_200_OK)
async def update_wind_speed(
    speed_update: schema.SpeedUpdate, 
    db: AsyncSession = Depends(database.get_db),
    current_user: schema.TokenData = Depends(get_current_user)
):
    """Update the wind speed for the current test"""
    # Get user ID from email
    result = await db.execute(select(models.User).filter(models.User.email == current_user.email))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Update settings using repository function
    settings = await device.update_wind_speed(float(speed_update.wind_speed), user.id, db)
    
    # Broadcast update to all connected clients
    await broadcast_to_all({
        "type": "speed_update",
        "model_id": settings.model_id,
        "user_id": settings.user_id,
        "device_on": settings.device_on,
        "wind_speed": settings.wind_speed
    })
    
    return {
        "message": "Wind speed updated successfully",
        "wind_speed": settings.wind_speed
    }