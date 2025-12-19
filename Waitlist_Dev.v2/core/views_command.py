from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.contrib.auth.models import Group, User
from django.utils import timezone
from .models import CommandWorkflowEntry, Ban, BanAuditLog
from .command_data import WORKFLOW_RULES, WORKFLOW_STEPS
from .utils import get_user_highest_role, can_manage_role
from .models import Capability

# Helper to verify permissions
def has_command_access(user):
    # Check for 'access_management' capability as a baseline
    if user.is_superuser:
        return True
        
    try:
        cap = Capability.objects.get(slug='access_management')
        return cap.groups.filter(id__in=user.groups.values_list('id', flat=True)).exists()
    except Capability.DoesNotExist:
        # If capability doesn't exist, only superusers can access
        return False

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def api_command_workflow(request):
    if not has_command_access(request.user):
        return Response({'error': 'Access Denied'}, status=status.HTTP_403_FORBIDDEN)

    if request.method == 'GET':
        # Pagination
        limit = int(request.GET.get('limit', 20))
        offset = int(request.GET.get('offset', 0))
        
        queryset = CommandWorkflowEntry.objects.all().select_related('target_user', 'issuer')
        total = queryset.count()
        entries = queryset[offset:offset+limit]
        
        data = []
        for e in entries:
            # Resolve main character for display
            char_name = e.target_user.username
            # Try to get main char from active_char logic if available, or just username
            # In management views, we usually annotate, but let's keep it simple for now.
            
            data.append({
                'id': e.id,
                'target_user_id': e.target_user.id,
                'target_username': char_name,
                'issuer_username': e.issuer.username if e.issuer else 'System',
                'program': e.program,
                'action': e.action_type,
                'checklist': e.checklist_state,
                'created_at': e.created_at,
                'updated_at': e.updated_at
            })
            
        return Response({
            'items': data,
            'total': total,
            'workflow_steps': WORKFLOW_STEPS
        })

    elif request.method == 'POST':
        # Create new entry
        target_id = request.data.get('target_user_id')
        program = request.data.get('program')
        action = request.data.get('action')
        
        target_user = get_object_or_404(User, id=target_id)
        
        # Initialize checklist state with False
        initial_state = {step: False for step in WORKFLOW_STEPS}
        
        entry = CommandWorkflowEntry.objects.create(
            target_user=target_user,
            issuer=request.user,
            program=program,
            action_type=action,
            checklist_state=initial_state
        )
        
        return Response({'success': True, 'id': entry.id})

@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def api_command_workflow_detail(request, entry_id):
    if not has_command_access(request.user):
        return Response({'error': 'Access Denied'}, status=status.HTTP_403_FORBIDDEN)

    entry = get_object_or_404(CommandWorkflowEntry, id=entry_id)
    entry.delete()
    return Response({'success': True})

@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def api_command_workflow_step(request, entry_id):
    if not has_command_access(request.user):
        return Response({'error': 'Access Denied'}, status=status.HTTP_403_FORBIDDEN)

    entry = get_object_or_404(CommandWorkflowEntry, id=entry_id)
    
    step = request.data.get('step')
    value = request.data.get('value') # Boolean
    meta = request.data.get('meta', {}) # e.g. ban_reason
    
    if step not in WORKFLOW_STEPS:
        return Response({'error': 'Invalid step'}, status=400)
    
    # Update state
    entry.checklist_state[step] = value
    entry.save()
    
    # Automation Logic for 'Waitlist' step
    if step == 'Waitlist' and value is True:
        rules = WORKFLOW_RULES.get((entry.program, entry.action_type))
        
        if rules:
            try:
                # Execute Rules
                for action_code, payload in rules:
                    if action_code == 'add':
                        try:
                            group = Group.objects.get(name=payload)
                            entry.target_user.groups.add(group)
                        except Group.DoesNotExist:
                            # Log error but don't crash entire loop? 
                            # Or fail the whole transaction? 
                            # Raising exception here triggers rollback in outer try/except block
                            raise Exception(f"Group '{payload}' does not exist.")
                    
                    elif action_code == 'remove':
                        try:
                            group = Group.objects.get(name=payload)
                            entry.target_user.groups.remove(group)
                        except Group.DoesNotExist:
                            pass
                            
                    elif action_code == 'clear_all':
                        entry.target_user.groups.clear()
                        
                    elif action_code == 'ban':
                        reason = meta.get('reason', 'Command Workflow Ban')
                        Ban.objects.create(
                            user=entry.target_user,
                            issuer=request.user,
                            reason=reason
                        )
                        # Log it
                        BanAuditLog.objects.create(
                            target_user=entry.target_user,
                            actor=request.user,
                            action='create',
                            details=f"Workflow Ban: {reason}"
                        )
                        
                    elif action_code == 'unban':
                        # Expire all active bans
                        active_bans = Ban.objects.filter(user=entry.target_user, expires_at__isnull=True)
                        now = timezone.now()
                        for b in active_bans:
                            b.expires_at = now
                            b.save()
                            BanAuditLog.objects.create(
                                target_user=entry.target_user,
                                ban=b,
                                actor=request.user,
                                action='remove',
                                details="Workflow Unban"
                            )

                return Response({'success': True, 'message': 'Automation applied successfully'})
                
            except Exception as e:
                # Revert checkbox if failed
                entry.checklist_state[step] = False
                entry.save()
                return Response({'error': str(e)}, status=500)
        else:
             return Response({'success': True, 'message': 'No automation rules for this program/action'})

    return Response({'success': True})
