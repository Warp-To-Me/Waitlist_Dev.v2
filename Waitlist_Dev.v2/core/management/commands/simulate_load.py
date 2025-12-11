import time
import random
import threading
import requests
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.conf import settings
from django.utils import timezone
from importlib import import_module

from pilot_data.models import EveCharacter, ItemType
from waitlist_data.models import Fleet, DoctrineFit, WaitlistEntry

class Command(BaseCommand):
    help = 'Simulates concurrent user traffic (Browsing and X-Up).'

    def add_arguments(self, parser):
        parser.add_argument('--users', type=int, default=5, help='Number of concurrent users to simulate')
        parser.add_argument('--url', type=str, default='http://127.0.0.1:8000', help='Base URL of the running server')
        parser.add_argument('--loops', type=int, default=10, help='Number of actions per user before exiting')

    def handle(self, *args, **options):
        num_users = options['users']
        base_url = options['url'].rstrip('/')
        loops = options['loops']

        self.stdout.write(self.style.HTTP_INFO(f"Initializing Load Simulation: {num_users} users, {loops} loops each..."))

        # 1. Prerequisite Checks
        active_fleet = Fleet.objects.filter(is_active=True).first()
        if not active_fleet:
            self.stdout.write(self.style.ERROR("No active fleet found! Please create a fleet first."))
            return

        fits = list(DoctrineFit.objects.filter(is_doctrinal=True))
        if not fits:
            self.stdout.write(self.style.ERROR("No doctrine fits found! Please import some doctrines."))
            return

        # 2. Prepare Simulation Users
        sim_users = self.setup_users(num_users)
        
        # 3. Start Threads
        threads = []
        for i, (user, char) in enumerate(sim_users):
            t = threading.Thread(target=self.user_loop, args=(i, user, char, base_url, active_fleet, fits, loops))
            threads.append(t)
            t.start()
            # Stagger starts slightly
            time.sleep(random.uniform(0.5, 2.0))

        # 4. Wait
        for t in threads:
            t.join()

        self.stdout.write(self.style.SUCCESS("Simulation Complete."))

    def setup_users(self, count):
        """
        Creates or retrieves simulation users and ensures they have characters.
        """
        users = []
        for i in range(1, count + 1):
            username = f"sim_user_{i}"
            user, created = User.objects.get_or_create(username=username)
            if created:
                user.set_password('password')
                user.save()
            
            # Ensure Character
            char, char_created = EveCharacter.objects.get_or_create(
                character_id=90000000 + i, # Fake IDs
                defaults={
                    'user': user,
                    'character_name': f"Sim Pilot {i}",
                    'is_main': True,
                    'corporation_name': "Simulation Corp"
                }
            )
            
            users.append((user, char))
        return users

    def create_session_cookie(self, user):
        """
        Manually creates a Django session for the user to bypass SSO login.
        """
        engine = import_module(settings.SESSION_ENGINE)
        session = engine.SessionStore()
        session['_auth_user_id'] = str(user.pk)
        session['_auth_user_backend'] = 'django.contrib.auth.backends.ModelBackend'
        session['_auth_user_hash'] = user.get_session_auth_hash()
        session['active_char_id'] = 90000000 + int(user.username.split('_')[-1]) # Match the ID logic
        session.save()
        return session.session_key

    def user_loop(self, index, user, char, base_url, fleet, fits, loops):
        """
        The main behavior loop for a single simulated user.
        """
        # Create authenticated session
        session = requests.Session()
        session_key = self.create_session_cookie(user)
        session.cookies.set(settings.SESSION_COOKIE_NAME, session_key)
        
        # Initial GET to grab CSRF Token
        try:
            r = session.get(f"{base_url}/")
            if 'csrftoken' in session.cookies:
                csrf_token = session.cookies['csrftoken']
            else:
                self.stdout.write(self.style.WARNING(f"[User {index}] Failed to get CSRF token"))
                return
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"[User {index}] Connection failed: {e}"))
            return

        self.stdout.write(f"[User {index}] Logged in as {char.character_name}")

        for i in range(loops):
            action = random.choice(['browse', 'browse', 'x_up']) # 33% chance to X-up
            
            if action == 'browse':
                page = random.choice([
                    f"/fleet/{fleet.join_token}/dashboard/",
                    "/doctrines/",
                    f"/fleet/{fleet.join_token}/history/"
                ])
                try:
                    start = time.time()
                    resp = session.get(f"{base_url}{page}")
                    duration = round(time.time() - start, 2)
                    status = resp.status_code
                    self.stdout.write(f"  [User {index}] GET {page} - {status} ({duration}s)")
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"  [User {index}] Request Error: {e}"))

            elif action == 'x_up':
                # Check if already x-ed up to avoid spamming duplicates if not intended
                # But request asked to simulate load, so spamming fits is okay.
                
                # Logic: Randomly choose 1 to 3 fits to paste at once
                num_fits = random.randint(1, 3)
                selected_fits = random.sample(fits, min(len(fits), num_fits))
                
                paste_text = ""
                fit_names = []
                for fit in selected_fits:
                    paste_text += fit.eft_format + "\n\n"
                    fit_names.append(fit.name)
                
                payload = {
                    'character_id': char.character_id,
                    'eft_paste': paste_text
                }
                
                headers = {'X-CSRFToken': csrf_token, 'Referer': f"{base_url}/fleet/{fleet.join_token}/dashboard/"}
                
                try:
                    start = time.time()
                    resp = session.post(
                        f"{base_url}/fleet/{fleet.join_token}/xup/",
                        data=payload,
                        headers=headers
                    )
                    duration = round(time.time() - start, 2)
                    
                    if resp.status_code == 200 and resp.json().get('success'):
                        self.stdout.write(self.style.SUCCESS(f"  [User {index}] X-UP {', '.join(fit_names)} - OK ({duration}s)"))
                    else:
                        err = resp.json().get('error') if resp.headers.get('content-type') == 'application/json' else resp.status_code
                        self.stdout.write(self.style.WARNING(f"  [User {index}] X-UP Failed: {err}"))
                        
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"  [User {index}] POST Error: {e}"))

            # Sleep between actions
            time.sleep(random.uniform(2.0, 5.0))