"""Create admin/product-owner/engineer/viewer without a public registration API.
Usage: docker compose exec -it backend python -m app.cli.create_user --username admin --role admin
"""
import argparse
import getpass
from app.services.auth_service import create_user

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--username',required=True)
    parser.add_argument('--role',required=True,choices=['admin','product_owner','engineer','viewer'])
    args=parser.parse_args()
    password=getpass.getpass('Password (min 12 chars): ')
    confirm=getpass.getpass('Confirm password: ')
    if password!=confirm:
        raise SystemExit('Passwords do not match')
    print('Created user:',create_user(args.username,password,args.role))
if __name__=='__main__':main()
