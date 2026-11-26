"""Лёгкий счётчик запросов для метрик админки (запросов/мин)."""

import time
from collections import deque

_REQUEST_TIMES: deque[float] = deque(maxlen=2000)


def record_request() -> None:
    _REQUEST_TIMES.append(time.time())


def requests_per_minute() -> int:
    now = time.time()
    cutoff = now - 60.0
    while _REQUEST_TIMES and _REQUEST_TIMES[0] < cutoff:
        _REQUEST_TIMES.popleft()
    return len(_REQUEST_TIMES)


class RequestMetricsMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        record_request()
        return self.get_response(request)
