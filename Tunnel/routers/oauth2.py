from fastapi.security import HTTPBearer
from fastapi import HTTPException
from fastapi import Depends
from fastapi import status
from . import token 

# Changed from OAuth2PasswordBearer to HTTPBearer
oauth2_scheme = HTTPBearer()

def get_current_user(auth_header = Depends(oauth2_scheme)):
     credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
         )
     # Extract the token from the HTTPBearer credentials
     return token.verify_token(auth_header.credentials, credentials_exception)




