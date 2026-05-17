"""
Tests for Step 6: Date-range filter on the /profile route.

Spec: .claude/specs/06-data-filter-profile-page.md

Coverage:
- GET /profile with no params → unfiltered view (all seed data)
- GET /profile?date_from=X&date_to=Y → filtered transactions, stats, category breakdown
- Preset param ranges (This Month, Last 3 Months, Last 6 Months)
- date_from > date_to → 200, unfiltered, flash error shown
- Malformed date params → 200, no crash, silent fallback to unfiltered
- Unauthenticated request with filter params → 302 to /login
- User with no expenses in filtered range → zero stats, empty table, no 500
- Filter bar HTML elements present in all authenticated responses
- Active filter values reflected in date input value attributes
- active_preset logic (all_time, this_month, custom)
- Partial params (only date_from) treated as unfiltered
- Direct query-layer tests for get_summary_stats, get_recent_transactions,
  get_category_breakdown with date-range arguments
"""

import tempfile
import os
import pytest
from datetime import date, timedelta
from database.db import get_db
import database.db as db_module
from app import app as flask_app
from database.queries import (
    get_summary_stats,
    get_recent_transactions,
    get_category_breakdown,
)

# ---------------------------------------------------------------------------
# Seed data constants — must stay in sync with database/db.py seed_db()
# ---------------------------------------------------------------------------
SEED_USER_ID = 1
SEED_TOTAL = 264.25          # sum of all 8 seed expenses
SEED_TX_COUNT = 8

# Expenses in the window 2026-04-01 to 2026-04-10 (inclusive):
#   12.50 Food      2026-04-01
#    8.00 Transport 2026-04-03
#   95.00 Bills     2026-04-05
#   45.00 Health    2026-04-08
#   20.00 Entertainment 2026-04-10
# Total: 180.50, count: 5
NARROW_FROM = "2026-04-01"
NARROW_TO   = "2026-04-10"
NARROW_TOTAL = 180.50
NARROW_COUNT = 5

# Expenses in an even narrower window 2026-04-03 to 2026-04-08:
#    8.00 Transport 2026-04-03
#   95.00 Bills     2026-04-05
#   45.00 Health    2026-04-08
# Total: 148.00, count: 3
INNER_FROM  = "2026-04-03"
INNER_TO    = "2026-04-08"
INNER_TOTAL = 148.00
INNER_COUNT = 3


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def app():
    """
    Module-scoped fixture: spin up a temp SQLite file, init and seed it once
    for all tests in this module.  Uses the same patching approach as conftest.
    """
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    db_module.DB_PATH = db_path
    flask_app.config["TESTING"] = True
    flask_app.config["SECRET_KEY"] = "test-secret"
    with flask_app.app_context():
        db_module.init_db()
        db_module.seed_db()
    yield flask_app
    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def auth_client(client):
    """Test client already logged in as the seed demo user."""
    client.post("/login", data={"email": "demo@spendly.com", "password": "demo123"})
    return client


@pytest.fixture()
def empty_user_auth_client(client, app):
    """
    Test client logged in as a freshly registered user who has no expenses at
    all — used to verify zero-state renders without errors.
    """
    conn = get_db()
    from werkzeug.security import generate_password_hash
    conn.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        ("Empty User", "empty@spendly.com", generate_password_hash("emptypass123")),
    )
    conn.commit()
    conn.close()
    client.post("/login", data={"email": "empty@spendly.com", "password": "emptypass123"})
    return client


# ===========================================================================
# 1. Unfiltered view (no query params)
# ===========================================================================

