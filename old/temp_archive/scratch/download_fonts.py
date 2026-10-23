import urllib.request
import os
import re

fonts_dir = os.path.join(os.path.dirname(__file__), "..", "nicegui_ui", "fonts")
os.makedirs(fonts_dir, exist_ok=True)

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

url = 'https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700&family=Roboto:wght@400;500;700&display=swap'
req = urllib.request.Request(url, headers=headers)

try:
    css_content = urllib.request.urlopen(req).read().decode('utf-8')
    print("Successfully fetched Google Fonts CSS metadata.")
    
    # Extract woff2 URLs and font-family / font-weight info
    blocks = re.findall(r'@font-face\s*\{([^}]+)\}', css_content)
    
    downloaded_files = []
    local_css_rules = []
    
    for i, block in enumerate(blocks):
        family_match = re.search(r'font-family:\s*[\'"]?([^\'";]+)[\'"]?;', block)
        style_match = re.search(r'font-style:\s*([^\';]+);', block)
        weight_match = re.search(r'font-weight:\s*([^\';]+);', block)
        url_match = re.search(r'src:\s*url\((https://[^\)]+)\)', block)
        
        if family_match and url_match:
            fam = family_match.group(1).strip()
            style = style_match.group(1).strip() if style_match else 'normal'
            weight = weight_match.group(1).strip() if weight_match else '400'
            font_url = url_match.group(1).strip()
            
            clean_fam = fam.lower().replace(" ", "")
            filename = f"{clean_fam}-{weight}-{style}.woff2"
            filepath = os.path.join(fonts_dir, filename)
            
            print(f"Downloading {filename} from {font_url}...")
            font_data = urllib.request.urlopen(urllib.request.Request(font_url, headers=headers)).read()
            with open(filepath, 'wb') as f:
                f.write(font_data)
            
            downloaded_files.append(filename)
            
            rule = f"""@font-face {{
  font-family: '{fam}';
  font-style: {style};
  font-weight: {weight};
  font-display: swap;
  src: local('{fam}'), url('./fonts/{filename}') format('woff2');
}}"""
            local_css_rules.append(rule)
            
    print(f"\nSuccessfully downloaded {len(downloaded_files)} font files into nicegui_ui/fonts/")
    
    # Save offline_fonts.css
    offline_css_path = os.path.join(os.path.dirname(__file__), "..", "nicegui_ui", "offline_fonts.css")
    with open(offline_css_path, 'w', encoding='utf-8') as f:
        f.write("/* Offline Local Font Face Definitions */\n" + "\n\n".join(local_css_rules))
        
    print(f"Wrote offline font rules to {offline_css_path}")

except Exception as exc:
    print(f"Error fetching/downloading fonts: {exc}")
