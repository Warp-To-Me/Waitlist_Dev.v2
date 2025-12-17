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

DANGEROUS_KEYWORDS = ['delete', 'reset', 'flush', 'cleanup', 'wipe', 'remove', 'purge', 'backfill']

class ScriptManager:
    @staticmethod
    def get_available_scripts():
        """
        Scans installed local apps for management commands.
        Restricts to 'core', 'esi_calls', 'pilot_data' and 'waitlist_data' for safety/relevance.
        """
        target_apps = ['core', 'esi_calls', 'pilot_data', 'waitlist_data']
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
                        
                        try:
                            module = importlib.import_module(f"{app_name}.management.commands.{cmd_name}")
                            cmd_class = getattr(module, 'Command', None)
                            
                            # Inspect Command
                            help_text = getattr(cmd_class, 'help', 'No description available.')
                            
                            # Detect Danger
                            is_dangerous = any(k in cmd_name.lower() for k in DANGEROUS_KEYWORDS)
                            if not is_dangerous and help_text:
                                is_dangerous = any(k in help_text.lower() for k in DANGEROUS_KEYWORDS)

                            # Parse Arguments
                            args_list = []
                            try:
                                cmd_instance = cmd_class()
                                # create_parser returns an ArgumentParser
                                parser = cmd_instance.create_parser('manage.py', cmd_name)
                                for action in parser._actions:
                                    # Filter out default help/version/verbosity flags to keep it clean
                                    if action.dest in ['help', 'version', 'verbosity', 'settings', 'pythonpath', 'traceback', 'no_color', 'force_color', 'skip_checks']:
                                        continue
                                    
                                    # Format: --name (help)
                                    opts = '/'.join(action.option_strings)
                                    if not opts:
                                        opts = action.dest # Positional arg
                                    
                                    args_list.append({
                                        'name': opts,
                                        'help': action.help,
                                        'default': action.default if action.default is not None else ''
                                    })
                            except Exception as parse_err:
                                # Fallback if instantiation fails
                                args_list = [{'name': 'Error', 'help': f'Could not parse args: {parse_err}'}]

                            scripts.append({
                                'name': cmd_name,
                                'app': app_name,
                                'help': help_text,
                                'is_dangerous': is_dangerous,
                                'arguments': args_list
                            })
                        except Exception as e:
                            # Error loading module
                            scripts.append({
                                'name': cmd_name,
                                'app': app_name,
                                'help': f"Could not load: {e}",
                                'is_dangerous': False,
                                'arguments': []
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
        pass

    @staticmethod
    def _update_script_status(script_id, status, return_code=None):
        data = cache.get(f"script:{script_id}:data")
        if data:
            data['status'] = status
            if return_code is not None:
                data['return_code'] = return_code
            cache.set(f"script:{script_id}:data", data, timeout=CACHE_TIMEOUT)

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
                os.kill(pid, 15) # SIGTERM
                ScriptManager._update_script_status(script_id, 'stopping')
                return True
            except ProcessLookupError:
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
                pass
                
        if len(cleaned_ids) != len(active_ids):
             cache.set(CACHE_KEY_ACTIVE_SET, cleaned_ids, timeout=None)
             
        return sorted(results, key=lambda x: x['start_time'], reverse=True)

    @staticmethod
    def get_script_logs(script_id):
        return cache.get(f"script:{script_id}:logs") or []

    @staticmethod
    def _monitor_process(script_id, process):
        channel_layer = get_channel_layer()
        group_name = f"script_{script_id}"
        
        for line in iter(process.stdout.readline, ''):
            if not line:
                break
            
            line_stripped = line.rstrip()
            
            # Efficient Append (RMW)
            current_logs = cache.get(f"script:{script_id}:logs") or []
            current_logs.append(line_stripped)
            if len(current_logs) > LOG_retention:
                current_logs = current_logs[-LOG_retention:]
            cache.set(f"script:{script_id}:logs", current_logs, timeout=CACHE_TIMEOUT)
            
            async_to_sync(channel_layer.group_send)(
                group_name,
                {
                    'type': 'log_message',
                    'message': line_stripped
                }
            )

        process.wait()
        return_code = process.returncode

        final_msg = f"--- Process exited with code {return_code} ---"
        
        current_logs = cache.get(f"script:{script_id}:logs") or []
        current_logs.append(final_msg)
        cache.set(f"script:{script_id}:logs", current_logs, timeout=CACHE_TIMEOUT)
        
        ScriptManager._update_script_status(script_id, 'completed' if return_code == 0 else 'failed', return_code)

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
