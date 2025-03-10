# Novel Downloader API

A powerful web API for downloading novels from popular web novel sites like metruyencv.com and tangthuvien.net. The downloaded novels are converted to EPUB format for convenient reading on e-readers or mobile devices.

![Novel Downloader API](https://raw.githubusercontent.com/username/novel-downloader-api/main/preview.png)

## Features

- ✅ Download novels from metruyencv.com and tangthuvien.net
- ✅ Convert to EPUB format optimized for e-readers
- ✅ Real-time progress tracking with WebSocket
- ✅ Dropbox integration for cloud storage
- ✅ Web interface to monitor downloads
- ✅ RESTful API for programmatic access
- ✅ Support for premium/VIP content with access tokens

## Deployment Options

### Quick Setup on Replit

1. Create a new Replit project:
   - Go to [Replit](https://replit.com/) and sign in or create an account
   - Click on "Create Repl" button
   - Choose "Python" as the language
   - Give your project a name (e.g., "novel-downloader-api")
   - Click "Create Repl"

2. Upload project files:
   - Upload all the provided files to your Replit project
   - Alternatively, import directly from GitHub if you've forked the repository

3. Configure environment variables:
   - Create a `.env` file or use Replit's Secrets manager
   - Set `SECRET_KEY` to a random string
   - Optionally, set `DROPBOX_ACCESS_TOKEN` for Dropbox integration

4. Run the project:
   - Click the "Run" button in Replit
   - The web interface will be available at your Replit URL

### Deploy to Render.com

1. Push your code to a GitHub repository

2. Sign up or log in to [Render.com](https://render.com/)

3. Create a new Web Service:
   - Connect your GitHub repository
   - Set build command: `pip install -r requirements.txt`
   - Set start command: `gunicorn --worker-class eventlet -w 1 -b 0.0.0.0:$PORT "wsgi:create_app()"`

4. Configure environment variables:
   - Add `SECRET_KEY` with a random string
   - Optionally, add `DROPBOX_ACCESS_TOKEN` for Dropbox integration

5. Deploy the service

### Local Development Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/novel-downloader-api.git
   cd novel-downloader-api
   ```

2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Create a `.env` file:
   ```
   SECRET_KEY=your_random_secret_key
   PORT=8080
   DROPBOX_ACCESS_TOKEN=your_dropbox_access_token  # Optional
   ```

5. Run the setup script:
   ```bash
   python setup.py
   ```

6. Start the server:
   ```bash
   python main.py
   ```

7. Access the web interface at http://localhost:8080

### Google Colab Usage

For those who prefer using Google Colab for novel downloading:

1. Open [Google Colab](https://colab.research.google.com/)

2. Create a new notebook

3. Upload the `crawl_epub_google_colab.py` file to your Google Drive

4. In a Colab cell, mount your Google Drive:
   ```python
   from google.colab import drive
   drive.mount('/content/drive')
   ```

5. Run the script directly from your Drive:
   ```python
   %run /content/drive/My\ Drive/path_to_script/crawl_epub_google_colab.py
   ```

6. Follow the interactive prompts to download novels

## API Documentation

### Basic Endpoints

- `POST /api/download` - Start a novel download
  ```json
  {
    "url": "https://metruyencv.com/truyen/example-novel",
    "cookie": "optional_access_token"
  }
  ```

- `GET /api/status/:download_id` - Get download status
- `GET /api/logs` - Get recent logs
- `GET /downloads/:filename` - Download a novel file directly

### WebSocket Events

- `log_update` - New log entry
- `status_update` - Download status change
- `download_completed` - Download completed
- `download_failed` - Download failed

## Dropbox Integration Setup

To enable Dropbox integration for storing downloaded novels:

1. Go to [Dropbox Developer Console](https://www.dropbox.com/developers/apps)
2. Click "Create app"
3. Choose "Scoped access" -> "Full Dropbox" access
4. Give your app a name
5. Go to the "Permissions" tab and enable:
   - `files.content.write`
   - `files.content.read`
   - `sharing.write`
6. Generate an access token under "Generated access token"
7. Add the token to your `.env` file:
   ```
   DROPBOX_ACCESS_TOKEN=your_access_token_here
   ```

## Keeping the API Running 24/7

For Replit users, you can keep your API running 24/7 by using a service like UptimeRobot:

1. Register at [UptimeRobot](https://uptimerobot.com/)
2. Add a new monitor:
   - Choose "HTTP(s)" type
   - Enter your Replit URL + "/ping" path
   - Set 5-minute monitoring interval

## Usage Examples

### Web Interface

1. Open the web interface in your browser
2. Enter the novel URL in the form
3. Add your access token if needed for premium content
4. Click "Download Novel" and wait for the process to complete
5. Download your EPUB file from the provided link

### API Usage

```javascript
// Example: Start a download
fetch('https://your-api-url.com/api/download', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    url: 'https://metruyencv.com/truyen/my-novel',
    cookie: 'optional_access_token'
  })
})
.then(response => response.json())
.then(data => {
  console.log('Download ID:', data.download_id);

  // Check status
  return fetch(`https://your-api-url.com/api/status/${data.download_id}`);
})
.then(response => response.json())
.then(statusData => {
  console.log('Status:', statusData.status);
});
```

## License

This project is open-source and available under the MIT License.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Acknowledgements

This project is based on the novel downloader script originally created for Google Colab, adapted for a web API interface.