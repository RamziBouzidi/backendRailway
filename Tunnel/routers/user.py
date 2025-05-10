from fastapi import APIRouter, Depends, Response, status, HTTPException
from typing import Optional, List
from .. import schema, models
from ..database import get_db
from ..hashpass import hashman
from ..repositories import users
from .oauth2 import get_current_user
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()

@router.post("/adduser", status_code=status.HTTP_201_CREATED, response_model=schema.showuser, tags=["User"])
async def create(ramzi: schema.user, db: AsyncSession = Depends(get_db)):
    # No authentication required for user creation (registration)
    return await users.create_user(ramzi, db)

@router.get("/getusers", status_code=status.HTTP_202_ACCEPTED, response_model=List[schema.showuser], tags=["User"])
async def get_data(db: AsyncSession = Depends(get_db), current_user: schema.TokenData = Depends(get_current_user)):
    return await users.get_all(db)

@router.get("/getuser/{id}", status_code=status.HTTP_200_OK, tags=["User"], response_model=schema.showuser)
async def get_data(id: int, response: Response, db: AsyncSession = Depends(get_db), current_user: schema.TokenData = Depends(get_current_user)):
    return await users.get_user(id, db)
    
@router.delete("/deleteUser/{id}", status_code=status.HTTP_200_OK, tags=["User"])
async def delete(id: int, db: AsyncSession = Depends(get_db), current_user: schema.TokenData = Depends(get_current_user)):
    return await users.delete(id, db)

@router.put("/updateUser/{id}", status_code=status.HTTP_202_ACCEPTED, tags=["User"])
async def update(id: int, ramzi: schema.user, db: AsyncSession = Depends(get_db), current_user: schema.TokenData = Depends(get_current_user)):
    return await users.update(id, ramzi, db)