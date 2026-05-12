# API Contract

## Base URL
`FEEDBACK_API_BASE_URL` (normalized by trimming trailing `/`)

## Auth
- Optional header: `X-API-Key: <FEEDBACK_API_TOKEN>`
- Session cookie from login is required for admin endpoints.

## Endpoints
1. `POST /api/auth/login`
- body: `{ "user_id": "admin", "password": "***" }`
- success: auth session and cookie

2. `GET /api/admin/feedback`
- requires admin session
- returns feedback list sorted by unresolved first and latest created first

3. `POST /api/admin/feedback/{feedback_id}/reply`
- body: `{ "reply_message": "...", "close": true }`
- use `close=true` to resolve/close after replying

## Relevant Fields
- `id`: feedback ID
- `message`: user feedback text
- `resolved_at`: null means unresolved
- `reply_message`: admin reply text
