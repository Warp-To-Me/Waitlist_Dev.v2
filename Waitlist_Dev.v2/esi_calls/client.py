from esi.clients import EsiClientProvider

def get_esi_client(token=None):
    """
    Returns a configured ESI SwaggerClient.
    If a token is provided, the client will be authenticated.
    """
    provider = EsiClientProvider(
        ua_appname='Waitlist Project',
        ua_version='2.0',
        ua_url='https://github.com/example/waitlist'
    )

    # EsiClientProvider.client is a property that builds the client on first access
    # We can pass kwargs to it, but the provider __init__ takes most of them.
    # To attach a token dynamically for a specific request, we might want to
    # generate a client specific for that token.

    # EsiClientProvider creates a singleton-ish client provider, but we need
    # to attach tokens for auth.

    # The factory takes `token` as an argument.
    # If we use the provider, we get a generic client.
    # To get an AUTHENTICATED client, we should use the factory directly or
    # use the token method: `token.get_esi_client(...)`

    # However, to centralize the User-Agent config, we should wrap the factory here.

    from esi.clients import esi_client_factory

    return esi_client_factory(
        token=token,
        ua_appname='Waitlist Project',
        ua_version='2.0',
        ua_url='https://github.com/example/waitlist'
    )
