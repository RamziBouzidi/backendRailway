from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from .. import models
from fastapi import HTTPException
from ..hashpass import hashman
from .. import schema
from datetime import datetime
from ..utils.email_service import generate_verification_code, get_code_expiry, send_verification_email, EmailConfig

async def create_user(request, db: AsyncSession):
    # First check if a user with this email already exists
    result = await db.execute(select(models.User).where(models.User.email == request.email))
    existing_user = result.scalars().first()
    
    if existing_user:
        raise HTTPException(
            status_code=400,
            detail=f"User with email {request.email} already exists"
        )
    
    # Create user logic
    new_user = models.User(email=request.email, password=hashman.hash(request.password),phone_number=request.phone_number,surname=request.surname,age=request.age,name=request.name)
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return new_user

async def get_all(db: AsyncSession):
    # Get all users with async syntax
    result = await db.execute(select(models.User))
    return result.scalars().unique().all()

async def get_user(id: int, db: AsyncSession):
    # Get single user with async syntax
    result = await db.execute(select(models.User).where(models.User.id == id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail=f"User with id {id} not found")
    return user

async def delete(id: int, db: AsyncSession):
    # Delete user with async syntax
    result = await db.execute(select(models.User).where(models.User.id == id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail=f"User with id {id} not found")
    await db.delete(user)
    await db.commit()
    return {"message": "User deleted successfully"}

async def update(id: int, request, db: AsyncSession):
    # Update user with async syntax
    result = await db.execute(select(models.User).where(models.User.id == id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail=f"User with id {id} not found")
    
    # Update fields
    user.email = request.email
    user.password = hashman(request.password)
    
    await db.commit()
    await db.refresh(user)
    return user

async def start_login_verification(email: str, db: AsyncSession, email_config=None):
    """Generate and send verification code for login."""
    # Use async SQLAlchemy syntax
    result = await db.execute(select(models.User).where(models.User.email == email))
    user = result.scalars().first()
    
    if not user:
        raise HTTPException(status_code=404, detail=f"User with email {email} not found")
    
    # Generate new verification code
    verification_code = generate_verification_code()
    code_expiry = get_code_expiry()
    
    # Set new code and expiry time
    user.verification_code = verification_code
    user.code_expiry = code_expiry
    user.is_verified = False
    await db.commit()
    
    # Send verification email
    email_sent = send_verification_email(user.email, verification_code, config=email_config)
    if not email_sent:
        raise HTTPException(status_code=500, detail="Failed to send verification email")
    
    # Return user ID for the next step (but not the code)
    return {"message": "Verification code sent to your email", "user_id": user.id}

async def verify_login_code(email: str, code: str, db: AsyncSession):
    """Verify the code submitted during login."""
    # Use async SQLAlchemy syntax
    result = await db.execute(select(models.User).where(models.User.email == email))
    user = result.scalars().first()
    
    if not user:
        raise HTTPException(status_code=404, detail=f"User with email {email} not found")
    
    # Check if code is expired
    if user.code_expiry and user.code_expiry < datetime.now():
        raise HTTPException(status_code=400, detail="Verification code has expired. Please try logging in again.")
    
    # Check if code matches
    if user.verification_code != code:
        raise HTTPException(status_code=400, detail="Invalid verification code")
    
    # Mark user as verified for this session
    user.is_verified = True
    # Clear the verification code and expiry after successful verification
    user.verification_code = None
    user.code_expiry = None
    await db.commit()
    
    return {"message": "Login verification successful"}