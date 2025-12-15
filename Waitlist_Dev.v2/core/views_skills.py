from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db import transaction, models

from core.permissions import can_manage_doctrines

# Models
from pilot_data.models import ItemType, EveCharacter
from waitlist_data.models import (
    DoctrineFit, DoctrineCategory, DoctrineTag, FitModule,
    SkillTier, SkillGroup, SkillRequirement, SkillGroupMember
)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_skills_data(request):
    if not can_manage_doctrines(request.user):
        return Response({'error': 'Permission Denied'}, status=403)

    fits = DoctrineFit.objects.select_related('ship_type').all().order_by('name')
    tiers = SkillTier.objects.all().order_by('-order')
    groups = SkillGroup.objects.annotate(count=models.Count('members')).order_by('name')

    requirements = SkillRequirement.objects.select_related(
        'doctrine_fit', 'hull', 'skill', 'group', 'tier', 'doctrine_fit__ship_type'
    ).all().order_by('doctrine_fit__name', 'hull__type_name')

    return Response({
        'fits': [{
            'id': f.id,
            'name': f.name,
            'ship_name': f.ship_type.type_name
        } for f in fits],
        'tiers': [{
            'id': t.id,
            'name': t.name,
            'order': t.order,
            'hex': t.hex_color,
            'badge_class': t.badge_class
        } for t in tiers],
        'groups': [{
            'id': g.id,
            'name': g.name,
            'count': g.count
        } for g in groups],
        'requirements': [{
            'id': r.id,
            'fit_name': r.doctrine_fit.name if r.doctrine_fit else None,
            'ship_name': r.doctrine_fit.ship_type.type_name if r.doctrine_fit else (r.hull.type_name if r.hull else "Unknown"),
            'tier': {'name': r.tier.name, 'hex': r.tier.hex_color} if r.tier else None,
            'group_name': r.group.name if r.group else None,
            'skill_name': r.skill.type_name if r.skill else None,
            'level': r.level
        } for r in requirements]
    })

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_search_hull(request):
    q = request.GET.get('q', '')
    if len(q) < 3: return Response({'results': []})

    # Category 6 = Ship
    hulls = ItemType.objects.filter(group__category_id=6, type_name__icontains=q, published=True)[:20]
    return Response({'results': [{'id': h.type_id, 'name': h.type_name} for h in hulls]})

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_skill_req_manage(request, action):
    if not can_manage_doctrines(request.user): return Response({'error': 'Permission Denied'}, status=403)

    if action == 'add':
        data = request.data
        target_type = data.get('target_type')
        target_id = data.get('target_id')
        req_type = data.get('req_type')
        tier_id = data.get('tier_id')

        fit = None
        hull = None
        tier = None

        if target_type == 'fit':
            fit = get_object_or_404(DoctrineFit, id=target_id)
        else:
            hull = get_object_or_404(ItemType, type_id=target_id)

        if tier_id:
            tier = get_object_or_404(SkillTier, id=tier_id)

        skill = None
        group = None
        level = 1

        if req_type == 'skill':
            skill_name = data.get('skill_name')
            level = int(data.get('level', 1))
            skill = ItemType.objects.filter(type_name__iexact=skill_name, group__category_id=16).first()
            if not skill: return Response({'success': False, 'error': 'Skill not found'}, status=400)
        else:
            group_id = data.get('group_id')
            group = get_object_or_404(SkillGroup, id=group_id)

        SkillRequirement.objects.create(
            doctrine_fit=fit, hull=hull, tier=tier,
            skill=skill, group=group, level=level
        )
        return Response({'success': True})

    elif action == 'delete':
        req_id = request.data.get('req_id')
        SkillRequirement.objects.filter(id=req_id).delete()
        return Response({'success': True})

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_skill_group_manage(request):
    if not can_manage_doctrines(request.user): return Response({'error': 'Permission Denied'}, status=403)

    action = request.data.get('action')
    if action == 'create':
        name = request.data.get('name')
        if SkillGroup.objects.filter(name=name).exists():
             return Response({'success': False, 'error': 'Group exists'}, status=400)
        SkillGroup.objects.create(name=name)
    elif action == 'delete':
        group_id = request.data.get('group_id')
        SkillGroup.objects.filter(id=group_id).delete()

    return Response({'success': True})

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_skill_group_members(request, group_id):
    if not can_manage_doctrines(request.user): return Response({'error': 'Permission Denied'}, status=403)
    members = SkillGroupMember.objects.filter(group_id=group_id).select_related('skill').order_by('skill__type_name')
    return Response({'members': [
        {'id': m.id, 'name': m.skill.type_name, 'level': m.level} for m in members
    ]})

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_skill_member_manage(request, action):
    if not can_manage_doctrines(request.user): return Response({'error': 'Permission Denied'}, status=403)

    if action == 'add':
        group_id = request.data.get('group_id')
        skill_name = request.data.get('skill_name')
        level = request.data.get('level', 1)

        group = get_object_or_404(SkillGroup, id=group_id)
        skill = ItemType.objects.filter(type_name__iexact=skill_name, group__category_id=16).first()
        if not skill: return Response({'success': False, 'error': 'Skill not found'}, status=400)

        SkillGroupMember.objects.create(group=group, skill=skill, level=level)

    elif action == 'remove':
        member_id = request.data.get('member_id')
        SkillGroupMember.objects.filter(id=member_id).delete()

    return Response({'success': True})

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_skill_tier_manage(request):
    if not can_manage_doctrines(request.user): return Response({'error': 'Permission Denied'}, status=403)

    action = request.data.get('action')
    if action == 'create':
        SkillTier.objects.create(
            name=request.data.get('name'),
            order=request.data.get('order', 0),
            badge_class=request.data.get('badge_class'),
            hex_color=request.data.get('hex_color')
        )
    elif action == 'delete':
        tier_id = request.data.get('tier_id')
        SkillTier.objects.filter(id=tier_id).delete()

    return Response({'success': True})
