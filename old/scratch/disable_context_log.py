with open('nicegui_screens/certificate_screen.py', 'r', encoding='utf-8') as f:
    content = f.read()

import re

# Find print_certificate_context definition and clean it up
pattern = r'    @staticmethod\s+def print_certificate_context\(ctx: dict\) -> None:.*?(?=    def generate_docx)'
replacement = '''    @staticmethod
    def print_certificate_context(ctx: dict) -> None:
        """Verbose context logging disabled."""
        pass

'''

new_content = re.sub(pattern, replacement, content, flags=re.DOTALL)

# Remove call to self.print_certificate_context(ctx) inside generate_docx
new_content = new_content.replace("self.print_certificate_context(ctx)", "# self.print_certificate_context(ctx)")

with open('nicegui_screens/certificate_screen.py', 'w', encoding='utf-8') as f:
    f.write(new_content)

print("Context logging disabled successfully.")
