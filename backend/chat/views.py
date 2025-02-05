from rest_framework import viewsets, status, permissions
from rest_framework.response import Response
from rest_framework.decorators import action
from django.db.models import Q, Prefetch
from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.core.exceptions import PermissionDenied
from .models import ChatRoom, Message
from .serializers import ChatRoomSerializer, MessageSerializer
from users.models import User

class ChatRoomViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ChatRoomSerializer
    
    def get_queryset(self):
        return ChatRoom.objects.filter(
            participants=self.request.user
        ).prefetch_related(
            'participants',
            Prefetch(
                'messages',
                queryset=Message.objects.order_by('-created_at'),
                to_attr='message_list'
            )
        ).order_by('-updated_at')

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context
    
    def create(self, request, *args, **kwargs):
        participant_id = request.data.get('participant_id')
        
        if not participant_id:
            return Response({
                'success': False,
                'message': 'participant_id is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            participant = User.objects.get(id=participant_id)
            
            # Check if chat room already exists
            existing_room = ChatRoom.objects.filter(
                participants=request.user
            ).filter(
                participants=participant
            ).first()
            
            if existing_room:
                serializer = self.get_serializer(existing_room)
                return Response({
                    'success': True,
                    'data': serializer.data,
                    'message': 'Existing chat room retrieved'
                })
            
            # Create new chat room
            chat_room = ChatRoom.objects.create()
            chat_room.participants.add(request.user, participant)
            
            serializer = self.get_serializer(chat_room)
            return Response({
                'success': True,
                'data': serializer.data,
                'message': 'Chat room created successfully'
            })
            
        except User.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Participant not found'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({
                'success': False,
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        try:
            room = self.get_object()
            room.mark_messages_as_read(request.user)
            
            return Response({
                'success': True,
                'message': 'All messages marked as read'
            })
        except Exception as e:
            return Response({
                'success': False,
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class MessageViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = MessageSerializer
    
    def get_queryset(self):
        return Message.objects.filter(
            room_id=self.kwargs.get('room_pk')
        ).select_related('sender')

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context
    
    def perform_create(self, serializer):
        room = get_object_or_404(ChatRoom, id=self.kwargs.get('room_pk'))
        if self.request.user not in room.participants.all():
            raise PermissionDenied("You are not a participant of this chat room")
        serializer.save(room=room, sender=self.request.user)
    
    def create(self, request, *args, **kwargs):
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            self.perform_create(serializer)
            
            return Response({
                'success': True,
                'data': serializer.data,
                'message': 'Message sent successfully'
            })
        except PermissionDenied as e:
            return Response({
                'success': False,
                'message': str(e)
            }, status=status.HTTP_403_FORBIDDEN)
        except Exception as e:
            return Response({
                'success': False,
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None, room_pk=None):
        try:
            message = self.get_object()
            message.mark_as_read()
            return Response({
                'success': True,
                'message': 'Message marked as read'
            })
        except Exception as e:
            return Response({
                'success': False,
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['DELETE'])
    def delete_all(self, request, room_pk=None):
        """Delete all messages in the room."""
        try:
            room = get_object_or_404(ChatRoom, id=room_pk)
            if request.user not in room.participants.all():
                raise PermissionDenied("You are not a participant of this chat room")
            
            success = room.delete_all_messages(request.user)
            if success:
                return Response({
                    'success': True,
                    'message': 'All messages deleted successfully'
                })
            return Response({
                'success': False,
                'message': 'Failed to delete messages'
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({
                'success': False,
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['GET'])
    def filter(self, request, room_pk=None):
        """Filter messages based on criteria."""
        try:
            room = get_object_or_404(ChatRoom, id=room_pk)
            if request.user not in room.participants.all():
                raise PermissionDenied("You are not a participant of this chat room")

            # Get filter parameters
            filters = {}
            if request.query_params.get('start_date'):
                filters['start_date'] = request.query_params.get('start_date')
            if request.query_params.get('end_date'):
                filters['end_date'] = request.query_params.get('end_date')
            if request.query_params.get('is_read'):
                filters['is_read'] = request.query_params.get('is_read').lower() == 'true'
            if request.query_params.get('sender_id'):
                filters['sender_id'] = request.query_params.get('sender_id')
            if request.query_params.get('has_attachment'):
                filters['has_attachment'] = request.query_params.get('has_attachment').lower() == 'true'

            messages = room.filter_messages(**filters)
            serializer = self.get_serializer(messages, many=True)
            
            return Response({
                'success': True,
                'data': serializer.data,
                'message': 'Messages filtered successfully'
            })
        except Exception as e:
            return Response({
                'success': False,
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['POST'])
    def mark_all_read(self, request, room_pk=None):
        """Mark all messages in the room as read."""
        try:
            room = get_object_or_404(ChatRoom, id=room_pk)
            if request.user not in room.participants.all():
                raise PermissionDenied("You are not a participant of this chat room")
            
            room.mark_messages_as_read(request.user)
            return Response({
                'success': True,
                'message': 'All messages marked as read'
            })
        except Exception as e:
            return Response({
                'success': False,
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)