"""OMIM official REST API client.

Replaces the legacy HTML scraper. All network data access now goes through the
official OMIM API (https://api.omim.org/api) which requires an API key.

API key resolution order:
    1. explicit argument
    2. environment variable OMIM_API_KEY
    3. config file ~/.omim_api_key

The same key is also used as the download token for the official text files
(mimTitles.txt / genemap2.txt / morbidmap.txt) hosted under
``data.omim.org/downloads/{KEY}/``.
"""
import json
import os
import time
from pathlib import Path

import requests
from simple_loggers import SimpleLogger


BASE_URL = 'https://api.omim.org/api'
ENV_VAR_KEY = 'OMIM_API_KEY'
CONFIG_FILE = Path.home() / '.omim_api_key'
RATE_LIMIT_DELAY = 0.5  # seconds between requests (be polite)
ENTRY_BATCH_WITH_INCLUDE = 20  # API caps entries per request when include is set
ENTRY_BATCH_NO_INCLUDE = 100


class ApiKeyError(Exception):
    """Raised when no API key can be resolved."""


class ApiError(Exception):
    """Raised on unrecoverable API errors."""


class QuotaExhausted(ApiError):
    """Daily API quota / persistent rate limit reached.

    Raised when a 429 persists past the single retry — the caller should stop
    the whole bulk run (not just skip the batch) and resume later.
    """


def load_api_key(explicit=None):
    """Resolve the API key from argument > env var > config file."""
    if explicit:
        return explicit.strip()
    key = os.environ.get(ENV_VAR_KEY)
    if key:
        return key.strip()
    if CONFIG_FILE.exists():
        key = CONFIG_FILE.read_text().strip()
        if key:
            return key
    raise ApiKeyError(
        'No OMIM API key found.\n'
        '  Set it with:  omim api config --set-key YOUR_KEY\n'
        '  Or env var:   export OMIM_API_KEY=YOUR_KEY\n'
        '  Register at:  https://omim.org/downloads'
    )


