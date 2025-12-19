# Mapping of Programs/Actions to automated logic and steps.
# Logic is processed in views_command.py

WORKFLOW_STEPS = [
    'Action Mail',
    'Waitlist',
    'Discord',
    'Forums',
    'Teamspeak',
    'Tracker',
    'Mailing Lists',
    'WTM Channels',
    'Google Drive'
]

# Defines the automated role changes for the "Waitlist" step.
# Keys are (Program, Action).
# Values are lists of tuples: (ActionType, RoleName/Description)
# ActionType: 'add', 'remove', 'clear_all'
WORKFLOW_RULES = {
    ('Resident', 'Confirmed'): [
        ('add', 'Resident')
    ],
    ('Resident', 'Removal-CC'): [
        ('remove', 'Resident'),
        ('remove', 'Line Commander'),
        ('remove', 'Training FC'),
        ('remove', 'Fleet Commander'),
        ('remove', 'Training CT'),
        ('remove', 'Certified Trainer'),
        ('remove', 'Officer'),
        ('remove', 'Leadership'),
        # "Set Community Member" is implied by removing staff roles but keeping account active.
    ],
    # LC
    ('LC', 'Confirmed'): [
        ('add', 'Line Commander'),
        ('remove', 'Resident')
    ],
    ('LC', 'Removal-CC'): [
        ('remove', 'Line Commander')
    ],
    # TFC
    ('TFC', 'Confirmed'): [
        ('add', 'Training FC'),
        ('remove', 'Line Commander')
    ],
    ('TFC', 'Demotion'): [
        ('remove', 'Training FC'),
        ('add', 'Line Commander')
    ],
    ('TFC', 'Removal-CC'): [
        ('remove', 'Training FC')
    ],
    # FC
    ('FC', 'Confirmed'): [
        ('add', 'Fleet Commander'),
        ('remove', 'Training FC')
    ],
    ('FC', 'Demotion'): [
        ('remove', 'Fleet Commander'),
        ('add', 'Line Commander') # "Remove FC/Add LC"
    ],
    ('FC', 'Removal-CC'): [
        ('remove', 'Fleet Commander')
    ],
    # Training CT
    ('Training CT', 'Confirmed'): [
        ('add', 'Training CT')
    ],
    ('Training CT', 'Demotion'): [
        ('remove', 'Training CT')
    ],
    # Certified Trainer
    ('Certified Trainer', 'Confirmed'): [
        ('add', 'Certified Trainer'),
        ('remove', 'Training CT')
    ],
    ('Certified Trainer', 'Demotion'): [
        ('remove', 'Certified Trainer')
    ],
    # Leadership/Officer
    ('Officer', 'Confirmed'): [
        ('add', 'Officer')
    ],
    ('Officer', 'Demotion'): [
        ('remove', 'Officer')
    ],
    ('Leadership', 'Confirmed'): [
        ('add', 'Leadership')
    ],
    ('Leadership', 'Demotion'): [
        ('remove', 'Leadership')
    ],
    
    # Line Pilot - Bans
    ('Line Pilot', 'Park'): [
        ('ban', 'Ban with Comment')
    ],
    ('Line Pilot', 'Un-Park'): [
        ('unban', 'Remove Ban')
    ],
    ('Line Pilot', 'Ban'): [
        ('ban', 'Ban with Comment')
    ]
}

# Explicit "Deactivate account" handling for "Removal-CC" actions across the board?
# The CSV says "Deactivate account" for Resident, LC, TFC, FC in 'Removal-CC'.
# My interpretation in the plan was: "Remove all roles except Public".
# I'll implement a helper in the view to check for 'Removal-CC' specifically if it needs 'clear_all'.
# But based on the specific "Waitlist" column text "Remove Commander/LC", "Remove R", it seems granular.
# However, the user said: "deactivate account ... should remove all roles except "Public" in this new waitlist."
# So I will add a special rule for 'Removal-CC' actions in the View logic to enforcing clearing,
# OR I can map them here.
# Let's map them explicitly here to be safe and data-driven.

WORKFLOW_RULES[('Resident', 'Removal-CC')] = [('clear_all', None)]
WORKFLOW_RULES[('LC', 'Removal-CC')] = [('clear_all', None)]
WORKFLOW_RULES[('TFC', 'Removal-CC')] = [('clear_all', None)]
WORKFLOW_RULES[('FC', 'Removal-CC')] = [('clear_all', None)]
