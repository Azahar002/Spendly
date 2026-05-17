from datetime import datetime
from database.db import get_db


def _date_clause(date_from, date_to):
    if date_from and date_to:
        return ' AND date BETWEEN ? AND ?', [date_from, date_to]
    return '', []


def get_user_by_id(user_id):
    """Return dict: name, email, member_since ("Month YYYY"), initials — or None."""
    conn = get_db()
    row = conn.execute(
        'SELECT name, email, created_at FROM users WHERE id = ?',
        (user_id,)
    ).fetchone()
    conn.close()
    if row is None:
        return None
    dt = datetime.strptime(row['created_at'][:19], '%Y-%m-%d %H:%M:%S')
    name = row['name']
    initials = ''.join(w[0].upper() for w in name.split()[:2])
    return {
        'name':         name,
        'email':        row['email'],
        'member_since': dt.strftime('%B %Y'),
        'initials':     initials,
    }


def get_summary_stats(user_id, date_from=None, date_to=None):
    """Return dict: total_spent (float), tx_count (int), top_category (str or "—")."""
    dc, dp = _date_clause(date_from, date_to)
    conn = get_db()
    row = conn.execute(
        'SELECT COALESCE(SUM(amount), 0) as total_spent, COUNT(*) as tx_count'
        ' FROM expenses WHERE user_id = ?' + dc,
        [user_id] + dp
    ).fetchone()
    top_row = conn.execute(
        'SELECT category FROM expenses WHERE user_id = ?' + dc
        + ' GROUP BY category ORDER BY SUM(amount) DESC LIMIT 1',
        [user_id] + dp
    ).fetchone()
    conn.close()
    return {
        'total_spent':  round(row['total_spent'], 2),
        'tx_count':     row['tx_count'],
        'top_category': top_row['category'] if top_row else '—',
    }


def get_recent_transactions(user_id, limit=10, date_from=None, date_to=None):
    """Return list of dicts: date ("Mon DD, YYYY"), description, category, amount. Newest first."""
    dc, dp = _date_clause(date_from, date_to)
    conn = get_db()
    rows = conn.execute(
        'SELECT date, description, category, amount'
        ' FROM expenses WHERE user_id = ?' + dc
        + ' ORDER BY date DESC LIMIT ?',
        [user_id] + dp + [limit]
    ).fetchall()
    conn.close()
    result = []
    for row in rows:
        dt = datetime.strptime(row['date'], '%Y-%m-%d')
        result.append({
            'date':        dt.strftime('%b %d, %Y'),
            'description': row['description'],
            'category':    row['category'],
            'amount':      row['amount'],
        })
    return result


def get_category_breakdown(user_id, date_from=None, date_to=None):
    """Return list of dicts: name, total (float), pct (int). Sorted by total DESC. pcts sum to 100."""
    dc, dp = _date_clause(date_from, date_to)
    conn = get_db()
    rows = conn.execute(
        'SELECT category as name, SUM(amount) as total'
        ' FROM expenses WHERE user_id = ?' + dc
        + ' GROUP BY category ORDER BY total DESC',
        [user_id] + dp
    ).fetchall()
    conn.close()
    if not rows:
        return []
    grand_total = sum(row['total'] for row in rows)
    items = [{'name': row['name'], 'total': round(row['total'], 2)} for row in rows]
    raw = [item['total'] / grand_total * 100 for item in items]
    floored = [int(p) for p in raw]
    remainders = sorted(range(len(items)), key=lambda i: -(raw[i] - floored[i]))
    needed = 100 - sum(floored)
    for j in range(needed):
        floored[remainders[j]] += 1
    for i, item in enumerate(items):
        item['pct'] = floored[i]
    return items
