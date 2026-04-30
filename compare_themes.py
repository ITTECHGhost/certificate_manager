import json
import customtkinter
import os

ctk_path = os.path.dirname(customtkinter.__file__)
blue_theme_path = os.path.join(ctk_path, 'assets', 'themes', 'blue.json')

with open(blue_theme_path, 'r') as f:
    blue = json.load(f)

with open('themes/orange.json', 'r') as f:
    orange = json.load(f)

def print_missing(default_theme, custom_theme, path=""):
    for key, value in default_theme.items():
        if key not in custom_theme:
            print(f"Missing: {path}{key} = {value}")
        elif isinstance(value, dict) and isinstance(custom_theme[key], dict):
            print_missing(value, custom_theme[key], path + key + ".")

print_missing(blue, orange)
