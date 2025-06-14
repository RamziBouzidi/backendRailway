from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, HTTPException, status
from typing import Dict, Optional, Any, List
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from .. import models, database, analysis
from ..routers.token import verify_token
from ..repositories import carmodels
import asyncio
import json
import os
import pathlib
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Create router with WebSocket tag
router = APIRouter(tags=['WebSockets'])

# Store active websocket connections
client_connections: List[WebSocket] = []

# In-memory storage for settings and test data
memory_settings = {
    "model_id": None,
    "user_id": None,
    "device_on": False,
    "wind_speed": 0.0,
    "car_name": None,
    "last_updated": datetime.now().isoformat(),
    "drag_force": 0,
    "down_force": 0,
    "microcontroller_connected": False,
    "last_microcontroller_data": None
}

# Background task for database persistence
recording_task = None
# Hardcoded interval value of 0.1 seconds
persistence_interval = 0.05

async def record_data_to_db():
    """Background task to record test data to database only when all conditions are met for a valid test"""
    global persistence_interval
    
    print(f"Starting data recording task with fixed interval: {persistence_interval} seconds")
    recording_status = "stopped"  # Track recording status to avoid repeated messages
    
    while True:
        try:
            # IMPORTANT: First strictly check if device is on
            device_is_on = memory_settings.get("device_on") is True  # Must be exactly True
            
            if not device_is_on:
                # Only print message when status changes from recording to stopped
                if recording_status != "stopped":
                    print(f"Recording STOPPED at {datetime.now().isoformat()} - device is OFF")
                    recording_status = "stopped"
                
                # Device is off, skip all recording logic completely
                await asyncio.sleep(1.0)  # Sleep for 1 second when device is off
                continue
                
            # Only proceed from here if device is definitely ON
            current_time = datetime.now()
            microcontroller_active = memory_settings["microcontroller_connected"]
            
            # If we have a last data timestamp, check if it's recent (within 10 seconds)
            if not microcontroller_active and memory_settings["last_microcontroller_data"]:
                last_data_time = datetime.fromisoformat(memory_settings["last_microcontroller_data"])
                time_diff = (current_time - last_data_time).total_seconds()
                microcontroller_active = time_diff < 10  # Consider active if data received in last 10 seconds
            
            # Check all required conditions together
            recording_ready = (client_connections and 
                memory_settings["model_id"] is not None and 
                memory_settings["user_id"] is not None and
                microcontroller_active)
                
            if not recording_ready:
                # If not ready to record, update status and skip
                if recording_status != "waiting":
                    print(f"Recording WAITING at {current_time.isoformat()} - prerequisites not met")
                    recording_status = "waiting"
                await asyncio.sleep(persistence_interval)
                continue
                
            # Check if we have meaningful data to record
            test_data = {
                "drag_force": memory_settings["drag_force"],
                "down_force": memory_settings["down_force"],
                "wind_speed": memory_settings["wind_speed"],
                "model_id": memory_settings["model_id"],
                "user_id": memory_settings["user_id"]
            }
            
            has_meaningful_data = test_data["drag_force"] != 0 or test_data["down_force"] != 0
            
            if not has_meaningful_data:
                # No meaningful data to record yet
                if recording_status != "waiting_data":
                    print(f"Recording WAITING at {current_time.isoformat()} - no meaningful force data yet")
                    recording_status = "waiting_data"
                await asyncio.sleep(persistence_interval)
                continue
                
            # Double-check device is still on before writing to database
            # This protects against the device being turned off during processing
            if memory_settings.get("device_on") is not True:
                if recording_status != "stopped":
                    print(f"Recording STOPPED at {datetime.now().isoformat()} - device turned OFF")
                    recording_status = "stopped"
                await asyncio.sleep(1.0)
                continue
                
            # Create a new async db session for the background task
            async with database.AsyncSessionLocal() as db:
                try:
                    from ..repositories.tests import save_test_data
                    await save_test_data(test_data, db)
                    
                    # Update recording status
                    recording_status = "recording"
                    print(f"RECORDING test to database at {current_time.isoformat()} - device ON")
                except Exception as e:
                    print(f"Error recording data to database: {str(e)}")
            
            # Wait for next recording interval
            await asyncio.sleep(persistence_interval)
        except Exception as e:
            print(f"Error in data recording task: {str(e)}")
            # Keep trying even if there's an error
            await asyncio.sleep(persistence_interval)

