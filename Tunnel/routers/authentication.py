from fastapi import APIRouter, Depends, Response, status, HTTPException
from typing import Optional
from .. import schema, models, database
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from ..repositories import users
from ..hashpass import hashman
from datetime import timedelta
from .token import create_access_token
from ..utils.email_service import email_config

# Use default email configuration from environment variables
current_email_config = email_config

router = APIRouter(tags=['Authentication'])


@router.post("/login-step1", status_code=status.HTTP_200_OK)
async def login_step1(request: schema.LoginCredentials, db: AsyncSession = Depends(database.get_db)):
    """
    Step 1 of login process: Verify credentials and send verification code
    """
    # Use async query
    result = await db.execute(select(models.User).filter(models.User.email == request.email))
    user = result.scalars().first()
    
    if not user or not hashman.verify(request.password, user.password):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    
    # Credentials are valid, send verification code
    result = await users.start_login_verification(user.email, db, email_config=current_email_config)
    
    return {
        "message": "Verification code sent to your email",
        "user_id": result["user_id"],
        "email": user.email
    }


@router.post("/login-step2", status_code=status.HTTP_200_OK, response_model=schema.TokenResponse)
async def login_step2(request: schema.VerifyLogin, db: AsyncSession = Depends(database.get_db)):
    """
    Step 2 of login process: Verify the code and issue access token
    """
    # Verify the code
    await users.verify_login_code(request.email, request.verification_code, db)
    
    # Get user ID
    result = await db.execute(select(models.User).filter(models.User.email == request.email))
    user = result.scalars().first()
    
    # Code verification successful, generate access token
    access_token = create_access_token(
        data={"sub": request.email}
    )
    
    return {
        "access_token": access_token, 
        "token_type": "bearer",
        "user_id": user.id
    }
