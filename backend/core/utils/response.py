from rest_framework.response import Response
from rest_framework import status
from typing import Any

class ErrorCode:
    # Auth Errors
    INVALID_CREDENTIALS = "AUTH_001"
    EMAIL_NOT_VERIFIED = "AUTH_002"
    EMAIL_ALREADY_EXISTS = "AUTH_003"
    INVALID_TOKEN = "AUTH_004"
    
    # User Errors
    USER_NOT_FOUND = "USER_001"
    USERNAME_TAKEN = "USER_002"
    INVALID_EMAIL = "USER_003"
    
    # Validation Errors
    INVALID_PASSWORD = "VAL_001"
    REQUIRED_FIELD = "VAL_002"
    INVALID_FORMAT = "VAL_003"
    
    # Profile Errors
    INVALID_IMAGE = "PROF_001"
    FILE_TOO_LARGE = "PROF_002"

ERROR_MESSAGES = {
    ErrorCode.INVALID_CREDENTIALS: "Invalid email or password",
    ErrorCode.EMAIL_NOT_VERIFIED: "Please verify your email before proceeding",
    ErrorCode.EMAIL_ALREADY_EXISTS: "An account with this email already exists",
    ErrorCode.INVALID_TOKEN: "Invalid or expired token",
    ErrorCode.USER_NOT_FOUND: "User not found",
    ErrorCode.USERNAME_TAKEN: "This username is already taken",
    ErrorCode.INVALID_EMAIL: "Please enter a valid email address",
    ErrorCode.INVALID_PASSWORD: "Password must be at least 8 characters and contain letters and numbers",
    ErrorCode.REQUIRED_FIELD: "This field is required",
    ErrorCode.INVALID_FORMAT: "Invalid format",
    ErrorCode.INVALID_IMAGE: "Invalid image format. Please upload JPG, PNG or WebP",
    ErrorCode.FILE_TOO_LARGE: "File size should not exceed 5MB"
}

def api_response(
    message: str = "",
    data: Any = None,
    success: bool = True,
    status_code: int = status.HTTP_200_OK
) -> Response:
    """
    Standard API response format
    """
    response_data = {
        "success": success,
        "message": message,
        "data": data
    }
    
    return Response(
        response_data,
        status=status_code
    )

def error_response(
    message: str,
    error_code: ErrorCode,
    status_code: int = status.HTTP_400_BAD_REQUEST,
    errors: dict = None
) -> Response:
    """
    Standard error response format
    """
    response_data = {
        "success": False,
        "message": message,
        "error_code": error_code,
        "errors": errors
    }
    
    return Response(
        response_data,
        status=status_code
    ) 