# Function to detect anomalies in memory settings
async def check_memory_for_anomalies():
    """Check current memory settings for anomalies and notify clients if found"""
    # Only check if we have valid data to analyze
    if (memory_settings["model_id"] is None or 
        memory_settings["user_id"] is None or 
        memory_settings["drag_force"] == 0 and memory_settings["down_force"] == 0):
        return None
    
    # Check for identical force values (most common anomaly)
    identical_forces = False
    anomaly_message = None
    
    if memory_settings["drag_force"] != 0 and memory_settings["down_force"] != 0:
        abs_diff = abs(memory_settings["drag_force"] - memory_settings["down_force"])
        
        if abs_diff < 0.001:
            # Forces are suspiciously identical
            identical_forces = True
            anomaly_message = {
                "type": "anomaly_alert",
                "anomaly_type": "DATA_ANOMALY",
                "message": "Identical drag and downforce values detected",
                "severity": "warning",
                "data": {
                    "drag_force": memory_settings["drag_force"],
                    "down_force": memory_settings["down_force"],
                    "wind_speed": memory_settings["wind_speed"],
                    "difference": abs_diff
                }
            }
    
    # Check for unrealistic force ratio (if wind speed is significant)
    if memory_settings["wind_speed"] > 1.0 and memory_settings["drag_force"] > 0:
        force_ratio = memory_settings["down_force"] / memory_settings["drag_force"]
        if force_ratio > 5.0:
            anomaly_message = {
                "type": "anomaly_alert",
                "anomaly_type": "PHYSICS_VIOLATION",
                "message": "Unrealistic downforce to drag ratio detected",
                "severity": "warning",
                "data": {
                    "drag_force": memory_settings["drag_force"],
                    "down_force": memory_settings["down_force"],
                    "wind_speed": memory_settings["wind_speed"],
                    "force_ratio": force_ratio
                }
            }
    
    # Check for negative drag at positive wind speed
    if memory_settings["wind_speed"] > 1.0 and memory_settings["drag_force"] < 0:
        anomaly_message = {
            "type": "anomaly_alert",
            "anomaly_type": "PHYSICS_VIOLATION",
            "message": "Negative drag force at positive wind speed detected",
            "severity": "error",
            "data": {
                "drag_force": memory_settings["drag_force"],
                "down_force": memory_settings["down_force"],
                "wind_speed": memory_settings["wind_speed"]
            }
        }
    
    return anomaly_message

# Start the background tasks when this module is imported
async def start_background_tasks():
    global recording_task
    if recording_task is None or recording_task.done():
        recording_task = asyncio.create_task(record_data_to_db())
        print("Started background data recording task")

# Helper function to broadcast messages to all clients
async def broadcast_to_all(message):
    """Broadcast a message to all connected clients, removing disconnected ones"""
    disconnected = []
    for client in client_connections:
        try:
            await client.send_json(message)
        except Exception as e:
            print(f"Error sending to client: {str(e)}")
            disconnected.append(client)
    # Remove disconnected clients
    for client in disconnected:
        if client in client_connections:
            client_connections.remove(client)

# Helper: send message to a specific microcontroller by device_role
async def send_to_micro(device_role, message):
    ws = getattr(router, 'micro_ws_by_role', {}).get(device_role)
    if ws:
        try:
            await ws.send_json(message)
        except Exception as e:
            print(f"Error sending to {device_role}: {e}")

# Load settings from database to memory on startup
async def initialize_memory_settings(db: AsyncSession):
    """Initialize memory settings from database"""
    try:
        from ..repositories.device import get_or_create_test_settings
        
        # Pass no user_id initially - the function will try to find a valid user
        settings = await get_or_create_test_settings(db)
        
        # Get car model name if available
        car_model = None
        if settings.model_id:
            result = await db.execute(select(models.CarModels).filter(models.CarModels.id == settings.model_id))
            car_model = result.scalars().first()
        
        # Update memory settings
        memory_settings.update({
            "model_id": settings.model_id,
            "user_id": settings.user_id,
            "device_on": settings.device_on,
            "wind_speed": settings.wind_speed,
            "car_name": car_model.car_name if car_model else None,
            "last_updated": settings.last_updated.isoformat() if settings.last_updated else datetime.now().isoformat(),
            "drag_force": 0,
            "down_force": 0,
            "microcontroller_connected": False,
            "last_microcontroller_data": None
        })
        
        print("Initialized memory settings from database")
    except Exception as e:
        print(f"Error initializing memory settings: {str(e)}")

