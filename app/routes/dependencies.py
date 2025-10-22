# app/routes/dependencies.py
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from .. import auth

bearer = HTTPBearer()

# AWS TODO (JWT verification via Cognito):
# - Replace local verification with Cognito JWKS validation
# - Optionally enforce group-based authorization by reading "cognito:groups" claim

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    token = credentials.credentials
    payload = auth.verify_token(token)
    
    # Get user info including groups from Cognito
    from ..cognito_service import cognito_service
    user_info = cognito_service.get_user_info(token)
    
    return {
        "username": payload.get("sub"), 
        "role": user_info.get("role", "user"),
        "groups": user_info.get("groups", ["User"]),
        "email": user_info.get("email")
    }

def admin_required(user: dict = Depends(get_current_user)):
    # Check role
    role = user.get("role", "").lower()
    is_admin_role = role == "admin"
    
    # Check groups (case insensitive)
    groups = [g.lower() for g in user.get("groups", [])]
    is_admin_group = "admin" in groups
    
    if not (is_admin_role or is_admin_group):
        raise HTTPException(
            status_code=403, 
            detail=f"Admin privileges required. Current role: {user.get('role')}, Groups: {user.get('groups')}"
        )
    return user

def group_required(group_name: str):
    """Require user to be in a specific group"""
    def _group_required(user: dict = Depends(get_current_user)):
        if group_name not in user.get("groups", []) and user.get("role", "").lower() != group_name.lower():
            raise HTTPException(status_code=403, detail=f"{group_name} group membership required")
        return user
    return _group_required