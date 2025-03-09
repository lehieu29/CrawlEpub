!pip install requests beautifulsoup4 ebooklib tqdm lxml

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
from google.colab import drive
from google.colab import userdata
from ebooklib import epub
from IPython.display import display, HTML
from tqdm.notebook import tqdm
import uuid
from urllib.parse import urlparse, unquote

# Mount Google Drive
drive.mount('/content/drive')

# Create a queue and event for checkpoint saving
save_queue = queue.Queue()
exit_event = threading.Event()

# Tạo queue cho việc lưu file debug
debug_save_queue = queue.Queue()
debug_save_event = threading.Event()

# Lưu checkpoint mỗi 50 chương
checkpoint_interval = 50

# Tạo thư mục nếu chưa tồn tại
temp_folder = '/content/drive/My Drive/Book/Novel/Temp'
main_folder = '/content/drive/My Drive/Book/Novel'
os.makedirs(temp_folder, exist_ok=True)
os.makedirs(main_folder, exist_ok=True)

# Hàm tạm dừng có thông báo
def delay(second):
    """Tạm dừng thực thi với thông báo"""
    print(f"⏳ Delay {second:.2f}s...")
    time.sleep(second)

# Hàm sinh ngẫu nhiên user-agent
def generate_user_agent():
    try:
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
    except Exception as e:
        print("Lỗi khi sinh user-agent: " + str(e))
        traceback.print_exc()
        # Return a default user agent in case of error
        return "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"

# Thread cho việc lưu file debug
def debug_save_thread():
    while not debug_save_event.is_set():
        try:
            # Try to get a save task from the queue with timeout
            save_task = debug_save_queue.get(timeout=1.0)
            if save_task:
                try:
                    novel_title, chapter_info, html_content, folder_path = save_task

                    # Đảm bảo thư mục tồn tại
                    os.makedirs(folder_path, exist_ok=True)

                    # Tạo tên file an toàn - xử lý trường hợp không có chapter_info
                    if not chapter_info or not isinstance(chapter_info, dict):
                        # Nếu không có chapter_info, tạo tên file dựa trên timestamp
                        timestamp = int(time.time())
                        file_name = f"debug_{timestamp}.html"
                    else:
                        # Lấy thông tin chương nếu có
                        chapter_num = chapter_info.get('index', '0')
                        chapter_title = chapter_info.get('name', 'unknown')

                        # Tạo tên file an toàn
                        safe_title = re.sub(r'[\\/*?:"<>|]', "_", str(chapter_title))
                        file_name = f"{chapter_num}_{safe_title}.html"

                    # Đường dẫn đầy đủ
                    file_path = os.path.join(folder_path, file_name)

                    # Lưu nội dung
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(html_content)

                    print(f"🔍 Đã lưu file debug: {file_path}")
                except Exception as e:
                    print(f"⚠️ Lỗi khi lưu file debug: {e}")
                    traceback.print_exc()

                    # Thử lưu với tên file đơn giản nhất trong trường hợp lỗi
                    try:
                        timestamp = int(time.time())
                        simple_path = os.path.join(temp_folder, f"debug_error_{timestamp}.html")
                        with open(simple_path, 'w', encoding='utf-8') as f:
                            f.write(html_content)
                        print(f"🔍 Đã lưu file debug dự phòng: {simple_path}")
                    except:
                        print("❌ Không thể lưu file debug dù đã thử phương án dự phòng")

                debug_save_queue.task_done()
        except queue.Empty:
            # No save task in queue, continue checking
            pass
        except Exception as e:
            print(f"❌ Lỗi trong luồng lưu debug: {e}")
            traceback.print_exc()

