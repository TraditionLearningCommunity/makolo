from rest_framework.throttling import AnonRateThrottle, UserRateThrottle


class PaymentInitiationThrottle(UserRateThrottle):
    rate = "30/hour"


class PaymentTransitionThrottle(UserRateThrottle):
    rate = "60/hour"


class PaymentWebhookThrottle(AnonRateThrottle):
    rate = "120/minute"
