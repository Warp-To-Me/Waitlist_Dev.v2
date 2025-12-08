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

class ComparisonCache:
    """
    Helper to bulk fetch data needed for comparisons to avoid N+1 queries.
    """
    def __init__(self, doctrine_items, pilot_items):
        # Collect all Item IDs and Group IDs involved
        all_items = list(doctrine_items) + list(pilot_items)
        self.item_ids = [i.type_id for i in all_items if i]
        self.group_ids = list(set([i.group_id for i in all_items if i]))

        # 1. Bulk Fetch Rules
        self.rules_map = defaultdict(list)
        if self.group_ids:
            rules = FitAnalysisRule.objects.filter(
                group_id__in=self.group_ids
            ).select_related('attribute')
            
            for r in rules:
                self.rules_map[r.group_id].append(r)

        # 2. Bulk Fetch Attributes
        self.attr_map = defaultdict(dict)
        
        relevant_attr_ids = set()
        for r_list in self.rules_map.values():
            for r in r_list:
                relevant_attr_ids.add(r.attribute_id)
        
        if relevant_attr_ids and self.item_ids:
            attrs = TypeAttribute.objects.filter(
                item_id__in=self.item_ids,
                attribute_id__in=relevant_attr_ids
            )
            for a in attrs:
                self.attr_map[a.item_id][a.attribute_id] = a.value

    def get_rules(self, group_id):
        return self.rules_map.get(group_id, [])

    def get_attributes(self, item_id):
        return self.attr_map.get(item_id, {})


class FitComparator:
    @staticmethod
    def compare_items(doctrine_item, pilot_item, cache):
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
            return result

        # 3. Get Rules from Cache
        rules = cache.get_rules(doctrine_item.group_id)
        
        if not rules:
            result['status'] = ComparisonStatus.SIDEGRADE
            return result

        # 4. Compare Attributes using Cache
        doc_attrs = cache.get_attributes(doctrine_item.type_id)
        pilot_attrs = cache.get_attributes(pilot_item.type_id)

        all_passed = True
        has_upgrade = False
        
        for rule in rules:
            attr_id = rule.attribute.attribute_id
            doc_val = doc_attrs.get(attr_id, 0.0)
            pilot_val = pilot_attrs.get(attr_id, 0.0)
            
            if doc_val == 0 and pilot_val == 0: continue

            # Calculate Diff %
            if doc_val == 0:
                diff_pct = 100.0 if pilot_val > 0 else 0.0
            else:
                diff_pct = ((pilot_val - doc_val) / abs(doc_val)) * 100.0

            is_pass = False

            if rule.comparison_logic == 'match':
                is_pass = abs(doc_val - pilot_val) < 0.01
            elif rule.comparison_logic == 'higher':
                if diff_pct >= -rule.tolerance_percent:
                    is_pass = True
                    if diff_pct > 0.1: has_upgrade = True
                else:
                    is_pass = False
            elif rule.comparison_logic == 'lower':
                if diff_pct <= rule.tolerance_percent:
                    is_pass = True
                    if diff_pct < -0.1: has_upgrade = True
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

        if all_passed:
            result['status'] = ComparisonStatus.UPGRADE if has_upgrade else ComparisonStatus.SIDEGRADE
        else:
            result['status'] = ComparisonStatus.DOWNGRADE

        return result