# Hàm thêm tác vụ lưu file debug vào queue
def queue_debug_save(novel_title, chapter_info, html_content):
    try:
        # Xử lý trường hợp novel_title rỗng hoặc None
        if not novel_title:
            novel_title = "Unknown_Novel"

        # Tạo tên thư mục an toàn
        safe_title = re.sub(r'[\\/*?:"<>|]', "_", str(novel_title))
        folder_path = os.path.join(temp_folder, safe_title)

        # Thêm vào queue
        debug_save_queue.put((novel_title, chapter_info, html_content, folder_path))
    except Exception as e:
        print(f"⚠️ Lỗi khi thêm nhiệm vụ lưu debug: {e}")
        traceback.print_exc()

        # Thử lưu trực tiếp mà không qua queue trong trường hợp lỗi nghiêm trọng
        try:
            timestamp = int(time.time())
            emergency_path = os.path.join(temp_folder, f"emergency_debug_{timestamp}.html")
            with open(emergency_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            print(f"🔍 Đã lưu file debug khẩn cấp: {emergency_path}")
        except:
            print("❌ Không thể lưu file debug trong trường hợp khẩn cấp")

# Background thread function for saving checkpoints
def checkpoint_saver_thread():
    while not exit_event.is_set():
        try:
            # Try to get a save task from the queue with timeout
            save_task = save_queue.get(timeout=1.0)
            if save_task:
                book, intro, chapters, output_path = save_task
                try:
                    save_epub(book, intro, chapters, output_path, True)
                    print(f"\n\n✨✨✨ Đã lưu tạm checkpoint sau {len(chapters)} chương... ✨✨✨\n\n")
                except Exception as e:
                    print(f"⚠️ Lỗi khi lưu checkpoint: {e}")
                save_queue.task_done()
        except queue.Empty:
            # No save task in queue, continue checking
            pass
        except Exception as e:
            print(f"❌ Lỗi trong luồng lưu điểm kiểm tra: {e}")
            traceback.print_exc()

# Hàm xóa file tạm sau khi lưu thành công
def delete_temp_file(temp_path):
    """Xóa file truyện tạm thời sau khi đã lưu thành công vào thư mục chính"""
    try:
        if os.path.exists(temp_path):
            os.remove(temp_path)
            print(f"🧹 Đã xóa file tạm: {temp_path}")
            return True
        else:
            print(f"⚠️ Không tìm thấy file tạm: {temp_path}")
            return False
    except Exception as e:
        print(f"❌ Lỗi khi xóa file tạm: {e}")
        traceback.print_exc()
        return False

# Hàm lấy cookie từ userdata của Google Colab
def get_cookie():
    try:
        # Kiểm tra xem đã có cookie trong userdata chưa
        try:
            cookie = userdata.get('cookie')
            if cookie:
                print("🔍 Đã tìm thấy cookie trong userdata")
                return cookie
        except:
            print("⚠️ Không tìm thấy cookie trong userdata")

        # Nếu chưa có, yêu cầu người dùng nhập cookie
        cookie = input("🔑 Nhập cookie accessToken: ").strip()

        # Lưu cookie vào userdata cho lần sau
        try:
            userdata.set('cookie', cookie)
            print("Đã lưu cookie vào userdata")
        except Exception as e:
            print("❌ Không thể lưu cookie vào userdata: " + str(e))
            traceback.print_exc()

        return cookie
    except Exception as e:
        print("❌ Lỗi khi lấy cookie: " + str(e))
        traceback.print_exc()
        return input("Nhập cookie accessToken: ")

# Lấy cookie
cookie = get_cookie()

# Hàm request trang web với headers đã cung cấp
def make_request(url, is_api=False, is_mtc=True):
    try:
        headers = {
            'user-agent': generate_user_agent(),
            'referer': 'https://metruyencv.com/' if is_mtc else 'https://tangthuvien.net/'
        }

        # Thêm cookie nếu là metruyenchu
        if is_mtc:
            headers['cookie'] = 'accessToken=' + cookie

        # Thêm headers phù hợp dựa vào loại request
        if is_api and is_mtc:
            headers['authorization'] = f'Bearer {cookie}'
            headers['accept'] = 'application/json, text/plain, */*'

        # Thử lại tối đa 3 lần nếu bị lỗi
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = requests.get(url, headers=headers)
                response.raise_for_status()
                # Trả về JSON nếu là API request, ngược lại trả về text
                if is_api and is_mtc:
                    return response.json()
                else:
                    return response.text
            except Exception as e:
                print("❌ Lỗi khi tải trang " + url + ", lần thử " + str(attempt+1) + "/" + str(max_retries) + ": " + str(e))
                traceback.print_exc()
                if attempt < max_retries - 1:
                    delay_time = random.uniform(1, 2)
                    delay(delay_time)  # Chờ 1-2 giây trước khi thử lại
                else:
                    raise Exception("Đã thử " + str(max_retries) + " lần nhưng không thành công: " + str(e))
    except Exception as e:
        print("❌ Lỗi không xử lý được khi tải trang " + url + ": " + str(e))
        traceback.print_exc()
        raise

# Hàm xác định loại trang web từ URL
def detect_site_type(url):
    if "metruyencv.com" in url.lower():
        return "metruyenchu"
    elif "tangthuvien.net" in url.lower():
        return "tangthuvien"
    else:
        raise ValueError("URL không được hỗ trợ. Hiện tại chỉ hỗ trợ metruyencv.com và tangthuvien.net")

# Hàm lấy thông tin truyện từ Metruyenchu
def get_mtc_novel_info(url):
    try:
        html = make_request(url, is_mtc=True)
        soup = BeautifulSoup(html, 'html.parser')

        # Lấy tiêu đề truyện
        title_elem = soup.select_one('h1 a')
        title = title_elem.text.strip() if title_elem else "Không xác định"
        print("📌 Tiêu đề truyện: " + title)

        # Lấy tên tác giả
        author_elem = soup.select_one('h1 ~ div')
        author = author_elem.text.strip() if author_elem else "Không xác định"
        print("👤 Tác giả: " + author)

        # Lấy link ảnh bìa
        cover_elem = soup.select_one('img.h-60')
        cover_url = cover_elem['src'] if cover_elem and 'src' in cover_elem.attrs else None
        print("🖼️ Ảnh bìa: " + ("Có" if cover_url else "Không có"))

        # Lấy nội dung giới thiệu
        synopsis_elem = soup.select_one('#synopsis .text-base')
        synopsis = synopsis_elem.get_text('\n', strip=True) if synopsis_elem else ""
        print("📝 Giới thiệu: " + ("Có" if synopsis else "Không có"))

        # Lấy book_id từ nút "Đọc từ đầu"
        read_button = soup.select_one('div button[title="Đọc từ đầu"]')
        book_id = None

        if read_button and read_button.parent:
            data_x_data = read_button.parent.get('data-x-data', '')
            book_id_match = re.search(r'readings\((\d+)\)', data_x_data)
            if book_id_match:
                book_id = book_id_match.group(1)
                print(f"📘 Book ID: {book_id}")
            else:
                print("⚠️ Không tìm thấy book_id trong nút đọc từ đầu")
        else:
            print("⚠️ Không tìm thấy nút đọc từ đầu")

        # Lấy danh sách chương từ API nếu có book_id
        chapters_list = []
        if book_id:
            api_url = f"https://backend.metruyencv.com/api/chapters?filter[book_id]={book_id}"
            try:
                api_data = make_request(api_url, is_api=True, is_mtc=True)
                if 'data' in api_data and isinstance(api_data['data'], list):
                    chapters_list = api_data['data']
                    print(f"📚 Đã lấy thông tin {len(chapters_list)} chương từ API")
            except Exception as e:
                print(f"❌ Lỗi khi lấy danh sách chương từ API: {e}")
                traceback.print_exc()

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
        print("❌ Lỗi khi lấy thông tin truyện: " + str(e))
        traceback.print_exc()
        raise

# Hàm lấy thông tin truyện từ Tangthuvien
def get_ttv_novel_info(url):
    try:
        html = make_request(url, is_mtc=False)
        soup = BeautifulSoup(html, 'html.parser')

        # Lấy tiêu đề truyện
        title_elem = soup.select_one('h1')
        title = title_elem.text.strip() if title_elem else "Không xác định"
        print("📌 Tiêu đề truyện: " + title)

        # Tác giả mặc định
        author = "Không xác định"
        # print("👤 Tác giả: " + author)

        # Lấy link ảnh bìa
        cover_elem = soup.select_one('.book-img img')
        cover_url = cover_elem['src'] if cover_elem and 'src' in cover_elem.attrs else None
        print("🖼️ Ảnh bìa: " + ("Có" if cover_url else "Không có"))

        # Lấy nội dung giới thiệu
        synopsis_elem = soup.select_one('.book-intro')
        synopsis = synopsis_elem.get_text('\n', strip=True) if synopsis_elem else ""
        print("📝 Giới thiệu: " + ("Có" if synopsis else "Không có"))

        # Lấy book_id
        book_id_elem = soup.select_one('#story_id_hidden')
        book_id = book_id_elem['value'] if book_id_elem else None
        print(f"📘 Book ID: {book_id or 'Không tìm thấy'}")

        if not book_id:
            # Không tìm thấy book_id thì lưu file để DEBUG
            queue_debug_save(url, null, html)

        # Lấy tổng số chương
        total_chapters = 0
        catalog_elem = soup.select_one('#j-bookCatalogPage')
        if catalog_elem:
            chapter_count_match = re.search(r'Danh sách chương \((\d+) chương\)', catalog_elem.text)
            if chapter_count_match:
                total_chapters = int(chapter_count_match.group(1))
                print(f"📚 Tổng số chương: {total_chapters}")

        # Lấy danh sách chương
        chapters_list = []
        if book_id and total_chapters > 0:
            chapters_url = f"https://tangthuvien.net/doc-truyen/page/{book_id}?page=0&limit={total_chapters}&web=1"
            try:
                chapters_html = make_request(chapters_url, is_mtc=False)
                chapters_soup = BeautifulSoup(chapters_html, 'html.parser')
                chapter_links = chapters_soup.select('ul.cf > li > a')

                for i, link in enumerate(chapter_links, 1):
                    chapter_url = link.get('href')
                    chapter_title = link.get('title') or f"Chương {i}"

                    chapters_list.append({
                        'index': i,
                        'name': chapter_title,
                        'url': chapter_url
                    })

                print(f"📚 Đã lấy thông tin {len(chapters_list)} chương")
            except Exception as e:
                print(f"❌ Lỗi khi lấy danh sách chương từ Tangthuvien: {e}")
                traceback.print_exc()

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
        print("❌ Lỗi khi lấy thông tin truyện từ Tangthuvien: " + str(e))
        traceback.print_exc()
        raise

# Hàm lấy thông tin truyện (tự nhận biết trang)
def get_novel_info(url):
    site_type = detect_site_type(url)
    if site_type == "metruyenchu":
        return get_mtc_novel_info(url)
    elif site_type == "tangthuvien":
        return get_ttv_novel_info(url)
    else:
        raise ValueError("Không hỗ trợ loại trang web này")

# Hàm trích xuất tiêu đề chương từ nội dung
def extract_chapter_title(chapter_number, content=None, default_title=None):
    """Trích xuất hoặc tạo tiêu đề chương phù hợp"""
    # Nếu đã có tiêu đề tốt, sử dụng nó
    if default_title and default_title != f"Chương {chapter_number}" and default_title != "":
        return default_title

    # Cố gắng trích xuất tiêu đề từ nội dung nếu có
    if content:
        try:
            title_pattern = re.compile(r"Chương\s+\d+\s*[:\-]\s*(.*?)[\n\r]", re.IGNORECASE)
            match = title_pattern.search(content)
            if match:
                return f"Chương {chapter_number}: {match.group(1).strip()}"
        except Exception as e:
            print(f"⚠️ Lỗi khi trích xuất tiêu đề: {e}")

    # Tiêu đề mặc định chỉ với số chương
    return f"Chương {chapter_number}"

# Hàm trích xuất tiêu đề từ nội dung HTML
def extract_title_from_html(html_content):
    """Trích xuất tiêu đề từ nội dung HTML, thường từ thẻ h2"""
    try:
        if not html_content:
            return None

        soup = BeautifulSoup(html_content, 'html.parser')

        # Tìm thẻ h2 đầu tiên (thường là tiêu đề chương)
        # h2 = soup.find('h2')
        #if h2 and h2.text.strip():
        #    return h2.text.strip()

        # Hoặc tìm trong title
        title_tag = soup.find('title')
        if title_tag and title_tag.text.strip():
            return title_tag.text.strip()

        return None
    except Exception as e:
        print(f"⚠️ Lỗi khi trích xuất tiêu đề từ HTML: {e}")
        return None

# Hàm chuẩn hóa và tối ưu HTML cho e-reader
def optimize_html_for_ereader(html_content):
    """Tối ưu hóa nội dung HTML cho thiết bị đọc sách điện tử"""
    try:
        if not html_content:
            return html_content

        # Parse HTML
        soup = BeautifulSoup(html_content, 'html.parser')

        # 1. Loại bỏ các thuộc tính không cần thiết
        for tag in soup.find_all(True):
            allowed_attrs = ['id', 'class', 'href', 'src', 'alt']
            attrs = dict(tag.attrs)
            for attr in attrs:
                if attr not in allowed_attrs:
                    del tag[attr]

        # 2. Tách các đoạn văn dài
        for p in soup.find_all('p'):
            if len(p.get_text()) > 1000:  # Nếu đoạn văn quá dài
                text = p.get_text()
                p.clear()

                # Chia nhỏ đoạn văn
                sentences = re.split(r'(?<=[.!?])\s+', text)
                current_p = p

                for i, sentence in enumerate(sentences):
                    if i > 0 and i % 3 == 0:  # Mỗi 3 câu tạo đoạn mới
                        new_p = soup.new_tag('p')
                        current_p.insert_after(new_p)
                        current_p = new_p

                    if current_p.string:
                        current_p.string = current_p.string + " " + sentence
                    else:
                        current_p.string = sentence

        # 3. Thêm ngắt trang sau mỗi ~10 đoạn văn
        # paragraphs = soup.find_all('p')
        # for i, p in enumerate(paragraphs):
        #    if (i+1) % 10 == 0 and i < len(paragraphs) - 1:
        #        page_break = soup.new_tag('div')
        #        page_break['style'] = 'page-break-after: always; break-after: page;'
        #        p.insert_after(page_break)

        # 4. Đảm bảo khoảng cách giữa các đoạn
        for p in soup.find_all('p'):
            p['style'] = 'margin-top: 0.5em; margin-bottom: 0.5em;'

        # 5. Chuyển đổi các thẻ phức tạp thành thẻ đơn giản hơn
        for tag in soup.find_all(['div', 'span']):
            if not tag.find_all(True):  # Nếu không có thẻ con
                new_tag = soup.new_tag('p')
                new_tag.string = tag.get_text()
                tag.replace_with(new_tag)

        # 6. Chuẩn hóa các thẻ trống
        for tag in soup.find_all():
            if len(tag.get_text(strip=True)) == 0 and tag.name not in ['br', 'img', 'hr']:
                tag.decompose()

        # 7. Đảm bảo các ký tự đặc biệt được hiển thị đúng
        for entity in soup.find_all(string=lambda text: '&' in text):
            new_text = entity.replace('&nbsp;', ' ')
            entity.replace_with(new_text)

        return str(soup)
    except Exception as e:
        print(f"⚠️ Lỗi khi tối ưu hóa HTML: {e}")
        traceback.print_exc()
        return html_content  # Trả về nguyên bản nếu có lỗi

# Hàm lấy nội dung chương từ Metruyenchu
def get_mtc_chapter_content(url, chapter_number, chapter_title=None, novel_title=""):
    try:
        chapter_url = url + "/chuong-" + str(chapter_number)
        html = make_request(chapter_url, is_mtc=True)
        soup = BeautifulSoup(html, 'html.parser')

        # Lấy tiêu đề chương
        title_elem = soup.select_one('h2')
        base_title = title_elem.text.strip() if title_elem and title_elem.text else "Chương " + str(chapter_number)

        # Sử dụng tiêu đề từ API nếu có
        if chapter_title:
            base_title = chapter_title

        # Lấy nội dung chương
        content_elem = soup.select_one('[data-x-bind="ChapterContent"]')
        content = ""

        if content_elem:
            content = content_elem.get_text('\n', strip=True)

        if not content or len(content.strip()) == 0:
            # Lưu file HTML để debug
            queue_debug_save(novel_title, chapter_info, html)

            # Still no content, use fallback
            content = "Không có nội dung. Chương này có thể bị khóa hoặc không tồn tại."
            print(f"⚠️ Không tìm thấy nội dung cho chương {chapter_number}: Nội dung có thể bị khoá hoặc không tồn tại, sử dụng nội dung mặc định")

        # Trích xuất tiêu đề tốt hơn nếu có thể
        title = extract_chapter_title(chapter_number, content, base_title)

        # Format lại nội dung html
        if content_elem:
            # Xử lý các thẻ p và br
            for p in content_elem.find_all('p'):
                p.insert_after(soup.new_tag('br'))
            content_html = str(content_elem)

            # Tối ưu hóa HTML cho e-reader
            content_html = optimize_html_for_ereader(content_html)
        else:
            content_html = "<p>" + content + "</p>"

        # In thông tin có được
        print("✅ Đã tải chương " + str(chapter_number) + ": " + title + " - Độ dài: " + str(len(content)) + " ký tự")

        return {
            'title': title,
            'content': content,
            'content_html': content_html
        }
    except Exception as e:
        print("❌ Lỗi khi tải chương " + str(chapter_number) + " từ Metruyenchu: " + str(e))
        traceback.print_exc()
        raise

# Hàm lấy nội dung chương từ Tangthuvien
def get_ttv_chapter_content(chapter_info, novel_title=""):
    try:
        chapter_number = chapter_info['index']
        chapter_url = chapter_info['url']
        chapter_title = chapter_info['name']

        # Lấy HTML từ trang
        html = make_request(chapter_url, is_mtc=False)

        # Phân tích nội dung
        soup = BeautifulSoup(html, 'html.parser')

        # Xóa hết nội dung trong thẻ head để giảm kích thước file debug
        if soup.head:
            soup.head.clear()
            soup.head.append(soup.new_tag('title'))
            soup.head.title.string = f"Debug HTML - Chương {chapter_number}"

        # Nội dung truyện - thử với selector chính
        content_elem = soup.select_one('.box-chap')
        content = ""
        content_html = ""

        # Nếu không tìm thấy selector chính, thử với selector thay thế
        if not content_elem or not content_elem.text.strip():
            content_blocks = soup.select('p.content-block')

            if content_blocks:
                print(f"ℹ️ Sử dụng selector thay thế cho chương {chapter_number}")

                # Tạo nội dung từ các thẻ p.content-block
                content = "\n".join([block.get_text(strip=True) for block in content_blocks])

                # Tạo HTML mới với các thẻ p
                content_container = soup.new_tag('div')
                content_container['class'] = 'chapter-content'

                for block in content_blocks:
                    p = soup.new_tag('p')
                    p.string = block.get_text(strip=True)
                    content_container.append(p)

                    # Thêm thẻ br sau mỗi đoạn để đảm bảo xuống dòng trong EPUB
                    br = soup.new_tag('br')
                    content_container.append(br)

                content_elem = content_container
                content_html = str(content_container)
            else:
                # Vẫn không tìm thấy nội dung
                content_elem = None

        # Xử lý nếu tìm thấy nội dung với selector chính
        if content_elem and not content:
            content = content_elem.get_text('\n', strip=True)

            # Tạo HTML mới từ văn bản với các ký tự xuống dòng \n được chuyển thành thẻ p
            if content:
                # Tách các đoạn theo ký tự xuống dòng \n
                paragraphs = content.split('\n')

                # Tạo div chứa nội dung
                fixed_content_elem = soup.new_tag('div')
                fixed_content_elem['class'] = 'chapter-content'

                # Thêm mỗi đoạn văn vào một thẻ p riêng
                for paragraph in paragraphs:
                    # Bỏ qua các dòng trống
                    if paragraph.strip():
                        p = soup.new_tag('p')
                        p.string = paragraph.strip()
                        fixed_content_elem.append(p)

                content_html = str(fixed_content_elem)
            else:
                content_html = "<div class='chapter-content'></div>"

        # Nếu không lấy được nội dung, lưu file HTML để debug
        if not content or len(content.strip()) == 0:
            # Lưu file HTML để debug
            clean_html = str(soup)
            queue_debug_save(novel_title, chapter_info, clean_html)

            # Sử dụng nội dung mặc định
            content = "Không có nội dung. Chương này có thể bị khóa hoặc không tồn tại."
            print(f"⚠️ Không tìm thấy nội dung cho chương {chapter_number}: Nội dung có thể bị khoá hoặc không tồn tại, đã lưu HTML để debug")
            content_html = "<p>" + content + "</p>"

        # Nếu chưa có content_html (hiếm gặp)
        if not content_html:
            content_html = "<p>" + content.replace("\n\n", "</p><p>") + "</p>"

        # Trích xuất tiêu đề tốt hơn nếu có thể
        title = extract_chapter_title(chapter_number, content, chapter_title)

        # Tối ưu hóa HTML cho e-reader
        content_html = optimize_html_for_ereader(content_html)

        # In thông tin có được
        print("✅ Đã tải chương " + str(chapter_number) + ": " + title + " - Độ dài: " + str(len(content)) + " ký tự")

        return {
            'title': title,
            'content': content,
            'content_html': content_html
        }
    except Exception as e:
        print("❌ Lỗi khi tải chương " + str(chapter_number) + " từ Tangthuvien: " + str(e))
        traceback.print_exc()
        raise

# Hàm lấy nội dung chương
def get_chapter_content(url, chapter_info, site_type, novel_title):
    if site_type == 'metruyenchu':
        return get_mtc_chapter_content(url, chapter_info['index'], chapter_info.get('name'), novel_title)
    elif site_type == 'tangthuvien':
        return get_ttv_chapter_content(chapter_info, novel_title)
    else:
        raise ValueError(f"Không hỗ trợ loại trang web: {site_type}")

# Hàm tạo EPUB mới
def create_epub(novel_info):
    try:
        print("📙 Bắt đầu tạo file EPUB mới...")
        book = epub.EpubBook()

        # Thêm metadata
        book_id = str(uuid.uuid4())
        book.set_identifier(book_id)
        book.set_title(novel_info['title'])
        book.set_language('vi')
        book.add_author(novel_info['author'])
        print("📝 Đã thêm metadata (id: " + book_id[:8] + "...)")

        # Thêm metadata cho e-reader
        book.add_metadata(None, 'meta', '', {'name': 'fixed-layout', 'content': 'false'})
        book.add_metadata(None, 'meta', '', {'name': 'book-type', 'content': 'text'})
        book.add_metadata(None, 'meta', '', {'name': 'viewport', 'content': 'width=device-width, height=device-height'})

        # Tải và thêm ảnh bìa
        if novel_info['cover_url']:
            try:
                print("🖼️ Đang tải ảnh bìa từ: " + novel_info['cover_url'])
                headers = {
                    'user-agent': generate_user_agent(),
                    'referer': 'https://metruyencv.com/'
                }
                cover_response = requests.get(novel_info['cover_url'], headers=headers)
                cover_response.raise_for_status()
                cover_content = cover_response.content

                # Xác định định dạng ảnh
                parsed_url = urlparse(novel_info['cover_url'])
                path = unquote(parsed_url.path)
                _, ext = os.path.splitext(path)
                if not ext:
                    ext = '.jpg'  # Mặc định là jpg nếu không có extension

                book.set_cover("cover" + ext, cover_content)
                print("✅ Đã thêm ảnh bìa (" + str(len(cover_content)) + " bytes)")
            except Exception as e:
                print("⚠️ Lỗi khi tải ảnh bìa: " + str(e))
                traceback.print_exc()

        # Thêm trang giới thiệu
        print("📄 Tạo trang giới thiệu...")
        intro = epub.EpubHtml(title='Giới thiệu', file_name='intro.xhtml')
        intro.id = 'intro'  # Đặt thuộc tính id

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

        # Thêm CSS tối ưu cho e-reader
        print("🎨 Thêm stylesheet...")
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

        # Thêm nav
        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())

        print("✅ Đã tạo xong cấu trúc EPUB cơ bản")
        return book, intro
    except Exception as e:
        print("❌ Lỗi khi tạo file EPUB: " + str(e))
        traceback.print_exc()
        raise

