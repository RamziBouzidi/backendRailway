from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from .. import models
from datetime import datetime
from fastapi import HTTPException

async def get_or_create_test_settings(db: AsyncSession, user_id=None):
    """Get current test settings or create if not exists"""
    result = await db.execute(select(models.CurrentTestSettings))
    settings = result.scalars().first()
    
    if not settings:
        # Get first model in database if available
        model_result = await db.execute(select(models.CarModels))
        model = model_result.scalars().first()
        model_id = model.id if model else None
        
        # If user_id is provided, verify it exists
        if user_id:
            user_result = await db.execute(select(models.User).filter(models.User.id == user_id))
            user = user_result.scalars().first()
            if not user:
                print(f"Warning: User with ID {user_id} not found in database")
                user_id = None
                
        # If no user_id provided or the provided ID doesn't exist,
        # find any valid user in the database
        if not user_id:
            user_result = await db.execute(select(models.User))
            user = user_result.scalars().first()
            if user:
                user_id = user.id
                print(f"Using existing user with ID {user_id} for settings")
            else:
                print("Warning: No users found in database. Settings will be created with NULL user_id")
                # NULL user_id will be handled specially in the websocket code
        
        try:
            settings = models.CurrentTestSettings(
                model_id=model_id,
                user_id=user_id,  # May be None if no users exist
                device_on=False,
                wind_speed=0.0,
                last_updated=datetime.now()
            )
            db.add(settings)
            await db.commit()
            await db.refresh(settings)
        except Exception as e:
            await db.rollback()
            print(f"Error creating settings: {str(e)}")
            # Create minimal settings with NULL foreign keys as fallback
            settings = models.CurrentTestSettings(
                model_id=None,
                user_id=None,
                device_on=False,
                wind_speed=0.0,
                last_updated=datetime.now()
            )
            db.add(settings)
            await db.commit()
            await db.refresh(settings)
    return settings

async def update_model_setting(model_id: int, user_id: int, db: AsyncSession):
    """Update the current model being tested"""
    # Verify model exists
    result = await db.execute(select(models.CarModels).filter(models.CarModels.id == model_id))
    model = result.scalars().first()
    if not model:
        raise HTTPException(status_code=404, detail=f"Model with ID {model_id} not found")
    
    # Update settings
    settings = await get_or_create_test_settings(db, user_id)
    settings.model_id = model_id
    settings.user_id = user_id
    settings.last_updated = datetime.now()
    await db.commit()
    await db.refresh(settings)
    
    return settings, model

async def update_device_control(device_on: bool, user_id: int, db: AsyncSession):
    """Update device on/off state"""
    # Update settings
    settings = await get_or_create_test_settings(db, user_id)
    settings.device_on = device_on
    settings.user_id = user_id
    settings.last_updated = datetime.now()
    await db.commit()
    await db.refresh(settings)
    
    return settings

async def update_wind_speed(speed: float, user_id: int, db: AsyncSession):
    """Update wind speed setting"""
    # Update settings
    settings = await get_or_create_test_settings(db, user_id)
    settings.wind_speed = speed
    settings.user_id = user_id
    settings.last_updated = datetime.now()
    await db.commit()
    await db.refresh(settings)
    
    return settings