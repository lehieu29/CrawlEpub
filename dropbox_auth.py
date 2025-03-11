import os
import json
import time
import logging
import requests
from urllib.parse import urlencode
from flask import url_for, redirect, request, session

class DropboxAuth:
    def __init__(self, logger=None, socket=None):
        """Initialize Dropbox Auth with required parameters"""
        self.logger = logger or logging.getLogger('dropbox_storage')
        self.socket = socket
        self.client_id = os.getenv('DROPBOX_APP_KEY', '')
        self.client_secret = os.getenv('DROPBOX_APP_SECRET', '')
        self.redirect_uri = None  # Will be set dynamically based on request
        self.token_file = os.path.join(os.getcwd(), 'secure', 'dropbox_tokens.json')
        self.access_token = ''

        self._log('info', f'ClientID: {self.client_id}')
        
        # Create the secure directory if it doesn't exist
        os.makedirs(os.path.dirname(self.token_file), exist_ok=True)
    
    def _log(self, level, message, download_id=None):
        """Log a message and emit it via socket if available"""
        message = f'DropBoxAuth: {message}'
        if level == 'info':
            self.logger.info(message)
        elif level == 'error':
            self.logger.error(message)
        elif level == 'warning':
            self.logger.warning(message)

        # Emit via socket if available
        if self.socket and download_id:
            self.socket.emit('log_update', {
                'download_id': download_id,
                'level': level,
                'message': message,
                'timestamp': time.time(),
                'source': 'dropbox_storage'  # Add source identifier
            })

    def init_app(self, app):
        """Initialize with Flask app context for URL generation"""
        @app.route('/dropbox/auth')
        def dropbox_auth():
            """Start the OAuth flow by redirecting to Dropbox"""
            # Set the redirect URI based on the current request
            self.redirect_uri = url_for('dropbox_callback', _external=True)
            
            # Build the authorization URL
            params = {
                'client_id': self.client_id,
                'response_type': 'code',
                'redirect_uri': self.redirect_uri,
                'token_access_type': 'offline',  # Request a refresh token
            }
            auth_url = f"https://www.dropbox.com/oauth2/authorize?{urlencode(params)}"
            
            self._log('info', (f"Redirecting to Dropbox Auth: {auth_url}"))
            return redirect(auth_url)
            
        @app.route('/dropbox/callback')
        def dropbox_callback():
            """Handle the OAuth callback from Dropbox"""
            code = request.args.get('code')
            error = request.args.get('error')
            
            if error:
                self._log('error', (f"Dropbox auth error: {error}"))
                return f"Authentication failed: {error}", 400
                
            if not code:
                self._log('error', ("No authorization code received from Dropbox"))
                return "No authorization code received", 400
                
            # Exchange the code for tokens
            self.redirect_uri = url_for('dropbox_callback', _external=True)
            token_data = self._exchange_code_for_tokens(code)
            
            if not token_data:
                return "Failed to obtain access tokens", 500
                
            # Save tokens
            self._save_tokens(token_data)
            self._log('info', ("Dropbox authentication successful. Tokens saved."))
            
            return redirect('/dropbox/status')
            
        @app.route('/dropbox/status')
        def dropbox_status():
            """Check and display Dropbox connection status"""
            is_authorized = self.is_authorized()
            tokens = self.get_tokens()
            
            if is_authorized:
                account_info = self.get_account_info()
                if account_info:
                    return f"""
                    <h1>Dropbox Connected</h1>
                    <p>Account: {account_info.get('email')} ({account_info.get('name', {}).get('display_name', 'Unknown')})</p>
                    <p>Account ID: {account_info.get('account_id', 'Unknown')}</p>
                    <p>Token expires in: {tokens.get('expires_at', 0) - int(time.time())} seconds</p>
                    <a href="/">Return to homepage</a>
                    """
                else:
                    return f"""
                    <h1>Dropbox Connected</h1>
                    <p>Warning: Could not retrieve account information.</p>
                    <p>Token may be valid but account access is limited.</p>
                    <a href="/dropbox/auth">Reconnect to Dropbox</a> | 
                    <a href="/">Return to homepage</a>
                    """
            else:
                return f"""
                <h1>Dropbox Not Connected</h1>
                <p>You need to connect your Dropbox account to use cloud storage.</p>
                <a href="/dropbox/auth" class="btn btn-primary">Connect to Dropbox</a>
                """
                
        @app.route('/dropbox/disconnect')
        def dropbox_disconnect():
            """Disconnect Dropbox account by removing stored tokens"""
            self._remove_tokens()
            return redirect('/dropbox/status')
    
    def _exchange_code_for_tokens(self, code):
        """Exchange authorization code for access and refresh tokens"""
        try:
            data = {
                'code': code,
                'grant_type': 'authorization_code',
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'redirect_uri': self.redirect_uri,
            }
            
            response = requests.post('https://api.dropboxapi.com/oauth2/token', data=data)
            response.raise_for_status()
            token_data = response.json()
            
            # Add expiration time for easier checking later
            if 'expires_in' in token_data:
                token_data['expires_at'] = int(time.time()) + token_data['expires_in']
                
            self._log('info', (f"Successfully exchanged code for tokens. Expires in {token_data.get('expires_in')} seconds"))
            return token_data
        except Exception as e:
            self._log('error', (f"Error exchanging code for tokens: {str(e)}"))
            return None

    def refresh_access_token(self):
        """Refresh the access token using the refresh token"""
        tokens = self.get_tokens()
        
        if not tokens or 'refresh_token' not in tokens:
            self._log('error', ("No refresh token available. User needs to re-authenticate."))
            return False
            
        try:
            data = {
                'grant_type': 'refresh_token',
                'refresh_token': tokens['refresh_token'],
                'client_id': self.client_id,
                'client_secret': self.client_secret,
            }
            
            response = requests.post('https://api.dropboxapi.com/oauth2/token', data=data)
            response.raise_for_status()
            new_token_data = response.json()
            
            # Add expiration time
            if 'expires_in' in new_token_data:
                new_token_data['expires_at'] = int(time.time()) + new_token_data['expires_in']
            
            # Keep the refresh token if not returned in response
            if 'refresh_token' not in new_token_data and 'refresh_token' in tokens:
                new_token_data['refresh_token'] = tokens['refresh_token']
                
            self._save_tokens(new_token_data)
            self._log('info', (f"Successfully refreshed access token. Expires in {new_token_data.get('expires_in')} seconds"))
            return True
        except Exception as e:
            self._log('error', (f"Error refreshing access token: {str(e)}"))
            return False

    def get_account_info(self):
        """Get current user's account information"""
        access_token = self.get_access_token()
        if not access_token:
            return None
            
        try:
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json',
            }
            
            response = requests.post('https://api.dropboxapi.com/2/users/get_current_account', 
                                     headers=headers)
            self._log('info', f'Request Account Info Token Length: {len(access_token)}')

            response.raise_for_status()
            return response.json()
        except Exception as e:
            self._log('error', (f"Error getting account info: {str(e)}"))
            
            # If 401 Unauthorized, try refreshing the token
            if hasattr(e, 'response') and getattr(e.response, 'status_code', 0) == 401:
                self._log('info', "Access token expired. Attempting to refresh...")
                if self.refresh_access_token():
                    # Get a fresh token after refresh
                    fresh_token = self.get_tokens().get('access_token')
                    if fresh_token:
                        try:
                            headers = {
                                'Authorization': f'Bearer {fresh_token}',
                                'Content-Type': 'application/json',
                            }
                            response = requests.post('https://api.dropboxapi.com/2/users/get_current_account', 
                                                    headers=headers)
                            response.raise_for_status()
                            return response.json()
                        except Exception as retry_e:
                            self._log('error', f"Error getting account info after token refresh: {str(retry_e)}")
                            return None
                    
            return None

    def get_access_token(self):
        """Get the current access token, refreshing if needed"""
        tokens = self.get_tokens()
        
        if not tokens:
            self._log('warning', ("No tokens available"))
            return None
            
        # Check if token is expired or will expire soon (within 5 minutes)
        current_time = int(time.time())
        if 'expires_at' in tokens and tokens['expires_at'] - current_time < 300:
            self._log('info', ("Access token expired or will expire soon. Refreshing..."))
            if not self.refresh_access_token():
                return None
            tokens = self.get_tokens()  # Get the refreshed tokens
            
        return tokens.get('access_token')
        
    def is_authorized(self):
        """Check if we have valid tokens for Dropbox API access"""
        return self.get_access_token() is not None

    def get_tokens(self):
        """Get the stored tokens"""
        try:
            if self.access_token:
                return self.access_token
            
            if os.path.exists(self.token_file):
                with open(self.token_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            self._log('error', (f"Error reading token file: {str(e)}"))
        
        return None

    def _save_tokens(self, token_data):
        """Save tokens to the secure file"""
        try:
            self.access_token = token_data

            with open(self.token_file, 'w') as f:
                json.dump(token_data, f)
            
            # Secure the file permissions (UNIX only)
            try:
                os.chmod(self.token_file, 0o600)
            except:
                pass
                
            return True
        except Exception as e:
            self._log('error', (f"Error saving tokens: {str(e)}"))
            return False
            
    def _remove_tokens(self):
        """Remove the stored tokens file"""
        try:
            self.access_token = ''

            if os.path.exists(self.token_file):
                os.remove(self.token_file)
                self._log('info', ("Dropbox tokens removed successfully"))
            return True
        except Exception as e:
            self._log('error', (f"Error removing tokens: {str(e)}"))
            return False