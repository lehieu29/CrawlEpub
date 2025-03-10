import os
import re
import time
import random
import requests
import traceback
import json
import threading
import queue
from bs4 import BeautifulSoup
from ebooklib import epub
from tqdm.auto import tqdm
import uuid
import logging
from urllib.parse import urlparse, unquote

class NovelDownloader:
    def __init__(self, logger=None, socket=None, dropbox=None):
        self.logger = logger or logging.getLogger('novel_downloader')
        self.socket = socket
        self.dropbox = dropbox

        # Create temp folder for downloaded files
        self.temp_folder = os.path.join(os.getcwd(), 'novel_temp')
        os.makedirs(self.temp_folder, exist_ok=True)

        # Create output folder for final files
        self.output_folder = os.path.join(os.getcwd(), 'novel_output')
        os.makedirs(self.output_folder, exist_ok=True)

        # Set up queues for background processing
        self.save_queue = queue.Queue()
        self.exit_event = threading.Event()
        self.checkpoint_interval = 50

        # Start checkpoint saver thread
        self.saver_thread = threading.Thread(target=self._checkpoint_saver_thread, daemon=True)
        self.saver_thread.start()

    def _log(self, level, message, download_id=None):
        """Log a message and emit it via socket if available"""
        # Thêm biểu tượng emoji vào message dựa trên level
        if level == 'info':
            # Thêm biểu tượng cho các loại thông báo info
            if "Bắt đầu" in message or "Khởi tạo" in message or "Tạo" in message:
                message = f"🔵 {message}"
            elif "Hoàn thành" in message or "thành công" in message or "Đã lưu" in message:
                message = f"✅ {message}"
            elif "Tải" in message and "chương" in message:
                message = f"📥 {message}"
            elif "Tổng số" in message:
                message = f"📊 {message}"
            elif "Tìm thấy" in message:
                message = f"🔍 {message}"
            else:
                message = f"ℹ️ {message}"
        elif level == 'error':
            message = f"❌ {message}"
        elif level == 'warning':
            message = f"⚠️ {message}"

        if download_id:
            message = f"[{download_id}] {message}"

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
                'source': 'novel_downloader'
            })

    def _checkpoint_saver_thread(self):
        """Background thread for saving checkpoints"""
        while not self.exit_event.is_set():
            try:
                # Try to get a save task from the queue with timeout
                save_task = self.save_queue.get(timeout=1.0)
                if save_task:
                    book, intro, chapters, output_path, download_id = save_task
                    try:
                        # First save to local temp file
                        self._save_epub(book, intro, chapters, output_path, True, download_id)
                        
                        # If Dropbox is available, also save to Dropbox/Novel/Temp
                        if self.dropbox and self.dropbox.is_active:
                            filename = os.path.basename(output_path)
                            dropbox_temp_path = f"/Novel/Temp/{filename}"
                            
                            # Ensure the Temp folder exists
                            self.dropbox.create_folder("/Novel/Temp")
                            
                            # Upload the checkpoint to Dropbox
                            dropbox_url = self.dropbox.upload_file(output_path, dropbox_temp_path)
                            if dropbox_url:
                                self._log('info', f"Checkpoint also saved to Dropbox: {dropbox_url}", download_id)
                            else:
                                self._log('warning', "Failed to save checkpoint to Dropbox", download_id)
                        
                        self._log('info', f"Saved checkpoint after {len(chapters)} chapters", download_id)
                    except Exception as e:
                        self._log('error', f"Error saving checkpoint: {str(e)}", download_id)
                    self.save_queue.task_done()
            except queue.Empty:
                # No save task in queue, continue checking
                pass
            except Exception as e:
                self.logger.error(f"Error in checkpoint saver thread: {str(e)}")
                traceback.print_exc()

    def _generate_user_agent(self):
        """Generate a random user agent"""
        user_agents = [
            # Chrome
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/93.0.4577.63 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.81 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.159 Safari/537.36",
            # Firefox
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:90.0) Gecko/20100101 Firefox/90.0",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:91.0) Gecko/20100101 Firefox/91.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:89.0) Gecko/20100101 Firefox/89.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:90.0) Gecko/20100101 Firefox/90.0",
            # Safari
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Safari/605.1.15",
            # Edge
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36 Edg/91.0.864.59",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36 Edg/92.0.902.62",
            # Opera
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36 OPR/77.0.4054.254",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36 OPR/78.0.4093.112",
            # Mobile
            "Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Mobile/15E148 Safari/604.1",
            "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1",
            "Mozilla/5.0 (Linux; Android 11; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.120 Mobile Safari/537.36",
            "Mozilla/5.0 (Linux; Android 12; Pixel 5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.159 Mobile Safari/537.36"
        ]
        return random.choice(user_agents)
    
    def _delete_local_file(self, file_path, download_id=None):
        """Delete a local file after successful Dropbox upload"""
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                self._log('info', f"🗑️ Đã xóa tệp cục bộ sau khi tải lên Dropbox: {file_path}", download_id)
                return True
            else:
                self._log('warning', f"❓Không thể tìm thấy tệp cục bộ để xóa: {file_path}", download_id)
                return False
        except Exception as e:
            self._log('error', f"⚠️ Lỗi khi xóa tệp cục bộ: {str(e)}", download_id)
            return False

    def _delay(self, second, download_id=None):
        """Delay execution with a message"""
        self._log('info', f"⏳ Delay {second:.2f}s...", download_id)
        time.sleep(second)

    def _make_request(self, url, is_api=False, is_mtc=True, cookie='', download_id=None):
        """Make an HTTP request with appropriate headers"""
        try:
            headers = {
                'user-agent': self._generate_user_agent(),
                'referer': 'https://metruyencv.com/' if is_mtc else 'https://tangthuvien.net/'
            }

            # Add cookie if provided for metruyenchu
            if is_mtc and cookie:
                headers['cookie'] = 'accessToken=' + cookie

            # Add headers for API requests
            if is_api and is_mtc:
                headers['authorization'] = f'Bearer {cookie}'
                headers['accept'] = 'application/json, text/plain, */*'

            # Try up to 3 times if there's an error
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    response = requests.get(url, headers=headers)
                    response.raise_for_status()

                    # Return JSON for API requests, text otherwise
                    if is_api and is_mtc:
                        return response.json()
                    else:
                        return response.text
                except Exception as e:
                    error_message = f"Error loading page {url}, attempt {attempt+1}/{max_retries}: {str(e)}"
                    self._log('error', error_message, download_id)
                    if attempt < max_retries - 1:
                        delay_time = random.uniform(1, 2)
                        self._delay(delay_time, download_id)
                    else:
                        raise Exception(f"Failed after {max_retries} attempts: {str(e)}")
        except Exception as e:
            self._log('error', f"Unhandled error loading page {url}: {str(e)}", download_id)
            traceback.print_exc()
            raise

    def _detect_site_type(self, url):
        """Detect the type of website from the URL"""
        if "metruyencv.com" in url.lower():
            return "metruyenchu"
        elif "tangthuvien.net" in url.lower():
            return "tangthuvien"
        else:
            raise ValueError("Unsupported URL. Currently only metruyencv.com and tangthuvien.net are supported")

    def _check_existing_novel(self, epub_filename, download_id=None):
        """Check if novel already exists locally or in Dropbox, and load it if possible"""
        try:
            # Generate file paths
            safe_filename = re.sub(r'[\\/*?:"<>|]', "_", epub_filename)
            temp_epub_path = os.path.join(self.temp_folder, safe_filename)
            final_epub_path = os.path.join(self.output_folder, safe_filename)
            
            # Check paths to search
            check_paths = [final_epub_path, temp_epub_path]
            found_path = None
            
            # Check local files first
            for path in check_paths:
                if os.path.exists(path):
                    self._log('info', f"📄 Đã tìm thấy tệp EPUB trong: {path}", download_id)
                    found_path = path
                    break
            
            # If not found locally and Dropbox is active, check Dropbox
            if not found_path and self.dropbox and self.dropbox.is_active:
                # Check if file exists in Dropbox /Novel directory
                dropbox_path = f"/Novel/{safe_filename}"
                try:
                    # List files in the Novel directory
                    files = self.dropbox.list_files("/Novel")
                    for file in files:
                        if file['name'] == safe_filename:
                            self._log('info', f"📦 Đã tìm thấy EPUB trong Dropbox: {dropbox_path}", download_id)
                            
                            # Download the file to local temp
                            self._log('info', f"⬇️ Đang tải EPUB từ Dropbox...", download_id)
                            if self.dropbox.download_file(dropbox_path, temp_epub_path):
                                self._log('info', f"✅ Đã tải thành công EPUB hiện có từ Dropbox", download_id)
                                found_path = temp_epub_path
                            else:
                                self._log('warning', f"❌ Tải EPUB hiện có từ Dropbox thất bại", download_id)
                            break
                    
                    # Also check Temp directory
                    if not found_path:
                        files = self.dropbox.list_files("/Novel/Temp")
                        for file in files:
                            if file['name'] == safe_filename:
                                dropbox_temp_path = f"/Novel/Temp/{safe_filename}"
                                self._log('info', f"✅ Đã tìm thấy checkpoint hiện có trong Dropbox: {dropbox_temp_path}", download_id)
                                
                                # Download the file to local temp
                                if self.dropbox.download_file(dropbox_temp_path, temp_epub_path):
                                    self._log('info', f"✅ Đã tải thành công checkpoint từ Dropbox", download_id)
                                    found_path = temp_epub_path
                                else:
                                    self._log('warning', f"❌ Tải checkpoint từ Dropbox thất bại", download_id)
                                break
                except Exception as e:
                    self._log('warning', f"⚠️ Lỗi khi kiểm tra Dropbox để tìm EPUB hiện có: {str(e)}", download_id)
            
            # If we found a file, try to load it
            if found_path:
                try:
                    self._log('info', f"🔄 Đang đọc tệp EPUB hiện có: {found_path}", download_id)
                    book = epub.read_epub(found_path)
                    
                    # Find introduction page
                    intro = None
                    for item in book.items:
                        if isinstance(item, epub.EpubHtml) and item.file_name == 'intro.xhtml':
                            intro = item
                            # Ensure intro has an id
                            if not hasattr(intro, 'id') or not intro.id:
                                intro.id = 'intro'
                            self._log('info', f"📑 Đã tìm thấy trang giới thiệu", download_id)
                            break
                    
                    if not intro:
                        self._log('warning', f"❌ Không tìm thấy trang giới thiệu trong EPUB hiện có", download_id)
                    
                    # Find existing chapters
                    existing_chapters = []
                    for item in book.items:
                        if isinstance(item, epub.EpubHtml) and item.file_name.startswith('chapter_') and item.file_name.endswith('.xhtml'):
                            # Ensure chapter has id
                            if not hasattr(item, 'id') or not item.id:
                                try:
                                    chapter_num = int(item.file_name.split('_')[1].split('.')[0])
                                    item.id = f'chapter_{chapter_num}'
                                except Exception as e:
                                    self._log('warning', f"⚠️ Lỗi khi thiết lập ID chương: {str(e)}", download_id)
                            
                            existing_chapters.append(item)
                    
                    self._log('info', f"📚 Đã tìm thấy {len(existing_chapters)} chương hiện có", download_id)
                    
                    # Find max chapter number
                    max_chapter = 0
                    for chapter in existing_chapters:
                        try:
                            if hasattr(chapter, 'id') and chapter.id:
                                chapter_num = int(chapter.id.split('_')[1])
                            else:
                                chapter_num = int(chapter.file_name.split('_')[1].split('.')[0])
                            max_chapter = max(max_chapter, chapter_num)
                        except Exception as e:
                            self._log('warning', f"⚠️ Lỗi khi lấy số chương: {str(e)}", download_id)
                    
                    self._log('info', f"📖 Chương cuối cùng hiện có: Chương {max_chapter}", download_id)
                    
                    return book, intro, existing_chapters, max_chapter
                
                except Exception as e:
                    self._log('error', f"⚠️ Lỗi khi tải EPUB hiện có: {str(e)}", download_id)
                    traceback.print_exc()
            
            return None, None, [], 0
        
        except Exception as e:
            self._log('error', f"⚠️ Lỗi khi kiểm tra tiểu thuyết hiện có: {str(e)}", download_id)
            traceback.print_exc()
            return None, None, [], 0

    def _get_mtc_novel_info(self, url, cookie='', download_id=None):
        """Get novel information from Metruyenchu"""
        try:
            html = self._make_request(url, is_mtc=True, cookie=cookie, download_id=download_id)
            soup = BeautifulSoup(html, 'html.parser')

            # Get novel title
            title_elem = soup.select_one('h1 a')
            title = title_elem.text.strip() if title_elem else "Unknown"
            self._log('info', f"Novel title: {title}", download_id)

            # Get author name
            author_elem = soup.select_one('h1 ~ div')
            author = author_elem.text.strip() if author_elem else "Unknown"
            self._log('info', f"Author: {author}", download_id)

            # Get cover image URL
            cover_elem = soup.select_one('img.h-60')
            cover_url = cover_elem['src'] if cover_elem and 'src' in cover_elem.attrs else None
            self._log('info', f"Cover image: {'Yes' if cover_url else 'No'}", download_id)

            # Get synopsis
            synopsis_elem = soup.select_one('#synopsis .text-base')
            synopsis = synopsis_elem.get_text('\n', strip=True) if synopsis_elem else ""
            self._log('info', f"Synopsis: {'Yes' if synopsis else 'No'}", download_id)

            # Get book_id from the "Read from beginning" button
            read_button = soup.select_one('div button[title="Đọc từ đầu"]')
            book_id = None

            if read_button and read_button.parent:
                data_x_data = read_button.parent.get('data-x-data', '')
                book_id_match = re.search(r'readings\((\d+)\)', data_x_data)
                if book_id_match:
                    book_id = book_id_match.group(1)
                    self._log('info', f"Book ID: {book_id}", download_id)
                else:
                    self._log('warning', "Book ID not found in 'Read from beginning' button", download_id)
            else:
                self._log('warning', "'Read from beginning' button not found", download_id)

            # Get chapter list from API if book_id is available
            chapters_list = []
            if book_id:
                api_url = f"https://backend.metruyencv.com/api/chapters?filter[book_id]={book_id}"
                try:
                    api_data = self._make_request(api_url, is_api=True, is_mtc=True, cookie=cookie, download_id=download_id)
                    if 'data' in api_data and isinstance(api_data['data'], list):
                        chapters_list = api_data['data']
                        self._log('info', f"Retrieved information for {len(chapters_list)} chapters from API", download_id)
                except Exception as e:
                    self._log('error', f"Error getting chapter list from API: {str(e)}", download_id)

            return {
                'title': title,
                'author': author,
                'cover_url': cover_url,
                'synopsis': synopsis,
                'book_id': book_id,
                'chapters_list': chapters_list,
                'site_type': 'metruyenchu'
            }
        except Exception as e:
            self._log('error', f"Error getting novel information: {str(e)}", download_id)
            traceback.print_exc()
            raise

    def _get_ttv_novel_info(self, url, download_id=None):
        """Get novel information from Tangthuvien"""
        try:
            html = self._make_request(url, is_mtc=False, download_id=download_id)
            soup = BeautifulSoup(html, 'html.parser')

            # Get novel title
            title_elem = soup.select_one('h1')
            title = title_elem.text.strip() if title_elem else "Unknown"
            self._log('info', f"Novel title: {title}", download_id)

            # Default author
            author = "Unknown"

            # Get cover image URL
            cover_elem = soup.select_one('.book-img img')
            cover_url = cover_elem['src'] if cover_elem and 'src' in cover_elem.attrs else None
            self._log('info', f"Cover image: {'Yes' if cover_url else 'No'}", download_id)

            # Get synopsis
            synopsis_elem = soup.select_one('.book-intro')
            synopsis = synopsis_elem.get_text('\n', strip=True) if synopsis_elem else ""
            self._log('info', f"Synopsis: {'Yes' if synopsis else 'No'}", download_id)

            # Get book_id
            book_id_elem = soup.select_one('#story_id_hidden')
            book_id = book_id_elem['value'] if book_id_elem else None
            self._log('info', f"Book ID: {book_id or 'Not found'}", download_id)

            # Get total number of chapters
            total_chapters = 0
            catalog_elem = soup.select_one('#j-bookCatalogPage')
            if catalog_elem:
                chapter_count_match = re.search(r'Danh sách chương \((\d+) chương\)', catalog_elem.text)
                if chapter_count_match:
                    total_chapters = int(chapter_count_match.group(1))
                    self._log('info', f"Total chapters: {total_chapters}", download_id)

            # Get chapter list
            chapters_list = []
            if book_id and total_chapters > 0:
                chapters_url = f"https://tangthuvien.net/doc-truyen/page/{book_id}?page=0&limit={total_chapters}&web=1"
                try:
                    chapters_html = self._make_request(chapters_url, is_mtc=False, download_id=download_id)
                    chapters_soup = BeautifulSoup(chapters_html, 'html.parser')
                    chapter_links = chapters_soup.select('ul.cf > li > a')

                    for i, link in enumerate(chapter_links, 1):
                        chapter_url = link.get('href')
                        chapter_title = link.get('title') or f"Chapter {i}"

                        chapters_list.append({
                            'index': i,
                            'name': chapter_title,
                            'url': chapter_url
                        })

                    self._log('info', f"Retrieved information for {len(chapters_list)} chapters", download_id)
                except Exception as e:
                    self._log('error', f"Error getting chapter list from Tangthuvien: {str(e)}", download_id)

            return {
                'title': title,
                'author': author,
                'cover_url': cover_url,
                'synopsis': synopsis,
                'book_id': book_id,
                'chapters_list': chapters_list,
                'site_type': 'tangthuvien'
            }
        except Exception as e:
            self._log('error', f"Error getting novel information from Tangthuvien: {str(e)}", download_id)
            traceback.print_exc()
            raise

    def _extract_chapter_title(self, chapter_number, content=None, default_title=None):
        """Extract or create an appropriate chapter title"""
        # If we already have a good title, use it
        if default_title and default_title != f"Chapter {chapter_number}" and default_title != "":
            return default_title

        # Try to extract title from content if available
        if content:
            try:
                title_pattern = re.compile(r"Chương\s+\d+\s*[:\-]\s*(.*?)[\n\r]", re.IGNORECASE)
                match = title_pattern.search(content)
                if match:
                    return f"Chương {chapter_number}: {match.group(1).strip()}"
            except Exception as e:
                self.logger.warning(f"Error extracting title: {e}")

        # Default title with just the chapter number
        return f"Chương {chapter_number}"

    def _optimize_html_for_ereader(self, html_content):
        """Optimize HTML content for e-readers"""
        try:
            if not html_content:
                return html_content

            # Parse HTML
            soup = BeautifulSoup(html_content, 'html.parser')

            # Remove unnecessary attributes
            for tag in soup.find_all(True):
                allowed_attrs = ['id', 'class', 'href', 'src', 'alt']
                attrs = dict(tag.attrs)
                for attr in attrs:
                    if attr not in allowed_attrs:
                        del tag[attr]

            # Split long paragraphs
            for p in soup.find_all('p'):
                if len(p.get_text()) > 1000:  # If paragraph is too long
                    text = p.get_text()
                    p.clear()

                    # Split paragraph
                    sentences = re.split(r'(?<=[.!?])\s+', text)
                    current_p = p

                    for i, sentence in enumerate(sentences):
                        if i > 0 and i % 3 == 0:  # Every 3 sentences create a new paragraph
                            new_p = soup.new_tag('p')
                            current_p.insert_after(new_p)
                            current_p = new_p

                        if current_p.string:
                            current_p.string = current_p.string + " " + sentence
                        else:
                            current_p.string = sentence

            # Ensure spacing between paragraphs
            for p in soup.find_all('p'):
                p['style'] = 'margin-top: 0.5em; margin-bottom: 0.5em;'

            # Convert complex tags to simpler ones
            for tag in soup.find_all(['div', 'span']):
                if not tag.find_all(True):  # If it has no child tags
                    new_tag = soup.new_tag('p')
                    new_tag.string = tag.get_text()
                    tag.replace_with(new_tag)

            # Remove empty tags
            for tag in soup.find_all():
                if len(tag.get_text(strip=True)) == 0 and tag.name not in ['br', 'img', 'hr']:
                    tag.decompose()

            # Fix special characters
            for entity in soup.find_all(string=lambda text: '&' in text):
                new_text = entity.replace('&nbsp;', ' ')
                entity.replace_with(new_text)

            return str(soup)
        except Exception as e:
            self.logger.error(f"Error optimizing HTML: {e}")
            traceback.print_exc()
            return html_content  # Return original content if there's an error

    def _get_mtc_chapter_content(self, url, chapter_number, chapter_title=None, novel_title="", cookie='', download_id=None):
        """Get chapter content from Metruyenchu"""
        try:
            chapter_url = url + "/chuong-" + str(chapter_number)
            html = self._make_request(chapter_url, is_mtc=True, cookie=cookie, download_id=download_id)
            soup = BeautifulSoup(html, 'html.parser')

            # Get chapter title
            title_elem = soup.select_one('h2')
            base_title = title_elem.text.strip() if title_elem and title_elem.text else "Chương " + str(chapter_number)

            # Use title from API if available
            if chapter_title:
                base_title = chapter_title

            # Get chapter content
            content_elem = soup.select_one('[data-x-bind="ChapterContent"]')
            content = ""

            if content_elem:
                content = content_elem.get_text('\n', strip=True)

            if not content or len(content.strip()) == 0:
                # Use default content if not found
                content = "Không có nội dung. Chương này có thể bị khóa hoặc không tồn tại."
                self._log('warning', f"⚠️ Không tìm thấy nội dung cho chương {chapter_number}: Nội dung có thể bị khoá hoặc không tồn tại, sử dụng nội dung mặc định", download_id)

            # Extract better title if possible
            title = self._extract_chapter_title(chapter_number, content, base_title)

            # Format HTML content
            if content_elem:
                # Process p and br tags
                for p in content_elem.find_all('p'):
                    p.insert_after(soup.new_tag('br'))
                content_html = str(content_elem)

                # Optimize HTML for e-reader
                content_html = self._optimize_html_for_ereader(content_html)
            else:
                content_html = "<p>" + content + "</p>"

            # Log information
            self._log('info', f"✅ Đã tải chương {chapter_number}: {title} - Độ dài: {len(content)} ký tự", download_id)

            return {
                'title': title,
                'content': content,
                'content_html': content_html
            }
        except Exception as e:
            self._log('error', f"❌ Lỗi khi tải chương {chapter_number} từ Metruyenchu: {str(e)}", download_id)
            traceback.print_exc()
            raise

    def _get_ttv_chapter_content(self, chapter_info, novel_title="", download_id=None):
        """Get chapter content from Tangthuvien"""
        try:
            chapter_number = chapter_info['index']
            chapter_url = chapter_info['url']
            chapter_title = chapter_info['name']

            # Get HTML from the page
            html = self._make_request(chapter_url, is_mtc=False, download_id=download_id)

            # Parse content
            soup = BeautifulSoup(html, 'html.parser')

            # Clear head content to reduce debug file size
            if soup.head:
                soup.head.clear()
                soup.head.append(soup.new_tag('title'))
                soup.head.title.string = f"Debug HTML - Chapter {chapter_number}"

            # Novel content - try with main selector
            content_elem = soup.select_one('.box-chap')
            content = ""
            content_html = ""

            # If main selector not found, try alternative selector
            if not content_elem or not content_elem.text.strip():
                content_blocks = soup.select('p.content-block')

                if content_blocks:
                    self._log('info', f"ℹ️ Sử dụng selector thay thế cho chương {chapter_number}", download_id)

                    # Create content from p.content-block tags
                    content = "\n".join([block.get_text(strip=True) for block in content_blocks])

                    # Create new HTML with p tags
                    content_container = soup.new_tag('div')
                    content_container['class'] = 'chapter-content'

                    for block in content_blocks:
                        p = soup.new_tag('p')
                        p.string = block.get_text(strip=True)
                        content_container.append(p)

                    content_elem = content_container
                    content_html = str(content_container)
                else:
                    # Still no content found
                    content_elem = None

            # Process if content found with main selector
            if content_elem and not content:
                content = content_elem.get_text('\n', strip=True)

                # Create new HTML from text with \n converted to p tags
                if content:
                    # Split paragraphs by \n
                    paragraphs = content.split('\n')

                    # Create div to contain content
                    fixed_content_elem = soup.new_tag('div')
                    fixed_content_elem['class'] = 'chapter-content'

                    # Add each paragraph to a separate p tag
                    for paragraph in paragraphs:
                        # Skip empty lines
                        if paragraph.strip():
                            p = soup.new_tag('p')
                            p.string = paragraph.strip()
                            fixed_content_elem.append(p)

                    content_html = str(fixed_content_elem)
                else:
                    content_html = "<div class='chapter-content'></div>"

            # If no content could be retrieved, use default content
            if not content or len(content.strip()) == 0:
                # Use default content
                content = "Không có nội dung. Chương này có thể bị khóa hoặc không tồn tại."
                self._log('warning', f"⚠️ Không tìm thấy nội dung cho chương {chapter_number}: Nội dung có thể bị khoá hoặc không tồn tại", download_id)
                content_html = "<p>" + content + "</p>"

            # If content_html still not set (rare case)
            if not content_html:
                content_html = "<p>" + content.replace("\n\n", "</p><p>") + "</p>"

            # Extract better title if possible
            title = self._extract_chapter_title(chapter_number, content, chapter_title)

            # Optimize HTML for e-reader
            content_html = self._optimize_html_for_ereader(content_html)

            # Log information
            self._log('info', f"✅ Đã tải chương {chapter_number}: {title} - Độ dài: {len(content)} ký tự", download_id)

            return {
                'title': title,
                'content': content,
                'content_html': content_html
            }
        except Exception as e:
            self._log('error', f"❌ Lỗi khi tải chương {chapter_number} từ Tangthuvien: {str(e)}", download_id)
            traceback.print_exc()
            raise

    def _extract_title_from_html(self, html_content):
        """Extract title from HTML content, usually from h2 tag"""
        try:
            if not html_content:
                return None

            soup = BeautifulSoup(html_content, 'html.parser')

            # Look in title tag
            title_tag = soup.find('title')
            if title_tag and title_tag.text.strip():
                return title_tag.text.strip()

            return None
        except Exception as e:
            self.logger.warning(f"Error extracting title from HTML: {e}")
            return None

    def _get_novel_info(self, url, cookie='', download_id=None):
        """Get novel information (auto-detect site type)"""
        site_type = self._detect_site_type(url)
        if site_type == "metruyenchu":
            return self._get_mtc_novel_info(url, cookie, download_id)
        elif site_type == "tangthuvien":
            return self._get_ttv_novel_info(url, download_id)
        else:
            raise ValueError("Unsupported website type")

    def _get_chapter_content(self, url, chapter_info, site_type, novel_title, cookie='', download_id=None):
        """Get chapter content based on site type"""
        if site_type == 'metruyenchu':
            return self._get_mtc_chapter_content(url, chapter_info['index'], chapter_info.get('name'), novel_title, cookie, download_id)
        elif site_type == 'tangthuvien':
            return self._get_ttv_chapter_content(chapter_info, novel_title, download_id)
        else:
            raise ValueError(f"Unsupported website type: {site_type}")

    def _create_epub(self, novel_info, download_id=None):
        """Create a new EPUB file"""
        try:
            self._log('info', "📙 Bắt đầu tạo file EPUB mới...", download_id)
            book = epub.EpubBook()

            # Add metadata
            book_id = str(uuid.uuid4())
            book.set_identifier(book_id)
            book.set_title(novel_info['title'])
            book.set_language('vi')
            book.add_author(novel_info['author'])
            self._log('info', f"📝 Đã thêm metadata (id: {book_id[:8]}...)", download_id)

            # Add metadata for e-reader
            book.add_metadata(None, 'meta', '', {'name': 'fixed-layout', 'content': 'false'})
            book.add_metadata(None, 'meta', '', {'name': 'book-type', 'content': 'text'})
            book.add_metadata(None, 'meta', '', {'name': 'viewport', 'content': 'width=device-width, height=device-height'})

            # Download and add cover image
            if novel_info['cover_url']:
                try:
                    self._log('info', f"🖼️ Đang tải ảnh bìa từ: {novel_info['cover_url']}", download_id)
                    headers = {
                        'user-agent': self._generate_user_agent(),
                        'referer': 'https://metruyencv.com/'
                    }
                    cover_response = requests.get(novel_info['cover_url'], headers=headers)
                    cover_response.raise_for_status()
                    cover_content = cover_response.content

                    # Determine image format
                    parsed_url = urlparse(novel_info['cover_url'])
                    path = unquote(parsed_url.path)
                    _, ext = os.path.splitext(path)
                    if not ext:
                        ext = '.jpg'  # Default to jpg if no extension

                    book.set_cover("cover" + ext, cover_content)
                    self._log('info', f"✅ Đã thêm ảnh bìa ({len(cover_content)} bytes)", download_id)
                except Exception as e:
                    self._log('warning', f"⚠️ Lỗi khi tải ảnh bìa: {str(e)}", download_id)

            # Add introduction page
            self._log('info', "📄 Đang tạo trang giới thiệu...", download_id)
            intro = epub.EpubHtml(title='Giới thiệu', file_name='intro.xhtml')
            intro.id = 'intro'

            synopsis_html = '<p>Không có giới thiệu</p>'
            if novel_info['synopsis']:
                synopsis_html = '<p>' + novel_info['synopsis'].replace('\n', '</p><p>') + '</p>'

            intro_content = """
            <html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
            <head>
                <title>Giới thiệu</title>
                <meta charset="utf-8"/>
                <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
            </head>
            <body>
                <h1>""" + novel_info['title'] + """</h1>
                <p><strong>Tác giả:</strong> """ + novel_info['author'] + """</p>
                <h2>Giới thiệu</h2>
                """ + synopsis_html + """
            </body>
            </html>
            """
            intro.content = intro_content
            book.add_item(intro)

            # Add CSS optimized for e-reader
            self._log('info', "🎨 Đang thêm stylesheet...", download_id)
            style = """
            @namespace epub "http://www.idpf.org/2007/ops";

            html, body {
                margin: 0;
                padding: 0;
                font-family: serif;
                line-height: 1.5;
                text-align: justify;
                hyphens: auto;
                -webkit-hyphens: auto;
                -epub-hyphens: auto;
            }

            body {
                padding: 0% 3% 0% 3%;
                font-size: 1em;
                background-color: transparent;
            }

            h1, h2, h3, h4 {
                text-align: center;
                font-weight: bold;
                margin: 1em 0;
                page-break-after: avoid;
                page-break-inside: avoid;
                break-after: avoid;
            }

            h1 { font-size: 1.5em; }
            h2 { font-size: 1.3em; }

            p {
                margin: 0;
                padding: 0;
                text-indent: 1.5em;
                text-align: justify;
                orphans: 2;
                widows: 2;
                line-height: 1.5em;
            }

            p + p {
                margin-top: 0.3em;
            }

            div.page-break {
                page-break-after: always;
                break-after: page;
            }
            """
            css = epub.EpubItem(uid="style", file_name="style/style.css", media_type="text/css", content=style)
            book.add_item(css)

            # Add nav
            book.add_item(epub.EpubNcx())
            book.add_item(epub.EpubNav())

            self._log('info', "✅ Đã tạo xong cấu trúc EPUB cơ bản", download_id)
            return book, intro
        except Exception as e:
            self._log('error', f"❌ Lỗi khi tạo file EPUB: {str(e)}", download_id)
            traceback.print_exc()
            raise
    
    def _add_chapter_to_epub(self, book, chapter_data, chapter_number, download_id=None):
        """Add a chapter to the EPUB book"""
        try:
            chapter_id = 'chapter_' + str(chapter_number)

            # Get better title from content if possible
            title = self._extract_chapter_title(chapter_number, chapter_data['content'], chapter_data['title'])

            chapter = epub.EpubHtml(title=title, file_name='chapter_' + str(chapter_number) + '.xhtml')
            chapter.id = chapter_id

            content_html = "<p>No content</p>"
            if 'content_html' in chapter_data:
                content_html = chapter_data['content_html']

            # Check if content_html already contains the chapter title
            title_present = False
            try:
                soup = BeautifulSoup(content_html, 'html.parser')

                # Check if title appears in heading tags
                for heading in soup.find_all(['h1', 'h2', 'h3']):
                    if title.lower() in heading.get_text().lower():
                        title_present = True
                        break

                # If not found in headings, check first paragraphs
                if not title_present:
                    # Check first two paragraphs
                    first_paragraphs = soup.find_all('p', limit=2)
                    for p in first_paragraphs:
                        if title.lower() in p.get_text().lower():
                            # Title is in content but not as heading
                            # Convert p to h2
                            p.name = 'h2'
                            title_present = True
                            # Update content_html with modified soup
                            content_html = str(soup)
                            break
            except Exception as e:
                self.logger.warning(f"Error parsing HTML to check for title: {e}")

            # If title still not present, add it to beginning of content
            if not title_present:
                title_html = f"<h2>{title}</h2>"
                content_html = title_html + content_html

            # Prepare optimized HTML content for e-reader
            chapter_content = """
            <html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
            <head>
                <title>""" + title + """</title>
                <meta charset="utf-8"/>
                <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
            </head>
            <body>
                """ + content_html + """
            </body>
            </html>
            """
            chapter.content = chapter_content
            book.add_item(chapter)

            return chapter
        except Exception as e:
            self._log('error', f"Error adding chapter {chapter_number} to EPUB: {str(e)}", download_id)
            traceback.print_exc()
            raise

    def _fix_navigation_files(self, book, is_temp, download_id=None):
        """Fix navigation files to ensure all chapters have appropriate titles"""
        try:
            # Get all chapters and extract full titles from content
            chapter_titles = {}
            for item in book.items:
                if isinstance(item, epub.EpubHtml) and hasattr(item, 'id') and item.id and item.id.startswith('chapter_'):
                    try:
                        chapter_num = int(item.id.split('_')[1])

                        # Prioritize extracting title from HTML content
                        full_title = None
                        if hasattr(item, 'content') and item.content:
                            full_title = self._extract_title_from_html(item.content)

                        # If not found from HTML, use existing title
                        if not full_title and hasattr(item, 'title') and item.title:
                            full_title = item.title

                        # If still no title, create default
                        if not full_title:
                            full_title = f"Chương {chapter_num}"

                        # Save extracted title
                        chapter_titles[chapter_num] = full_title

                        # Update chapter title
                        item.title = full_title

                    except Exception as e:
                        self.logger.warning(f"Error processing chapter {item.id}: {e}")

            if not chapter_titles:
                self._log('warning', "No chapters found to update navigation", download_id)
                return False

            if not is_temp:
                self._log('info', f"Found {len(chapter_titles)} chapters with titles to update navigation", download_id)

            # Create new nav.xhtml content if needed
            nav_content = """<?xml version='1.0' encoding='utf-8'?>
            <!DOCTYPE html>
            <html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" lang="vi" xml:lang="vi">
              <head>
                <title>{title}</title>
                <meta charset="utf-8"/>
              </head>
              <body>
                <nav epub:type="toc" id="id" role="doc-toc">
                  <h2>{title}</h2>
                  <ol>
                    <li>
                      <a href="intro.xhtml">Introduction</a>
                    </li>
                    {chapter_items}
                  </ol>
                </nav>
              </body>
            </html>
            """

            # Create new toc.ncx content if needed
            toc_content = """<?xml version='1.0' encoding='utf-8'?>
            <ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
              <head>
                <meta content="{uuid}" name="dtb:uid"/>
                <meta content="0" name="dtb:depth"/>
                <meta content="0" name="dtb:totalPageCount"/>
                <meta content="0" name="dtb:maxPageNumber"/>
              </head>
              <docTitle>
                <text>{title}</text>
              </docTitle>
              <navMap>
                <navPoint id="intro">
                  <navLabel>
                    <text>Introduction</text>
                  </navLabel>
                  <content src="intro.xhtml"/>
                </navPoint>
                {chapter_items}
              </navMap>
            </ncx>
            """

            # Find and update nav.xhtml
            nav_item = None
            for item in book.items:
                if isinstance(item, epub.EpubHtml) and item.file_name == 'nav.xhtml':
                    nav_item = item
                    break

            title = book.title if hasattr(book, 'title') else "Novel EPUB"

            if nav_item:
                try:
                    if hasattr(nav_item, 'content') and nav_item.content:
                        soup = BeautifulSoup(nav_item.content, 'html.parser')
                        links = soup.select('nav ol li a')

                        for link in links:
                            href = link.get('href', '')
                            if href.startswith('chapter_') and href.endswith('.xhtml'):
                                try:
                                    chapter_num = int(href.split('_')[1].split('.')[0])
                                    if chapter_num in chapter_titles and chapter_titles[chapter_num]:
                                        link.string = chapter_titles[chapter_num]
                                except:
                                    pass

                        nav_item.content = str(soup)
                        if not is_temp:
                            self._log('info', "Updated nav.xhtml with correct chapter titles", download_id)
                    else:
                        # Create new nav.xhtml content
                        chapter_items = ""
                        for num in sorted(chapter_titles.keys()):
                            chapter_items += f"""
                            <li>
                              <a href="chapter_{num}.xhtml">{chapter_titles[num]}</a>
                            </li>"""

                        nav_item.content = nav_content.format(
                            title=title,
                            chapter_items=chapter_items
                        )
                        if not is_temp:
                            self._log('info', "Created new nav.xhtml content", download_id)
                except Exception as e:
                    self._log('warning', f"Error updating nav.xhtml: {e}", download_id)
            else:
                self._log('warning', "nav.xhtml not found in EPUB", download_id)

            # Find and update toc.ncx
            toc_item = None
            for item in book.items:
                if item.file_name == 'toc.ncx':
                    toc_item = item
                    break

            if toc_item:
                try:
                    if hasattr(toc_item, 'content') and toc_item.content:
                        soup = BeautifulSoup(toc_item.content, 'xml')
                        navpoints = soup.select('navPoint')

                        for navpoint in navpoints:
                            nav_id = navpoint.get('id', '')
                            if nav_id.startswith('chapter_'):
                                try:
                                    chapter_num = int(nav_id.split('_')[1])
                                    if chapter_num in chapter_titles and chapter_titles[chapter_num]:
                                        text_tag = navpoint.select_one('navLabel text')
                                        if text_tag:
                                            text_tag.string = chapter_titles[chapter_num]
                                except:
                                    pass

                        toc_item.content = str(soup)
                        if not is_temp:
                            self._log('info', "Updated toc.ncx with correct chapter titles", download_id)
                    else:
                        # Create new toc.ncx content
                        chapter_items = ""
                        for num in sorted(chapter_titles.keys()):
                            chapter_items += f"""
                            <navPoint id="chapter_{num}">
                              <navLabel>
                                <text>{chapter_titles[num]}</text>
                              </navLabel>
                              <content src="chapter_{num}.xhtml"/>
                            </navPoint>"""

                        book_uuid = book.get_metadata('DC', 'identifier')[0][0] if hasattr(book, 'get_metadata') else str(uuid.uuid4())

                        toc_item.content = toc_content.format(
                            uuid=book_uuid,
                            title=title,
                            chapter_items=chapter_items
                        )
                        if not is_temp:
                            self._log('info', "Created new toc.ncx content", download_id)
                except Exception as e:
                    self._log('warning', f"Error updating toc.ncx: {e}", download_id)
            else:
                self._log('warning', "toc.ncx not found in EPUB", download_id)

            return True
        except Exception as e:
            self._log('error', f"Error fixing navigation files: {e}", download_id)
            traceback.print_exc()
            return False

    def _split_large_chapters(self, book, is_temp, download_id=None):
        """Split large chapters into smaller parts to avoid performance issues on e-readers"""
        try:
            modified = False
            large_chapters = []

            # Find chapters that are too large
            for item in book.items:
                if isinstance(item, epub.EpubHtml) and hasattr(item, 'id') and item.id.startswith('chapter_'):
                    if hasattr(item, 'content') and item.content and len(item.content) > 100000:  # ~100KB
                        large_chapters.append(item)

            if not large_chapters:
                return False

            if not is_temp:
                self._log('info', f"Found {len(large_chapters)} large chapters that need to be split", download_id)

            # Process each large chapter
            for chapter in large_chapters:
                try:
                    chapter_num = int(chapter.id.split('_')[1])
                    soup = BeautifulSoup(chapter.content, 'html.parser')

                    # Get body section
                    body = soup.find('body')
                    if not body:
                        continue

                    # Get title
                    title_tag = soup.find('h2')
                    title = title_tag.get_text() if title_tag else chapter.title

                    # Get all paragraphs
                    paragraphs = body.find_all('p')

                    if len(paragraphs) < 20:  # Not enough paragraphs to split
                        continue

                    # Split into parts
                    parts = []
                    part_size = max(10, len(paragraphs) // 3)  # At least 10 paragraphs per part, max 3 parts

                    for i in range(0, len(paragraphs), part_size):
                        part_paragraphs = paragraphs[i:i+part_size]
                        if not part_paragraphs:
                            continue

                        part_soup = BeautifulSoup("""
                        <html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
                        <head>
                            <title></title>
                            <meta charset="utf-8"/>
                        </head>
                        <body></body>
                        </html>
                        """, 'html.parser')

                        part_soup.title.string = title

                        # Add title to first part
                        if i == 0 and title_tag:
                            part_soup.body.append(title_tag)
                        # Add subtitle to later parts
                        else:
                            part_title = part_soup.new_tag('h3')
                            part_title.string = f"{title} (continued)"
                            part_soup.body.append(part_title)

                        # Add paragraphs
                        for p in part_paragraphs:
                            part_soup.body.append(p)

                        # Add page break at end
                        page_break = part_soup.new_tag('div')
                        page_break['style'] = 'page-break-after: always; break-after: page;'
                        part_soup.body.append(page_break)

                        parts.append(str(part_soup))

                    if len(parts) <= 1:  # No need to split if only one part
                        continue

                    # Create sub-chapters
                    for i, part_content in enumerate(parts):
                        sub_id = f"chapter_{chapter_num}_{i+1}"
                        sub_filename = f"chapter_{chapter_num}_{i+1}.xhtml"

                        # Name for part
                        if i == 0:
                            sub_title = title
                        else:
                            sub_title = f"{title} (part {i+1})"

                        sub_chapter = epub.EpubHtml(title=sub_title, file_name=sub_filename)
                        sub_chapter.id = sub_id
                        sub_chapter.content = part_content
                        book.add_item(sub_chapter)

                    # Replace original chapter in spine
                    spine_index = book.spine.index(chapter) if chapter in book.spine else -1
                    if spine_index > 0:
                        # Remove original chapter
                        book.spine.pop(spine_index)

                        # Add sub-chapters at that position
                        for i in range(len(parts)):
                            sub_id = f"chapter_{chapter_num}_{i+1}"
                            for item in book.items:
                                if hasattr(item, 'id') and item.id == sub_id:
                                    book.spine.insert(spine_index + i, item)

                    # Mark as modified
                    modified = True
                    if not is_temp:
                        self._log('info', f"Split chapter {chapter_num} into {len(parts)} parts", download_id)

                except Exception as e:
                    self._log('warning', f"Error splitting chapter {chapter.id}: {e}", download_id)

            return modified
        except Exception as e:
            self._log('error', f"Error splitting chapters: {e}", download_id)
            traceback.print_exc()
            return False

    def _save_epub(self, book, intro, chapters, output_path, is_temp, download_id=None):
        """Save EPUB file"""
        try:
            if not is_temp:
                self._log('info', f"Saving EPUB to: {output_path}", download_id)

            # Clear old spine and create new one to ensure correct order
            book.spine = [('nav', 'nav')]
            book.spine.append(intro)

            # Add chapters to spine in order
            # Ensure all chapters have id attribute
            for chapter in chapters:
                if not hasattr(chapter, 'id') or not chapter.id:
                    chapter_num = int(chapter.file_name.split('_')[1].split('.')[0])
                    chapter.id = 'chapter_' + str(chapter_num)

                # Ensure all chapters have appropriate titles
                if not hasattr(chapter, 'title') or not chapter.title or chapter.title == "":
                    chapter_num = int(chapter.id.split('_')[1])
                    # Extract title from HTML content if possible
                    if hasattr(chapter, 'content') and chapter.content:
                        full_title = self._extract_title_from_html(chapter.content)
                        if full_title:
                            chapter.title = full_title
                        else:
                            chapter.title = f"Chương {chapter_num}"
                    else:
                        chapter.title = f"Chương {chapter_num}"

            # Sort chapters by number
            try:
                sorted_chapters = sorted(chapters, key=lambda x: int(x.id.split('_')[1]))
            except Exception as e:
                self.logger.warning(f"Error sorting chapters: {e}")
                # Fallback: sort by filename
                sorted_chapters = sorted(chapters,
                    key=lambda x: int(re.search(r'chapter_(\d+)', x.file_name).group(1))
                        if re.search(r'chapter_(\d+)', x.file_name) else 0
                )

            for chapter in sorted_chapters:
                book.spine.append(chapter)

            if not is_temp:
                self._log('info', f"Total chapters in spine: {len(sorted_chapters)}", download_id)

            # Create table of contents
            toc = [epub.Link('intro.xhtml', 'Introduction', 'intro')]
            for chapter in sorted_chapters:
                toc.append(epub.Link(chapter.file_name, chapter.title, chapter.id))

            book.toc = toc

            if not is_temp:
                self._log('info', f"Created table of contents with {len(toc)} items", download_id)

            # Fix navigation files before saving
            self._fix_navigation_files(book, is_temp, download_id)

            # Split large chapters
            self._split_large_chapters(book, is_temp, download_id)

            # Save EPUB
            try:
                epub.write_epub(output_path, book, {})

                if not is_temp:
                    self._log('info', f"Successfully saved EPUB to: {output_path}", download_id)

                # Check file size
                if not is_temp:
                    file_size = os.path.getsize(output_path)
                    self._log('info', f"File size: {round(file_size / (1024*1024), 2)} MB", download_id)

                return True
            except Exception as e:
                self._log('error', f"Error writing EPUB file: {str(e)}", download_id)
                traceback.print_exc()
                raise
        except Exception as e:
            self._log('error', f"Error saving EPUB: {str(e)}", download_id)
            traceback.print_exc()
            raise

    def download_novel(self, url, cookie='', download_id=None):
        """Main method to download a novel"""
        try:
            self._log('info', "🚀 Bắt đầu quá trình tải truyện...", download_id)

            # Get novel information
            self._log('info', "📚 Đang lấy thông tin truyện...", download_id)
            novel_info = self._get_novel_info(url, cookie, download_id)

            # Check if chapter list is available
            if not novel_info['chapters_list']:
                error_msg = "❌ Không thể lấy danh sách chương truyện"
                self._log('error', error_msg, download_id)
                return {'success': False, 'error': error_msg}

            total_chapters = len(novel_info['chapters_list'])
            self._log('info', f"📚 Tổng số chương: {total_chapters}", download_id)

            # Get website type
            site_type = novel_info['site_type']
            self._log('info', f"🌐 Loại trang web: {site_type}", download_id)

            # Sort chapters by index
            sorted_chapters = sorted(novel_info['chapters_list'], key=lambda x: x.get('index', 0))

            # EPUB filename
            epub_filename = novel_info['title'].strip() + ".epub"
            safe_filename = re.sub(r'[\\/*?:"<>|]', "_", epub_filename)
            temp_epub_path = os.path.join(self.temp_folder, safe_filename)
            final_epub_path = os.path.join(self.output_folder, safe_filename)
            
            # Check if novel already exists and load it
            existing_book, existing_intro, existing_chapters, max_existing_chapter = self._check_existing_novel(epub_filename, download_id)
            
            if existing_book and existing_intro and existing_chapters:
                book = existing_book
                intro = existing_intro
                self._log('info', f"📕 Đã tìm thấy truyện đã tải trước đó với {len(existing_chapters)} chương", download_id)
                self._log('info', f"📕 Sẽ tiếp tục tải từ chương {max_existing_chapter + 1}", download_id)
            else:
                # Create new EPUB
                self._log('info', "📕 Đang tạo file EPUB mới...", download_id)
                book, intro = self._create_epub(novel_info, download_id)
                existing_chapters = []
                max_existing_chapter = 0
            
            # Filter chapters to download (only chapters after the max existing chapter)
            chapters_to_download = [chapter for chapter in sorted_chapters if chapter.get('index', 0) > max_existing_chapter]
            
            if not chapters_to_download:
                self._log('info', "✅ Tất cả các chương đã có, không cần tải thêm", download_id)
                # Still save EPUB to update navigation and optimize
                all_chapters = existing_chapters
                self._save_epub(book, intro, all_chapters, final_epub_path, False, download_id)
                
                # Upload to Dropbox if available
                dropbox_url = None
                if self.dropbox and self.dropbox.is_active:
                    try:
                        self._log('info', "☁️ Đang tải EPUB lên Dropbox...", download_id)
                        dropbox_path = f"/Novel/{safe_filename}"
                        dropbox_url = self.dropbox.upload_file(final_epub_path, dropbox_path)
                        if dropbox_url:
                            self._log('info', f"☁️ EPUB đã được tải lên Dropbox: {dropbox_url}", download_id)
                            
                            # Delete local file after successful upload
                            self._delete_local_file(final_epub_path, download_id)
                        else:
                            self._log('warning', "⚠️ Không thể tạo URL tải xuống Dropbox", download_id)
                    except Exception as e:
                        self._log('warning', f"⚠️ Lỗi khi tải lên Dropbox: {str(e)}", download_id)
                
                return {
                    'success': True,
                    'file_path': final_epub_path,
                    'dropbox_url': dropbox_url,
                    'title': novel_info['title'],
                    'author': novel_info['author'],
                    'chapter_count': len(all_chapters),
                    'message': "All chapters already exist"
                }
            
            self._log('info', f"📥 Cần tải {len(chapters_to_download)} chương mới", download_id)
            
            # Download chapters
            new_chapters = []

            for chapter_info in tqdm(chapters_to_download, desc="Đang tải chương"):
                try:
                    chapter_index = chapter_info.get('index')
                    self._log('info', f"📥 Đang tải chương {chapter_index}: {chapter_info.get('name', 'Không tên')}", download_id)

                    # Download chapter content
                    chapter_data = self._get_chapter_content(url, chapter_info, site_type, novel_info['title'], cookie, download_id)

                    # Add chapter to EPUB
                    chapter = self._add_chapter_to_epub(book, chapter_data, chapter_index, download_id)
                    new_chapters.append(chapter)

                    # Save checkpoint every 50 chapters
                    if len(new_chapters) % self.checkpoint_interval == 0:
                        all_chapters = existing_chapters + new_chapters
                        self.save_queue.put((book, intro, all_chapters, temp_epub_path, download_id))
                        self._log('info', f"💾 Đã lên lịch lưu điểm kiểm tra sau khi tải {len(new_chapters)} chương", download_id)

                    # Short delay between requests to avoid being blocked
                    delay_time = random.uniform(0.5, 1)
                    self._delay(delay_time, download_id)

                except Exception as e:
                    self._log('error', f"Lỗi khi tải chương {chapter_index}: {str(e)}", download_id)
                    traceback.print_exc()

                    # Save current state if error occurs
                    try:
                        all_chapters = existing_chapters + new_chapters
                        self.save_queue.put((book, intro, all_chapters, temp_epub_path, download_id))
                        self.save_queue.join()
                        self._log('warning', f"💾 Đã lưu trạng thái sau khi tải {len(new_chapters)} chương do lỗi", download_id)
                    except Exception as save_err:
                        self._log('error', f"Lỗi khi lưu trạng thái sau khi gặp lỗi: {str(save_err)}", download_id)

            # Combine existing and new chapters
            all_chapters = existing_chapters + new_chapters

            # Save final EPUB
            self._log('info', "🏁 Tải xuống hoàn tất, đang lưu EPUB cuối cùng...", download_id)
            self._save_epub(book, intro, all_chapters, final_epub_path, False, download_id)

            # Upload to Dropbox if available
            dropbox_url = None
            if self.dropbox and self.dropbox.is_active:
                try:
                    self._log('info', "☁️ Đang tải EPUB lên Dropbox...", download_id)
                    dropbox_path = f"/Novel/{safe_filename}"
                    dropbox_url = self.dropbox.upload_file(final_epub_path, dropbox_path)
                    if dropbox_url:
                        self._log('info', f"☁️ EPUB đã được tải lên Dropbox: {dropbox_url}", download_id)
                        
                        # Delete local file after successful upload
                        self._delete_local_file(final_epub_path, download_id)
                        
                        # Also delete temp files
                        self._delete_local_file(temp_epub_path, download_id)
                    else:
                        self._log('warning', "⚠️ Không thể tạo URL tải xuống Dropbox", download_id)
                except Exception as e:
                    self._log('warning', f"⚠️ Lỗi khi tải lên Dropbox: {str(e)}", download_id)
            else:
                self._log('info', "⚠️ Tích hợp Dropbox không hoạt động, file chỉ được lưu cục bộ", download_id)

            self._log('info', f"🎉🎉🎉 Tải xuống hoàn tất! Truyện đã được lưu tại: {final_epub_path}", download_id)

            return {
                'success': True,
                'file_path': final_epub_path,
                'dropbox_url': dropbox_url,
                'title': novel_info['title'],
                'author': novel_info['author'],
                'chapter_count': len(all_chapters)
            }
        except Exception as e:
            error_msg = f"Lỗi không xử lý được trong quá trình tải xuống: {str(e)}"
            self._log('error', error_msg, download_id)
            traceback.print_exc()
            return {'success': False, 'error': error_msg}
        finally:
            # Ensure threads exit cleanly
            self.exit_event.set()
