class SnmpActionError(Exception):
    """Exception raised for errors produced during execution of SNMP operations"""

    pass


def summarize_exception_group(eg: ExceptionGroup, context: str | None = None) -> str:
    """
    This wraps multiple exceptions into a single, pickle-safe error message.
    Needed because Celery cannot serialize complex exceptions (like
    ExceptionGroup), so all nested errors are flattened into a simple string.

    :param eg: ExceptionGroup of exceptions to summarize.
    :param context (str, optional): Additional context to include in the summary.

    :return: A formatted error summary safe for logging or raising in a pickle-safe exception.
    """

    messages = [
        f"[{i}] {type(ex).__name__}: {ex}"
        for i, ex in enumerate(eg.exceptions, start=1)
    ]

    unique_types = ", ".join({type(e).__name__ for e in eg.exceptions})
    base_message = f"{len(eg.exceptions)} error(s) ({unique_types})"

    if context:
        summary = f"{context}: {base_message}"
    else:
        summary = base_message

    return summary + "\n  " + "\n  ".join(messages)