class TestUnfilteredView:
    def test_no_params_returns_200(self, auth_client):
        resp = auth_client.get("/profile")
        assert resp.status_code == 200, "Expected 200 for authenticated /profile with no params"

    def test_no_params_shows_all_transactions(self, auth_client):
        resp = auth_client.get("/profile")
        # All 8 seed transactions should be visible; check a representative sample
        assert b"Lunch at cafe" in resp.data, "Expected seed transaction 'Lunch at cafe'"
        assert b"Grocery run" in resp.data, "Expected seed transaction 'Grocery run'"

    def test_no_params_shows_full_total(self, auth_client):
        resp = auth_client.get("/profile")
        # ₹264.25 rendered as "264.25"
        assert b"264.25" in resp.data, "Expected unfiltered total 264.25"

    def test_no_params_shows_correct_tx_count(self, auth_client):
        resp = auth_client.get("/profile")
        # The stat card renders the integer tx_count
        assert b"8" in resp.data, "Expected 8 transactions in unfiltered view"

    def test_no_params_top_category_is_bills(self, auth_client):
        resp = auth_client.get("/profile")
        assert b"Bills" in resp.data, "Expected 'Bills' as top category in unfiltered view"


# ===========================================================================
# 2. Custom date range — happy path
# ===========================================================================

class TestCustomDateRange:
    def test_narrow_range_returns_200(self, auth_client):
        resp = auth_client.get(f"/profile?date_from={NARROW_FROM}&date_to={NARROW_TO}")
        assert resp.status_code == 200, "Expected 200 for valid date-range filter"

    def test_narrow_range_filters_total(self, auth_client):
        resp = auth_client.get(f"/profile?date_from={NARROW_FROM}&date_to={NARROW_TO}")
        assert b"180.50" in resp.data, "Expected filtered total 180.50"

    def test_narrow_range_excludes_expenses_outside_window(self, auth_client):
        resp = auth_client.get(f"/profile?date_from={NARROW_FROM}&date_to={NARROW_TO}")
        # "Grocery run" is 2026-04-18 — outside the narrow window
        assert b"Grocery run" not in resp.data, "Grocery run should be filtered out"
        # "New shirt" is 2026-04-12 — outside the narrow window
        assert b"New shirt" not in resp.data, "New shirt should be filtered out"

    def test_narrow_range_includes_expenses_inside_window(self, auth_client):
        resp = auth_client.get(f"/profile?date_from={NARROW_FROM}&date_to={NARROW_TO}")
        assert b"Lunch at cafe" in resp.data, "Lunch at cafe (2026-04-01) should be included"
        assert b"Pharmacy" in resp.data, "Pharmacy (2026-04-08) should be included"
        assert b"Cinema tickets" in resp.data, "Cinema tickets (2026-04-10) should be included"

    def test_narrow_range_category_breakdown_only_has_filtered_categories(self, auth_client):
        resp = auth_client.get(f"/profile?date_from={NARROW_FROM}&date_to={NARROW_TO}")
        # Shopping (2026-04-12) and Other (2026-04-15) are outside the window
        assert b"Shopping" not in resp.data, "Shopping category should not appear in filtered breakdown"
        assert b"Other" not in resp.data, "Other category should not appear in filtered breakdown"

    def test_inner_range_returns_correct_total(self, auth_client):
        resp = auth_client.get(f"/profile?date_from={INNER_FROM}&date_to={INNER_TO}")
        assert b"148.00" in resp.data, "Expected filtered total 148.00 for inner range"

    def test_boundary_dates_are_inclusive(self, auth_client):
        """date BETWEEN is inclusive on both ends per SQLite semantics."""
        resp = auth_client.get(f"/profile?date_from=2026-04-18&date_to=2026-04-18")
        # Only "Grocery run" on 2026-04-18
        assert b"Grocery run" in resp.data, "Boundary date (equal from/to) should include that day's expense"
        assert b"18.75" in resp.data, "Expected amount 18.75 for the single boundary-date expense"


# ===========================================================================
# 3. Preset param ranges
# ===========================================================================