# Hàm sửa các tệp điều hướng với tiêu đề chính xác
def fix_navigation_files(book, is_temp):
    """Sửa các tệp điều hướng để đảm bảo tất cả các chương có tiêu đề phù hợp"""
    try:
        # Lấy tất cả chương và trích xuất tiêu đề đầy đủ từ nội dung
        chapter_titles = {}
        for item in book.items:
            if isinstance(item, epub.EpubHtml) and hasattr(item, 'id') and item.id and item.id.startswith('chapter_'):
                try:
                    chapter_num = int(item.id.split('_')[1])

                    # Ưu tiên trích xuất tiêu đề từ nội dung HTML
                    full_title = None
                    if hasattr(item, 'content') and item.content:
                        full_title = extract_title_from_html(item.content)

                    # Nếu không tìm thấy từ HTML, sử dụng tiêu đề có sẵn
                    if not full_title and hasattr(item, 'title') and item.title:
                        full_title = item.title

                    # Nếu vẫn không có, tạo tiêu đề mặc định
                    if not full_title:
                        full_title = f"Chương {chapter_num}"

                    # Lưu lại tiêu đề trích xuất được
                    chapter_titles[chapter_num] = full_title

                    # Cập nhật lại tiêu đề chương
                    item.title = full_title

                except Exception as e:
                    print(f"⚠️ Lỗi khi xử lý chương {item.id}: {e}")

        if not chapter_titles:
            print("⚠️ Không tìm thấy chương nào để cập nhật điều hướng")
            return False

        if not is_temp:
            print(f"📚 Tìm thấy {len(chapter_titles)} chương có tiêu đề để cập nhật điều hướng")

        # Tạo nội dung nav.xhtml mới từ đầu nếu cần
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
                  <a href="intro.xhtml">Giới thiệu</a>
                </li>
                {chapter_items}
              </ol>
            </nav>
          </body>
        </html>
        """

        # Tạo nội dung toc.ncx mới từ đầu nếu cần
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
                <text>Giới thiệu</text>
              </navLabel>
              <content src="intro.xhtml"/>
            </navPoint>
            {chapter_items}
          </navMap>
        </ncx>
        """

        # Tìm và cập nhật tệp nav.xhtml
        nav_item = None
        for item in book.items:
            if isinstance(item, epub.EpubHtml) and item.file_name == 'nav.xhtml':
                nav_item = item
                break

        title = book.title if hasattr(book, 'title') else "Truyện EPUB"

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
                        print("✅ Đã cập nhật nav.xhtml với tiêu đề chương chính xác")
                else:
                    # Tạo nội dung nav.xhtml mới
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
                        print("✅ Đã tạo mới nội dung nav.xhtml")
            except Exception as e:
                print(f"⚠️ Lỗi khi cập nhật nav.xhtml: {e}")
                traceback.print_exc()
        else:
            print("⚠️ Không tìm thấy nav.xhtml trong EPUB")

        # Tìm và cập nhật tệp toc.ncx
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
                        print("✅ Đã cập nhật toc.ncx với tiêu đề chương chính xác")
                else:
                    # Tạo nội dung toc.ncx mới
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
                        print("✅ Đã tạo mới nội dung toc.ncx")
            except Exception as e:
                print(f"⚠️ Lỗi khi cập nhật toc.ncx: {e}")
                traceback.print_exc()
        else:
            print("⚠️ Không tìm thấy toc.ncx trong EPUB")

        return True
    except Exception as e:
        print(f"❌ Lỗi khi sửa tệp điều hướng: {e}")
        traceback.print_exc()
        return False

