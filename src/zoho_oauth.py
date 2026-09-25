"""
Zoho OAuth 2.0 / OpenID Connect login.

Configured entirely through environment variables (see .env.example):
    ZOHO_OAUTH_ENABLED   "true" to show "Login with Zoho"
    ZOHO_CLIENT_ID       client ID from https://api-console.zoho.com
    ZOHO_CLIENT_SECRET   client secret from the same place
    ZOHO_REDIRECT_URI    callback URL registered in the API console
                         (default: <this host>/auth/zoho/callback)
    ZOHO_ACCOUNTS_URL    Zoho accounts server for your data center
                         (default: https://accounts.zoho.com)
    ZOHO_SCOPES          requested scopes (default: openid,email,profile)
    ZOHO_ALLOWED_DOMAINS comma-separated email domains allowed to log in
                         (default: any domain)
    ZOHO_ALLOW_SIGNUP    create accounts for new Zoho users
                         (default: follows REGISTRATION_DISABLED)
    ZOHO_DEFAULT_TIER    tier for accounts created via Zoho (default: user)
"""
import base64
import json
import os
import re
from urllib.parse import urlencode

import requests

VALID_TIERS = ('guest', 'user', 'extra', 'admin')

# Zoho data centers: accounts.zoho.com, .eu, .in, .com.au, .jp, .sa,
# accounts.zohocloud.ca, ...
ACCOUNTS_SERVER_RE = re.compile(r'^https://accounts\.zoho(cloud)?\.[a-z]{2,3}(\.[a-z]{2})?$')


def _env_bool(key, default=False):
    value = os.getenv(key)
    if value is None or value.strip() == '':
        return default
    return value.strip().lower() in ('true', '1', 'yes')


class ZohoOAuthConfig:
    def __init__(self, registration_disabled=False):
        self.client_id = os.getenv('ZOHO_CLIENT_ID', '').strip()
        self.client_secret = os.getenv('ZOHO_CLIENT_SECRET', '').strip()
        self.redirect_uri = os.getenv('ZOHO_REDIRECT_URI', '').strip() or None
        self.accounts_url = (os.getenv('ZOHO_ACCOUNTS_URL', '').strip() or 'https://accounts.zoho.com').rstrip('/')
        self.scopes = os.getenv('ZOHO_SCOPES', '').strip() or 'openid,email,profile'
        self.allowed_domains = [d.strip().lower().lstrip('@')
                                for d in os.getenv('ZOHO_ALLOWED_DOMAINS', '').split(',') if d.strip()]
        self.allow_signup = _env_bool('ZOHO_ALLOW_SIGNUP', default=not registration_disabled)

        self.default_tier = os.getenv('ZOHO_DEFAULT_TIER', '').strip().lower() or 'user'
        if self.default_tier not in VALID_TIERS:
            print(f"⚠️  ZOHO_DEFAULT_TIER '{self.default_tier}' is invalid, using 'user'")
            self.default_tier = 'user'

        self.enabled = _env_bool('ZOHO_OAUTH_ENABLED')
        if self.enabled and not (self.client_id and self.client_secret):
            print('⚠️  ZOHO_OAUTH_ENABLED is set but ZOHO_CLIENT_ID / ZOHO_CLIENT_SECRET are missing. '
                  'Zoho login is disabled.')
            self.enabled = False

    def authorize_url(self, redirect_uri, state):
        params = {
            'response_type': 'code',
            'client_id': self.client_id,
            'scope': self.scopes,
            'redirect_uri': redirect_uri,
            'state': state,
            # No `prompt`: Zoho rejects any value but "consent", which would
            # make users re-approve the app on every login
            'access_type': 'online',
        }
        return f'{self.accounts_url}/oauth/v2/auth?{urlencode(params)}'

    def accounts_server_for(self, callback_accounts_server):
        """Zoho sends users from other data centers back with an
        `accounts-server` param; the code must be exchanged there."""
        if callback_accounts_server and ACCOUNTS_SERVER_RE.match(callback_accounts_server):
            return callback_accounts_server.rstrip('/')
        return self.accounts_url

    def fetch_identity(self, code, redirect_uri, accounts_server):
        """Exchange the auth code and return the user's identity claims.
        Raises ZohoOAuthError on failure."""
        try:
            resp = requests.post(f'{accounts_server}/oauth/v2/token', data={
                'grant_type': 'authorization_code',
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'redirect_uri': redirect_uri,
                'code': code,
            }, timeout=15)
            token = resp.json()
        except (requests.RequestException, ValueError) as e:
            raise ZohoOAuthError(f'Could not reach Zoho: {e}')

        if 'error' in token or 'access_token' not in token:
            raise ZohoOAuthError(f"Zoho token exchange failed: {token.get('error', resp.status_code)}")

        claims = {}
        # The id_token came straight from Zoho's token endpoint over TLS, so
        # its claims can be read without verifying the signature.
        if token.get('id_token'):
            claims.update(_decode_jwt_payload(token['id_token']))

        try:
            info = requests.get(f'{accounts_server}/oauth/v2/userinfo',
                                headers={'Authorization': f"Zoho-oauthtoken {token['access_token']}"},
                                timeout=15)
            if info.ok:
                claims.update(info.json())
        except (requests.RequestException, ValueError):
            pass

        zoho_id = str(claims.get('sub') or claims.get('ZUID') or '')
        email = (claims.get('email') or claims.get('Email') or '').strip().lower()
        name = (claims.get('name') or claims.get('Display_Name')
                or ' '.join(filter(None, [claims.get('given_name'), claims.get('family_name')])))
        if not zoho_id or not email:
            raise ZohoOAuthError('Zoho did not return an account ID and email. '
                                 'Check that ZOHO_SCOPES includes openid and email.')

        email_verified = claims.get('email_verified', True)
        if email_verified in (False, 'false'):
            raise ZohoOAuthError('Your Zoho email address is not verified.')

        return {'zoho_id': zoho_id, 'email': email, 'name': name}

    def domain_allowed(self, email):
        if not self.allowed_domains:
            return True
        return email.rsplit('@', 1)[-1] in self.allowed_domains


class ZohoOAuthError(Exception):
    pass


def _decode_jwt_payload(jwt):
    try:
        payload = jwt.split('.')[1]
        payload += '=' * (-len(payload) % 4)
        return json.loads(base64.urlsafe_b64decode(payload))
    except (IndexError, ValueError):
        return {}