async def get_complete_car_info(model_id: int, db: AsyncSession) -> dict:
    """Get full car model info including manufacturer and type from database with improved error handling"""
    try:
        if model_id is None:
            print("Warning: Null model_id passed to get_complete_car_info")
            return None
            
        # Convert to integer in case it's a string or other type
        try:
            model_id = int(model_id)
        except (ValueError, TypeError):
            print(f"Error: Invalid model_id format: {model_id}, type: {type(model_id)}")
            return None
            
        # Query the car model details
        result = await db.execute(select(models.CarModels).filter(models.CarModels.id == model_id))
        car_model = result.scalars().first()
        
        if car_model:
            # Return a complete dictionary with car details
            return {
                "model_id": car_model.id,
                "car_name": car_model.car_name,
                "Manufacturer": car_model.Manufacturer,
                "Type_car": car_model.Type_car
            }
        else:
            print(f"Car model with ID {model_id} not found in database")
            return None
    except Exception as e:
        print(f"Error fetching car model info: {str(e)}")
        return None

async def get_first_available_car(db: AsyncSession):
    cars = await carmodels.get_all(db)
    if cars:
        car = cars[0]
        return {
            "model_id": car.id,
            "car_name": car.car_name,
            "Manufacturer": car.Manufacturer,
            "Type_car": car.Type_car
        }
    return None

# Function to update memory settings with full car model details
async def update_memory_with_car_details(model_id: int, db: AsyncSession) -> bool:
    """Update memory settings with complete car model information"""
    try:
        car_info = await get_complete_car_info(model_id, db)
        if car_info:
            memory_settings["model_id"] = car_info["model_id"]
            memory_settings["car_name"] = car_info["car_name"]
            memory_settings["car_manufacturer"] = car_info["Manufacturer"]
            memory_settings["car_type"] = car_info["Type_car"]
            return True
        return False
    except Exception as e:
        print(f"Error updating memory with car details: {str(e)}")
        return False

