"""Account admin CLI for a LibreCrawl server.

There is no admin UI, so approving accounts and changing tiers happens here
rather than through hand-written SQL against data/users.db.

    python manage.py users
    python manage.py approve <username> [--tier user]
    python manage.py set-tier <username> <guest|user|extra|admin>

In Docker, run it inside the container:

    docker compose exec librecrawl python manage.py users
"""
import argparse
import sys

from dotenv import load_dotenv

load_dotenv()

from src import auth_db  # noqa: E402

TIERS = ('guest', 'user', 'extra', 'admin')


def _find(cursor, username):
    cursor.execute('SELECT id, username, verified, tier FROM users WHERE username = ?', (username,))
    user = cursor.fetchone()
    if not user:
        sys.exit(f"no account named '{username}' (see: python manage.py users)")
    return user


def cmd_users(args):
    with auth_db.get_db() as conn:
        rows = conn.execute(
            'SELECT id, username, email, verified, tier, created_at, last_login '
            'FROM users ORDER BY id').fetchall()
    if not rows:
        print('no accounts')
        return
    print(f'{"id":>4} {"username":<22} {"email":<32} {"verified":<9} {"tier":<6} {"last login":<19}')
    for row in rows:
        print(f'{row["id"]:>4} {row["username"][:22]:<22} {row["email"][:32]:<32} '
              f'{"yes" if row["verified"] else "no":<9} {(row["tier"] or "guest"):<6} '
              f'{(row["last_login"] or "never")[:19]:<19}')


def cmd_approve(args):
    with auth_db.get_db() as conn:
        cursor = conn.cursor()
        user = _find(cursor, args.username)
        cursor.execute('UPDATE users SET verified = 1, tier = ? WHERE id = ?', (args.tier, user['id']))
    print(f"approved '{args.username}' with tier {args.tier}")


def cmd_set_tier(args):
    with auth_db.get_db() as conn:
        cursor = conn.cursor()
        user = _find(cursor, args.username)
        cursor.execute('UPDATE users SET tier = ? WHERE id = ?', (args.tier, user['id']))
    note = '' if user['verified'] else " (account is still unverified: use 'approve' to let it log in)"
    print(f"'{args.username}' is now tier {args.tier}{note}")


def main(argv=None):
    parser = argparse.ArgumentParser(description='LibreCrawl account admin')
    sub = parser.add_subparsers(dest='command', required=True)

    sub.add_parser('users', help='list accounts').set_defaults(func=cmd_users)

    approve = sub.add_parser('approve', help='verify an account so it can log in')
    approve.add_argument('username')
    approve.add_argument('--tier', choices=TIERS, default='user',
                         help='tier to give the account (default: user)')
    approve.set_defaults(func=cmd_approve)

    set_tier = sub.add_parser('set-tier', help="change an account's tier")
    set_tier.add_argument('username')
    set_tier.add_argument('tier', choices=TIERS)
    set_tier.set_defaults(func=cmd_set_tier)

    args = parser.parse_args(argv)
    auth_db.init_db()
    args.func(args)


if __name__ == '__main__':
    main()
