# CloudFront Signed Cookie API (PoC)

Lambda-driven Web API that returns CloudFront signed cookies using canned policy.

## Browser behavior for Set-Cookie

To persist cookies in a browser, the response host and cookie Domain rules must match.

- If this API is called directly via execute-api domain, do not set CookieDomain to a CloudFront domain. The browser will reject it.
- Recommended: expose this API through the same CloudFront domain (for example `/auth/signed-cookie`) and then set `CookieDomain` to that domain or keep it empty for host-only cookies.
- HTTPS is required because cookies are emitted with `Secure`.

## Folder layout

- `template.yaml`: AWS SAM template (HTTP API + Lambda + IAM)
- `src/app.py`: Lambda handler to generate signed cookies
- `src/private_key.pem`: Local private key file for test only (do not commit)
- `src/requirements.txt`: Python dependencies
- `events/get_signed_cookie.json`: sample event for local invoke

## Prerequisites

1. CloudFront distribution configured with Trusted Key Group.
2. CloudFront public key already associated to a key group.
3. Test stage only: place private key file at `src/private_key.pem`.
  - PEM text (`-----BEGIN PRIVATE KEY----- ... -----END PRIVATE KEY-----`), or
  - JSON: `{"private_key":"-----BEGIN PRIVATE KEY-----..."}`

## Build and validate

```bash
sam validate -t template.yaml
sam build --use-container -t template.yaml
```

## Local test

```bash
sam local invoke SignedCookieFunction -t template.yaml -e events/get_signed_cookie.json
```

## Deploy example

```bash
sam deploy \
  --stack-name cloudfront-signed-cookie-api-poc \
  --template-file .aws-sam/build/template.yaml \
  --capabilities CAPABILITY_IAM \
  --resolve-s3 \
  --parameter-overrides \
    CloudFrontDomain=d111111abcdef8.cloudfront.net \
    CloudFrontKeyPairId=K1234567890ABC \
    CloudFrontPrivateKeyFilePath=/var/task/private_key.pem \
    DebugErrorResponse=true \
    CookieDomain=d111111abcdef8.cloudfront.net
```

Note:
- 依存ライブラリを含めるため、`sam build` の後は `.aws-sam/build/template.yaml` を指定して deploy してください。
- `sam build`/`sam deploy` 時に `src/private_key.pem` がパッケージに同梱されます。
- テスト専用です。本番ではSecrets ManagerやSSM SecureStringに移行してください。
- For production, move the key to Secrets Manager or SSM SecureString.

## API usage

```bash
curl "https://<api-id>.execute-api.<region>.amazonaws.com/signed-cookie?resource=/private/*&expires_in=300" -i
```

For easier debugging in test stage, detailed error response is enabled by default:

- `DebugErrorResponse=true`
- 500 response includes exception type, traceback, request summary, and config summary
- Set `DebugErrorResponse=false` to disable detailed output

Expected behavior:
- HTTP 200
- `Set-Cookie` values for CloudFront signed cookie fields
- Cookie attributes include `Secure`, `HttpOnly`, `SameSite=None`

## Notes for frontend fetch()

If the browser calls this endpoint via JavaScript from another origin, use:

- client: `fetch(url, { credentials: "include" })`
- API side: enable CORS with a specific origin (not `*`) and allow credentials
