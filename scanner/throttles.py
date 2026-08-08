from rest_framework.throttling import UserRateThrottle


class ScannerScanThrottle(UserRateThrottle):
    rate = "180/min"
