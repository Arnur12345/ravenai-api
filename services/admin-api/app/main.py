import logging
import secrets
import string
import os
from fastapi import FastAPI, APIRouter, Depends, HTTPException, status, Security, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload, attributes
from typing import List # Import List for response model
from datetime import datetime # Import datetime
from sqlalchemy import func
from pydantic import BaseModel, HttpUrl

# Import shared models and schemas
from shared_models.models import User, APIToken, Base, Meeting # Import Base for init_db and Meeting
from shared_models.schemas import UserCreate, UserResponse, TokenResponse, UserDetailResponse, UserBase, UserUpdate, UserPutUpdate, UserMeetingCountResponse, MeetingStatusCount, MeetingResponse, UserLogin, UserLoginResponse # Import UserBase for update and new schemas
from shared_models.auth_utils import hash_password, verify_password # Import password hashing utility

# Database utilities (needs to be created)
from shared_models.database import get_db, init_db # New import

# Logging configuration
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("admin_api")

# App initialization
app = FastAPI(
    title="Vexa Admin API",
    description="""
    **Administrative API for Vexa platform user and token management.**
    
    🚀 **Quick Start:**
    ```bash
    # 1. Create a user
    curl -X POST http://localhost:18057/admin/users \\
      -H "X-Admin-API-Key: qP4zo7lWA84W2iIqa6dtI884K3slfPli61mFlr5v" \\
      -H "Content-Type: application/json" \\
      -d '{"email":"user@example.com","name":"John Doe","password":"securepassword123"}'
    
    # 2. Generate API token for user
    curl -X POST http://localhost:18057/admin/users/USER_ID/tokens \\
      -H "X-Admin-API-Key: YOUR_ADMIN_TOKEN"
    ```
    
    ## Authentication
    
    **Required:** `X-Admin-API-Key` header for all admin operations.
    
    Set the admin token via `ADMIN_API_TOKEN` environment variable.
    
    ## Common Operations
    
    **Create User:**
    ```bash
    curl -X POST http://localhost:18057/admin/users \\
      -H "X-Admin-API-Key: qP4zo7lWA84W2iIqa6dtI884K3slfPli61mFlr5v" \\
      -H "Content-Type: application/json" \\
      -d '{"email":"user@example.com","name":"John Doe","password":"securepassword123"}'
    ```
    
    **List Users:**
    ```bash
    curl -X GET http://localhost:18057/admin/users \\
      -H "X-Admin-API-Key: qP4zo7lWA84W2iIqa6dtI884K3slfPli61mFlr5v"
    ```
    
    **Generate Token:**
    ```bash
    curl -X POST http://localhost:18057/admin/users/1/tokens \\
      -H "X-Admin-API-Key: YOUR_ADMIN_TOKEN"
    ```
    """,
    version="1.1.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Pydantic Schemas for new endpoint ---
class WebhookUpdate(BaseModel):
    webhook_url: HttpUrl

class MeetingUserStat(MeetingResponse): # Inherit from MeetingResponse to get meeting fields
    user: UserResponse # Embed UserResponse

class PaginatedMeetingUserStatResponse(BaseModel):
    total: int
    items: List[MeetingUserStat]

# Security - Reuse logic from bot-manager/auth.py for admin token verification
API_KEY_HEADER = APIKeyHeader(name="X-Admin-API-Key", auto_error=False) # Use a distinct header
USER_API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False) # For user-facing endpoints
ADMIN_API_TOKEN = os.getenv("ADMIN_API_TOKEN") # Read from environment

async def verify_admin_token(admin_api_key: str = Security(API_KEY_HEADER)):
    """Dependency to verify the admin API token."""
    if not ADMIN_API_TOKEN:
        logger.error("CRITICAL: ADMIN_API_TOKEN environment variable not set!")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Admin authentication is not configured on the server."
        )
    
    if not admin_api_key or admin_api_key != ADMIN_API_TOKEN:
        logger.warning(f"Invalid admin token provided.")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing admin token."
        )
    logger.info("Admin token verified successfully.")
    # No need to return anything, just raises exception on failure 

