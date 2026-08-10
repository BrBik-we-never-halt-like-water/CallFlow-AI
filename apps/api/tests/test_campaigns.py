"""Built-in campaign constants and the slug helper.

Custom, org-owned campaigns are no longer module-global state - they're rows
created through `app/api/v1/routes/campaigns.py` and
`app/database/repositories/campaigns.py`, RLS-scoped like everything else
under an organisation. That code path needs a real Postgres connection to
exercise (the uniqueness loop, the RLS cross-tenant boundary) and isn't
covered by this repo's local test run, which has no live database - it needs
an integration test against a real Supabase branch.
"""

from app.domain.campaigns import slugify


def test_slugify() -> None:
    assert slugify("Renewal Outreach!") == "renewal-outreach"
    assert slugify("  多  ") == "campaign"
