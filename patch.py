import re
import os

with open("common/loaders.py", "r") as f:
    content = f.read()

# Replace the data/access_log.jsonl path with os.environ.get
content = re.sub(
    r"with open\(os\.path\.join\(os\.path\.dirname\(__file__\), '\.\.', 'data', 'access_log\.jsonl'\), 'a'\) as logf:",
    r"""log_path = os.environ.get('ACCESS_LOG_PATH', os.path.join(os.path.dirname(__file__), '..', 'data', 'access_log.jsonl'))
            with open(log_path, 'a') as logf:""",
    content
)

# Now inject the DEV logging before if allow_test:
azure_dev_log = r"""        import datetime
        import inspect
        import json
        import os
        caller = inspect.stack()[1].function if len(inspect.stack()) > 1 else 'unknown'
        log_path = os.environ.get('ACCESS_LOG_PATH', os.path.join(os.path.dirname(__file__), '..', 'data', 'access_log.jsonl'))
        log_entry_dev = json.dumps({'timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'function': 'load_and_split (Azure)', 'caller': caller, 'split': 'DEV'})
        with open(log_path, 'a') as logf:
            logf.write(log_entry_dev + '\n')
            
        if allow_test:"""

content = re.sub(
    r"        if allow_test:\n            import datetime\n            import inspect\n            import json\n            caller = inspect.stack\(\)\[1\].function if len\(inspect.stack\(\)\) > 1 else 'unknown'\n            log_entry = json.dumps\(\{'timestamp': datetime.datetime.now\(datetime.timezone.utc\).isoformat\(\), 'function': 'load_and_split \(Azure\)', 'caller': caller, 'split': 'TEST'\}\)",
    azure_dev_log + r"""
            log_entry = json.dumps({'timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'function': 'load_and_split (Azure)', 'caller': caller, 'split': 'TEST'})""",
    content
)

wsdream_dev_log = r"""        import datetime
        import inspect
        import json
        import os
        caller = inspect.stack()[1].function if len(inspect.stack()) > 1 else 'unknown'
        log_path = os.environ.get('ACCESS_LOG_PATH', os.path.join(os.path.dirname(__file__), '..', 'data', 'access_log.jsonl'))
        log_entry_dev = json.dumps({'timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'function': 'load_and_split (WS-DREAM)', 'caller': caller, 'split': 'DEV'})
        with open(log_path, 'a') as logf:
            logf.write(log_entry_dev + '\n')
            
        if allow_test:"""

content = re.sub(
    r"        if allow_test:\n            import datetime\n            import inspect\n            import json\n            caller = inspect.stack\(\)\[1\].function if len\(inspect.stack\(\)\) > 1 else 'unknown'\n            log_entry = json.dumps\(\{'timestamp': datetime.datetime.now\(datetime.timezone.utc\).isoformat\(\), 'function': 'load_and_split \(WS-DREAM\)', 'caller': caller, 'split': 'TEST'\}\)",
    wsdream_dev_log + r"""
            log_entry = json.dumps({'timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'function': 'load_and_split (WS-DREAM)', 'caller': caller, 'split': 'TEST'})""",
    content
)

with open("common/loaders.py", "w") as f:
    f.write(content)

print("Patch applied using regex.")
