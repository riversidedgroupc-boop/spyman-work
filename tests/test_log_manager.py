"""Tests for LogManager multi-category log system."""
import os

from core.log_manager import LogManager


def _reset_log_manager():
    LogManager._instance = None


def test_instance_singleton(tmp_path):
    _reset_log_manager()
    lm = LogManager(log_dir=str(tmp_path))
    lm2 = LogManager.instance()
    assert lm is lm2
    _reset_log_manager()


def test_get_logger_creates_file(tmp_path):
    _reset_log_manager()
    lm = LogManager(log_dir=str(tmp_path))
    logger = lm.get_logger("app")
    logger.info("Test message")
    log_path = lm.get_log_path("app")
    assert os.path.isfile(log_path)
    _reset_log_manager()


def test_all_categories(tmp_path):
    _reset_log_manager()
    lm = LogManager(log_dir=str(tmp_path))
    for cat in LogManager.CATEGORIES:
        logger = lm.get_logger(cat)
        logger.info(f"Hello from {cat}")
        assert os.path.isfile(lm.get_log_path(cat))
    _reset_log_manager()


def test_unknown_category_raises(tmp_path):
    _reset_log_manager()
    lm = LogManager(log_dir=str(tmp_path))
    try:
        lm.get_logger("nonexistent")
        assert False, "Should have raised"
    except ValueError:
        pass
    _reset_log_manager()


def test_audit_logs_operations(tmp_path):
    _reset_log_manager()
    lm = LogManager(log_dir=str(tmp_path))
    lm.log_audit("model_activate", "model_v001 set active")
    log_path = lm.get_log_path("audit")
    assert os.path.isfile(log_path)
    with open(log_path, encoding="utf-8") as f:
        content = f.read()
    assert "model_activate" in content
    assert "model_v001" in content
    _reset_log_manager()


def test_all_log_paths(tmp_path):
    _reset_log_manager()
    lm = LogManager(log_dir=str(tmp_path))
    paths = lm.all_log_paths()
    assert len(paths) == 6
    for cat in LogManager.CATEGORIES:
        assert cat in paths
    _reset_log_manager()
