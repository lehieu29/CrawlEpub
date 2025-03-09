# Novel Downloader API

A web API for downloading novels from popular web novel sites like metruyencv.com and tangthuvien.net. The downloaded novels are saved in EPUB format and can be stored on Dropbox for easy access.

## Features

- Download novels from metruyencv.com and tangthuvien.net
- Convert to EPUB format optimized for e-readers
- Real-time progress tracking with WebSocket
- Dropbox integration for cloud storage
- Web interface to monitor downloads
- RESTful API for programmatic access

## Setup on Replit

### 1. Create a New Replit Project

1. Go to [Replit](https://replit.com/) and sign in or create an account
2. Click on "Create Repl" button
3. Choose "Python" as the language
4. Give your project a name (e.g., "novel-downloader-api")
5. Click "Create Repl"

### 2. Add the Project Files

Upload or create the following files in your Replit project:

- `main.py` - The main Flask application
- `novel_downloader.py` - The novel downloader module
- `dropbox_storage.py` - The Dropbox integration module
- `requirements.txt` - The Python dependencies
- `.env` - Configuration file (create this from `.env.example`)
- `templates/` - Directory containing HTML templates
  - `templates/base.html` - Base template
  - `templates/index.html` - Main page template
  - `templates/api_docs.html` - API documentation template

### 3. Setup Dropbox Integration (Optional)

To enable Dropbox integration for storing downloaded novels:

1. Go to [Dropbox Developer Console](https://www.dropbox.com/developers/apps)
2. Click "Create app"
3. Choose "Scoped access" -> "Full Dropbox" access
4. Give your app a name
5. Go to the "Permissions" tab and enable the following permissions:
   - `files.content.write`
   - `files.content.read`
   - `sharing.write`
6. Go to the "Settings" tab and add your Replit domain to "OAuth 2 Redirect URIs"
7. Generate an access token under "Generated access token"
8. Copy the access token and paste it in the `.env` file:
```
DROPBOX_ACCESS_TOKEN=your_access_token_here
```

### 4. Configure Environment Variables

Update the `.env` file with your configuration:

```
# Server configuration
SECRET_KEY=your_random_secret_key
PORT=8080

# Dropbox configuration (optional)
DROPBOX_ACCESS_TOKEN=your_dropbox_access_token
```

### 5. Start the Application

In Replit, simply click the "Run" button to start the application. The web interface should be available at the URL provided by Replit.

## API Documentation

The API documentation is available at `/api-docs` when the application is running. It provides details on the available endpoints and how to use them.

### Basic Endpoints

- `POST /api/download` - Start a novel download
- `GET /api/status/:download_id` - Get download status
- `GET /api/logs` - Get recent logs

### WebSocket Events

- `log_update` - New log entry
- `status_update` - Download status change
- `download_completed` - Download completed
- `download_failed` - Download failed

## Usage Examples

### Using the Web Interface

1. Open the web interface in your browser
2. Enter the novel URL in the form
3. Add your access token if needed for premium content
4. Click "Download Novel" and wait for the process to complete
5. Download your EPUB file from the provided link

### Using the API

```javascript
// Example: Start a download
fetch('https://your-replit-url.repl.co/api/download', {
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
  return fetch(`https://your-replit-url.repl.co/api/status/${data.download_id}`);
})
.then(response => response.json())
.then(statusData => {
  console.log('Status:', statusData.status);
});
```

## Folder Structure

The downloaded novels are organized as follows:

- `novel_temp/` - Temporary files during download
- `novel_output/` - Final EPUB files

## License

This project is open-source and available under the MIT License.

## Acknowledgements

This project is based on the novel downloader script originally created for Google Colab, adapted for a web API interface.