#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Configuration module for Leaflow Auto Check-in Control Panel
"""

import os
import secrets
import logging
from urllib.parse import urlparse, unquote
import pytz

# Environment variables
ADMIN_USERNAME = os.getenv('ADMIN_USERNAME', 'admin')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'admin123')
PORT = int(os.getenv('PORT', '8181'))
MAX_MYSQL_RETRIES = int(os.getenv('MAX_MYSQL_RETRIES', '12'))

# Data directory - use /app/data in Docker, local ./data otherwise
DATA_DIR = os.getenv('DATA_DIR', '/app/data' if os.path.exists('/app') else './data')

# JWT Secret Key
JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', secrets.token_hex(32))

# Timezone - Beijing Time
TIMEZONE = pytz.timezone('Asia/Shanghai')


def parse_mysql_dsn(dsn):
    """Parse MySQL DSN string"""
    try:
        parsed = urlparse(dsn)

        if parsed.scheme not in ['mysql', 'mysql+pymysql']:
            return None

        config = {
            'type': 'mysql',
            'host': parsed.hostname or 'localhost',
            'port': parsed.port or 3306,
            'database': parsed.path.lstrip('/') if parsed.path else 'leaflow_checkin',
            'password': unquote(parsed.password) if parsed.password else ''
        }

        username = unquote(parsed.username) if parsed.username else 'root'

        if '.' in username:
            username = username.split('.')[-1]

        config['user'] = username

        return config
    except Exception as e:
        logging.error(f"Error parsing MySQL DSN: {e}")
        return None


# Parse database configuration
MYSQL_DSN = os.getenv('MYSQL_DSN', '')
db_config = None

if MYSQL_DSN:
    db_config = parse_mysql_dsn(MYSQL_DSN)

if db_config:
    DB_TYPE = 'mysql'
    DB_HOST = db_config['host']
    DB_PORT = db_config['port']
    DB_NAME = db_config['database']
    DB_USER = db_config['user']
    DB_PASSWORD = db_config['password']
else:
    DB_TYPE = 'sqlite'
    DB_HOST = 'localhost'
    DB_PORT = 3306
    DB_NAME = 'leaflow_checkin'
    DB_USER = 'root'
    DB_PASSWORD = ''

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


# Flask app configuration class
class AppConfig:
    SECRET_KEY = JWT_SECRET_KEY
