import logging
from app.utils.logger import setup_logger, LOG_FILE

def test_logger_setup():
    logger_instance = setup_logger("TEST_LOGGER")
    assert logger_instance.name == "TEST_LOGGER"
    assert len(logger_instance.handlers) >= 2

def test_logger_no_duplicate_handlers():
    logger1 = setup_logger("TEST_DUP")
    handlers_count = len(logger1.handlers)
    logger2 = setup_logger("TEST_DUP")
    assert len(logger2.handlers) == handlers_count

def test_logger_file_created():
    logger_instance = setup_logger("TEST_FILE")
    logger_instance.info("Test log message for health check")
    assert LOG_FILE.exists()
