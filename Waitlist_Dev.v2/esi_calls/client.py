from esi.clients import esi_client_factory

def get_esi_client(token=None):
    """
    Returns a configured ESI SwaggerClient with the correct User-Agent.
    If a token is provided, the client will be authenticated.
    """
    return esi_client_factory(
        token=token,
        ua_appname='Waitlist Project',
        ua_version='2.0',
        ua_url='https://github.com/example/waitlist'
    )