async def get_current_user(api_key: str = Security(USER_API_KEY_HEADER), db: AsyncSession = Depends(get_db)) -> User:
    """Dependency to verify user API key and return user object."""
    if not api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing API Key")

    result = await db.execute(
        select(APIToken).where(APIToken.token == api_key).options(selectinload(APIToken.user))
    )
    db_token = result.scalars().first()

    if not db_token or not db_token.user:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid API Key")
    
    return db_token.user

# Router setup (all routes require admin token verification)
admin_router = APIRouter(
    prefix="/admin",
    tags=["Admin"],
    dependencies=[Depends(verify_admin_token)]
)

# New router for user-facing actions
user_router = APIRouter(
    prefix="/user",
    tags=["User"],
    dependencies=[Depends(get_current_user)]
)

auth_router = APIRouter(
    prefix="/auth",
    tags=["Auth"],
)

# --- Helper Functions --- 
def generate_secure_token(length=40):
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for i in range(length))

@auth_router.post("/login", response_model=UserLoginResponse, summary="Login with email and password", description="Login with email and password to get a token.")
async def login(user_in: UserLogin, response: Response, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == user_in.email))
    existing_user = result.scalars().first()

    if not existing_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not found user"
        )
    
    # Verify the password
    # Need to import verify_password function to properly check hashed passwords
    # The current code is hashing the input password and comparing to stored hash
    
    if not verify_password(user_in.password, existing_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    # Generate a new API token for the user
    new_token = generate_secure_token()
    db_token = APIToken(
        token=new_token,
        user_id=existing_user.id
    )
    db.add(db_token)
    await db.commit()
    
    logger.info(f"Successfully logged in user: {existing_user.email} (ID: {existing_user.id})")
    response.status_code = status.HTTP_200_OK
    return UserLoginResponse(user=UserResponse.from_orm(existing_user), token=new_token)

@auth_router.post("/register", response_model=UserLoginResponse, summary="Register a new user", description="Register a new user with email and password.")
async def register(user_in: UserCreate, response: Response, db: AsyncSession = Depends(get_db)):
    # Check if user already exists
    result = await db.execute(select(User).where(User.email == user_in.email))
    existing_user = result.scalars().first()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists"
        )

    # Hash the password before storing
    user_data = user_in.dict()
    hashed_password = hash_password(user_data['password'])
    
    # Create new user
    db_user = User(
        email=user_data['email'],
        name=user_data.get('name'),
        image_url=user_data.get('image_url'),
        hashed_password=hashed_password,
        max_concurrent_bots=user_data.get('max_concurrent_bots', 1),
        data=user_data.get('data', {})
    )
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    
    # Generate API token for the new user
    new_token = generate_secure_token()
    db_token = APIToken(
        token=new_token,
        user_id=db_user.id
    )
    db.add(db_token)
    await db.commit()
    
    logger.info(f"Successfully registered new user: {db_user.email} (ID: {db_user.id})")
    response.status_code = status.HTTP_201_CREATED
    return UserLoginResponse(user=UserResponse.from_orm(db_user), token=new_token)

@auth_router.post("/logout", 
                 status_code=status.HTTP_200_OK,
                 summary="Logout user and invalidate token",
                 description="Logout the current user by invalidating their API token.")
async def logout(api_key: str = Security(USER_API_KEY_HEADER), db: AsyncSession = Depends(get_db)):
    """
    Logout the current user by invalidating their API token.
    The API key used for this request will be deleted from the database.
    """
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Missing API Key"
        )

    # Find the token in the database
    result = await db.execute(
        select(APIToken).where(APIToken.token == api_key).options(selectinload(APIToken.user))
    )
    db_token = result.scalars().first()

    if not db_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Invalid API Key"
        )

    # Delete the token to invalidate it
    await db.delete(db_token)
    await db.commit()
    
    logger.info(f"User {db_token.user.email} (ID: {db_token.user.id}) logged out successfully")
    
    return {"message": "Successfully logged out"}

