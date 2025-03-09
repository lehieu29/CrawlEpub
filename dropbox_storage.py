import os
import logging
import dropbox
from dropbox.exceptions import ApiError, AuthError
from dropbox.files import WriteMode
import time
import json

class DropboxStorage:
    def __init__(self, access_token=None):
        self.logger = logging.getLogger('dropbox_storage')
        self.access_token = access_token
        self._initialize_client()

    def _initialize_client(self):
        """Initialize Dropbox client if access token is available"""
        if self.access_token:
            try:
                # Log token length for debugging
                token_length = len(self.access_token) if self.access_token else 0
                self.logger.info(f"Khởi tạo Dropbox với token (độ dài: {token_length} chars)")
                
                # Log first and last 5 chars of token (safe for debugging without exposing full token)
                # if token_length > 10:
                #    token_prefix = self.access_token[:5]
                #    token_suffix = self.access_token[-5:]
                #    self.logger.info(f"Token starts with '{token_prefix}...' and ends with '...{token_suffix}'")

                self.dbx = dropbox.Dropbox(self.access_token)

                # Check if the access token is valid
                self.logger.info("Đang cố gắng lấy thông tin tài khoản để xác minh mã token...")
                account = self.dbx.users_get_current_account()
                self.logger.info(f"Dropbox đã được kết nối cho tài khoản: {account.name.display_name} (Email: {account.email})")
                self.is_active = True
            except AuthError as e:
                self.logger.error(f"Lỗi xác thực Dropbox: {str(e)}")
                self.logger.error("Mã token truy cập Dropbox không hợp lệ hoặc quyền truy cập không đủ.")
                self.is_active = False
            except Exception as e:
                self.logger.error(f"Lỗi khi khởi tạo Dropbox: {str(e)}")
                import traceback
                self.logger.error(f"Traceback: {traceback.format_exc()}")
                self.is_active = False
        else:
            self.logger.warning("Không cung cấp mã token truy cập Dropbox")
            self.is_active = False

    def upload_file(self, local_path, dropbox_path):
        """
        Upload a file to Dropbox

        Args:
            local_path: Path to the local file
            dropbox_path: Path where the file should be saved in Dropbox

        Returns:
            Shared link URL if successful, None otherwise
        """
        if not self.is_active:
            self.logger.warning("Dropbox integration not active")
            return None

        try:
            # Check if file exists
            if not os.path.exists(local_path):
                self.logger.error(f"File not found: {local_path}")
                return None

            # Get file size and details
            file_size = os.path.getsize(local_path)
            file_name = os.path.basename(local_path)
            self.logger.info(f"Uploading file: {file_name} ({file_size / (1024*1024):.2f} MB)")
            self.logger.info(f"Local path: {local_path}")
            self.logger.info(f"Dropbox path: {dropbox_path}")

            # Read file contents
            with open(local_path, 'rb') as f:
                file_content = f.read()

            self.logger.info(f"File read successfully, content length: {len(file_content)} bytes")

            # Upload the file
            self.logger.info("Starting Dropbox upload...")
            upload_start = time.time()
            upload_result = self.dbx.files_upload(
                file_content,
                dropbox_path,
                mode=WriteMode('overwrite')
            )
            upload_time = time.time() - upload_start

            # Log upload result
            self.logger.info(f"Upload completed in {upload_time:.2f} seconds")
            self.logger.info(f"Upload result: {upload_result}")
            self.logger.info(f"File uploaded successfully to {dropbox_path}")

            # Create a shared link
            self.logger.info("Creating shared link...")
            shared_link_start = time.time()
            try:
                shared_link = self.dbx.sharing_create_shared_link_with_settings(dropbox_path)
                shared_link_time = time.time() - shared_link_start
                self.logger.info(f"Shared link created in {shared_link_time:.2f} seconds")
                self.logger.info(f"Shared link result: {shared_link}")

                link_url = shared_link.url

                # Convert dropbox.com links to dl.dropboxusercontent.com links for direct download
                if link_url.startswith('https://www.dropbox.com'):
                    dl_url = link_url.replace('www.dropbox.com', 'dl.dropboxusercontent.com')
                    dl_url = dl_url.replace('?dl=0', '')
                    self.logger.info(f"Converted URL for direct download: {dl_url}")
                else:
                    dl_url = link_url
                    self.logger.info(f"Using original URL (no conversion needed): {dl_url}")

                return dl_url
            except Exception as e:
                self.logger.error(f"Error creating shared link: {str(e)}")
                self.logger.error(f"Will try alternate method to create shared link...")

                # Try alternate method for shared link
                try:
                    sharing_info = self.dbx.sharing_get_shared_links(dropbox_path)
                    self.logger.info(f"Got existing sharing info: {sharing_info}")

                    if sharing_info.links:
                        link_url = sharing_info.links[0].url
                        self.logger.info(f"Found existing shared link: {link_url}")

                        # Convert URL for direct download
                        if link_url.startswith('https://www.dropbox.com'):
                            dl_url = link_url.replace('www.dropbox.com', 'dl.dropboxusercontent.com')
                            dl_url = dl_url.replace('?dl=0', '')
                        else:
                            dl_url = link_url

                        return dl_url
                    else:
                        self.logger.error("No existing shared links found")
                        return None
                except Exception as alt_e:
                    self.logger.error(f"Alternate method also failed: {str(alt_e)}")
                    return None

        except ApiError as e:
            self.logger.error(f"Dropbox API error: {str(e)}")
            error_details = getattr(e, 'error', None)
            if error_details:
                try:
                    self.logger.error(f"API Error details: {json.dumps(error_details.to_dict())}")
                except:
                    self.logger.error(f"API Error details (non-serializable): {error_details}")
            return None
        except Exception as e:
            self.logger.error(f"Error uploading file to Dropbox: {str(e)}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")
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
            self.logger.warning("Dropbox integration not active")
            return False

        try:
            self.logger.info(f"Downloading file: {dropbox_path} to {local_path}")

            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(local_path), exist_ok=True)

            # Download the file
            download_start = time.time()
            self.dbx.files_download_to_file(local_path, dropbox_path)
            download_time = time.time() - download_start

            # Log download info
            file_size = os.path.getsize(local_path) if os.path.exists(local_path) else 0
            self.logger.info(f"File downloaded in {download_time:.2f} seconds")
            self.logger.info(f"Downloaded file size: {file_size / (1024*1024):.2f} MB")
            self.logger.info(f"File downloaded successfully to {local_path}")
            return True

        except ApiError as e:
            self.logger.error(f"Dropbox API error: {str(e)}")
            return False
        except Exception as e:
            self.logger.error(f"Error downloading file from Dropbox: {str(e)}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")
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
            self.logger.warning("Dropbox integration not active")
            return False

        try:
            self.logger.info(f"Creating folder: {path}")
            folder_result = self.dbx.files_create_folder_v2(path)
            self.logger.info(f"Folder created successfully: {path}")
            self.logger.info(f"Folder creation result: {folder_result}")
            return True

        except ApiError as e:
            # Ignore error if folder already exists
            if isinstance(e.error, dropbox.files.CreateFolderError) and e.error.is_path() and e.error.get_path().is_conflict():
                self.logger.info(f"Folder already exists: {path}")
                return True
            else:
                self.logger.error(f"Dropbox API error: {str(e)}")
                return False
        except Exception as e:
            self.logger.error(f"Error creating folder in Dropbox: {str(e)}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")
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
            self.logger.warning("Dropbox integration not active")
            return []

        try:
            self.logger.info(f"Listing files in: {path}")
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

            self.logger.info(f"Listed {len(files)} files/folders in {path}")
            return files

        except ApiError as e:
            self.logger.error(f"Dropbox API error: {str(e)}")
            return []
        except Exception as e:
            self.logger.error(f"Error listing files in Dropbox: {str(e)}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            return []