# Hàm đọc EPUB đã tồn tại
def load_existing_epub(epub_path):
    try:
        print("📚 Đang đọc file EPUB hiện có: " + epub_path)
        book = epub.read_epub(epub_path)

        # Tìm số chương đã có
        spine_items = [item for item in book.spine if isinstance(item, tuple) and item[0] != 'nav']

        # Find chapters by file name pattern instead of relying on id attribute
        chapter_items = [item for item in book.items if isinstance(item, epub.EpubHtml)
                         and item.file_name.startswith('chapter_') and item.file_name.endswith('.xhtml')]

        # Ensure all chapters have proper IDs
        for item in chapter_items:
            if not hasattr(item, 'id') or not item.id:
                try:
                    chapter_num = int(item.file_name.split('_')[1].split('.')[0])
                    item.id = 'chapter_' + str(chapter_num)
                except Exception as e:
                    print("⚠️ Lỗi khi tạo ID cho chapter: " + str(e))

        # Bây giờ trích xuất tiêu đề đầy đủ từ nội dung HTML
        for item in chapter_items:
            try:
                if hasattr(item, 'content') and item.content:
                    full_title = extract_title_from_html(item.content)
                    if full_title:
                        item.title = full_title
                        print(f"📝 Đã trích xuất tiêu đề từ HTML: {full_title}")

                    # Tối ưu hóa HTML cho e-reader
                    item.content = optimize_html_for_ereader(item.content)
            except Exception as e:
                print(f"⚠️ Lỗi khi trích xuất tiêu đề từ HTML: {e}")

        # Now filter items with IDs
        chapter_items = [item for item in chapter_items if hasattr(item, 'id') and item.id.startswith('chapter_')]

        print("📊 Đã tìm thấy " + str(len(chapter_items)) + " chương trong file")

        # Lấy trang giới thiệu
        intro = None
        for item in book.items:
            if isinstance(item, epub.EpubHtml) and item.file_name == 'intro.xhtml':
                intro = item
                # Ensure intro has an id
                if not hasattr(intro, 'id') or not intro.id:
                    intro.id = 'intro'
                print("📄 Đã tìm thấy trang giới thiệu")
                break

        if intro is None:
            print("⚠️ Không tìm thấy trang giới thiệu trong file EPUB")

        # Tìm chương cuối cùng
        max_chapter = 0
        for item in chapter_items:
            # Lấy số chương từ id (chapter_X)
            try:
                if hasattr(item, 'id') and item.id:
                    chapter_num = int(item.id.split('_')[1])
                else:
                    # Fallback to file_name if id is not available
                    chapter_num = int(item.file_name.split('_')[1].split('.')[0])
                max_chapter = max(max_chapter, chapter_num)
            except Exception as e:
                print("⚠️ Lỗi khi đọc số chương từ " + str(getattr(item, 'id', item.file_name)) + ": " + str(e))

        print("📌 Chương cuối cùng tìm thấy: Chương " + str(max_chapter))

        # Sửa tệp điều hướng
        fix_navigation_files(book, True)

        return book, intro, max_chapter
    except Exception as e:
        print("❌ Lỗi khi đọc file EPUB " + epub_path + ": " + str(e))
        traceback.print_exc()
        raise

