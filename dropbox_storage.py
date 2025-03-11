import os
import logging
import dropbox
from dropbox.exceptions import ApiError, AuthError
from dropbox.files import WriteMode
import time
import json

class DropboxStorage:
    def __init__(self, logger=None, socket=None, dropbox_auth=None):
        self.logger = logger or logging.getLogger('dropbox_storage')
        self.socket = socket
        self.dropbox_auth = dropbox_auth
        self.dbx = None
        self.is_active = False
        self._initialize_client()

    def _log(self, level, message, download_id=None):
        """Log a message and emit it via socket if available"""
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

    def _initialize_client(self):
        """Initialize Dropbox client if auth is available"""
        if not self.dropbox_auth:
            self._log('warning', "No Dropbox authentication handler provided")
            self.is_active = False
            return
            
        try:
            access_token = self.dropbox_auth.get_access_token()
            
            if not access_token:
                self._log('warning', "No valid Dropbox access token available")
                self.is_active = False
                return
                
            # Log token length for debugging
            token_length = len(access_token) if access_token else 0
            self._log('info', f"Initializing Dropbox with token (length: {token_length} chars)")
            
            # Log first and last 5 chars of token (safe for debugging without exposing full token)
            if token_length > 10:
                token_prefix = access_token[:5]
                token_suffix = access_token[-5:]
                self._log('info', f"Token begins with '{token_prefix}...' and ends with '...{token_suffix}'")

            self.dbx = dropbox.Dropbox(access_token)

            # Check if the access token is valid
            self._log('info', "Attempting to get account info to verify token...")
            try:
                account = self.dbx.users_get_current_account()
                self._log('info', f"Dropbox connected for account: {account.name.display_name} (Email: {account.email})")
                self.is_active = True
            except AuthError:
                self._log('error', "Dropbox authentication error - token might be invalid")
                # Try refreshing the token
                self._log('info', "Attempting to refresh token...")
                if self.dropbox_auth.refresh_access_token():
                    # Retry with the new token
                    self._log('info', "Token refreshed, retrying initialization...")
                    return self._initialize_client()
                else:
                    self._log('error', "Failed to refresh token")
                    self.is_active = False
        except Exception as e:
            self._log('error', f"Error initializing Dropbox: {str(e)}")
            import traceback
            self._log('error', f"Traceback: {traceback.format_exc()}")
            self.is_active = False

    def refresh_connection(self):
        """Refresh Dropbox connection with latest token"""
        self._log('info', "Refreshing Dropbox connection...")
        return self._initialize_client()

    def create_folder_with_parents(self, path):
        """Create a folder in Dropbox, creating parent folders if needed"""
        if not self.is_active:
            self.logger.warning("Dropbox integration not active")
            return False
        
        try:
            # Split path into components
            path = path.rstrip('/')  # Remove trailing slash
            components = path.split('/')
            
            # Start with root
            current_path = ""
            
            # Create each component of the path
            for component in components:
                if not component:  # Skip empty components (like the first one if path starts with /)
                    continue
                    
                current_path += f"/{component}"
                
                try:
                    # Try to create the folder
                    self.logger.info(f"Creating folder: {current_path}")
                    self.dbx.files_create_folder_v2(current_path)
                    self.logger.info(f"Folder created: {current_path}")
                except ApiError as e:
                    # Ignore if folder already exists
                    if isinstance(e.error, dropbox.files.CreateFolderError) and e.error.is_path() and e.error.get_path().is_conflict():
                        self.logger.info(f"Folder already exists: {current_path}")
                    else:
                        # Re-raise if it's a different error
                        raise
            
            return True
        except Exception as e:
            self.logger.error(f"Error creating folder structure in Dropbox: {str(e)}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            return False

    def upload_file(self, local_path, dropbox_path, download_id=None):
        """
        Upload a file to Dropbox

        Args:
            local_path: Path to the local file
            dropbox_path: Path where the file should be saved in Dropbox

        Returns:
            Shared link URL if successful, None otherwise
        """
        if not self.is_active:
            self._log('warning', "Dropbox integration not active", download_id, download_id)
            return None

        try:
            # Check if file exists
            if not os.path.exists(local_path):
                self._log('error', f"File not found: {local_path}", download_id)
                return None

            # Get file size and details
            file_size = os.path.getsize(local_path)
            file_name = os.path.basename(local_path)
            self._log('info', f"Uploading file: {file_name} ({file_size / (1024*1024):.2f} MB)", download_id)
            self._log('info', f"Local path: {local_path}", download_id)
            self._log('info', f"Dropbox path: {dropbox_path}", download_id)

            # Read file contents
            with open(local_path, 'rb') as f:
                file_content = f.read()

            self._log('info', f"File read successfully, content length: {len(file_content)} bytes", download_id)

            # Upload the file
            self._log('info', "Starting Dropbox upload...", download_id)
            upload_start = time.time()
            upload_result = self.dbx.files_upload(
                file_content,
                dropbox_path,
                mode=WriteMode('overwrite')
            )
            upload_time = time.time() - upload_start

            # Log upload result
            self._log('info', f"Upload completed in {upload_time:.2f} seconds", download_id)
            self._log('info', f"Upload result: {upload_result}", download_id)
            self._log('info', f"File uploaded successfully to {dropbox_path}", download_id)

            # Create a shared link
            self._log('info', "Creating shared link...", download_id)
            shared_link_start = time.time()
            try:
                shared_link = self.dbx.sharing_create_shared_link_with_settings(dropbox_path)
                shared_link_time = time.time() - shared_link_start
                self._log('info', f"Shared link created in {shared_link_time:.2f} seconds", download_id)
                self._log('info', f"Shared link result: {shared_link}", download_id)

                link_url = shared_link.url

                # Convert dropbox.com links to dl.dropboxusercontent.com links for direct download
                if link_url.startswith('https://www.dropbox.com'):
                    dl_url = link_url.replace('www.dropbox.com', 'dl.dropboxusercontent.com')
                    dl_url = dl_url.replace('?dl=0', '')
                    self._log('info', f"Converted URL for direct download: {dl_url}", download_id)
                else:
                    dl_url = link_url
                    self._log('info', f"Using original URL (no conversion needed): {dl_url}", download_id)

                return dl_url
            except Exception as e:
                self._log('error', f"Error creating shared link: {str(e)}", download_id)
                self._log('error', f"Will try alternate method to create shared link...", download_id)

                # Try alternate method for shared link
                try:
                    sharing_info = self.dbx.sharing_get_shared_links(dropbox_path)
                    self._log('info', f"Got existing sharing info: {sharing_info}", download_id)

                    if sharing_info.links:
                        link_url = sharing_info.links[0].url
                        self._log('info', f"Found existing shared link: {link_url}", download_id)

                        # Convert URL for direct download
                        if link_url.startswith('https://www.dropbox.com'):
                            dl_url = link_url.replace('www.dropbox.com', 'dl.dropboxusercontent.com')
                            dl_url = dl_url.replace('?dl=0', '')
                        else:
                            dl_url = link_url

                        return dl_url
                    else:
                        self._log('error', "No existing shared links found", download_id)
                        return None
                except Exception as alt_e:
                    self._log('error', f"Alternate method also failed: {str(alt_e)}", download_id)
                    return None

        except ApiError as e:
            self._log('error', f"Dropbox API error: {str(e)}", download_id)
            error_details = getattr(e, 'error', None)
            if error_details:
                try:
                    self._log('error', f"API Error details: {json.dumps(error_details.to_dict())}", download_id)
                except:
                    self._log('error', f"API Error details (non-serializable): {error_details}", download_id)
            return None
        except Exception as e:
            self._log('error', f"Error uploading file to Dropbox: {str(e)}", download_id)
            import traceback
            self._log('error', f"Traceback: {traceback.format_exc()}", download_id)
            return None

    def download_file(self, dropbox_path, local_path):
        """
        Download a file from Dropbox

        Args:
            dropbox_path: Path of the file in Dropbox
            local_path: Path where the file should be saved locally

        Returns:
            True if successful, False otherwise
        """
        if not self.is_active:
            self._log('warning', "Dropbox integration not active")
            return False

        try:
            self._log('info', f"Downloading file: {dropbox_path} to {local_path}")

            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(local_path), exist_ok=True)

            # Download the file
            download_start = time.time()
            self.dbx.files_download_to_file(local_path, dropbox_path)
            download_time = time.time() - download_start

            # Log download info
            file_size = os.path.getsize(local_path) if os.path.exists(local_path) else 0
            self._log('info', f"File downloaded in {download_time:.2f} seconds")
            self._log('info', f"Downloaded file size: {file_size / (1024*1024):.2f} MB")
            self._log('info', f"File downloaded successfully to {local_path}")
            return True

        except ApiError as e:
            self._log('error', f"Dropbox API error: {str(e)}")
            return False
        except Exception as e:
            self._log('error', f"Error downloading file from Dropbox: {str(e)}")
            import traceback
            self._log('error', f"Traceback: {traceback.format_exc()}")
            return False

    def create_folder(self, path):
        """
        Create a folder in Dropbox

        Args:
            path: Path of the folder to create

        Returns:
            True if successful, False otherwise
        """
        if not self.is_active:
            self._log('warning', "Dropbox integration not active")
            return False

        try:
            self._log('info', f"Creating folder: {path}")
            folder_result = self.dbx.files_create_folder_v2(path)
            self._log('info', f"Folder created successfully: {path}")
            self._log('info', f"Folder creation result: {folder_result}")
            return True

        except ApiError as e:
            # Ignore error if folder already exists
            if isinstance(e.error, dropbox.files.CreateFolderError) and e.error.is_path() and e.error.get_path().is_conflict():
                self._log('info', f"Folder already exists: {path}")
                return True
            else:
                self._log('error', f"Dropbox API error: {str(e)}")
                return False
        except Exception as e:
            self._log('error', f"Error creating folder in Dropbox: {str(e)}")
            import traceback
            self._log('error', f"Traceback: {traceback.format_exc()}")
            return False

    def list_files(self, path=""):
        """
        List files in a Dropbox folder

        Args:
            path: Path of the folder to list

        Returns:
            List of file metadata if successful, empty list otherwise
        """
        if not self.is_active:
            self._log('warning', "Dropbox integration not active")
            return []

        try:
            self._log('info', f"Listing files in: {path}")
            result = self.dbx.files_list_folder(path)

            files = []
            for entry in result.entries:
                file_info = {
                    'name': entry.name,
                    'path': entry.path_display,
                    'type': 'folder' if isinstance(entry, dropbox.files.FolderMetadata) else 'file',
                    'size': getattr(entry, 'size', 0) if hasattr(entry, 'size') else 0
                }
                files.append(file_info)

            self._log('info', f"Listed {len(files)} files/folders in {path}")
            return files

        except ApiError as e:
            self._log('error', f"Dropbox API error: {str(e)}")
            return []
        except Exception as e:
            self._log('error', f"Error listing files in Dropbox: {str(e)}")
            import traceback
            self._log('error', f"Traceback: {traceback.format_exc()}")
            return []