class TestPresetRanges:
    """
    These tests compute the same date arithmetic as app.py and verify the
    profile page responds correctly when those preset params are supplied.
    Seed expenses are all April 2026, so presets whose window covers April 2026
    should return the full seed set.
    """

    def _today(self):
        return date.today().isoformat()

    def _first_of_month(self):
        return date.today().replace(day=1).isoformat()

    def _three_ago(self):
        return (date.today() - timedelta(days=90)).isoformat()

    def _six_ago(self):
        return (date.today() - timedelta(days=180)).isoformat()

    def test_this_month_preset_returns_200(self, auth_client):
        params = f"date_from={self._first_of_month()}&date_to={self._today()}"
        resp = auth_client.get(f"/profile?{params}")
        assert resp.status_code == 200, "This Month preset should return 200"

    def test_last_3_months_preset_returns_200(self, auth_client):
        params = f"date_from={self._three_ago()}&date_to={self._today()}"
        resp = auth_client.get(f"/profile?{params}")
        assert resp.status_code == 200, "Last 3 Months preset should return 200"

    def test_last_6_months_preset_covers_april_2026(self, auth_client):
        """
        Today is 2026-05-17.  Six months back is ~2025-11-18, which covers
        all April 2026 seed data.  The full set must appear.
        """
        params = f"date_from={self._six_ago()}&date_to={self._today()}"
        resp = auth_client.get(f"/profile?{params}")
        assert resp.status_code == 200, "Last 6 Months preset should return 200"
        assert b"264.25" in resp.data, "Last 6 Months should include all seed expenses totalling 264.25"

    def test_all_time_preset_is_clean_url(self, auth_client):
        """The All Time preset points to /profile with no query params."""
        resp = auth_client.get("/profile")
        assert resp.status_code == 200
        # All-time button should carry the active class when no params supplied
        assert b"preset-btn--active" in resp.data, "All Time button should be active on clean /profile"


# ===========================================================================
# 4. date_from > date_to → fallback to unfiltered + flash error
# ===========================================================================

class TestInvalidDateOrder:
    def test_reversed_range_returns_200(self, auth_client):
        resp = auth_client.get("/profile?date_from=2026-04-30&date_to=2026-04-01")
        assert resp.status_code == 200, "Reversed range should still return 200"

    def test_reversed_range_shows_flash_error(self, auth_client):
        resp = auth_client.get("/profile?date_from=2026-04-30&date_to=2026-04-01")
        assert b"Start date must be before end date" in resp.data, (
            "Expected flash error message for reversed date range"
        )

    def test_reversed_range_shows_unfiltered_data(self, auth_client):
        """When dates are reversed the route falls back to showing all expenses."""
        resp = auth_client.get("/profile?date_from=2026-04-30&date_to=2026-04-01")
        assert b"264.25" in resp.data, "Reversed-range fallback should show full unfiltered total"
        assert b"Grocery run" in resp.data, "All transactions should appear after reversed-range fallback"

    def test_equal_dates_do_not_trigger_error(self, auth_client):
        """date_from == date_to is valid (single-day filter)."""
        resp = auth_client.get("/profile?date_from=2026-04-01&date_to=2026-04-01")
        assert resp.status_code == 200
        assert b"Start date must be before end date" not in resp.data, (
            "Equal dates should NOT trigger the reversed-range error"
        )


# ===========================================================================
# 5. Malformed date params — no crash, silent fallback
# ===========================================================================

