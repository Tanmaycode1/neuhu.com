from django.conf import settings
from django.core.files.storage import FileSystemStorage

# Local Storage Configuration
local_storage = FileSystemStorage(
    location=settings.MEDIA_ROOT,
    base_url=settings.MEDIA_URL
)

"""
# AWS S3 Configuration (Commented out for future use)
from storages.backends.s3boto3 import S3Boto3Storage

class MediaStorage(S3Boto3Storage):
    location = 'media'
    file_overwrite = False
    default_acl = 'public-read'
""" 