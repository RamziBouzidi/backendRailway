from fastapi import FastAPI
from .routers import testCases, user, authentication, CarModels, microcontroller, websockets
from fastapi.middleware.cors import CORSMiddleware
from . import models
from .database import engine

app = FastAPI(title="Wind Tunnel API",
              description="API for controlling and monitoring a wind tunnel testing device",
              version="1.0.0")

# Add CORS middleware
app.add_middleware(
  CORSMiddleware,
  allow_origins=["*"],  
  allow_methods=["*"], allow_headers=["*"],
)
# Root endpoint
@app.get("/")
async def root():
    return {"message": "Welcome to Wind Tunnel API", "status": "online"}

# Core endpoints
app.include_router(authentication.router)
app.include_router(user.router)

# Wind tunnel specific endpoints
app.include_router(CarModels.router)
app.include_router(testCases.router)
app.include_router(microcontroller.router)
app.include_router(websockets.router)

# Create database tables asynchronously on startup
@app.on_event("startup")
async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(models.Base.metadata.create_all)








