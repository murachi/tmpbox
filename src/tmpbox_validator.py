import re

re_name_token = re.compile(r"[a-z][\w\-]*\Z", re.I | re.A)
re_uri_unreserved = re.compile(r"[\w\.\-\~]+$", re.A)

def validateNameToken(val):
    return bool(re_name_token.match(val))

def validateURIUnreserved(val):
    return bool(re_uri_unreserved.match(val))