# Hàm thêm chương vào EPUB
def add_chapter_to_epub(book, chapter_data, chapter_number):
    try:
        chapter_id = 'chapter_' + str(chapter_number)

        # Lấy tiêu đề tốt hơn từ nội dung nếu có
        title = extract_chapter_title(chapter_number, chapter_data['content'], chapter_data['title'])

        chapter = epub.EpubHtml(title=title, file_name='chapter_' + str(chapter_number) + '.xhtml')
        chapter.id = chapter_id  # Đặt thuộc tính id sau khi tạo

        content_html = "<p>Không có nội dung</p>"
        if 'content_html' in chapter_data:
            content_html = chapter_data['content_html']

        # Chuẩn bị nội dung HTML tối ưu cho e-reader
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
        print("❌ Lỗi khi thêm chương " + str(chapter_number) + " vào EPUB: " + str(e))
        traceback.print_exc()
        raise

# Hàm chia nhỏ chương dài thành nhiều phần
def split_large_chapters(book, is_temp):
    """Chia nhỏ các chương quá dài để tránh vấn đề hiệu suất trên e-reader"""
    try:
        modified = False
        large_chapters = []

        # Tìm các chương quá dài
        for item in book.items:
            if isinstance(item, epub.EpubHtml) and hasattr(item, 'id') and item.id.startswith('chapter_'):
                if hasattr(item, 'content') and item.content and len(item.content) > 100000:  # ~100KB
                    large_chapters.append(item)

        if not large_chapters:
            return False

        if not is_temp:
            print(f"📏 Đã tìm thấy {len(large_chapters)} chương quá dài cần chia nhỏ")

        # Xử lý từng chương dài
        for chapter in large_chapters:
            try:
                chapter_num = int(chapter.id.split('_')[1])
                soup = BeautifulSoup(chapter.content, 'html.parser')

                # Lấy phần body
                body = soup.find('body')
                if not body:
                    continue

                # Lấy tiêu đề
                title_tag = soup.find('h2')
                title = title_tag.get_text() if title_tag else chapter.title

                # Lấy tất cả đoạn văn
                paragraphs = body.find_all('p')

                if len(paragraphs) < 20:  # Không đủ đoạn để chia
                    continue

                # Chia thành các phần
                parts = []
                part_size = max(10, len(paragraphs) // 3)  # Ít nhất 10 đoạn mỗi phần, tối đa 3 phần

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

                    # Thêm tiêu đề vào phần đầu tiên
                    if i == 0 and title_tag:
                        part_soup.body.append(title_tag)

                    # Thêm phụ đề cho các phần sau
                    else:
                        part_title = part_soup.new_tag('h3')
                        part_title.string = f"{title} (tiếp theo)"
                        part_soup.body.append(part_title)

                    # Thêm các đoạn văn
                    for p in part_paragraphs:
                        part_soup.body.append(p)

                    # Thêm ngắt trang cuối phần
                    page_break = part_soup.new_tag('div')
                    page_break['style'] = 'page-break-after: always; break-after: page;'
                    part_soup.body.append(page_break)

                    parts.append(str(part_soup))

                if len(parts) <= 1:  # Không cần chia nếu chỉ có 1 phần
                    continue

                # Tạo các chương con
                for i, part_content in enumerate(parts):
                    sub_id = f"chapter_{chapter_num}_{i+1}"
                    sub_filename = f"chapter_{chapter_num}_{i+1}.xhtml"

                    # Đặt tên cho phần
                    if i == 0:
                        sub_title = title
                    else:
                        sub_title = f"{title} (phần {i+1})"

                    sub_chapter = epub.EpubHtml(title=sub_title, file_name=sub_filename)
                    sub_chapter.id = sub_id
                    sub_chapter.content = part_content
                    book.add_item(sub_chapter)

                # Thêm vào spine thay thế chương gốc
                spine_index = book.spine.index(chapter) if chapter in book.spine else -1
                if spine_index > 0:
                    # Xóa chương gốc
                    book.spine.pop(spine_index)

                    # Thêm các chương con vào vị trí đó
                    for i in range(len(parts)):
                        sub_id = f"chapter_{chapter_num}_{i+1}"
                        for item in book.items:
                            if hasattr(item, 'id') and item.id == sub_id:
                                book.spine.insert(spine_index + i, item)

                # Đánh dấu đã sửa đổi
                modified = True
                if not is_temp:
                    print(f"✂️ Đã chia chương {chapter_num} thành {len(parts)} phần")

            except Exception as e:
                print(f"⚠️ Lỗi khi chia nhỏ chương {chapter.id}: {e}")
                traceback.print_exc()

        return modified
    except Exception as e:
        print(f"❌ Lỗi khi chia nhỏ chương: {e}")
        traceback.print_exc()
        return False

# Hàm lưu EPUB
def save_epub(book, intro, chapters, output_path, is_temp):
    try:
        if not is_temp:
            print("💾 Đang lưu EPUB vào: " + output_path)

        # Xóa spine cũ và tạo mới để đảm bảo thứ tự đúng
        book.spine = [('nav', 'nav')]
        book.spine.append(intro)

        # Thêm chapters vào spine theo thứ tự
        # Đảm bảo tất cả các chương có thuộc tính id
        for chapter in chapters:
            if not hasattr(chapter, 'id') or not chapter.id:
                chapter_num = int(chapter.file_name.split('_')[1].split('.')[0])
                chapter.id = 'chapter_' + str(chapter_num)

            # Đảm bảo tất cả các chương có tiêu đề phù hợp
            if not hasattr(chapter, 'title') or not chapter.title or chapter.title == "":
                chapter_num = int(chapter.id.split('_')[1])
                # Trích xuất tiêu đề từ nội dung HTML nếu có
                if hasattr(chapter, 'content') and chapter.content:
                    full_title = extract_title_from_html(chapter.content)
                    if full_title:
                        chapter.title = full_title
                    else:
                        chapter.title = f"Chương {chapter_num}"
                else:
                    chapter.title = f"Chương {chapter_num}"

        # Sắp xếp chương theo số thứ tự
        try:
            sorted_chapters = sorted(chapters, key=lambda x: int(x.id.split('_')[1]))
        except Exception as e:
            print(f"⚠️ Lỗi khi sắp xếp chương: {e}")
            # Fallback: sắp xếp theo tên file
            sorted_chapters = sorted(chapters,
                key=lambda x: int(re.search(r'chapter_(\d+)', x.file_name).group(1))
                    if re.search(r'chapter_(\d+)', x.file_name) else 0
            )

        for chapter in sorted_chapters:
            book.spine.append(chapter)

        if not is_temp:
            print("📚 Tổng số chương trong spine: " + str(len(sorted_chapters)))

        # Tạo mục lục
        toc = [epub.Link('intro.xhtml', 'Giới thiệu', 'intro')]
        for chapter in sorted_chapters:
            toc.append(epub.Link(chapter.file_name, chapter.title, chapter.id))

        book.toc = toc

        if not is_temp:
            print("📋 Đã tạo mục lục với " + str(len(toc)) + " mục")

        # Sửa tệp điều hướng trước khi lưu
        fix_navigation_files(book, is_temp)

        # Chia nhỏ các chương quá dài
        split_large_chapters(book, is_temp)

        # Lưu EPUB
        try:
            epub.write_epub(output_path, book, {})

            if not is_temp:
                print("✅ Đã lưu thành công EPUB tại: " + output_path)

            # Kiểm tra kích thước file
            if not is_temp:
                file_size = os.path.getsize(output_path)
                print("📊 Kích thước file: " + str(round(file_size / (1024*1024), 2)) + " MB")

            return True
        except Exception as e:
            print("❌ Lỗi khi ghi file EPUB: " + str(e))
            traceback.print_exc()
            raise
    except Exception as e:
        print("❌ Lỗi khi lưu EPUB: " + str(e))
        traceback.print_exc()
        raise

# Hàm chính để tải truyện
def download_novel(url, start_chapter_index=None, end_chapter_index=None):

    # Start background saver thread
    saver_thread = threading.Thread(target=checkpoint_saver_thread, daemon=True)
    saver_thread.start()

    # Khởi động thread lưu debug
    debug_thread = threading.Thread(target=debug_save_thread, daemon=True)
    debug_thread.start()

    try:
        # Lấy thông tin truyện
        print("📚 Đang lấy thông tin truyện...")
        novel_info = get_novel_info(url)

        # Kiểm tra xem có danh sách chương không
        if not novel_info['chapters_list']:
            print("❌ Không thể lấy danh sách chương")
            return None

        total_chapters = len(novel_info['chapters_list'])
        print(f"📚 Tổng số chương: {total_chapters}")

        # Lấy loại trang web
        site_type = novel_info['site_type']
        print(f"🌐 Loại trang web: {site_type}")

        # Sắp xếp chương theo index
        sorted_chapters = sorted(novel_info['chapters_list'], key=lambda x: x.get('index', 0))

        # Tên file epub
        epub_filename = novel_info['title'] + ".epub"
        local_epub_path = epub_filename
        temp_epub_path = os.path.join(temp_folder, epub_filename)
        final_epub_path = os.path.join(main_folder, epub_filename)

        # Kiểm tra nếu file đã tồn tại
        book = None
        intro = None
        existing_chapters = []
        existing_epub = False

         # Kiểm tra file trong bộ nhớ local trước
        if os.path.exists(local_epub_path):
            print("🔍 Tìm thấy file EPUB ở local: " + local_epub_path)
            try:
                print("TODO: comment")
                # book, intro, _ = load_existing_epub(local_epub_path)
                # existing_epub = True
            except Exception as e:
                print(f"⚠️ Không thể đọc file EPUB local ({e}), kiểm tra tiếp các vị trí khác")

        if not existing_epub:
            for check_path in [temp_epub_path, final_epub_path]:
                if os.path.exists(check_path):
                    print("🔍 Tìm thấy file EPUB: " + check_path)
                    try:
                        print("TODO: comment")
                        # book, intro, _ = load_existing_epub(check_path)
                        # existing_epub = True
                        break
                    except Exception as e:
                        print(f"⚠️ Không thể đọc file EPUB {check_path} ({e}), tiếp tục kiểm tra")

        # Nếu truyện chưa tồn tại, tạo mới
        if not existing_epub:
            print("🆕 Tạo file EPUB mới...")
            book, intro = create_epub(novel_info)
            existing_chapters = []
        else:
            # Lấy danh sách chapters hiện có
            try:
                # Tìm chương bằng mẫu tên tệp trước
                existing_chapters = [item for item in book.items if isinstance(item, epub.EpubHtml)
                           and item.file_name.startswith('chapter_') and item.file_name.endswith('.xhtml')]

                # Đảm bảo tất cả các chương có ID phù hợp
                for item in existing_chapters:
                    if not hasattr(item, 'id') or not item.id:
                        try:
                            chapter_num = int(item.file_name.split('_')[1].split('.')[0])
                            item.id = 'chapter_' + str(chapter_num)
                        except Exception as e:
                            print("⚠️ Lỗi khi tạo ID cho chapter từ file_name: " + str(e))

                print("📚 Đã tìm thấy " + str(len(existing_chapters)) + " chương trong file EPUB hiện có")
            except Exception as e:
                print("⚠️ Lỗi khi lấy danh sách chương từ file EPUB: " + str(e))
                traceback.print_exc()
                existing_chapters = []

        # Hiển thị lựa chọn tải
        print("\n=== 📥 LỰA CHỌN TẢI ===")
        print(f"1. Tải tất cả các chương ({total_chapters} chương)")
        print("2. Tải từ chương x đến chương y")
        download_choice = input("Nhập lựa chọn (1 hoặc 2, mặc định 1): ").strip() or "1"

        if download_choice == "1":
            # Tải tất cả chương
            download_chapters = sorted_chapters
            print(f"📥 Bạn đã chọn tải tất cả {len(download_chapters)} chương")
        else:
            # Tải từ chương x đến chương y
            print(f"Danh sách chương có index từ 1 đến {len(sorted_chapters)}")

            # Nếu đã có tham số từ bên ngoài
            if start_chapter_index is not None and end_chapter_index is not None:
                start_idx = start_chapter_index
                end_idx = end_chapter_index
            else:
                # Nhập từ người dùng
                while True:
                    try:
                        start_idx = int(input(f"Nhập index chương bắt đầu (1-{len(sorted_chapters)}): "))
                        if 1 <= start_idx <= len(sorted_chapters):
                            break
                        print(f"⚠️ Index phải từ 1 đến {len(sorted_chapters)}")
                    except ValueError:
                        print("⚠️ Vui lòng nhập một số nguyên")

                while True:
                    try:
                        end_idx = int(input(f"Nhập index chương kết thúc ({start_idx}-{len(sorted_chapters)}): "))
                        if start_idx <= end_idx <= len(sorted_chapters):
                            break
                        print(f"⚠️ Index phải từ {start_idx} đến {len(sorted_chapters)}")
                    except ValueError:
                        print("⚠️ Vui lòng nhập một số nguyên")

            # Lấy danh sách chương cần tải
            download_chapters = sorted_chapters[start_idx-1:end_idx]
            print(f"📥 Bạn đã chọn tải {len(download_chapters)} chương từ index {start_idx} đến {end_idx}")

        # Danh sách các ID chương đã tồn tại
        existing_chapter_ids = set()
        for chapter in existing_chapters:
            try:
                chapter_id = int(chapter.id.split('_')[1])
                existing_chapter_ids.add(chapter_id)
            except Exception as e:
                print(f"⚠️ Không thể xác định ID chương từ {chapter.id}: {e}")

        print(f"🔍 Đã tìm thấy {len(existing_chapter_ids)} ID chương hiện có trong EPUB")

        # Lọc danh sách chương cần tải (chỉ tải những chương chưa có)
        chapters_to_download = []
        for chapter_info in download_chapters:
            chapter_index = chapter_info.get('index')
            if chapter_index not in existing_chapter_ids:
                chapters_to_download.append(chapter_info)

        print(f"📥 Cần tải {len(chapters_to_download)} chương mới")

        if not chapters_to_download:
            print("✅ Tất cả các chương đã có, không cần tải thêm")
            # Vẫn lưu EPUB để cập nhật điều hướng và tối ưu hóa
            save_epub(book, intro, existing_chapters, final_epub_path, False)
            return final_epub_path

        # Hiển thị thông tin các chương cần tải
        print("\n=== 📝 THÔNG TIN TẢI ===")
        print(f"🔢 Tổng số chương cần tải: {len(chapters_to_download)}")
        if chapters_to_download:
            first_chapter = chapters_to_download[0]
            last_chapter = chapters_to_download[-1]
            print(f"📌 Từ: {first_chapter.get('name', 'Không tên')} (Index {first_chapter.get('index')})")
            print(f"📌 Đến: {last_chapter.get('name', 'Không tên')} (Index {last_chapter.get('index')})")

        new_chapters = []

        for chapter_info in tqdm(chapters_to_download, desc="Đang tải chương"):
            try:
                chapter_index = chapter_info.get('index')

                # Tải nội dung chương theo loại trang web
                chapter_data = get_chapter_content(url, chapter_info, site_type, novel_info['title'])

                # Thêm chương vào EPUB
                chapter = add_chapter_to_epub(book, chapter_data, chapter_index)
                new_chapters.append(chapter)

                # Lưu tạm sau mỗi 50 chương
                if len(new_chapters) % checkpoint_interval == 0:
                    all_chapters = existing_chapters + new_chapters
                    save_queue.put((book, intro, all_chapters, temp_epub_path))
                    print(f"\n\n📥 Đã lên lịch lưu tạm sau khi tải {len(new_chapters)} chương\n\n")

                # Nghỉ ngắn giữa các request để tránh bị chặn
                delay_time = random.uniform(0.5, 1)
                delay(delay_time)
            except Exception as e:
                print(f"❌ Lỗi khi tải chương index {chapter_index}: {e}")
                traceback.print_exc()
                # Nếu gặp lỗi, lưu trạng thái hiện tại và dừng
                try:
                    all_chapters = existing_chapters + new_chapters
                    save_queue.put((book, intro, all_chapters, temp_epub_path))
                    # Wait for save to complete in case of error
                    save_queue.join()
                    print(f"⚠️ Đã lưu trạng thái sau khi tải {len(new_chapters)} chương")
                except Exception as save_err:
                    print(f"❌❌ Lỗi khi lưu trạng thái sau khi gặp lỗi: {save_err}")
                    traceback.print_exc()

        # Kết hợp chương mới và chương cũ
        all_chapters = existing_chapters + new_chapters

        # Lưu bản cuối vào thư mục chính
        print("🏁 Tải hoàn tất, đang lưu EPUB cuối cùng...")

        save_epub(book, intro, all_chapters, final_epub_path, False)

        # Xóa file tạm sau khi lưu thành công
        if os.path.exists(final_epub_path):
            delete_temp_file(temp_epub_path)

        print("\n🎉🎉🎉 Hoàn tất! Truyện đã được lưu tại: " + final_epub_path)
        return final_epub_path
    except Exception as e:
        print("❌ Lỗi không xử lý được: " + str(e))
        traceback.print_exc()
        return None
    finally:
        # Signal thread to exit and wait for completion
        exit_event.set()
        debug_save_event.set()
        saver_thread.join(timeout=5.0)
        debug_thread.join(timeout=5.0)


# Hàm chính
def main():
    try:
        print("=== ✨✨✨ TRÌNH TẢI TRUYỆN ✨✨✨ ===")

        # Nhập URL truyện
        url = input("📝 Nhập URL truyện: ")

        # Tải truyện
        print("🔗 URL truyện: " + url)
        download_novel(url)
    except Exception as e:
        print("❌ Lỗi không xử lý được trong chương trình chính: " + str(e))
        traceback.print_exc()

# Chạy chương trình
if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("❌ Lỗi nghiêm trọng: " + str(e))
        traceback.print_exc()
        print("Chương trình đã kết thúc không như mong đợi.")