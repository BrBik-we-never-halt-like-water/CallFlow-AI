# Supabase setup

Everything a human has to click, and the environment variables that follow from it.
The schema itself is never edited here - it lives in `apps/api/alembic/versions/` and is
applied with `alembic upgrade head`.

---

## 1. Project

Create a project, or use the existing one.

| Setting | Value                                                                                                                       |
| ------- | --------------------------------------------------------------------------------------------------------------------------- |
| Region  | **ap-south-1 (Mumbai)** for an India-first product                                                                          |
| Plan    | Free for development. **Pro before the first paying customer** - Free pauses a project after 7 days idle and has no backups |

## 2. Dashboard settings

**Auth → Providers → Email**

| Setting                 | Value       | Why                                                                                                                                                                                                    |
| ----------------------- | ----------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Email provider          | **Enabled** |                                                                                                                                                                                                        |
| **Confirm email**       | **OFF**     | Current product decision: sign up and sign in with credentials, no inbox round-trip. Supabase ships this **ON**, so it must be turned off explicitly or every signup lands unconfirmed and logins fail |
| Minimum password length | 12          | Matches the client-side rule in `components/ui/password-strength.tsx`                                                                                                                                  |

**Auth → URL Configuration**

| Setting       | Value                                                                                          |
| ------------- | ---------------------------------------------------------------------------------------------- |
| Site URL      | `http://localhost:3000` (dev) · your domain in production                                      |
| Redirect URLs | `http://localhost:3000/**` - needed for the password-reset link to return to `/reset-password` |

**Auth → Providers → Google** - deliberately **not configured**. Email and password only
for now. Adding it later is additive: a client ID, a secret, and a button.

## 3. Email - two separate paths, both need Resend

There are two independent ways mail leaves this system, configured in two different
places. Fixing one does nothing for the other.

**Password reset** goes through Supabase Auth's mailer (`resetPasswordForEmail` in
`apps/web/lib/auth/actions.ts`). Supabase's built-in sender allows only a few messages
per hour and is explicitly not for production. Signup doesn't depend on it (confirmation
is off), but password reset does, and it fails silently once the quota is gone. Set
**Auth → SMTP Settings** to a real provider (Resend) before relying on password reset.
See `ISSUES.md` #19.

**Team invitations** never touch Supabase Auth's mailer at all, so the SMTP Settings
above have no effect on them. `POST /api/v1/organisations/me/invitations`
(`apps/api/app/api/v1/routes/organisations.py`) calls `EmailGateway.send_invitation()`
(`apps/api/app/integrations/email/resend.py`), which POSTs directly to
`https://api.resend.com/emails` using `RESEND_API_KEY` / `RESEND_FROM_EMAIL` from `.env`.
For this to work:

