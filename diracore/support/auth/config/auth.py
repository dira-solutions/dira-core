import os

config = {
    'secret_key': os.getenv('AUTH_SECRET_KEY', 'your-secret-key'),
    'algorithm': os.getenv('AUTH_ALGORITHM', 'HS256'),
    'token_expire_minutes': os.getenv('AUTH_TOKEN_EXPIRE_MINUTES', 2*60)
}