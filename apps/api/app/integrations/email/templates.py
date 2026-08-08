"""HTML for the transactional emails `resend.py` sends.

Kept separate from the transport so the markup can be read and changed without
touching the HTTP client, and so nothing here forgets to escape a user-controlled
string — `org_name` is free text a person typed into Settings, not something this
module can trust.

Table-based layout with inline styles throughout: most email clients strip
`<style>` blocks and ignore modern CSS, so anything not inlined is a gamble.
"""

from __future__ import annotations

from html import escape

_TEXT = "#0b0f12"
_TEXT_DIM = "#47545a"
_RULE = "#dde2e1"
_SURFACE = "#f4f6f5"
_INVERSE = "#12181c"

# System-font stack: the deployed app's Archivo/Inter Tight webfonts don't load
# in email clients, so this approximates the same "bold display, plain body"
# feel with fonts every client already has.
_FONT_DISPLAY = "'Helvetica Neue', Helvetica, Arial, sans-serif"
_FONT_BODY = "-apple-system, 'Segoe UI', Helvetica, Arial, sans-serif"

_ROLE_HINT = {
    "owner": "full control of the organisation, including billing",
    "admin": "everything except deleting the organisation",
    "operator": "campaigns, runs, and escalations",
    "viewer": "read-only access to results",
}


def invitation_email(*, org_name: str, role: str, accept_url: str) -> tuple[str, str]:
    """Returns `(subject, html)`."""
    safe_org = escape(org_name)
    safe_role = escape(role)
    safe_url = escape(accept_url, quote=True)
    role_hint = escape(_ROLE_HINT.get(role, "access to the organisation"))
    article = "an" if role[:1].lower() in "aeiou" else "a"

    # The subject is a plain-text field, not HTML — html.escape() would make an
    # ordinary apostrophe in an org name show up as a literal "&#x27;" in the
    # recipient's inbox, a worse and more visible bug than the one being
    # guarded against here. Strip line breaks instead, so a multi-line org name
    # can't produce a mangled or unexpectedly wrapped subject line.
    subject_org = " ".join(org_name.splitlines()) or org_name
    subject = f"You've been invited to {subject_org} on CallFlow AI"

    html = f"""\
<!doctype html>
<html>
  <body style="margin:0; padding:0; background-color:{_SURFACE}; font-family:{_FONT_BODY};">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
           style="background-color:{_SURFACE}; padding:32px 16px;">
      <tr>
        <td align="center">
          <table role="presentation" width="480" cellpadding="0" cellspacing="0"
                 style="max-width:480px; background-color:#ffffff; border:1px solid {_RULE};
                        border-radius:12px; overflow:hidden;">
            <tr>
              <td style="padding:28px 32px 20px 32px; border-bottom:1px solid {_RULE};">
                <span style="font-family:{_FONT_DISPLAY}; font-weight:700; font-size:15px;
                             letter-spacing:0.02em; color:{_TEXT};">CallFlow</span>
                <span style="font-family:'SFMono-Regular', Consolas, monospace; font-size:13px;
                             color:{_TEXT_DIM};"> AI</span>
              </td>
            </tr>
            <tr>
              <td style="padding:32px;">
                <h1 style="margin:0 0 16px 0; font-family:{_FONT_DISPLAY}; font-weight:700;
                           font-size:22px; line-height:1.3; color:{_TEXT};">
                  Join {safe_org} on CallFlow AI
                </h1>
                <p style="margin:0 0 12px 0; font-size:15px; line-height:1.6; color:{_TEXT_DIM};">
                  You've been invited as {article} <strong style="color:{_TEXT};">{safe_role}</strong>
                  &mdash; {role_hint}.
                </p>
                <p style="margin:0 0 28px 0; font-size:15px; line-height:1.6; color:{_TEXT_DIM};">
                  Nothing happens on your account until you accept.
                </p>
                <table role="presentation" cellpadding="0" cellspacing="0">
                  <tr>
                    <td style="border-radius:8px; background-color:{_INVERSE};">
                      <a href="{safe_url}"
                         style="display:inline-block; padding:12px 24px; font-size:15px;
                                font-weight:600; color:#ffffff; text-decoration:none;
                                border-radius:8px;">
                        Accept the invitation
                      </a>
                    </td>
                  </tr>
                </table>
                <p style="margin:28px 0 0 0; font-size:13px; line-height:1.5; color:{_TEXT_DIM};">
                  Or paste this link into your browser:<br>
                  <a href="{safe_url}" style="color:{_TEXT_DIM}; word-break:break-all;">{safe_url}</a>
                </p>
              </td>
            </tr>
            <tr>
              <td style="padding:20px 32px; border-top:1px solid {_RULE};
                         font-size:12px; line-height:1.5; color:{_TEXT_DIM};">
                If you weren't expecting this, you can ignore this email &mdash; nothing
                is created or shared until the invitation is accepted.
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>
"""
    return subject, html
