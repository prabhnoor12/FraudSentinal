# backend/utils/testing_utils.py
import os


def is_testing() -> bool:
    return os.getenv("TESTING", "").lower() in {"1", "true", "yes"}
