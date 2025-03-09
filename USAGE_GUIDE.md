# Novel Downloader API Usage Guide

This guide provides comprehensive instructions on how to set up and use the Novel Downloader API.

## Table of Contents

1. [Setting Up the Project](#setting-up-the-project)
2. [Using the Web Interface](#using-the-web-interface)
3. [Using the API Endpoints](#using-the-api-endpoints)
4. [Real-time Updates with WebSocket](#real-time-updates-with-websocket)
5. [Dropbox Integration](#dropbox-integration)
6. [Troubleshooting](#troubleshooting)

## Setting Up the Project

### On Replit

1. Go to [Replit](https://replit.com/) and sign in or create an account
2. Click on "Create Repl" button
3. Choose "Import from GitHub"
4. Enter the repository URL for this project
5. Alternatively, choose "Python" as the language and create a new project
6. Upload all the project files to your Replit project

### Local Setup

For local development:

1. Clone the repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Create a `.env` file based on `.env.example` with your configurations
4. Run the application:
   ```bash
   python main.py
   ```

## Using the Web Interface

The web interface provides an easy way to download novels and monitor their progress.

### Downloading a Novel

1. Open the web interface in your browser (your Replit URL or `http://localhost:8080` for local development)
2. Enter the novel URL in the form field (e.g., `https://metruyencv.com/truyen/example-novel`)
3. If the novel requires an access token (premium/VIP content), enter it in the "Access Token" field
4. Click "Download Novel"
5. The download will be queued and start processing

### Monitoring Download Progress

1. The download will appear in the "Active Downloads" section
2. You can view real-time logs in the "Download Logs" section
3. Click the "Eye" icon to view detailed information about a specific download
4. When the download completes, a Dropbox download link will be available (if Dropbox integration is configured)

### Filtering Logs

You can filter logs by selecting options from the dropdown:
- **All Logs**: Show all log messages
- **Info Only**: Show only information messages
- **Warnings & Errors**: Show warning and error messages
- **Errors Only**: Show only error messages

## Using the API Endpoints

The API provides several endpoints for programmatic access.

### Start a Download

**Endpoint:** `POST /api/download`

**Request Body:**
```json
{
  "url": "https://metruyencv.com/truyen/example-novel",
  "cookie": "optional_access_token"
}
```

**Response:**
```json
{
  "success": true,
  "download_id": "download_1615482631",
  "message": "Download has been queued"
}
```

**Example:**
```javascript
fetch('https://your-replit-url.repl.co/api/download', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    url: 'https://metruyencv.com/truyen/example-novel',
    cookie: 'your_access_token'  // Optional
  })
})
.then(response => response.json())
.then(data => console.log(data));
```

### Check Download Status

**Endpoint:** `GET /api/status/:download_id`

**Parameters:**
- `download_id`: The ID of the download task
- `logs` (query parameter): Number of log entries to return (default: 20)

**Response:**
```json
{
  "success": true,
  "download_id": "download_1615482631",
  "status": {
    "status": "in_progress",
    "url": "https://metruyencv.com/truyen/example-novel",
    "submit_time": 1615482631,
    "start_time": 1615482635,
    "progress": 50,
    "file_path": "/path/to/novel.epub",
    "dropbox_url": "https://dl.dropboxusercontent.com/..."
  },
  "logs": [
    "2023-03-01 12:34:56 - [INFO] - Starting download...",
    "2023-03-01 12:35:01 - [INFO] - Downloaded chapter 1"
  ]
}
```

**Example:**
```javascript
fetch('https://your-replit-url.repl.co/api/status/download_1615482631?logs=50')
.then(response => response.json())
.then(data => console.log(data));
```

### Get Recent Logs

**Endpoint:** `GET /api/logs`

**Parameters:**
- `n` (query parameter): Number of log entries to return (default: 100)

**Response:**
```json
{
  "success": true,
  "logs": [
    "2023-03-01 12:34:56 - [INFO] - Server started",
    "2023-03-01 12:35:01 - [INFO] - New download queued"
  ]
}
```

**Example:**
```javascript
fetch('https://your-replit-url.repl.co/api/logs?n=50')
.then(response => response.json())
.then(data => console.log(data));
```

## Real-time Updates with WebSocket

The API provides real-time updates via WebSocket.

### Connecting to WebSocket

```javascript
// Connect to WebSocket
const socket = io('https://your-replit-url.repl.co');

// Connection events
socket.on('connect', () => {
  console.log('Connected to WebSocket server');
});

socket.on('disconnect', () => {
  console.log('Disconnected from WebSocket server');
});
```

### WebSocket Events

```javascript
// Log updates
socket.on('log_update', (data) => {
  console.log(`[${data.level.toUpperCase()}] ${data.message}`);
});

// Status updates
socket.on('status_update', (data) => {
  console.log(`Status update for ${data.download_id}: ${data.status}`);
});

// Download completed
socket.on('download_completed', (data) => {
  console.log(`Download completed: ${data.download_id}`);
  console.log(`Download URL: ${data.dropbox_url}`);
});

// Download failed
socket.on('download_failed', (data) => {
  console.log(`Download failed: ${data.download_id}`);
  console.log(`Error: ${data.error}`);
});
```

## Dropbox Integration

To store downloaded novels in Dropbox:

1. Go to [Dropbox Developer Console](https://www.dropbox.com/developers/apps)
2. Create a new app with "Full Dropbox" access
3. Generate an access token
4. Add the token to your `.env` file:
   ```
   DROPBOX_ACCESS_TOKEN=your_access_token_here
   ```

When a novel download is completed, it will be automatically uploaded to Dropbox in the `/NovelDownloader/` folder, and a download link will be provided.

## Troubleshooting

### Common Issues

1. **Download fails to start**:
   - Check if the novel URL is correct
   - For premium content, ensure you've provided a valid access token
   - Check the logs for specific error messages

2. **WebSocket connection issues**:
   - Ensure your firewall/network allows WebSocket connections
   - Try refreshing the page to reconnect

3. **Dropbox integration not working**:
   - Verify that you've provided a valid Dropbox access token
   - Check if the token has the necessary permissions
   - Check the logs for Dropbox-specific error messages

4. **Novel not downloading correctly**:
   - Some chapters might be locked or require premium access
   - The website structure might have changed, requiring an update to the scraper
   - Check the logs for specific errors during the download process

### Getting Help

If you encounter any issues not covered in this guide:

1. Check the full logs for detailed error messages
2. Look for similar issues in the GitHub repository
3. Open a new issue with detailed information about the problem, including logs and steps to reproduce

---

This guide covers the basic usage of the Novel Downloader API. For more detailed information, refer to the API documentation available at `/api-docs` when the server is running.