class APIClient(object):
    """Thin, reusable wrapper around the OMIM REST API."""

    def __init__(self, api_key=None, base_url=BASE_URL, delay=RATE_LIMIT_DELAY,
                 logger=None, timeout=30):
        self.api_key = load_api_key(api_key)
        self.base_url = base_url
        self.delay = delay
        self.timeout = timeout
        self.logger = logger or SimpleLogger('OMIM-API')
        self.session = requests.Session()
        self.session.headers.update({
            'ApiKey': self.api_key,
            'Accept-Encoding': 'gzip',
            'User-Agent': 'omim-cli/2.1 (https://github.com/Liozhang/omim-cli)',
        })

    # ------------------------------------------------------------------
    # low-level
    # ------------------------------------------------------------------
    def _request(self, path, params=None):
        url = self.base_url + path
        params = dict(params or {})
        params.setdefault('format', 'json')

        try:
            resp = self.session.get(url, params=params, timeout=self.timeout)
        except requests.exceptions.Timeout:
            raise ApiError(f'Request timed out after {self.timeout}s: {url}')
        except requests.exceptions.ConnectionError as exc:
            raise ApiError(
                f'Cannot connect to OMIM API ({exc}). Check your network or '
                f'whether the host is reachable.'
            )

        # quota / rate-limit -> back off and retry once
        if resp.status_code == 429:
            self.logger.warning(
                'OMIM rate limit / quota reached (429); backing off 10s and '
                'retrying once. If this persists, your daily API quota may be '
                'exhausted — wait and resume later.'
            )
            time.sleep(10)
            resp = self.session.get(url, params=params, timeout=self.timeout)

        if resp.status_code == 429:
            raise QuotaExhausted(
                'OMIM API quota exhausted (429) even after retry. Stop the '
                'bulk run and resume later; review OMIM API usage limits.'
            )
        elif resp.status_code in (401, 403):
            raise ApiError(
                f'OMIM rejected the API key (HTTP {resp.status_code}). The key '
                f'may be invalid, revoked, or not yet activated (new keys take '
                f'~2 hours). Re-check with: omim api config --show'
            )
        elif resp.status_code == 404:
            raise ApiError(f'Requested data not found (404): {url}')
        elif resp.status_code == 400:
            hint = self._hint_for_body(resp)
            raise ApiError(
                f'OMIM rejected the request (HTTP 400). {hint}'
            )
        elif resp.status_code >= 500:
            raise ApiError(
                f'OMIM server error (HTTP {resp.status_code}); try again later.'
            )
        elif resp.status_code != 200:
            raise ApiError(f'OMIM request failed (HTTP {resp.status_code}).')

        if self.delay:
            time.sleep(self.delay)
        try:
            return resp.json()
        except json.JSONDecodeError:
            body_preview = (resp.text or '')[:200]
            raise ApiError(
                f'OMIM returned non-JSON response (HTTP {resp.status_code}). '
                f'This may indicate a CAPTCHA or access block. '
                f'Open the URL in a browser: {url}'
            )

    @staticmethod
    def _hint_for_body(resp):
        """Turn an error response body into a short human hint (no HTML dump)."""
        body = resp.text or ''
        # OMIM returns an HTML error page for some rejections (e.g. bad key)
        if '<html' in body.lower() or '<!doctype' in body.lower():
            return ('This usually means the API key is invalid/not activated, '
                    'or the request was malformed.')
        return body[:200]

    @staticmethod
    def _join_include(include):
        """Accept a comma-string or an iterable -> comma-separated string."""
        if not include:
            return None
        if isinstance(include, str):
            return include
        return ','.join(include)

    # ------------------------------------------------------------------
    # entry
    # ------------------------------------------------------------------
    def get_entry(self, mim_number, include=None, exclude=None):
        """Fetch a single entry. Returns the entry dict or None."""
        params = {'mimNumber': mim_number}
        inc = self._join_include(include)
        if inc:
            params['include'] = inc
        if exclude:
            params['exclude'] = self._join_include(exclude)
        data = self._request('/entry', params)
        entries = data.get('omim', {}).get('entryList', [])
        return entries[0].get('entry') if entries else None

    def get_entries(self, mim_numbers, include=None):
        """Fetch multiple entries in one request (API caps 20 when include set).

        Returns a list of entry dicts. Raises ValueError if the batch violates
        the documented limit (20 with include).
        """
        mims = [str(m) for m in mim_numbers]
        if include and len(mims) > ENTRY_BATCH_WITH_INCLUDE:
            raise ValueError(
                f'OMIM API limits entry requests to {ENTRY_BATCH_WITH_INCLUDE} '
                f'mimNumbers when an include is set (got {len(mims)}). '
                f'Use iter_entries() which batches automatically.'
            )
        params = {'mimNumber': ','.join(mims)}
        inc = self._join_include(include)
        if inc:
            params['include'] = inc
        data = self._request('/entry', params)
        return [item.get('entry') for item in data.get('omim', {}).get('entryList', [])]

    def iter_entries(self, mim_numbers, include=None, batch_size=None):
        """Yield entry dicts, handling batching transparently.

        When ``include`` is given, batches are capped at ENTRY_BATCH_WITH_INCLUDE.
        """
        mims = list(mim_numbers)
        if batch_size is None:
            batch_size = ENTRY_BATCH_WITH_INCLUDE if include else ENTRY_BATCH_NO_INCLUDE
        for i in range(0, len(mims), batch_size):
            batch = mims[i:i + batch_size]
            for entry in self.get_entries(batch, include=include):
                yield entry

    # ------------------------------------------------------------------
    # search
    # ------------------------------------------------------------------
    def search(self, query, start=0, limit=10, include=None, retrieve=None,
               filter_=None, sort=None, operator=None):
        params = {'search': query, 'start': start, 'limit': limit}
        if include:
            params['include'] = self._join_include(include)
        if retrieve:
            params['retrieve'] = retrieve
        if filter_:
            params['filter'] = filter_
        if sort:
            params['sort'] = sort
        if operator:
            params['operator'] = operator
        data = self._request('/entry/search', params)
        return data.get('omim', {}).get('searchResponse', {})

    # ------------------------------------------------------------------
    # component handlers
    # ------------------------------------------------------------------
    def get_gene_map(self, mim_number, start=None, limit=None):
        """geneMap handler. API caps results at 100 per request.

        Response: omim.listResponse.geneMapList
        """
        params = {'mimNumber': mim_number}
        if start is not None:
            params['start'] = start
        if limit is not None:
            params['limit'] = min(int(limit), 100)
        data = self._request('/geneMap', params)
        list_resp = data.get('omim', {}).get('listResponse', {})
        return list_resp.get('geneMapList', [])

    def get_clinical_synopsis(self, mim_number, include=None, start=None, limit=None):
        params = {'mimNumber': mim_number}
        inc = self._join_include(include) or 'clinicalSynopsis'
        params['include'] = inc
        if start is not None:
            params['start'] = start
        if limit is not None:
            params['limit'] = limit
        data = self._request('/clinicalSynopsis', params)
        return data.get('omim', {}).get('clinicalSynopsisList', [])

    def get_allelic_variants(self, mim_number):
        """entry/allelicVariantList component.

        Response: omim.allelicVariantLists[*].allelicVariantList
        """
        data = self._request('/entry/allelicVariantList', {'mimNumber': mim_number})
        out = []
        for group in data.get('omim', {}).get('allelicVariantLists', []):
            out.extend(group.get('allelicVariantList', []))
        return out

    def get_references(self, mim_number):
        """entry/referenceList component.

        Response: omim.referenceLists[*].referenceList
        """
        data = self._request('/entry/referenceList', {'mimNumber': mim_number})
        out = []
        for group in data.get('omim', {}).get('referenceLists', []):
            out.extend(group.get('referenceList', []))
        return out

    def status(self):
        return self._request('/status')
