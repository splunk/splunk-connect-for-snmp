from typing import Union


def isTrueish(flag: Union[str, bool]) -> bool:

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
    else:
        return False


def isFalseish(flag: Union[str, bool]) -> bool:
    if isinstance(flag, bool):
        return flag
    if flag.lower() in [
        "false",
        "0",
        "f",
        "n",
        "no",
    ]:
        return False
    else:
        return True
