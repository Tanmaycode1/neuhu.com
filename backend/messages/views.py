from django.shortcuts import render, get_object_or_404
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Q, Max, F, Count
from django.utils import timezone
from .models import ChatRoom, Message
from .serializers import ChatRoomSerializer, MessageSerializer, ChatRoomListSerializer
from django.contrib.auth import get_user_model

User = get_user_model()

class ChatRoomViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ChatRoomSerializer
    
    def get_queryset(self):
        return ChatRoom.objects.filter(
            participants=self.request.user
        ).annotate(
            unread_count=Count(
                'messages',
                filter=Q(messages__is_read=False) & ~Q(messages__sender=self.request.user)
            )
        ).order_by('-updated_at')
    
    def get_serializer_class(self):
        if self.action == 'list':
            return ChatRoomListSerializer
        return ChatRoomSerializer
    
    def create(self, request):
        participant_id = request.data.get('participant_id')
        if not participant_id:
            return Response(
                {'error': 'participant_id is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
            
        # Check if chat room already exists
        participant = get_object_or_404(User, id=participant_id)
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
    
    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        room = self.get_object()
        Message.objects.filter(
            room=room,
            is_read=False
        ).exclude(
            sender=request.user
        ).update(
            is_read=True,
            read_at=timezone.now()
        )
        
        return Response({
            'success': True,
            'message': 'All messages marked as read'
        })

class MessageViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = MessageSerializer
    
    def get_queryset(self):
        room_id = self.kwargs.get('room_pk')
        return Message.objects.filter(room_id=room_id)
    
    def create(self, request, room_pk=None):
        room = get_object_or_404(ChatRoom, id=room_pk)
        
        # Ensure user is participant
        if request.user not in room.participants.all():
            return Response(
                {'error': 'You are not a participant of this chat room'}, 
                status=status.HTTP_403_FORBIDDEN
            )
            
        # Create message
        serializer = self.get_serializer(data={
            **request.data,
            'room': room.id,
            'sender': request.user.id
        })
        serializer.is_valid(raise_exception=True)
        message = serializer.save()
        
        # Update room's last message and timestamp
        room.last_message = message
        room.save()
        
        return Response({
            'success': True,
            'data': serializer.data,
            'message': 'Message sent successfully'
        })
    
    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None, room_pk=None):
        message = self.get_object()
        message.mark_as_read()
        return Response({
            'success': True,
            'message': 'Message marked as read'
        })
