import os
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.conf import settings

def handle_uploaded_file(file, subdirectory):
    """
    Handle file upload to either local storage or S3 (when configured)
    """
    if not file:
        return None

    # Generate unique filename
    filename = f"{subdirectory}/{file.name}"
    
    # Save file using default storage (local or S3)
    path = default_storage.save(filename, ContentFile(file.read()))
    return path

"""
# AWS S3 specific utilities (for future use)
def generate_presigned_url(file_path, expiration=3600):
    try:
        from boto3 import client
        s3_client = client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_S3_REGION_NAME
        )
        
        url = s3_client.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': settings.AWS_STORAGE_BUCKET_NAME,
                'Key': file_path
            },
            ExpiresIn=expiration
        )
        return url
    except Exception as e:
        print(f"Error generating presigned URL: {e}")
        return None
""" 