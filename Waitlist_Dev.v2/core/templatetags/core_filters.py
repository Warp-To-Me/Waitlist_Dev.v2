from django import template

register = template.Library()

@register.filter(name='split_actions')
def split_actions(value):
    """
    Parses a string like "key|Label|Icon,key2|Label2|Icon2" into a list of lists.
    Usage: {% for action, label, icon in "key|Lbl|Ic,..."|split_actions %}
    """
    if not value:
        return []
    
    result = []
    # Split by comma first
    items = value.split(',')
    for item in items:
        # Split each item by pipe
        parts = item.split('|')
        # Ensure we have exactly 3 parts (Action, Label, Icon)
        if len(parts) == 3:
            result.append([p.strip() for p in parts])
            
    return result