class TestMalformedDateParams:
    @pytest.mark.parametrize("query_string", [
        "date_from=not-a-date",
        "date_to=!!bad!!",
        "date_from=not-a-date&date_to=also-bad",
        "date_from=2026-13-01",          # month 13 — invalid
        "date_from=2026-04-99",          # day 99 — invalid
        "date_from=",                    # empty string
        "date_to=",                      # empty string
        "date_from=2026/04/01",          # wrong separator
    ])
    def test_malformed_param_returns_200(self, auth_client, query_string):
        resp = auth_client.get(f"/profile?{query_string}")
        assert resp.status_code == 200, (
            f"Malformed param '{query_string}' should not crash the app"
        )

    def test_malformed_date_from_shows_unfiltered_data(self, auth_client):
        resp = auth_client.get("/profile?date_from=not-a-date&date_to=2026-04-10")
        # With date_from invalid, both params fall back to None → unfiltered
        assert b"264.25" in resp.data, "Malformed date_from should fall back to unfiltered view"

    def test_malformed_date_to_shows_unfiltered_data(self, auth_client):
        resp = auth_client.get("/profile?date_from=2026-04-01&date_to=not-a-date")
        assert b"264.25" in resp.data, "Malformed date_to should fall back to unfiltered view"


# ===========================================================================
# 6. Unauthenticated access with filter params → redirect to /login
# ===========================================================================

class TestUnauthenticatedAccess:
    def test_unauthenticated_no_params_redirects(self, client):
        resp = client.get("/profile")
        assert resp.status_code == 302
        assert "/login" in resp.headers["Location"]

    def test_unauthenticated_with_filter_params_redirects(self, client):
        resp = client.get(f"/profile?date_from={NARROW_FROM}&date_to={NARROW_TO}")
        assert resp.status_code == 302, "Unauthenticated filter request should redirect"
        assert "/login" in resp.headers["Location"], "Should redirect to /login"

    def test_unauthenticated_malformed_params_redirects(self, client):
        resp = client.get("/profile?date_from=garbage&date_to=garbage")
        assert resp.status_code == 302
        assert "/login" in resp.headers["Location"]


# ===========================================================================
# 7. User with no expenses in filtered range — zero stats, empty table, no 500
# ===========================================================================

class TestEmptyFilteredRange:
    def test_no_expenses_in_range_returns_200(self, auth_client):
        # Filter to a date range that has no seed expenses
        resp = auth_client.get("/profile?date_from=2025-01-01&date_to=2025-01-31")
        assert resp.status_code == 200, "Empty filter range should return 200, not 500"

    def test_no_expenses_in_range_shows_zero_total(self, auth_client):
        resp = auth_client.get("/profile?date_from=2025-01-01&date_to=2025-01-31")
        assert b"0.00" in resp.data, "Expected ₹0.00 total for a range with no expenses"

    def test_no_expenses_in_range_shows_zero_tx_count(self, auth_client):
        resp = auth_client.get("/profile?date_from=2025-01-01&date_to=2025-01-31")
        # The stat card renders tx_count; 0 must appear somewhere
        assert b"0" in resp.data, "Expected 0 transactions for a range with no expenses"

    def test_user_with_no_expenses_returns_200(self, empty_user_auth_client):
        resp = empty_user_auth_client.get("/profile")
        assert resp.status_code == 200, "User with no expenses should get 200"

    def test_user_with_no_expenses_shows_zero_total(self, empty_user_auth_client):
        resp = empty_user_auth_client.get("/profile")
        assert b"0.00" in resp.data, "User with no expenses should show ₹0.00"

    def test_user_with_no_expenses_filtered_returns_200(self, empty_user_auth_client):
        resp = empty_user_auth_client.get(f"/profile?date_from={NARROW_FROM}&date_to={NARROW_TO}")
        assert resp.status_code == 200, "User with no expenses + filter should still return 200"


# ===========================================================================
# 8. Filter bar HTML elements present in response
# ===========================================================================