# --- User Endpoints ---
@user_router.put("/webhook",
             response_model=UserResponse,
             summary="Set user webhook URL",
             description="Set a webhook URL for the authenticated user to receive notifications.")
async def set_user_webhook(
    webhook_update: WebhookUpdate, 
    user: User = Depends(get_current_user), 
    db: AsyncSession = Depends(get_db)
):
    """
    Updates the webhook_url for the currently authenticated user.
    The URL is stored in the user's 'data' JSONB field.
    """
    if user.data is None:
        user.data = {}
    
    user.data['webhook_url'] = str(webhook_update.webhook_url)

    # Flag the 'data' field as modified for SQLAlchemy to detect the change
    attributes.flag_modified(user, "data")

    db.add(user)
    await db.commit()
    await db.refresh(user)
    logger.info(f"Updated webhook URL for user {user.email}")
    
    return UserResponse.from_orm(user)

@user_router.get("/meetings/count",
             response_model=UserMeetingCountResponse,
             summary="Get authenticated user's meeting count",
             description="Get the total number of meetings and breakdown by status for the authenticated user.")
async def get_current_user_meeting_count(
    user: User = Depends(get_current_user), 
    db: AsyncSession = Depends(get_db)
):
    """
    Get meeting count statistics for the currently authenticated user.
    Returns total count and breakdown by meeting status.
    """
    user_id = user.id

    # Get total meeting count
    total_result = await db.execute(
        select(func.count(Meeting.id)).where(Meeting.user_id == user_id)
    )
    total_meetings = total_result.scalar_one()

    # Get count by status
    status_counts = {}
    status_list = ['active', 'completed', 'requested', 'stopping', 'failed']
    
    for status_name in status_list:
        count_result = await db.execute(
            select(func.count(Meeting.id)).where(
                Meeting.user_id == user_id,
                Meeting.status == status_name
            )
        )
        status_counts[status_name] = count_result.scalar_one()

    # Create response using the schema
    status_breakdown = MeetingStatusCount(**status_counts)
    
    response = UserMeetingCountResponse(
        user_id=user_id,
        total_meetings=total_meetings,
        by_status=status_breakdown
    )
    
    logger.info(f"User {user_id} requested their meeting count: {total_meetings} total meetings")
    return response

# --- Admin Endpoints (Copied and adapted from bot-manager/admin.py) --- 
@admin_router.post("/users",
             response_model=UserResponse,
             status_code=status.HTTP_201_CREATED,
             summary="Find or create a user by email",
             description="""Find or create a user by email address. If user exists, returns existing user. If not, creates new user.

**Example:**
```bash
curl -X POST http://localhost:18057/admin/users \\
  -H "X-Admin-API-Key: YOUR_ADMIN_TOKEN" \\
  -H "Content-Type: application/json" \\
  -d '{"email":"user@example.com","name":"John Doe","password":"securepassword123"}'
```

**Required fields:** `email`, `password`
**Optional fields:** `name`, `image_url`, `max_concurrent_bots`, `data`""",
             responses={
                 status.HTTP_200_OK: {
                     "description": "User found and returned",
                     "model": UserResponse,
                 },
                 status.HTTP_201_CREATED: {
                     "description": "User created successfully",
                     "model": UserResponse,
                 }
             })
