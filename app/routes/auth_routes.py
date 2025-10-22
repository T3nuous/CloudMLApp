# app/routes/auth_routes.py
from fastapi import APIRouter, HTTPException
from .. import auth
from ..schemas import LoginRequest, TokenResponse, RegisterRequest, ConfirmRequest
from ..cognito_service import cognito_service

router = APIRouter(tags=["auth"])

# AWS TODO (Cognito endpoints):
# - Add endpoints for Cognito user registration and confirmation:
#   * POST /register: call cognito-idp sign_up with username, password, email
#   * POST /confirm: call confirm_sign_up with username and confirmation code
# - For login below, replace local auth with Cognito initiate_auth (USER_PASSWORD_AUTH) and return Cognito's id/access tokens
# - Return JWTs (id_token/access_token) from Cognito; do not mint local tokens
# - Consider endpoints for MFA challenge responses if MFA is enabled


@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest):
    """Login with username/password using Cognito"""
    user = auth.authenticate(data.username, data.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    
    return {
        "access_token": user["access_token"], 
        "id_token": user.get("id_token"),
        "token_type": "bearer",
        "user": {
            "username": user["username"],
            "email": user["email"],
            "role": user["role"]
        }
    }


@router.post("/register")
def register(data: RegisterRequest):
    """Register a new user in Cognito (sign up)"""
    try:
        response = cognito_service.sign_up(data.username, data.password, data.email)
        return {"message": "Sign-up initiated. Check email for confirmation code.", "response": response}
    except HTTPException as e:
        raise e


@router.post("/confirm")
def confirm(data: ConfirmRequest):
    """Confirm sign-up with the code sent via email"""
    try:
        response = cognito_service.confirm_sign_up(data.username, data.code)
        return {"message": "Confirmation successful", "response": response}
    except HTTPException as e:
        raise e

