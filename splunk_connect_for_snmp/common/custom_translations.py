#
# Copyright 2021 Splunk Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
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
        with open(CONFIG_PATH, encoding="utf-8") as file:
            config_runtime = yaml.safe_load(file)
            if not config_runtime:
                return None
            return config_runtime.get("customTranslations")

    except FileNotFoundError:
        return None