async def create_user(user_in: UserCreate, response: Response, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == user_in.email))
    existing_user = result.scalars().first()

    if existing_user:
        logger.info(f"Found existing user: {existing_user.email} (ID: {existing_user.id})")
        response.status_code = status.HTTP_200_OK
        return UserResponse.from_orm(existing_user)

    user_data = user_in.dict()
    # Hash the password before storing
    hashed_password = hash_password(user_data['password'])
    
    db_user = User(
        email=user_data['email'],
        name=user_data.get('name'),
        image_url=user_data.get('image_url'),
        hashed_password=hashed_password,
        max_concurrent_bots=user_data.get('max_concurrent_bots', 1),
        data=user_data.get('data', {})
    )
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    logger.info(f"Admin created user: {db_user.email} (ID: {db_user.id})")
    return UserResponse.from_orm(db_user)

@admin_router.get("/users", 
            response_model=List[UserResponse], # Use List import
            summary="List all users",
            description="""Get a paginated list of all users in the system.

**Example:**
```bash
curl -X GET http://localhost:18057/admin/users \\
  -H "X-Admin-API-Key: YOUR_ADMIN_TOKEN"
```

**Optional parameters:** `skip` (default: 0), `limit` (default: 100)""")
async def list_users(skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).offset(skip).limit(limit))
    users = result.scalars().all()
    return [UserResponse.from_orm(u) for u in users]

@admin_router.get("/users/email/{user_email}",
            response_model=UserResponse, # Changed from UserDetailResponse
            summary="Get a specific user by email") # Removed ', including their API tokens'
async def get_user_by_email(user_email: str, db: AsyncSession = Depends(get_db)):
    """Gets a user by their email.""" # Removed ', eagerly loading their API tokens.'
    # Removed .options(selectinload(User.api_tokens))
    result = await db.execute(
        select(User)
        .where(User.email == user_email)
    )
    user = result.scalars().first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Return the user object. Pydantic will handle serialization using UserDetailResponse.
    return user

@admin_router.get("/users/{user_id}", 
            response_model=UserDetailResponse, # Use the detailed response schema
            summary="Get a specific user by ID, including their API tokens")
async def get_user(user_id: int, db: AsyncSession = Depends(get_db)):
    """Gets a user by their ID, eagerly loading their API tokens."""
    # Eagerly load the api_tokens relationship
    result = await db.execute(
        select(User)
        .where(User.id == user_id)
        .options(selectinload(User.api_tokens))
    )
    user = result.scalars().first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="User not found"
        )
        
    # Return the user object. Pydantic will handle serialization using UserDetailResponse.
    return user

@admin_router.patch("/users/{user_id}",
             response_model=UserResponse,
             summary="Update user details",
             description="Update user's name, image URL, max concurrent bots, or password. Password will be automatically hashed.")
async def update_user(user_id: int, user_update: UserUpdate, db: AsyncSession = Depends(get_db)):
    """
    Updates specific fields of a user.
    Only provide the fields you want to change in the request body.
    Requires admin privileges.
    """
    # Fetch the user to update
    result = await db.execute(select(User).where(User.id == user_id))
    db_user = result.scalars().first()

    if not db_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Get the update data, excluding unset fields to only update provided values
    update_data = user_update.dict(exclude_unset=True)

    # Prevent changing email via this endpoint (if desired)
    if 'email' in update_data and update_data['email'] != db_user.email:
         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot change user email via this endpoint.")
    elif 'email' in update_data:
         del update_data['email'] # Don't attempt to update email to the same value

    # Handle password hashing if password is provided
    if 'password' in update_data:
        hashed_password = hash_password(update_data['password'])
        update_data['hashed_password'] = hashed_password
        del update_data['password']  # Remove plain password from update_data

    # Update the user object attributes
    updated = False
    for key, value in update_data.items():
        if hasattr(db_user, key) and getattr(db_user, key) != value:
            setattr(db_user, key, value)
            updated = True

    # If any changes were made, commit them
    if updated:
        try:
            await db.commit()
            await db.refresh(db_user)
            logger.info(f"Admin updated user ID: {user_id}")
        except Exception as e: # Catch potential DB errors (e.g., constraints)
            await db.rollback()
            logger.error(f"Error updating user {user_id}: {e}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update user.")
    else:
        logger.info(f"Admin attempted update for user ID: {user_id}, but no changes detected.")

    return UserResponse.from_orm(db_user)

