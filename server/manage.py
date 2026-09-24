"""Local-only operator tools. No unauthenticated web admin endpoints."""
import argparse
import json
import sqlite3
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('action', choices=['reports', 'revoke'])
parser.add_argument('user_id', nargs='?')
parser.add_argument('--database', default='data/gas.sqlite3')
args = parser.parse_args()
if not Path(args.database).is_file():
    parser.error('Database does not exist')
with sqlite3.connect(args.database) as db:
    db.row_factory = sqlite3.Row
    if args.action == 'reports':
        rows = db.execute('''SELECT r.id,r.timestamp,r.reason,r.reporter,v.responder
            FROM reports r JOIN votes v ON v.id=r.vote_id ORDER BY r.timestamp DESC LIMIT 100''')
        print(json.dumps([dict(row) for row in rows], ensure_ascii=False, indent=2))
    else:
        if not args.user_id:
            parser.error('revoke requires USER_ID')
        cursor = db.execute('DELETE FROM sessions WHERE user_id=?', (args.user_id,))
        print(f'Revoked {cursor.rowcount} sessions')
