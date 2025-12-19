import datetime as dt
from hashlib import md5

from httpx import URL, Client, Response
from httpx._client import USE_CLIENT_DEFAULT, UseClientDefault
from httpx._types import (
    AuthTypes, CookieTypes, HeaderTypes, QueryParamTypes, RequestExtensions,
    TimeoutTypes,
)

from django.core.cache import cache
from django.utils import timezone


class SpecCachingClient(Client):

    def _is_spec(self, url: URL | str) -> bool:
        return "https://esi.evetech.net/meta/openapi" in str(url)

    def _get_seconds_to_dt(self) -> int:
        expire_time = timezone.now()
        if expire_time.hour > 11:
            expire_time += dt.timedelta(hours=24)

        expire_time = expire_time.replace(hour=11, minute=30, second=0)

        return int((expire_time - timezone.now()).total_seconds())

    def _get_spec_cache(self, url, ):
        return cache.get(self._get_api_cache_key(url), False)

    def _set_spec_cache(self, url, body):
        ttl = self._get_seconds_to_dt()
        cache.set(self._get_api_cache_key(url), body, ttl)

    def _get_api_cache_key(self, url: str) -> str:
        """
            provide a unique token for the spec url with compat date.
        """
        compat_date = self.headers.get("X-Compatibility-Date", None)
        return f"ESI_API_CACHE_{md5(f'{url}-{compat_date}'.encode()).hexdigest()}"

    def get(
        self,
        url: URL | str,
        *,
        params: QueryParamTypes | None = None,
        headers: HeaderTypes | None = None,
        cookies: CookieTypes | None = None,
        auth: AuthTypes | UseClientDefault | None = USE_CLIENT_DEFAULT,
        follow_redirects: bool | UseClientDefault = USE_CLIENT_DEFAULT,
        timeout: TimeoutTypes | UseClientDefault = USE_CLIENT_DEFAULT,
        extensions: RequestExtensions | None = None,
    ) -> Response:
        if self._is_spec(url):
            _spec = self._get_spec_cache(url)
            if not _spec:
                _spec = super().get(
                    url,
                    params=params,
                    headers=headers,
                    cookies=cookies,
                    auth=auth,
                    follow_redirects=follow_redirects,
                    timeout=timeout,
                    extensions=extensions
                )
                self._set_spec_cache(url, _spec)
            return _spec
        return super().get(
            url,
            params=params,
            headers=headers,
            cookies=cookies,
            auth=auth,
            follow_redirects=follow_redirects,
            timeout=timeout,
            extensions=extensions
        )