1. `RESEND_API_KEY` must be set to a real Resend API key (a send-only/restricted key is
   fine - that's the normal, more-secure key type for this).
2. `RESEND_FROM_EMAIL`'s domain **must be a domain verified in the Resend dashboard**
   (Domains → Add Domain → add the DNS records Resend gives you → Verify) before Resend
   will relay _any_ mail from that address. There is no way to satisfy this from code -
   it requires DNS records only the domain's actual owner can add.

Until that domain is verified, every invitation fails with a `502` whose message names
the unverified domain and points here - this is expected, not a new bug, and is exactly
what happened in `ISSUES.md` #51.

**A temporary stopgap for your own local testing only:** Resend's `onboarding@resend.dev`
sender is pre-verified and needs no domain of your own. Point `RESEND_FROM_EMAIL` at it
(e.g. `CallFlow AI <onboarding@resend.dev>`) and invitations will send - but, per Resend's
current documentation, only to the email address your Resend account itself was signed up
with, not to an actual invitee. Do this by hand when you need it; do not make it the
default, since a silent restriction on who can be invited is exactly the kind of thing
CLAUDE.md's non-negotiable #9 rules out.

## 4. Environment variables

**`.env`** at the repo root - the API reads this regardless of working directory.

| Variable                   | Where to find it                                                                                                             |
| -------------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| `SUPABASE_URL`             | Settings → API → Project URL                                                                                                 |
| `SUPABASE_PROJECT_REF`     | The `<ref>` inside that URL                                                                                                  |
| `SUPABASE_PUBLISHABLE_KEY` | Settings → API Keys → publishable (`sb_publishable_…`)                                                                       |
| `SUPABASE_SECRET_KEY`      | Settings → API Keys → secret (`sb_secret_…`). **Server only**                                                                |
| `SUPABASE_JWKS_URL`        | `https://<ref>.supabase.co/auth/v1/.well-known/jwks.json`                                                                    |
| `DATABASE_URL`             | Settings → Database → connection string, port **5432**                                                                       |
| `DIRECT_URL`               | The same. Used by Alembic                                                                                                    |
| `PHONE_HASH_PEPPER`        | Generate once: `python -c "import secrets; print(secrets.token_urlsafe(32))"`                                                |
| `RESEND_API_KEY`           | resend.com dashboard → API Keys. A send-only restricted key is fine                                                          |
| `RESEND_FROM_EMAIL`        | `Name <address@your-verified-domain>` - the domain must be verified under resend.com dashboard → Domains first; see §3 above |

**`apps/web/.env.local`** - only the public values ever reach the browser.

```
NEXT_PUBLIC_SUPABASE_URL=https://<ref>.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=sb_publishable_…
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
API_URL=http://127.0.0.1:8000
NEXT_PUBLIC_SITE_URL=http://localhost:3000
```

### Two things that will bite you

**Percent-encode special characters in the database password.** A password containing
`@` breaks the URL parser, which reads the first `@` as the host delimiter and fails with
a confusing connection error. `BrBik@0192837465` must be written `BrBik%400192837465`.

**`DATABASE_URL` is the direct connection (5432), not the pooler (6543).** The API is a
long-lived process with its own pool, and every request runs `SET LOCAL ROLE authenticated`
so RLS applies - transaction-mode pooling makes that session state unpredictable, and
asyncpg's prepared statements are unsupported there. Revisit only if the API moves to a
serverless runtime.

**`PHONE_HASH_PEPPER` is effectively permanent.** It is mixed into every suppression
`phone_hash`; changing it orphans every existing do-not-call entry.

## 5. Apply the schema

```bash
pip install -r requirements-dev.txt
cd apps/api
python -m alembic upgrade head
python -m alembic check      # expect: No new upgrade operations detected
```

## 6. Verify

```bash
cd apps/api && python -m pytest -q          # 95 tests, 11 of them cross-tenant RLS
```

Then run both services and sign up through the UI:

```bash
cd apps/api && uvicorn app.main:app --reload --port 8000
cd apps/web && npm run dev                  # :3000
```

`/app` should redirect to `/login` while signed out, and signing up should land you on
`/app/welcome` with your organisation named from your email domain.

## 7. Facts about this project worth knowing

**`postgres` holds `BYPASSRLS`.** A plain connection sees every organisation's rows, and
`FORCE ROW LEVEL SECURITY` does not change that. RLS is real only because each request
switches to the `authenticated` role - see `CLAUDE.md` §4b.

**Supabase validates email deliverability.** Domains without MX records are rejected with
`email_address_invalid`, so `example.com` and invented domains cannot be used as test
fixtures. Seed test users through the admin API instead:

```
POST /auth/v1/admin/users
Authorization: Bearer <SUPABASE_SECRET_KEY>
{ "email": "...", "password": "...", "email_confirm": true }
```

That skips both the domain check and the email send, so it does not consume the sender
quota.

**Never edit the schema in the dashboard.** It is read-only in this project; the SQL
editor and table editor will drift the database from `alembic/versions/` and the next
`alembic check` will report changes nobody can explain.
