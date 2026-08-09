import os
import re

for root, _, files in os.walk('f:/CR_PY/certificate_manager/nicegui_screens'):
    for f in files:
        if f.endswith('.py'):
            path = os.path.join(root, f)
            with open(path, 'r', encoding='utf-8') as file:
                content = file.read()
            
            # Simple global replace of print with log.warning for now to silence terminal
            new_content = re.sub(
                r'print\((f?\"\[[^\]]+\] .*?\")\)', 
                r'log.warning(\1)', 
                content
            )
            new_content = re.sub(
                r'print\((f?\"Error .*?\")\)', 
                r'log.error(\1)', 
                new_content
            )
            new_content = re.sub(
                r'print\((f?\"Failed .*?\")\)', 
                r'log.error(\1)', 
                new_content
            )
            new_content = re.sub(
                r'print\((f?\"Warning: .*?\")\)', 
                r'log.warning(\1)', 
                new_content
            )
            new_content = re.sub(
                r'print\((f?\"Async search error: .*?\")\)', 
                r'log.error(\1)', 
                new_content
            )
            if ('log.warning' in new_content or 'log.error' in new_content) and 'import logging' not in new_content:
                # Add logging import at the top after imports
                new_content = 'import logging\nlog = logging.getLogger(__name__)\n\n' + new_content
            
            if new_content != content:
                with open(path, 'w', encoding='utf-8') as file:
                    file.write(new_content)
                print(f'Cleaned up {f}')
