import os
from uuid import uuid4
from django.conf import settings

def handle_uploaded_file(file, directory='uploads'):
    """
    Handle file upload and return the file path
    """
    # Create directory if it doesn't exist
    upload_path = os.path.join(settings.MEDIA_ROOT, directory)
    os.makedirs(upload_path, exist_ok=True)

    # Generate unique filename
    ext = os.path.splitext(file.name)[1]
    filename = f"{uuid4().hex}{ext}"
    
    # Full path for the file
    filepath = os.path.join(upload_path, filename)
    
    # Write file
    with open(filepath, 'wb+') as destination:
        for chunk in file.chunks():
            destination.write(chunk)
    
    # Return relative path from MEDIA_ROOT
    return os.path.join(directory, filename) 