class SmartFitMatcher:
    def __init__(self, parser_result):
        self.parser = parser_result
        self.hull = parser_result.hull_obj
        # List of {'name', 'quantity', 'obj'}
        self.pilot_items_raw = parser_result.items 

    def find_best_match(self):
        print(f"DEBUG: SmartFitMatcher looking for hull: {self.hull.type_name} (ID: {self.hull.type_id})")

        # 1. Primary: Try matching by specific ItemType ID
        candidates = DoctrineFit.objects.filter(ship_type=self.hull).prefetch_related('modules__item_type')
        
        # 2. Fallback: Try matching by Exact Name
        if not candidates.exists():
            print(f"DEBUG: ID match failed. Trying Exact Name: {self.hull.type_name}")
            candidates = DoctrineFit.objects.filter(
                ship_type__type_name__iexact=self.hull.type_name
            ).prefetch_related('modules__item_type')

        # 3. Last Resort: Try 'Contains' Name (Handles "Kronos" vs "Kronos ")
        if not candidates.exists():
            print(f"DEBUG: Exact Name match failed. Trying Contains: {self.hull.type_name}")
            candidates = DoctrineFit.objects.filter(
                ship_type__type_name__icontains=self.hull.type_name
            ).prefetch_related('modules__item_type')

        if not candidates.exists():
            print(f"DEBUG: No candidates found. Aborting.")
            # Debug: what DOES exist?
            exists = DoctrineFit.objects.filter(ship_type__type_name__icontains="Kronos").count()
            print(f"DEBUG: Total 'Kronos' fits in DB: {exists}")
            return None, None

        best_fit = None
        best_score = -99999
        best_analysis = None

        # --- PRE-FETCH OPTIMIZATION ---
        all_doc_items = set()
        for fit in candidates:
            for mod in fit.modules.all():
                all_doc_items.add(mod.item_type)
        
        pilot_item_objs = [x['obj'] for x in self.pilot_items_raw if x['obj']]
        
        cache = ComparisonCache(all_doc_items, pilot_item_objs)

        # 3. Score
        for fit in candidates:
            score, analysis = self._score_fit(fit, cache)
            if score > best_score:
                best_score = score
                best_fit = fit
                best_analysis = analysis

        return best_fit, best_analysis

    def _score_fit(self, doctrine_fit, cache=None):
        score = 0
        analysis = [] 

        if not cache:
            doc_items = [m.item_type for m in doctrine_fit.modules.all()]
            pilot_items = [x['obj'] for x in self.pilot_items_raw if x['obj']]
            cache = ComparisonCache(doc_items, pilot_items)

        doctrine_checklist = []
        for mod in doctrine_fit.modules.all():
            for _ in range(mod.quantity):
                doctrine_checklist.append({
                    'item': mod.item_type,
                    'slot': mod.slot
                })

        pilot_inventory = []
        for p_item in self.pilot_items_raw:
            for _ in range(p_item['quantity']):
                pilot_inventory.append(p_item['obj'])

        for req in doctrine_checklist:
            doc_item = req['item']
            
            best_idx = -1
            
            # First pass: Look for Exact
            for idx, p_item in enumerate(pilot_inventory):
                if p_item.type_id == doc_item.type_id:
                    best_idx = idx
                    break
            
            # Second pass: If no exact, find ANY group match
            if best_idx == -1:
                for idx, p_item in enumerate(pilot_inventory):
                    if p_item.group_id == doc_item.group_id:
                        best_idx = idx
                        break 
            
            if best_idx != -1:
                pilot_item = pilot_inventory.pop(best_idx)
                comp = FitComparator.compare_items(doc_item, pilot_item, cache)
                
                if comp['status'] == ComparisonStatus.MATCH: score += 10
                elif comp['status'] == ComparisonStatus.UPGRADE: score += 8
                elif comp['status'] == ComparisonStatus.SIDEGRADE: score += 5
                elif comp['status'] == ComparisonStatus.DOWNGRADE: score -= 5
                else: score -= 2
                
                analysis.append({
                    'slot': req['slot'],
                    'doctrine_item': doc_item,
                    'pilot_item': pilot_item,
                    'status': comp['status'],
                    'diffs': comp['diffs']
                })
            else:
                score -= 10
                analysis.append({
                    'slot': req['slot'],
                    'doctrine_item': doc_item,
                    'pilot_item': None,
                    'status': ComparisonStatus.MISSING,
                    'diffs': []
                })

        for extra in pilot_inventory:
            analysis.append({
                'slot': 'cargo',
                'doctrine_item': None,
                'pilot_item': extra,
                'status': ComparisonStatus.EXTRA,
                'diffs': []
            })

        return score, analysis