@admin_router.put("/users/{user_id}",
             response_model=UserResponse,
             summary="Update user with PUT (partial updates allowed)",
             description="""Update user fields using PUT method. All fields are optional - only provide fields you want to change.

**Example:**
```bash
curl -X PUT http://localhost:18057/admin/users/1 \\
  -H "X-Admin-API-Key: YOUR_ADMIN_TOKEN" \\
  -H "Content-Type: application/json" \\
  -d '{"max_concurrent_bots": 5, "data": {"role": "admin"}, "password": "newpassword123"}'
```

**Supported fields:** `email`, `name`, `image_url`, `max_concurrent_bots`, `data`, `password` (will be hashed automatically)""")
async def put_update_user(user_id: int, user_update: UserPutUpdate, db: AsyncSession = Depends(get_db)):
    """
    Updates user fields using PUT method with partial update support.
    Only provided fields will be updated.
    Requires admin privileges.
    """
    # Fetch the user to update
    result = await db.execute(select(User).where(User.id == user_id))
    db_user = result.scalars().first()

    if not db_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Get the update data, excluding unset fields
    update_data = user_update.dict(exclude_unset=True)
    
    if not update_data:
        # No fields provided for update
        logger.info(f"PUT update for user {user_id}: no fields provided")
        return UserResponse.from_orm(db_user)

    # Handle password hashing if password is provided
    if 'password' in update_data:
        hashed_password = hash_password(update_data['password'])
        update_data['hashed_password'] = hashed_password
        del update_data['password']  # Remove plain password from update_data

    # Handle data field specially for JSONB
    if 'data' in update_data:
        new_data = update_data['data']
        if db_user.data is None:
            db_user.data = {}
        
        # Merge the new data with existing data
        if isinstance(new_data, dict):
            db_user.data.update(new_data)
            # Flag the 'data' field as modified for SQLAlchemy to detect the change
            attributes.flag_modified(db_user, "data")
        else:
            db_user.data = new_data
            attributes.flag_modified(db_user, "data")
        
        # Remove data from update_data as we handled it manually
        del update_data['data']

    # Update other user object attributes
    updated = False
    for key, value in update_data.items():
        if hasattr(db_user, key) and getattr(db_user, key) != value:
            setattr(db_user, key, value)
            updated = True

    # Mark as updated if data was modified
    if 'data' in user_update.dict(exclude_unset=True):
        updated = True

    # If any changes were made, commit them
    if updated:
        try:
            await db.commit()
            await db.refresh(db_user)
            logger.info(f"Admin PUT updated user ID: {user_id}")
        except Exception as e:
            await db.rollback()
            logger.error(f"Error PUT updating user {user_id}: {e}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update user.")
    else:
        logger.info(f"Admin attempted PUT update for user ID: {user_id}, but no changes detected.")

    return UserResponse.from_orm(db_user)

@admin_router.get("/users/{user_id}/meetings/count",
             response_model=UserMeetingCountResponse,
             summary="Get meeting count for a specific user",
             description="""Get the total number of meetings and breakdown by status for a specific user.

**Example:**
```bash
curl -X GET http://localhost:18057/admin/users/1/meetings/count \\
  -H "X-Admin-API-Key: YOUR_ADMIN_TOKEN"
```

**Returns:** Meeting count statistics including total and breakdown by status.""")
async def get_user_meeting_count(user_id: int, db: AsyncSession = Depends(get_db)):
    """
    Get meeting count statistics for a specific user.
    Returns total count and breakdown by meeting status.
    """
    # Verify user exists
    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalars().first()
    
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Get total meeting count
    total_result = await db.execute(
        select(func.count(Meeting.id)).where(Meeting.user_id == user_id)
    )
    total_meetings = total_result.scalar_one()

    # Get count by status
    status_counts = {}
    status_list = ['active', 'completed', 'requested', 'stopping', 'failed']
    
    for status_name in status_list:
        count_result = await db.execute(
            select(func.count(Meeting.id)).where(
                Meeting.user_id == user_id,
                Meeting.status == status_name
            )
        )
        status_counts[status_name] = count_result.scalar_one()

    # Create response using the schema
    status_breakdown = MeetingStatusCount(**status_counts)
    
    response = UserMeetingCountResponse(
        user_id=user_id,
        total_meetings=total_meetings,
        by_status=status_breakdown
    )
    
    logger.info(f"Admin requested meeting count for user {user_id}: {total_meetings} total meetings")
    return response

