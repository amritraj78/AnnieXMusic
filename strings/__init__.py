# Authored By Certified Coders © 2025
import os
import sys

import yaml

languages = {}
languages_present = {}
_LANGS_DIR = os.path.join(os.path.dirname(__file__), "langs")


def get_string(lang: str):
    return languages.get(lang) or languages["en"]


en_path = os.path.join(_LANGS_DIR, "en.yml")
with open(en_path, encoding="utf8") as f:
    languages["en"] = yaml.safe_load(f)
languages_present["en"] = languages["en"]["name"]

for filename in os.listdir(_LANGS_DIR):
    if not filename.endswith(".yml"):
        continue
    language_name = filename[:-4]
    if language_name == "en":
        continue
    lang_path = os.path.join(_LANGS_DIR, filename)
    try:
        with open(lang_path, encoding="utf8") as f:
            languages[language_name] = yaml.safe_load(f) or {}
        for item in languages["en"]:
            if item not in languages[language_name]:
                languages[language_name][item] = languages["en"][item]
        languages_present[language_name] = languages[language_name]["name"]
    except Exception:
        print(f"There is some issue with the language file '{filename}' inside bot.")
        sys.exit(1)
