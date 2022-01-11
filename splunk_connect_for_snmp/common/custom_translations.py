import os

import yaml

try:
    from dotenv import load_dotenv

    load_dotenv()
except:
    pass

CONFIG_PATH = os.getenv("CONFIG_PATH", "/app/config/config.yaml")


def load_custom_translations():
    try:
        with open(CONFIG_PATH, encoding='utf-8') as file:
            config_runtime = yaml.safe_load(file)
            return config_runtime.get("customTranslations")

    except FileNotFoundError:
        return None