# WebSocket endpoint for microcontroller - SUPPORTS MULTIPLE DEVICES
@router.websocket("/ws/microcontroller")
async def microcontroller_websocket(websocket: WebSocket, db: AsyncSession = Depends(database.get_db)):
    # Track all microcontrollers by device_role
    if not hasattr(router, "micro_ws_by_role"):
        router.micro_ws_by_role = {}
        router.micro_version_by_role = {}
    # Load latest firmware from environment or config file if available
    LATEST_FIRMWARE = {
        "fan_micro": os.getenv("FAN_MICRO_FW", "1.0.0"),
        "force_micro": os.getenv("FORCE_MICRO_FW", "1.0.0")
    }
    OTA_URLS = {
        "fan_micro": os.getenv("FAN_MICRO_OTA_URL", "https://github.com/youruser/yourrepo/releases/download/v1.0.0/fan_micro.bin"),
        "force_micro": os.getenv("FORCE_MICRO_OTA_URL", "https://github.com/youruser/yourrepo/releases/download/v1.0.0/force_micro.bin")
    }
    await websocket.accept()
    try:
        version_info = await websocket.receive_json()
        if version_info.get("type") == "version_info":
            device_role = version_info.get("device_role")
            device_version = version_info.get("firmware_version", "0.0.0")
            router.micro_ws_by_role[device_role] = websocket
            router.micro_version_by_role[device_role] = device_version
            # Always check server-side firmware version and trigger OTA if needed
            if device_role in LATEST_FIRMWARE and device_version != LATEST_FIRMWARE[device_role]:
                ota_url = OTA_URLS[device_role]
                await websocket.send_json({
                    "type": "updateMicro",
                    "ota_url": ota_url
                })
                print(f"Sent OTA updateMicro to {device_role} with ota_url: {ota_url}")
            else:
                print(f"{device_role} firmware up-to-date: {device_version}")
            # On connect, update connection status
            memory_settings["microcontroller_connected"] = True
            await broadcast_to_all({"type": "microcontroller_status", "device_role": device_role, "connected": True})
        else:
            print("First message from microcontroller was not version_info. Skipping OTA check.")
    except Exception as e:
        print(f"Error receiving version_info from microcontroller: {str(e)}")
        return

    # Main receive loop: process force data and broadcast to clients
    try:
        while True:
            data = await websocket.receive_json()
            device_role = version_info.get("device_role")
            # Handle force_data from either device
            if data.get("type") == "force_data":
                drag = data.get("drag_force")
                down = data.get("down_force")
                if device_role == "fan_micro":
                    memory_settings["drag_force"] = drag
                    memory_settings["down_force"] = down
                    memory_settings["last_microcontroller_data"] = datetime.now().isoformat()
                    memory_settings["microcontroller_connected"] = True
                    # Broadcast to all clients
                    settings_message = {
                        "type": "settings",
                        **memory_settings,
                        "microcontroller_connected": True
                    }
                    await broadcast_to_all(settings_message)
                elif device_role == "force_micro":
                    # Update memory_settings with force data
                    memory_settings["drag_force"] = drag
                    memory_settings["down_force"] = down
                    memory_settings["last_microcontroller_data"] = datetime.now().isoformat()
                    # Broadcast main settings message to clients (so UI gets force values)
                    settings_message = {
                        "type": "settings",
                        **memory_settings,
                        "microcontroller_connected": memory_settings["microcontroller_connected"]
                    }
                    await broadcast_to_all(settings_message)
                # --- ALERT CLIENTS IF ANOMALY DETECTED ---
                anomaly_message = await check_memory_for_anomalies()
                if anomaly_message:
                    await broadcast_to_all(anomaly_message)
            # Handle settings_update from client (should only be sent to fan_micro)
            if data.get("type") == "settings_update":
                # Only fan_micro should receive this
                await send_to_micro("fan_micro", data)
                # Update memory_settings and broadcast to clients
                if "device_on" in data:
                    memory_settings["device_on"] = data["device_on"]
                if "wind_speed" in data:
                    memory_settings["wind_speed"] = data["wind_speed"]
                await broadcast_to_all({
                    "type": "settings",
                    **memory_settings
                })
            # Optionally handle ota_ack, etc.
    except WebSocketDisconnect:
        # Remove from active connections
        device_role = version_info.get("device_role")
        if device_role in router.micro_ws_by_role:
            del router.micro_ws_by_role[device_role]
        if device_role in router.micro_version_by_role:
            del router.micro_version_by_role[device_role]
        memory_settings["microcontroller_connected"] = False
        await broadcast_to_all({"type": "microcontroller_status", "device_role": device_role, "connected": False})
        print(f"{device_role} disconnected from /ws/microcontroller")
    except Exception as e:
        print(f"Error in microcontroller WebSocket: {str(e)}")

