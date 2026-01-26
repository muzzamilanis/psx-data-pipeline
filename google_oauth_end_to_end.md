# Google OAuth End-to-End Guide (Client ID, Client Secret & Refresh Token)

This guide explains **from start to finish** how to obtain:

-   Google OAuth **Client ID**
-   Google OAuth **Client Secret**
-   Google OAuth **Refresh Token**

For the following scopes:

-   https://www.googleapis.com/auth/gmail.send
-   https://www.googleapis.com/auth/drive.file
-   https://www.googleapis.com/auth/drive

------------------------------------------------------------------------

## 1. Create Google Cloud Project

1.  Go to Google Cloud Console\
2.  Create a **new project**\
3.  Select the project

------------------------------------------------------------------------

## 2. Enable Required APIs

Enable these APIs:

-   Gmail API
-   Google Drive API

Path: APIs & Services → Library

------------------------------------------------------------------------

## 3. Configure OAuth Consent Screen

1.  Go to APIs & Services → OAuth consent screen
2.  User Type: **External**
3.  Fill:
    -   App name
    -   User support email
    -   Developer contact email
4.  Add scopes:
    -   gmail.send
    -   drive
    -   drive.file
5.  Save and publish (or add test user)

------------------------------------------------------------------------

## 4. Create OAuth Client ID & Secret

1.  APIs & Services → Credentials
2.  Create Credentials → OAuth Client ID
3.  Application type: **Web application**
4.  Authorized redirect URI: http://localhost

You will receive: - Client ID - Client Secret

Save them securely.

------------------------------------------------------------------------

## 5. Revoke Previous Access (IMPORTANT)

Before generating a new refresh token, revoke old access:

https://myaccount.google.com/permissions

Remove your app if it exists.

------------------------------------------------------------------------

## 6. Generate Authorization Code

Open the following URL in your browser (replace YOUR_CLIENT_ID):

https://accounts.google.com/o/oauth2/v2/auth?client_id=YOUR_CLIENT_ID&redirect_uri=http://localhost&response_type=code&scope=https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fgmail.send%20https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fdrive.file%20https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fdrive&access_type=offline&prompt=consent

After approval, you will be redirected to:

http://localhost/?code=XXXX

Copy the **code** value only.

------------------------------------------------------------------------

## 7. Exchange Code for Tokens (PowerShell)

``` powershell
$body = @{
  client_id     = "YOUR_CLIENT_ID"
  client_secret = "YOUR_CLIENT_SECRET"
  code          = "AUTH_CODE"
  grant_type    = "authorization_code"
  redirect_uri  = "http://localhost"
}

Invoke-RestMethod `
  -Uri "https://oauth2.googleapis.com/token" `
  -Method Post `
  -Body $body `
  -ContentType "application/x-www-form-urlencoded"
```

------------------------------------------------------------------------

## 8. Response Example

``` json
{
  "access_token": "ya29...",
  "expires_in": 3599,
  "refresh_token": "1//0gXXXX",
  "scope": "gmail.send drive drive.file",
  "token_type": "Bearer"
}
```

Save the **refresh_token** securely.

------------------------------------------------------------------------

## 9. Environment Variables

``` env
GOOGLE_OAUTH_CLIENT_ID=xxxx
GOOGLE_OAUTH_CLIENT_SECRET=yyyy
GOOGLE_OAUTH_REFRESH_TOKEN=1//0gXXXX
```

------------------------------------------------------------------------

## 10. Important Notes

-   Refresh token is shown **only once**
-   Do not commit secrets to GitHub
-   Use Secret Manager or .env file
-   `drive` scope already includes `drive.file`

------------------------------------------------------------------------

## 11. Recommended Scope Sets

### Least Privilege

-   gmail.send
-   drive.file

### Full Access

-   gmail.send
-   drive

------------------------------------------------------------------------

## 12. Troubleshooting

  Issue              Fix
  ------------------ --------------------------
  No refresh token   Revoke access and retry
  403 Gmail error    Missing gmail.send scope
  404 auth URL       URL not encoded
  Token expired      Regenerate via consent

------------------------------------------------------------------------

## 13. You Are Done 🎉

You now have: - Client ID - Client Secret - Refresh Token

Ready for Gmail API, Google Drive API, agents, or automation.