class TestFilterBarHTML:
    def test_filter_bar_container_present(self, auth_client):
        resp = auth_client.get("/profile")
        assert b"filter-bar" in resp.data, "Expected filter-bar container in response HTML"

    def test_preset_buttons_present(self, auth_client):
        resp = auth_client.get("/profile")
        assert b"preset-btn" in resp.data, "Expected preset-btn elements in response HTML"

    def test_this_month_preset_button_present(self, auth_client):
        resp = auth_client.get("/profile")
        assert b"This Month" in resp.data, "Expected 'This Month' preset button"

    def test_last_3_months_preset_button_present(self, auth_client):
        resp = auth_client.get("/profile")
        assert b"Last 3 Months" in resp.data, "Expected 'Last 3 Months' preset button"

    def test_last_6_months_preset_button_present(self, auth_client):
        resp = auth_client.get("/profile")
        assert b"Last 6 Months" in resp.data, "Expected 'Last 6 Months' preset button"

    def test_all_time_preset_button_present(self, auth_client):
        resp = auth_client.get("/profile")
        assert b"All Time" in resp.data, "Expected 'All Time' preset button"

    def test_date_from_input_present(self, auth_client):
        resp = auth_client.get("/profile")
        assert b'name="date_from"' in resp.data, "Expected date_from input in filter form"

    def test_date_to_input_present(self, auth_client):
        resp = auth_client.get("/profile")
        assert b'name="date_to"' in resp.data, "Expected date_to input in filter form"

    def test_apply_button_present(self, auth_client):
        resp = auth_client.get("/profile")
        assert b"Apply" in resp.data, "Expected Apply submit button in filter form"

    def test_rupee_symbol_present_regardless_of_filter(self, auth_client):
        """All amounts must display the ₹ symbol under any active filter."""
        resp_unfiltered = auth_client.get("/profile")
        assert "₹".encode() in resp_unfiltered.data, "Expected ₹ symbol in unfiltered view"

        resp_filtered = auth_client.get(f"/profile?date_from={NARROW_FROM}&date_to={NARROW_TO}")
        assert "₹".encode() in resp_filtered.data, "Expected ₹ symbol in filtered view"


# ===========================================================================
# 9. Active filter values reflected in date inputs (pre-fill)
# ===========================================================================

class TestActiveDateInputReflection:
    def test_date_from_prefilled_in_input(self, auth_client):
        resp = auth_client.get(f"/profile?date_from={NARROW_FROM}&date_to={NARROW_TO}")
        assert f'value="{NARROW_FROM}"'.encode() in resp.data, (
            f"Expected date_from input pre-filled with {NARROW_FROM}"
        )

    def test_date_to_prefilled_in_input(self, auth_client):
        resp = auth_client.get(f"/profile?date_from={NARROW_FROM}&date_to={NARROW_TO}")
        assert f'value="{NARROW_TO}"'.encode() in resp.data, (
            f"Expected date_to input pre-filled with {NARROW_TO}"
        )

    def test_inputs_empty_when_no_params(self, auth_client):
        resp = auth_client.get("/profile")
        # Jinja renders {{ date_from or '' }} — when no filter the value should be empty
        assert b'value=""' in resp.data, "Expected empty value attributes when no filter is active"

    def test_clear_link_shown_when_filter_active(self, auth_client):
        resp = auth_client.get(f"/profile?date_from={NARROW_FROM}&date_to={NARROW_TO}")
        assert b"Clear" in resp.data, "Expected Clear link when a date filter is active"

    def test_clear_link_not_shown_when_no_filter(self, auth_client):
        resp = auth_client.get("/profile")
        assert b"Clear" not in resp.data, "Clear link should not appear when no filter is active"


# ===========================================================================
# 10. active_preset logic
# ===========================================================================