# WebSocket endpoint for clients (users)
@router.websocket("/ws/client")
async def client_websocket(
    websocket: WebSocket, 
    db: AsyncSession = Depends(database.get_db)
):
    try:
        await websocket.accept()
        
        # Initialize memory settings from database if needed
        if memory_settings["model_id"] is None:
            await initialize_memory_settings(db)
        
        # Start background tasks if not already running
        await start_background_tasks()
        
        # First message must be a token verification
        try:
            initial_message = await websocket.receive_json()
            
            # Verify token
            if "type" in initial_message and initial_message["type"] == "verificationToken" and "token" in initial_message:
                try:
                    credentials_exception = HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Could not validate credentials"
                    )
                    # Get token payload
                    token = initial_message["token"]
                    payload = verify_token(token, credentials_exception)
                    
                    # Extract email from token payload
                    email = payload.email  # This is already set correctly in TokenData by verify_token
                    
                    # Get user_id from email - use async query
                    result = await db.execute(select(models.User).filter(models.User.email == email))
                    user = result.scalars().first()
                    
                    if user:
                        user_id = user.id
                        
                        # Send authentication confirmation
                        await websocket.send_json({
                            "type": "authenticationSuccess",
                            "user_id": user_id
                        })
                    else:
                        await websocket.send_json({
                            "type": "error",
                            "message": "User not found in database. Please log in again."
                        })
                        await websocket.close()
                        return
                except Exception as e:
                    # Log the exception for debugging
                    print(f"Token verification error: {str(e)}")
                    await websocket.send_json({
                        "type": "error",
                        "message": f"Invalid token: {str(e)}"
                    })
                    await websocket.close()
                    return
            else:
                await websocket.send_json({
                    "type": "error",
                    "message": "First message must be of type 'verificationToken' and include a token field"
                })
                await websocket.close()
                return
        except json.JSONDecodeError:
            await websocket.send_json({
                "type": "error",
                "message": "Invalid JSON format in initial message"
            })
            await websocket.close()
            return
        except Exception as e:
            await websocket.send_json({
                "type": "error",
                "message": f"Error processing initial message: {str(e)}"
            })
            await websocket.close()
            return
        
        # Add to active connections
        client_connections.append(websocket)

        # --- Robustness: Ensure valid car model after authentication ---
        car_info = await get_complete_car_info(memory_settings["model_id"], db)
        switched = False
        if not car_info:
            # Current model is missing, auto-switch to first available
            car_info = await get_first_available_car(db)
            if car_info:
                memory_settings["model_id"] = car_info["model_id"]
                memory_settings["car_name"] = car_info["car_name"]
                memory_settings["car_manufacturer"] = car_info["Manufacturer"]
                memory_settings["car_type"] = car_info["Type_car"]
                switched = True
            else:
                # No cars available at all
                memory_settings["model_id"] = None
                memory_settings["car_name"] = None
                memory_settings["car_manufacturer"] = None
                memory_settings["car_type"] = None

        # Send current memory settings with microcontroller status immediately after successful authentication
        settings_payload = {
            "type": "settings",
            "model_id": memory_settings["model_id"],
            "user_id": memory_settings["user_id"],
            "device_on": memory_settings["device_on"],
            "wind_speed": memory_settings["wind_speed"],
            "car_name": memory_settings["car_name"],
            "Manufacturer": memory_settings.get("car_manufacturer", "Unknown"),
            "Type_car": memory_settings.get("car_type", "Unknown"),
            "drag_force": memory_settings["drag_force"],
            "down_force": memory_settings["down_force"],
            "last_updated": memory_settings["last_updated"],
            "microcontroller_connected": memory_settings["microcontroller_connected"],
            "last_microcontroller_data": memory_settings["last_microcontroller_data"]
        }
        await websocket.send_json(settings_payload)
        if switched:
            await websocket.send_json({
                "type": "info",
                "message": "Selected car model was deleted. Switched to first available car model.",
                "model_id": memory_settings["model_id"]
            })
        
        # Keep connection open and handle client messages
        while True:
            try:
                message = await websocket.receive_json()
                
                # Process client commands based on message type
                try:
                    if "type" not in message:
                        await websocket.send_json({
                            "type": "error",
                            "message": "Message must include a 'type' field"
                        })
                        continue
                    
                    # Handle different message types
                    if message["type"] == "getCurrentSettings":
                        # Robustness: Ensure valid car model before sending
                        car_info = await get_complete_car_info(memory_settings["model_id"], db)
                        switched = False
                        if not car_info:
                            car_info = await get_first_available_car(db)
                            if car_info:
                                memory_settings["model_id"] = car_info["model_id"]
                                memory_settings["car_name"] = car_info["car_name"]
                                memory_settings["car_manufacturer"] = car_info["Manufacturer"]
                                memory_settings["car_type"] = car_info["Type_car"]
                                switched = True
                            else:
                                memory_settings["model_id"] = None
                                memory_settings["car_name"] = None
                                memory_settings["car_manufacturer"] = None
                                memory_settings["car_type"] = None
                        settings_payload = {
                            "type": "settings",
                            **memory_settings,
                            "microcontroller_connected": memory_settings["microcontroller_connected"]
                        }
                        await websocket.send_json(settings_payload)
                        if switched:
                            await websocket.send_json({
                                "type": "info",
                                "message": "Selected car model was deleted. Switched to first available car model.",
                                "model_id": memory_settings["model_id"]
                            })
                        continue
                    elif message["type"] == "updateSettings":
                        # Update settings in memory - NO direct database update
                        
                        # SECURITY: Always use the authenticated user_id from the token
                        # Do not allow clients to change the user_id directly
                        
                        memory_settings["user_id"] = user_id
                        
                        # Update memory with any provided settings
                        if "model_id" in message:
                            new_model_id = message["model_id"]
                            
                            # Use async query to check if model exists
                            car_info = await get_complete_car_info(new_model_id, db)
                            switched = False
                            if not car_info:
                                car_info = await get_first_available_car(db)
                                if car_info:
                                    memory_settings["model_id"] = car_info["model_id"]
                                    memory_settings["car_name"] = car_info["car_name"]
                                    memory_settings["car_manufacturer"] = car_info["Manufacturer"]
                                    memory_settings["car_type"] = car_info["Type_car"]
                                    switched = True
                                else:
                                    memory_settings["model_id"] = None
                                    memory_settings["car_name"] = None
                                    memory_settings["car_manufacturer"] = None
                                    memory_settings["car_type"] = None
                                    await websocket.send_json({
                                        "type": "error",
                                        "message": "No car models available. Please add a car model."
                                    })
                                    continue
                            else:
                                memory_settings["model_id"] = car_info["model_id"]
                                memory_settings["car_name"] = car_info["car_name"]
                                memory_settings["car_manufacturer"] = car_info["Manufacturer"]
                                memory_settings["car_type"] = car_info["Type_car"]
                            if switched:
                                await websocket.send_json({
                                    "type": "info",
                                    "message": "Selected car model was deleted. Switched to first available car model.",
                                    "model_id": memory_settings["model_id"]
                                })
                        
                        if "wind_speed" in message:
                            wind_speed = message["wind_speed"]
                            if wind_speed < 0:
                                await websocket.send_json({
                                    "type": "error",
                                    "message": "Wind speed cannot be negative"
                                })
                                continue
                            memory_settings["wind_speed"] = message["wind_speed"]
                        
                        if "device_on" in message:
                            previous_state = memory_settings.get("device_on")
                            
                            # Ensure device_on is a boolean value
                            if isinstance(message["device_on"], bool):
                                device_on = message["device_on"]
                            else:
                                # Try to convert to boolean if possible
                                try:
                                    # Handle string values like "true", "false"
                                    if isinstance(message["device_on"], str):
                                        device_on = message["device_on"].lower() == "true"
                                    else:
                                        # For any other type, use standard boolean conversion
                                        device_on = bool(message["device_on"])
                                    
                                    print(f"Converted device_on from {type(message['device_on'])} value '{message['device_on']}' to boolean: {device_on}")
                                except Exception as e:
                                    print(f"Error converting device_on: {str(e)}")
                                    device_on = False
                            
                            # Update memory settings with the boolean value
                            memory_settings["device_on"] = device_on
                            
                            # If turning device on, check microcontroller connection
                            if device_on and not memory_settings["microcontroller_connected"]:
                                # Check if we had recent data (within last 10 seconds)
                                microcontroller_active = False
                                if memory_settings["last_microcontroller_data"]:
                                    last_data_time = datetime.fromisoformat(memory_settings["last_microcontroller_data"])
                                    time_diff = (datetime.now() - last_data_time).total_seconds()
                                    microcontroller_active = time_diff < 10
                                
                                if not microcontroller_active:
                                    await websocket.send_json({
                                        "type": "warning",
                                        "message": "Device turned on but no microcontroller is connected. Data will not be recorded."
                                    })
                            
                            # If turning device off, send notification that recording has stopped
                            if previous_state is True and device_on is False:
                                print(f"Device turned OFF at {datetime.now().isoformat()} - recording stopped")
                                await broadcast_to_all({
                                    "type": "info",
                                    "message": "Device turned off - data recording stopped"
                                })
                        
                        # Update last_updated timestamp
                        memory_settings["last_updated"] = datetime.now().isoformat()
                        
                        # Broadcast updated memory settings to all clients
                        settings_message = {
                            "type": "settings",
                            **memory_settings,  # Unpack all memory settings
                            "microcontroller_connected": memory_settings["microcontroller_connected"]
                        }
                        
                        await broadcast_to_all(settings_message)
                        
                        # Also send settings update to microcontroller (without force data)
                        await send_to_micro("fan_micro", {
                            "type": "settings_update",
                            "model_id": memory_settings["model_id"],
                            "user_id": memory_settings["user_id"],
                            "device_on": memory_settings["device_on"],
                            "wind_speed": memory_settings["wind_speed"]
                        })
                    
                    else:
                        await websocket.send_json({
                            "type": "error",
                            "message": f"Unknown message type: {message['type']}"
                        })
                
                except Exception as e:
                    await websocket.send_json({
                        "type": "error",
                        "message": f"Error processing message: {str(e)}"
                    })
            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "message": "Invalid JSON message"
                })
            except Exception as e:
                print(f"Error in message loop: {str(e)}")
                break
                
    except WebSocketDisconnect:
        # Remove from active connections
        if websocket in client_connections:
            client_connections.remove(websocket)
    except Exception as e:
        print(f"Error in client WebSocket: {str(e)}")
        # Clean up on error
        if websocket in client_connections:
            client_connections.remove(websocket)