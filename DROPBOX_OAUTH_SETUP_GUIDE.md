# Setting Up Dropbox OAuth Integration

The Novel Downloader API now supports OAuth 2.0 for authentication with Dropbox, providing a more secure and user-friendly integration compared to the previous access token method.

## Creating a Dropbox App

1. Go to the [Dropbox Developer App Console](https://www.dropbox.com/developers/apps)
2. Click "Create app"
3. Select the following options:
   - Choose **Scoped access** (API)
   - Choose **Full Dropbox** access type
   - Enter a unique name for your app (e.g., "Novel Downloader API")
4. Click "Create app"

## Configuring App Permissions

1. In your new app's settings page, go to the **Permissions** tab
2. Enable the following permissions:
   - `files.content.write` - To upload EPUB files to Dropbox
   - `files.content.read` - To read existing files
   - `sharing.write` - To create shareable links
3. Click "Submit" to save the permission changes

## Configure OAuth Settings

1. In the app settings page, go to the **Settings** tab
2. Add the following Redirect URIs:
   - For local development: `http://localhost:10000/dropbox/callback`
   - For your deployed application: `https://your-app-url.com/dropbox/callback`
3. Click "Add" and then "Submit" to save
4. Note your **App key** and **App secret** from the app settings page

## Update Your Environment Variables

Add these values to your `.env` file:

```
DROPBOX_APP_KEY=your_app_key
DROPBOX_APP_SECRET=your_app_secret
```

## Authenticating with Dropbox

1. Start your application
2. Navigate to `/dropbox/status` in your browser
3. Click "Connect to Dropbox"
4. You'll be redirected to Dropbox to authorize the application
5. After authorization, you'll be redirected back to the application
6. Your application now has a refresh token that can be used to get new access tokens automatically

## How OAuth Integration Works

1. The application redirects users to Dropbox's OAuth authorization page
2. After the user approves, Dropbox redirects back to your app with an authorization code
3. Your app exchanges this code for an access token and a refresh token
4. The access token is used for API calls but expires after 4 hours
5. The refresh token is used to automatically get new access tokens when needed
6. The tokens are securely stored in a file in the application's secure directory

## Benefits Over the Previous Method

- Users don't need to manually create and copy access tokens
- No need to update expired tokens manually
- Better security with proper OAuth flow
- Supports token refresh, reducing authentication errors
- Clear user interface for connecting and disconnecting Dropbox

## Troubleshooting

If you encounter issues with Dropbox authentication:

1. Check if your Redirect URI is properly configured in the Dropbox app settings
2. Ensure your app has the required permissions enabled
3. Verify that both the App key and App secret are correctly set in your environment variables
4. Check the application logs for detailed error messages
5. Try disconnecting and reconnecting to Dropbox from the `/dropbox/status` page