from collections import defaultdict
from django.db import models  # <--- Added import
from pilot_data.models import ItemType, TypeAttribute, CharacterSkill
from waitlist_data.models import SkillRequirement, SkillTier

# EVE Dogma Attributes for Skill Requirements
SKILL_ATTRS = {
    182: 277,   # requiredSkill1 -> Level
    183: 278,
    184: 279,
    1285: 1286,
    1289: 1287,
    1290: 1288
}

def check_pilot_skills(character, parser_result, doctrine_fit=None):
    """
    Checks pilot skills against Minimum requirements and Tiers.
    
    Returns:
        tuple(can_fly (bool), missing_skills (list), met_tier (SkillTier|None))
    """
    
    # 1. Identify all items in the fit
    item_ids = set()
    if parser_result.hull_obj:
        item_ids.add(parser_result.hull_obj.type_id)
        
    for item in parser_result.items:
        if item.get('obj'):
            item_ids.add(item['obj'].type_id)
            
    if not item_ids:
        return True, [], None

    # --- STEP A: COMPILE MINIMUM REQUIREMENTS ---
    # Implicit SDE + Explicit DB Requirements where tier is None

    # Implicit SDE
    req_attr_ids = list(SKILL_ATTRS.keys()) + list(SKILL_ATTRS.values())
    attributes = TypeAttribute.objects.filter(
        item_id__in=item_ids,
        attribute_id__in=req_attr_ids
    ).values('item_id', 'attribute_id', 'value')
    
    item_attr_map = defaultdict(dict)
    for row in attributes:
        item_attr_map[row['item_id']][row['attribute_id']] = int(row['value'])
        
    min_requirements = defaultdict(int)
    for i_id in item_ids:
        attrs = item_attr_map.get(i_id, {})
        for skill_attr, level_attr in SKILL_ATTRS.items():
            skill_id = attrs.get(skill_attr)
            if skill_id:
                level = attrs.get(level_attr, 1)
                if level > min_requirements[skill_id]:
                    min_requirements[skill_id] = level

    # Explicit DB (Tier = None)
    # We query all relevant requirements first to optimize
    
    relevant_reqs = SkillRequirement.objects.select_related('skill', 'group', 'tier').prefetch_related('group__members__skill')
    
    q_filter = models.Q(hull=parser_result.hull_obj) if parser_result.hull_obj else models.Q()
    if doctrine_fit:
        q_filter |= models.Q(doctrine_fit=doctrine_fit)
    
    relevant_reqs = relevant_reqs.filter(q_filter)
    
    # Process Base
    for req in relevant_reqs:
        if req.tier is None: # Minimum
            _apply_req_to_dict(req, min_requirements)

    # --- CHECK MINIMUM ---
    # If failed, return immediately
    met_base, missing_base = _evaluate_skills(character, min_requirements)
    if not met_base:
        return False, missing_base, None

    # --- STEP B: CHECK TIERS (Descending Order) ---
    tiers = SkillTier.objects.all().order_by('-order')
    
    for tier in tiers:
        tier_reqs = defaultdict(int)
        
        # Start with minimums (assuming tiers build upon base)
        # NOTE: If tiers are completely independent sets, comment out the line below.
        # However, it's safer to assume a "Gold" pilot must also fly the ship (Base).
        tier_reqs.update(min_requirements)
        
        has_tier_rules = False
        for req in relevant_reqs:
            if req.tier_id == tier.id:
                _apply_req_to_dict(req, tier_reqs)
                has_tier_rules = True
        
        if not has_tier_rules:
            continue

        met_tier, _ = _evaluate_skills(character, tier_reqs)
        if met_tier:
            return True, [], tier

    # Met minimum, but no specific tiers
    return True, [], None

def _apply_req_to_dict(req, req_dict):
    if req.skill:
        if req.level > req_dict[req.skill.type_id]:
            req_dict[req.skill.type_id] = req.level
    if req.group:
        for member in req.group.members.all():
            if member.level > req_dict[member.skill.type_id]:
                req_dict[member.skill.type_id] = member.level

def _evaluate_skills(character, requirements):
    if not requirements:
        return True, []
        
    required_ids = list(requirements.keys())
    pilot_skills = CharacterSkill.objects.filter(
        character=character,
        skill_id__in=required_ids
    ).values('skill_id', 'active_skill_level')
    
    pilot_map = { s['skill_id']: s['active_skill_level'] for s in pilot_skills }
    
    missing = []
    # Resolve names only if missing
    missing_ids = [sid for sid in required_ids if pilot_map.get(sid, 0) < requirements[sid]]
    
    if not missing_ids:
        return True, []

    skill_names = {i.type_id: i.type_name for i in ItemType.objects.filter(type_id__in=missing_ids)}
    
    for sid in missing_ids:
        req_lvl = requirements[sid]
        have_lvl = pilot_map.get(sid, 0)
        name = skill_names.get(sid, f"Skill {sid}")
        
        romans = ["0", "I", "II", "III", "IV", "V"]
        r_req = romans[req_lvl] if req_lvl <= 5 else str(req_lvl)
        r_have = romans[have_lvl] if have_lvl <= 5 else str(have_lvl)
        
        missing.append(f"{name} {r_req} (Have {r_have})")
        
    return False, missing