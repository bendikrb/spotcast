from pychromecast.error import PyChromecastError


class TokenError(Exception):
    pass

class LaunchError(PyChromecastError):
    """When an app fails to launch."""
