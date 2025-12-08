from collections import defaultdict
from pilot_data.models import ItemType, TypeAttribute, FitAnalysisRule
from waitlist_data.models import DoctrineFit

class ComparisonStatus:
    MATCH = "MATCH"
    UPGRADE = "UPGRADE"
    DOWNGRADE = "DOWNGRADE"
    SIDEGRADE = "SIDEGRADE"
    MISSING = "MISSING"
    EXTRA = "EXTRA"
    UNKNOWN = "UNKNOWN"

class FitComparator:
    """
    Compares two items (Pilot's Item vs Doctrine Item) based on database Rules.
    """
    
    @staticmethod
    def compare_items(doctrine_item, pilot_item):
        """
        Returns: {
            'status': ComparisonStatus,
            'diffs': [ {'attr': 'Thermal Res', 'value': 20, 'target': 25, 'diff': -5, 'pass': False} ]
        }
        """
        result = {
            'status': ComparisonStatus.UNKNOWN,
            'diffs': []
        }

        # 1. Exact Match Check
        if doctrine_item.type_id == pilot_item.type_id:
            result['status'] = ComparisonStatus.MATCH
            return result

        # 2. Group Check (Sanity)
        if doctrine_item.group_id != pilot_item.group_id:
            # Totally different items (e.g. Shield Booster vs Armor Plate)
            # We treat this as a mismatch, likely user error or empty slot
            result['status'] = ComparisonStatus.UNKNOWN
            return result

        # 3. Fetch Rules for this Group
        rules = FitAnalysisRule.objects.filter(group_id=doctrine_item.group_id).select_related('attribute')
        
        # If no rules exist, we can only check exact match (which failed above).
        # We default to SIDEGRADE to give benefit of doubt if it's same group.
        if not rules.exists():
            result['status'] = ComparisonStatus.SIDEGRADE
            result['note'] = "No analysis rules defined for this item group."
            return result

        # 4. Compare Attributes
        # Bulk fetch attributes for both items
        required_attr_ids = [r.attribute_id for r in rules]
        
        # Helper to fetch values
        def get_attr_map(item, attr_ids):
            attrs = TypeAttribute.objects.filter(item=item, attribute_id__in=attr_ids)
            return {a.attribute_id: a.value for a in attrs}

        doc_attrs = get_attr_map(doctrine_item, required_attr_ids)
        pilot_attrs = get_attr_map(pilot_item, required_attr_ids)

        all_passed = True
        has_upgrade = False
        
        for rule in rules:
            attr_id = rule.attribute.attribute_id
            doc_val = doc_attrs.get(attr_id, 0.0)
            pilot_val = pilot_attrs.get(attr_id, 0.0)
            
            # Skip if irrelevant (e.g. comparing CPU on items that use none)
            if doc_val == 0 and pilot_val == 0:
                continue

            # Calculate Difference %
            # Avoid division by zero
            if doc_val == 0:
                diff_pct = 100.0 if pilot_val > 0 else 0.0
            else:
                diff_pct = ((pilot_val - doc_val) / abs(doc_val)) * 100.0

            is_pass = False
            rule_status = "NEUTRAL"

            if rule.comparison_logic == 'match':
                is_pass = abs(doc_val - pilot_val) < 0.01
            
            elif rule.comparison_logic == 'higher':
                # Pass if Pilot >= Doctrine (minus tolerance)
                # e.g. Tolerance 10%. Doc=100. Pilot=91. Diff=-9%. Pass.
                if diff_pct >= -rule.tolerance_percent:
                    is_pass = True
                    if diff_pct > 0: has_upgrade = True
                else:
                    is_pass = False

            elif rule.comparison_logic == 'lower':
                # Pass if Pilot <= Doctrine (plus tolerance)
                # e.g. CPU Usage. Lower is better.
                # Doc=100. Pilot=105. Diff=+5%. Tolerance=10%. Pass.
                if diff_pct <= rule.tolerance_percent:
                    is_pass = True
                    if diff_pct < 0: has_upgrade = True
                else:
                    is_pass = False

            if not is_pass:
                all_passed = False

            result['diffs'].append({
                'attribute': rule.attribute.display_name or rule.attribute.name,
                'doctrine_val': doc_val,
                'pilot_val': pilot_val,
                'diff_pct': round(diff_pct, 1),
                'is_pass': is_pass,
                'logic': rule.comparison_logic
            })

        # 5. Determine Final Status
        if all_passed:
            result['status'] = ComparisonStatus.UPGRADE if has_upgrade else ComparisonStatus.SIDEGRADE
        else:
            result['status'] = ComparisonStatus.DOWNGRADE

        return result


