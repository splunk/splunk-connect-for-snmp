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
import typing
from typing import Union


def human_bool(flag: Union[str, bool], default: bool = False) -> bool:

    if flag is None:
        return False

    if isinstance(flag, bool):
        return flag

    if flag.lower() in [
        "true",
        "1",
        "t",
        "y",
        "yes",
    ]:
        return True
    elif flag.lower() in [
        "false",
        "0",
        "f",
        "n",
        "no",
    ]:
        return False
    else:
        return default


class BadlyFormattedFieldError(Exception):
    pass


def convert_to_float(value: typing.Any, ignore_error: bool = False) -> typing.Any:
    try:
        return float(value)
    except ValueError:
        if ignore_error:
            return value
        raise BadlyFormattedFieldError(f"Value '{value}' should be numeric")
