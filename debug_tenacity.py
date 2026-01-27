from tenacity import retry, stop_after_attempt, RetryError, retry_if_exception_type
import logging

class CustomError(Exception):
    pass

@retry(stop=stop_after_attempt(1), reraise=True)
def failing_function_reraise():
    print("Running failing function (reraise=True)")
    raise CustomError("Original Error")

@retry(stop=stop_after_attempt(1), reraise=False)
def failing_function_no_reraise():
    print("Running failing function (reraise=False)")
    raise CustomError("Original Error")

print("--- Test 1: reraise=True ---")
try:
    failing_function_reraise()
except CustomError as e:
    print(f"CAUGHT EXPECTED: {e}")
except RetryError as e:
    print(f"CAUGHT UNEXPECTED RetryError: {e}")
except Exception as e:
    print(f"CAUGHT UNEXPECTED Exception: {type(e)} - {e}")

print("\n--- Test 2: reraise=False ---")
try:
    failing_function_no_reraise()
except RetryError as e:
    print(f"CAUGHT EXPECTED RetryError: {e}")
    # Inspecting the Future-like string
    print(f"Error repr: {repr(e)}")
except Exception as e:
    print(f"CAUGHT UNEXPECTED Exception: {type(e)} - {e}")
