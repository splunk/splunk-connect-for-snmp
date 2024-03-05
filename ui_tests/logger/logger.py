import logging
import sys

log = None


class Logger:
    logger = None

    @classmethod
    def initialize_logger(cls):
        logger = logging.getLogger(__name__)
        logger.setLevel(logging.INFO)
        formatter = logging.Formatter("%(message)s")
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        # return logger
        cls.logger = logger

    @classmethod
    def get_logger(cls):
        if cls.logger is None:
            cls.initialize_logger()
        return cls.logger
