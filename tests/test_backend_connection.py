import pytest
from database.queries import (
    get_user_by_id,
    get_summary_stats,
    get_recent_transactions,
    get_category_breakdown,
)

SEED_USER_ID = 1
NO_EXPENSE_USER_ID = 9999


# ================================================================== #
# SECTION 1: Transaction History  (Subagent 1)                       #
# ================================================================== #

def test_get_recent_transactions_returns_list(app):
    result = get_recent_transactions(SEED_USER_ID)
    assert isinstance(result, list)
    assert len(result) == 8


def test_get_recent_transactions_order_newest_first(app):
    result = get_recent_transactions(SEED_USER_ID)
    assert result[0]['date'] == 'Apr 18, 2026'
    assert result[-1]['date'] == 'Apr 01, 2026'


def test_get_recent_transactions_has_required_keys(app):
    result = get_recent_transactions(SEED_USER_ID)
    assert len(result) > 0
    row = result[0]
    assert 'date' in row
    assert 'description' in row
    assert 'category' in row
    assert 'amount' in row


def test_get_recent_transactions_empty_for_unknown_user(app):
    result = get_recent_transactions(NO_EXPENSE_USER_ID)
    assert result == []


# ================================================================== #
# SECTION 2: User Info + Summary Stats  (Subagent 2)                 #
# ================================================================== #

def test_get_user_by_id_valid(app):
    result = get_user_by_id(SEED_USER_ID)
    assert result is not None
    assert result['name'] == 'Demo User'
    assert result['email'] == 'demo@spendly.com'
    assert result['initials'] == 'DU'
    assert 'member_since' in result


def test_get_user_by_id_nonexistent(app):
    assert get_user_by_id(NO_EXPENSE_USER_ID) is None


def test_get_summary_stats_with_expenses(app):
    result = get_summary_stats(SEED_USER_ID)
    assert result['total_spent'] == 264.25
    assert result['tx_count'] == 8
    assert result['top_category'] == 'Bills'


def test_get_summary_stats_zero_expense_user(app):
    result = get_summary_stats(NO_EXPENSE_USER_ID)
    assert result['total_spent'] == 0
    assert result['tx_count'] == 0
    assert result['top_category'] == '—'


def test_profile_unauthenticated_redirects(client):
    response = client.get('/profile')
    assert response.status_code == 302
    assert '/login' in response.headers['Location']


def test_profile_authenticated_returns_200(auth_client):
    response = auth_client.get('/profile')
    assert response.status_code == 200
    assert b'Demo User' in response.data
    assert b'demo@spendly.com' in response.data


# ================================================================== #
# SECTION 3: Category Breakdown  (Subagent 3)                        #
# ================================================================== #

def test_get_category_breakdown_sorted_by_total_desc(app):
    result = get_category_breakdown(SEED_USER_ID)
    assert len(result) == 7
    totals = [item['total'] for item in result]
    assert totals == sorted(totals, reverse=True)
    assert result[0]['name'] == 'Bills'
    assert result[0]['total'] == 95.0


def test_get_category_breakdown_pcts_sum_to_100(app):
    result = get_category_breakdown(SEED_USER_ID)
    assert sum(item['pct'] for item in result) == 100
    bills_pct = next(item['pct'] for item in result if item['name'] == 'Bills')
    assert bills_pct == 36


def test_get_category_breakdown_has_required_keys(app):
    result = get_category_breakdown(SEED_USER_ID)
    assert len(result) > 0
    row = result[0]
    assert 'name' in row
    assert 'total' in row
    assert 'pct' in row


def test_get_category_breakdown_empty_for_unknown_user(app):
    result = get_category_breakdown(NO_EXPENSE_USER_ID)
    assert result == []
