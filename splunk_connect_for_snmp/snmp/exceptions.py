class Error(Exception):
    """Base class for exceptions in this module."""
    pass


class SnmpActionError(Error):
    """Exception raised for errors in the input."""
    def __init__(self, operation, host, error):
        self.operation = operation
        super().__init__(f"An error of SNMP {operation} for a host {host} occurred: {error}")