class SmartFitMatcher:
    """
    Matches a parsed fit against all DoctrineFits for the given hull.
    """

    def __init__(self, parser_result):
        self.parser = parser_result
        self.hull = parser_result.hull_obj
        self.pilot_items = parser_result.items # List of {'name', 'quantity', 'obj'}

    def find_best_match(self):
        """
        Returns tuple: (BestDoctrineFit, MatchDetails)
        MatchDetails contains the slot-by-slot comparison for the UI.
        """
        candidates = DoctrineFit.objects.filter(ship_type=self.hull)
        
        if not candidates.exists():
            return None, None

        best_fit = None
        best_score = -9999
        best_analysis = None

        for fit in candidates:
            score, analysis = self._score_fit(fit)
            if score > best_score:
                best_score = score
                best_fit = fit
                best_analysis = analysis

        return best_fit, best_analysis

    def _score_fit(self, doctrine_fit):
        """
        Scoring Logic:
        Exact Match: +10
        Upgrade: +8
        Sidegrade: +5
        Downgrade: -5
        Missing: -10
        """
        score = 0
        analysis = [] # List of comparison results for display

        # 1. Flatten Doctrine Modules into a checklist
        # We need to handle quantities. If doctrine has 2x Heat Sinks, we need to find 2x Heat Sinks.
        doctrine_checklist = []
        for mod in doctrine_fit.modules.all():
            for _ in range(mod.quantity):
                doctrine_checklist.append({
                    'item': mod.item_type,
                    'slot': mod.slot
                })

        # 2. Flatten Pilot Items (Mutable copy)
        pilot_inventory = []
        for p_item in self.pilot_items:
            for _ in range(p_item['quantity']):
                pilot_inventory.append(p_item['obj'])

        # 3. Matching Process
        # We iterate doctrine items and try to find the "best" match in pilot inventory
        
        for req in doctrine_checklist:
            doc_item = req['item']
            
            # Find candidate in pilot inventory
            # Priority: Exact ID > Same Group > Anything
            
            match_idx = -1
            match_quality = -1 # 0=Group, 1=Exact
            
            for idx, p_item in enumerate(pilot_inventory):
                if p_item.type_id == doc_item.type_id:
                    match_idx = idx
                    match_quality = 1
                    break # Found exact
                elif p_item.group_id == doc_item.group_id and match_idx == -1:
                    match_idx = idx
                    match_quality = 0
                    # Don't break, keep looking for exact
            
            if match_idx != -1:
                # We found a corresponding item
                pilot_item = pilot_inventory.pop(match_idx)
                
                # Run Comparison
                comp = FitComparator.compare_items(doc_item, pilot_item)
                
                # Apply Score
                if comp['status'] == ComparisonStatus.MATCH:
                    score += 10
                elif comp['status'] == ComparisonStatus.UPGRADE:
                    score += 8
                elif comp['status'] == ComparisonStatus.SIDEGRADE:
                    score += 5
                elif comp['status'] == ComparisonStatus.DOWNGRADE:
                    score -= 5
                else:
                    score -= 2 # Unknown match
                
                analysis.append({
                    'slot': req['slot'],
                    'doctrine_item': doc_item,
                    'pilot_item': pilot_item,
                    'status': comp['status'],
                    'diffs': comp['diffs']
                })
            else:
                # Missing Item
                score -= 10
                analysis.append({
                    'slot': req['slot'],
                    'doctrine_item': doc_item,
                    'pilot_item': None,
                    'status': ComparisonStatus.MISSING,
                    'diffs': []
                })

        # 4. Check for Extra Items (Pilot has stuff not in doctrine)
        # Usually fine, but maybe penalty for weird stuff?
        # For now, we ignore extra items in scoring, but listing them might be good.
        for extra in pilot_inventory:
            analysis.append({
                'slot': 'cargo', # Don't know slot
                'doctrine_item': None,
                'pilot_item': extra,
                'status': ComparisonStatus.EXTRA,
                'diffs': []
            })

        return score, analysis