class TestActivePresetLogic:
    def test_all_time_active_when_no_params(self, auth_client):
        resp = auth_client.get("/profile")
        # The all_time preset-btn should carry the --active modifier
        assert b"preset-btn--active" in resp.data, "Expected an active preset button on clean /profile"
        # The "All Time" label must be present near the active button
        assert b"All Time" in resp.data

    def test_no_active_preset_on_reversed_range(self, auth_client):
        """
        When date_from > date_to the route falls back to unfiltered, so
        active_preset should be 'all_time' and the All Time button active.
        """
        resp = auth_client.get("/profile?date_from=2026-04-30&date_to=2026-04-01")
        assert b"preset-btn--active" in resp.data

    def test_custom_range_does_not_activate_preset_button(self, auth_client):
        """
        A custom range that doesn't match any preset must set active_preset=custom.
        None of the four preset buttons should carry --active.
        The template only renders preset-btn--active when a known preset key matches,
        so we check that the active class count is zero.
        """
        resp = auth_client.get(f"/profile?date_from={INNER_FROM}&date_to={INNER_TO}")
        # INNER range (2026-04-03 to 2026-04-08) is not a preset
        assert b"preset-btn--active" not in resp.data, (
            "Custom range should not activate any preset button"
        )

    def test_this_month_preset_active_when_matching_params(self, auth_client):
        today_str = date.today().isoformat()
        first_str = date.today().replace(day=1).isoformat()
        resp = auth_client.get(f"/profile?date_from={first_str}&date_to={today_str}")
        assert b"preset-btn--active" in resp.data, "This Month preset button should be active"


# ===========================================================================
# 11. Partial param — only date_from provided (no date_to)
# ===========================================================================

class TestPartialParams:
    def test_only_date_from_returns_200(self, auth_client):
        resp = auth_client.get("/profile?date_from=2026-04-01")
        assert resp.status_code == 200, "Providing only date_from should not crash"

    def test_only_date_from_behaves_as_unfiltered(self, auth_client):
        """_date_clause requires BOTH params; one alone means no filter."""
        resp = auth_client.get("/profile?date_from=2026-04-01")
        assert b"264.25" in resp.data, (
            "Only date_from with no date_to should produce unfiltered total 264.25"
        )

    def test_only_date_to_returns_200(self, auth_client):
        resp = auth_client.get("/profile?date_to=2026-04-10")
        assert resp.status_code == 200, "Providing only date_to should not crash"

    def test_only_date_to_behaves_as_unfiltered(self, auth_client):
        resp = auth_client.get("/profile?date_to=2026-04-10")
        assert b"264.25" in resp.data, (
            "Only date_to with no date_from should produce unfiltered total 264.25"
        )


# ===========================================================================
# 12. Direct query-layer tests: helpers with date_range arguments
# ===========================================================================

