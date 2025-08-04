import requests


def retry_handler(task, task_run, state) -> bool:  # disabled pylint: disable=unused-argument
    """
    Retry handler that skips retries if the HTTP status code is 401 or 404.
    """
    try:
        state.result()
    except requests.HTTPError as exc:
        do_not_retry_on_these_codes = [401, 404]
        return exc.response.status_code not in do_not_retry_on_these_codes
    except requests.ConnectionError:
        return False
    except Exception:
        return True
