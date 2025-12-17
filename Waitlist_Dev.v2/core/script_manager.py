import os
import sys
import time
import uuid
import threading
import subprocess
import logging
import importlib
from django.conf import settings
from django.apps import apps
from django.core.cache import cache
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

logger = logging.getLogger(__name__)

# Constants
CACHE_KEY_ACTIVE_SET = "scripts:active_ids"
CACHE_TIMEOUT = 3600  # 1 hour auto-expiry for stale keys
LOG_retention = 1000  # Max lines to keep in memory/cache

class ScriptManager:
    @staticmethod
    def get_available_scripts():
        """
        Scans installed local apps for management commands.
        Restricts to 'core' and 'waitlist_data' for safety/relevance.
        """
        target_apps = ['core', 'waitlist_data']
        scripts = []

        for app_name in target_apps:
            try:
                app_config = apps.get_app_config(app_name)
                path = os.path.join(app_config.path, 'management', 'commands')

                if not os.path.exists(path):
                    continue

                for filename in os.listdir(path):
                    if filename.endswith('.py') and not filename.startswith('__'):
                        cmd_name = filename[:-3]

                        # Inspect the command to get help text
                        try:
                            module = importlib.import_module(f"{app_name}.management.commands.{cmd_name}")
                            cmd_class = getattr(module, 'Command', None)
                            help_text = getattr(cmd_class, 'help', 'No description available.')
                        except Exception as e:
                            help_text = f"Could not load description: {e}"

                        scripts.append({
                            'name': cmd_name,
                            'app': app_name,
                            'help': help_text
                        })
            except LookupError:
                continue

        return sorted(scripts, key=lambda x: x['name'])

    @staticmethod
    def _add_active_script(script_id, data):
        # 1. Set individual script data
        cache.set(f"script:{script_id}:data", data, timeout=CACHE_TIMEOUT)
        cache.set(f"script:{script_id}:logs", [], timeout=CACHE_TIMEOUT)

        # 2. Add ID to active set
        active_ids = cache.get(CACHE_KEY_ACTIVE_SET) or set()
        active_ids.add(script_id)
        cache.set(CACHE_KEY_ACTIVE_SET, active_ids, timeout=None)

    @staticmethod
    def _remove_active_script(script_id):
        # We don't delete the data immediately so user can see "Completed" status
        # But we might want to mark it as not "running" in the logic
        pass

    @staticmethod
    def _update_script_status(script_id, status, return_code=None):
        data = cache.get(f"script:{script_id}:data")
        if data:
            data['status'] = status
            if return_code is not None:
                data['return_code'] = return_code
            cache.set(f"script:{script_id}:data", data, timeout=CACHE_TIMEOUT)

            # If done, remove from active set after a delay?
            # Actually, keeping it in active set allows listing "Recently Completed"
            # We can rely on a cleaner task or just let them expire.
            # Ideally, get_active_scripts should return them.

    @staticmethod
    def start_script(script_name, args_str=""):
        """
        Starts a management command in a subprocess.
        """
        # SECURITY: Validation
        allowed_scripts = [s['name'] for s in ScriptManager.get_available_scripts()]
        if script_name not in allowed_scripts:
            raise ValueError(f"Script '{script_name}' is not allowed or does not exist.")

        script_id = str(uuid.uuid4())

        # Prepare command
        cmd = [sys.executable, 'manage.py', script_name]

        # Split args
        if args_str:
            import shlex
            try:
                cmd.extend(shlex.split(args_str))
            except Exception:
                cmd.extend(args_str.split())

        try:
            # Enforce unbuffered output for real-time streaming
            env = os.environ.copy()
            env['PYTHONUNBUFFERED'] = '1'

            # Note: We cannot pickle the process object into Cache.
            # The process object only lives in the worker that spawned it.
            # To support "stop", we need a way to signal that worker or store PID.
            # Storing PID works if workers are on same machine (Docker container).

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                cwd=settings.BASE_DIR,
                env=env,
                bufsize=1
            )

            entry = {
                'id': script_id,
                'name': script_name,
                'args': args_str,
                'start_time': time.time(),
                'status': 'running',
                'pid': process.pid, # Store PID for killing
                'return_code': None
            }

            ScriptManager._add_active_script(script_id, entry)

            # Start Monitor Thread
            # This thread lives only in this worker process.
            # If this worker dies, the monitoring stops, but the subprocess might become a zombie.
            # This is a known limitation of simple spawning in Django.
            monitor = threading.Thread(
                target=ScriptManager._monitor_process,
                args=(script_id, process)
            )
            monitor.daemon = True
            monitor.start()

            return script_id

        except Exception as e:
            logger.error(f"Failed to start script {script_name}: {e}")
            raise e

    @staticmethod
    def stop_script(script_id):
        data = cache.get(f"script:{script_id}:data")
        if not data or data['status'] != 'running':
            return False

        pid = data.get('pid')
        if pid:
            try:
                # Signal the process to terminate
                # This works if we are in the same container/OS namespace
                os.kill(pid, 15) # SIGTERM

                # We update status to 'stopping'
                ScriptManager._update_script_status(script_id, 'stopping')
                return True
            except ProcessLookupError:
                # Already gone
                ScriptManager._update_script_status(script_id, 'failed', return_code=-1)
                return False
            except Exception as e:
                logger.error(f"Failed to kill script {script_id}: {e}")
                return False
        return False

    @staticmethod
    def get_active_scripts():
        active_ids = cache.get(CACHE_KEY_ACTIVE_SET) or set()
        results = []
        cleaned_ids = set()

        for sid in active_ids:
            data = cache.get(f"script:{sid}:data")
            if data:
                results.append(data)
                cleaned_ids.add(sid)
            else:
                # Expired
                pass

        # Update set if we cleaned up
        if len(cleaned_ids) != len(active_ids):
             cache.set(CACHE_KEY_ACTIVE_SET, cleaned_ids, timeout=None)

        # Sort by start time desc
        return sorted(results, key=lambda x: x['start_time'], reverse=True)

    @staticmethod
    def get_script_logs(script_id):
        return cache.get(f"script:{script_id}:logs") or []

    @staticmethod
    def _monitor_process(script_id, process):
        channel_layer = get_channel_layer()
        group_name = f"script_{script_id}"

        local_logs = []

        # Read Output
        for line in iter(process.stdout.readline, ''):
            if not line:
                break

            line_stripped = line.rstrip()
            local_logs.append(line_stripped)

            # Update Cache periodically or on every line?
            # Doing it every line is heavy for Redis.
            # But we want real-time.
            # Let's append to cache list.

            # Efficient Append:
            # We can't efficiently append to a list in Memcached/Redis via Django Cache API easily without race conditions
            # unless we use specific Redis commands.
            # For simplicity, we'll Read-Modify-Write (RMW) but it's risky for concurrency if multiple threads write.
            # Here, only ONE thread writes logs for this script_id. So RMW is safe-ish.

            current_logs = cache.get(f"script:{script_id}:logs") or []
            current_logs.append(line_stripped)
            if len(current_logs) > LOG_retention:
                current_logs = current_logs[-LOG_retention:]
            cache.set(f"script:{script_id}:logs", current_logs, timeout=CACHE_TIMEOUT)

            # Broadcast
            async_to_sync(channel_layer.group_send)(
                group_name,
                {
                    'type': 'log_message',
                    'message': line_stripped
                }
            )

        # Wait for exit
        process.wait()
        return_code = process.returncode

        final_msg = f"--- Process exited with code {return_code} ---"

        # Final Cache Update
        current_logs = cache.get(f"script:{script_id}:logs") or []
        current_logs.append(final_msg)
        cache.set(f"script:{script_id}:logs", current_logs, timeout=CACHE_TIMEOUT)

        ScriptManager._update_script_status(script_id, 'completed' if return_code == 0 else 'failed', return_code)

        # Final Broadcast
        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                'type': 'log_message',
                'message': final_msg
            }
        )

        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                'type': 'status_update',
                'status': 'completed' if return_code == 0 else 'failed'
            }
        )