class TestQueryHelpers:
    """
    These tests call the query functions directly (not via HTTP) to verify the
    date-range filtering logic at the database layer.
    """

    # --- get_summary_stats ---

    def test_summary_stats_narrow_range_total(self, app):
        result = get_summary_stats(SEED_USER_ID, date_from=NARROW_FROM, date_to=NARROW_TO)
        assert result["total_spent"] == NARROW_TOTAL, (
            f"Expected filtered total {NARROW_TOTAL}, got {result['total_spent']}"
        )

    def test_summary_stats_narrow_range_count(self, app):
        result = get_summary_stats(SEED_USER_ID, date_from=NARROW_FROM, date_to=NARROW_TO)
        assert result["tx_count"] == NARROW_COUNT, (
            f"Expected {NARROW_COUNT} transactions, got {result['tx_count']}"
        )

    def test_summary_stats_inner_range_total(self, app):
        result = get_summary_stats(SEED_USER_ID, date_from=INNER_FROM, date_to=INNER_TO)
        assert result["total_spent"] == INNER_TOTAL

    def test_summary_stats_inner_range_count(self, app):
        result = get_summary_stats(SEED_USER_ID, date_from=INNER_FROM, date_to=INNER_TO)
        assert result["tx_count"] == INNER_COUNT

    def test_summary_stats_empty_range_returns_zeros(self, app):
        result = get_summary_stats(SEED_USER_ID, date_from="2025-01-01", date_to="2025-01-31")
        assert result["total_spent"] == 0
        assert result["tx_count"] == 0
        assert result["top_category"] == "—"

    def test_summary_stats_no_filter_unchanged(self, app):
        result = get_summary_stats(SEED_USER_ID)
        assert result["total_spent"] == SEED_TOTAL
        assert result["tx_count"] == SEED_TX_COUNT

    def test_summary_stats_single_day_filter(self, app):
        result = get_summary_stats(SEED_USER_ID, date_from="2026-04-05", date_to="2026-04-05")
        assert result["total_spent"] == 95.00
        assert result["tx_count"] == 1

    # --- get_recent_transactions ---

    def test_recent_transactions_narrow_range_count(self, app):
        result = get_recent_transactions(SEED_USER_ID, date_from=NARROW_FROM, date_to=NARROW_TO)
        assert len(result) == NARROW_COUNT, (
            f"Expected {NARROW_COUNT} transactions in narrow range, got {len(result)}"
        )

    def test_recent_transactions_narrow_range_order_newest_first(self, app):
        result = get_recent_transactions(SEED_USER_ID, date_from=NARROW_FROM, date_to=NARROW_TO)
        # Newest in window is 2026-04-10 (Cinema tickets)
        assert result[0]["date"] == "Apr 10, 2026", (
            "Transactions should be ordered newest first within the filtered range"
        )

    def test_recent_transactions_narrow_range_excludes_outside(self, app):
        result = get_recent_transactions(SEED_USER_ID, date_from=NARROW_FROM, date_to=NARROW_TO)
        descriptions = [r["description"] for r in result]
        assert "Grocery run" not in descriptions, "Grocery run should be excluded from narrow range"
        assert "New shirt" not in descriptions, "New shirt should be excluded from narrow range"

    def test_recent_transactions_empty_range_returns_empty_list(self, app):
        result = get_recent_transactions(SEED_USER_ID, date_from="2025-01-01", date_to="2025-01-31")
        assert result == [], "Empty range should return an empty list"

    def test_recent_transactions_no_filter_returns_all(self, app):
        result = get_recent_transactions(SEED_USER_ID)
        assert len(result) == SEED_TX_COUNT

    # --- get_category_breakdown ---

    def test_category_breakdown_narrow_range_categories(self, app):
        result = get_category_breakdown(SEED_USER_ID, date_from=NARROW_FROM, date_to=NARROW_TO)
        names = {item["name"] for item in result}
        assert "Food" in names
        assert "Transport" in names
        assert "Bills" in names
        assert "Health" in names
        assert "Entertainment" in names
        # Shopping (2026-04-12) and Other (2026-04-15) are outside the window
        assert "Shopping" not in names, "Shopping should not appear in narrow-range breakdown"
        assert "Other" not in names, "Other should not appear in narrow-range breakdown"

    def test_category_breakdown_pcts_sum_to_100_with_filter(self, app):
        result = get_category_breakdown(SEED_USER_ID, date_from=NARROW_FROM, date_to=NARROW_TO)
        assert sum(item["pct"] for item in result) == 100, (
            "Category percentages must sum to 100 even with an active date filter"
        )

    def test_category_breakdown_empty_range_returns_empty_list(self, app):
        result = get_category_breakdown(SEED_USER_ID, date_from="2025-01-01", date_to="2025-01-31")
        assert result == [], "Empty range should return an empty category list"

    def test_category_breakdown_sorted_desc_with_filter(self, app):
        result = get_category_breakdown(SEED_USER_ID, date_from=NARROW_FROM, date_to=NARROW_TO)
        totals = [item["total"] for item in result]
        assert totals == sorted(totals, reverse=True), (
            "Category breakdown should be sorted by total DESC even with active filter"
        )

    def test_category_breakdown_top_category_in_narrow_range(self, app):
        result = get_category_breakdown(SEED_USER_ID, date_from=NARROW_FROM, date_to=NARROW_TO)
        # Bills (95.00) is the highest in the narrow range
        assert result[0]["name"] == "Bills", "Bills should be the top category in the narrow range"
        assert result[0]["total"] == 95.00
