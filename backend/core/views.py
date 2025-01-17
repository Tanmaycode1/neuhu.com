from rest_framework import viewsets
from rest_framework.response import Response
from .utils.response import api_response

class BaseViewSet(viewsets.ModelViewSet):
    """
    Base ViewSet that includes common functionality and standardized responses
    """
    
    @property
    def model_name(self):
        """
        Returns the model name in lowercase.
        Override this if you need a custom model name.
        """
        return self.queryset.model._meta.model_name.lower()

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return api_response(data=serializer.data)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = self.perform_create(serializer)
        
        return api_response(
            message=f"{self.model_name} created successfully",
            data=serializer.data,
            status_code=201
        )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        
        return api_response(
            message=f"{self.model_name} updated successfully",
            data=serializer.data
        )

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        
        return api_response(
            message=f"{self.model_name} deleted successfully"
        ) 