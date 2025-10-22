# app/routes/cognito_routes.py
from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import RedirectResponse
from ..cognito_config import cognito_config
from ..cognito_service import cognito_service
import urllib.parse

router = APIRouter(tags=["cognito-oauth"])


@router.get("/login")
async def login(request: Request):
    """Redirect to Cognito login page"""
    # Generate the authorization URL
    if not cognito_config.domain_prefix:
        raise HTTPException(status_code=500, detail="COGNITO_DOMAIN_PREFIX not set")
    auth_url = (
        f"https://{cognito_config.domain_prefix}.auth.{cognito_config.region}.amazoncognito.com/oauth2/authorize?"
        f"response_type=code&"
        f"client_id={cognito_config.client_id}&"
        f"redirect_uri={cognito_config.redirect_uri}&"
        f"scope={'+'.join(cognito_config.scopes)}&"
        f"state=random_state_string"
    )
    
    return RedirectResponse(url=auth_url)

@router.get("/authorize")
async def authorize(request: Request):
    """Handle OAuth callback from Cognito"""
    code = request.query_params.get("code")
    state = request.query_params.get("state")
    error = request.query_params.get("error")
    
    if error:
        raise HTTPException(status_code=400, detail=f"OAuth error: {error}")
    
    if not code:
        raise HTTPException(status_code=400, detail="Authorization code not provided")
    
    try:
        # Exchange code for tokens
        token_data = {
            'grant_type': 'authorization_code',
            'client_id': cognito_config.client_id,
            'code': code,
            'redirect_uri': cognito_config.redirect_uri
        }
        
        if cognito_config.client_secret:
            token_data['client_secret'] = cognito_config.client_secret
        
        # Make token request
        import requests
        if not cognito_config.domain_prefix:
            raise HTTPException(status_code=500, detail="COGNITO_DOMAIN_PREFIX not set")
        token_url = f"https://{cognito_config.domain_prefix}.auth.{cognito_config.region}.amazoncognito.com/oauth2/token"
        
        response = requests.post(
            token_url,
            data=token_data,
            headers={'Content-Type': 'application/x-www-form-urlencoded'}
        )
        
        if response.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to exchange code for tokens")
        
        token_response = response.json()
        access_token = token_response.get('access_token')
        id_token = token_response.get('id_token')
        
        if not access_token:
            raise HTTPException(status_code=400, detail="No access token received")
        
        # Get user info
        user_info = cognito_service.get_user_info(access_token)
        
        # Store user info in session (you might want to use a proper session store)
        # For now, we'll return the tokens directly
        return {
            "access_token": access_token,
            "id_token": id_token,
            "user": user_info,
            "message": "Login successful"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Authorization failed: {str(e)}")

@router.get("/logout")
async def logout():
    """Logout and redirect to Cognito logout"""
    logout_url = cognito_config.get_logout_url()
    return RedirectResponse(url=logout_url)

@router.get("/userinfo")
async def get_user_info(request: Request):
    """Get current user information"""
    # This would typically get the user from the session or token
    # For now, this is a placeholder
    return {"message": "User info endpoint - implement session management"}

@router.post("/token/refresh")
async def refresh_token(request: Request):
    """Refresh access token using refresh token"""
    # This would handle token refresh
    # For now, this is a placeholder
    return {"message": "Token refresh endpoint - implement refresh logic"}