@admin_router.post("/users/{user_id}/tokens", 
             response_model=TokenResponse,
             status_code=status.HTTP_201_CREATED,
             summary="Generate a new API token for a user",
             description="""Generate a new API token for a user. The token can be used for regular API operations.

**Example:**
```bash
curl -X POST http://localhost:18057/admin/users/1/tokens \\
  -H "X-Admin-API-Key: YOUR_ADMIN_TOKEN"
```

**Returns:** Token object with `token` field that can be used as `X-API-Key` for user operations.""")
async def create_token_for_user(user_id: int, db: AsyncSession = Depends(get_db)):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    token_value = generate_secure_token()
    # Use the APIToken model from shared_models
    db_token = APIToken(token=token_value, user_id=user_id)
    db.add(db_token)
    await db.commit()
    await db.refresh(db_token)
    logger.info(f"Admin created token for user {user_id} ({user.email})")
    # Use TokenResponse for consistency with schema definition (datetime object)
    return TokenResponse.from_orm(db_token)

@admin_router.delete("/tokens/{token_id}", 
                status_code=status.HTTP_204_NO_CONTENT,
                summary="Revoke/Delete an API token by its ID")
async def delete_token(token_id: int, db: AsyncSession = Depends(get_db)):
    """Deletes an API token by its database ID."""
    # Fetch the token by its primary key ID
    db_token = await db.get(APIToken, token_id)
    
    if not db_token:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Token not found"
        )
        
    # Delete the token
    await db.delete(db_token)
    await db.commit()
    logger.info(f"Admin deleted token ID: {token_id}")
    # No body needed for 204 response
    return 

# --- Usage Stats Endpoints ---
@admin_router.get("/stats/meetings-users",
            response_model=PaginatedMeetingUserStatResponse,
            summary="Get paginated list of meetings joined with users")
async def list_meetings_with_users(
    skip: int = 0, 
    limit: int = 100, 
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieves a paginated list of all meetings, with user details embedded.
    This provides a comprehensive overview for administrators.
    """
    # First, get the total count of meetings for pagination headers
    count_result = await db.execute(select(func.count(Meeting.id)))
    total = count_result.scalar_one()

    # Then, fetch the paginated list of meetings, joining with users
    result = await db.execute(
        select(Meeting)
        .options(selectinload(Meeting.user))
        .order_by(Meeting.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    meetings = result.scalars().all()

    # Now, construct the response using Pydantic models
    response_items = [
        MeetingUserStat(
            **meeting.__dict__,
            user=UserResponse.from_orm(meeting.user)
        )
        for meeting in meetings if meeting.user
    ]

    return PaginatedMeetingUserStatResponse(total=total, items=response_items)

# App events
@app.on_event("startup")
async def startup_event():
    logger.info("Admin API starting up. Skipping automatic DB initialization.")
    # The 'migrate-or-init' Makefile target is now responsible for all DB setup.
    # await init_db()
    pass

# Include the admin router
app.include_router(admin_router)
app.include_router(user_router)
app.include_router(auth_router)

# Root endpoint (optional)
@app.get("/")
async def root():
    return {"message": "Vexa Admin API"}
