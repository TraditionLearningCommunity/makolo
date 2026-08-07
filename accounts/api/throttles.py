from rest_framework.throttling import AnonRateThrottle


class FixedRateAnonThrottle(AnonRateThrottle):
    rate = None

    def get_rate(self):
        return self.rate


class RegistrationThrottle(FixedRateAnonThrottle):
    scope = "registration"
    rate = "5/hour"


class LoginThrottle(FixedRateAnonThrottle):
    scope = "login"
    rate = "10/minute"
