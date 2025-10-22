# app/routes/admin.py
from fastapi import APIRouter, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from ..routes.dependencies import admin_required, get_current_user

bearer = HTTPBearer()

router = APIRouter(tags=["admin"])

@router.get("/admin/test")
def admin_test(user: dict = Depends(admin_required)):
    """Test endpoint for admin users only"""
    return {
        "message": "Admin access granted!",
        "user": user,
        "admin_features": [
            "User management",
            "System configuration", 
            "Analytics dashboard",
            "Advanced settings"
        ]
    }

@router.get("/admin/user-info")
def get_user_info(user: dict = Depends(get_current_user)):
    """Get current user info (accessible to all authenticated users)"""
    return {
        "message": "User info retrieved",
        "user": user,
        "is_admin": user.get("role") == "admin" or "Admin" in user.get("groups", [])
    }

@router.get("/admin/users")
def list_users(user: dict = Depends(admin_required)):
    """List all users (admin only)"""
    return {
        "message": "User list (admin only)",
        "users": [
            {"id": 1, "username": "admin_user", "role": "admin"},
            {"id": 2, "username": "regular_user", "role": "user"}
        ]
    }

@router.get("/admin/debug")
def debug_user_info(user: dict = Depends(get_current_user)):
    """Debug endpoint to check user authentication and group membership"""
    return {
        "message": "Debug user information",
        "user": user,
        "is_admin": user.get("role") == "admin" or "Admin" in user.get("groups", []),
        "role_check": {
            "role": user.get("role"),
            "role_is_admin": user.get("role") == "admin"
        },
        "groups_check": {
            "groups": user.get("groups", []),
            "has_admin_group": "Admin" in user.get("groups", []),
            "has_admin_group_lower": "admin" in [g.lower() for g in user.get("groups", [])]
        },
        "admin_required_check": {
            "role_condition": user.get("role") == "admin",
            "group_condition": "Admin" in user.get("groups", []),
            "would_pass_admin_required": (user.get("role") == "admin" or "Admin" in user.get("groups", []))
        }
    }

@router.get("/admin/auth-test")
def test_auth_step_by_step(credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    """Test authentication step by step without dependencies"""
    from .. import auth
    from ..cognito_service import cognito_service
    
    try:
        token = credentials.credentials
        print(f"🔍 Testing token: {token[:20]}...")
        
        # Step 1: Verify token
        try:
            payload = auth.verify_token(token)
            print(f"✅ Token verification successful")
            print(f"   Payload: {payload}")
        except Exception as e:
            print(f"❌ Token verification failed: {e}")
            return {"error": "Token verification failed", "details": str(e)}
        
        # Step 2: Get user info
        try:
            user_info = cognito_service.get_user_info(token)
            print(f"✅ User info retrieved")
            print(f"   User info: {user_info}")
        except Exception as e:
            print(f"❌ User info retrieval failed: {e}")
            return {"error": "User info retrieval failed", "details": str(e)}
        
        # Step 3: Check role and groups
        role = user_info.get("role", "user")
        groups = user_info.get("groups", [])
        
        return {
            "message": "Authentication test successful",
            "token_preview": f"{token[:20]}...",
            "payload": payload,
            "user_info": user_info,
            "role": role,
            "groups": groups,
            "is_admin": role == "admin" or "admin" in [g.lower() for g in groups]
        }
        
    except Exception as e:
        print(f"❌ Authentication test failed: {e}")
        return {"error": "Authentication test failed", "details": str(e)}

@router.post("/admin/test-upload-auth")
def test_upload_auth(credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    """Test upload authentication specifically"""
    from .. import auth
    from ..cognito_service import cognito_service
    
    try:
        token = credentials.credentials
        
        # Test the exact same flow as upload endpoint
        payload = auth.verify_token(token)
        user_info = cognito_service.get_user_info(token)
        
        return {
            "message": "Upload authentication test successful",
            "user": {
                "username": payload.get("sub"), 
                "role": user_info.get("role", "user"),
                "groups": user_info.get("groups", ["User"]),
                "email": user_info.get("email")
            },
            "can_upload": True
        }
        
    except Exception as e:
        return {
            "error": "Upload authentication failed", 
            "details": str(e),
            "can_upload": False
        }
