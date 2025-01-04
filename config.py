import os
from dotenv import load_dotenv

# Load variabel lingkungan dari file .env
load_dotenv()

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY') or '5f957e6105f189f9974ae631b351b321'
    
    # Database Configuration
    DB_HOST = os.getenv('DB_HOST')
    DB_USER = os.getenv('DB_USER')
    DB_PASSWORD = os.getenv('DB_PASSWORD')
    DB_NAME = os.getenv('DB_NAME')
    
    # SendGrid Configuration
    SENDGRID_API_KEY = os.getenv('SENDGRID_API_KEY')
    SENDGRID_DEFAULT_FROM = os.getenv('SENDGRID_DEFAULT_FROM')
    
    # WAPISender Configuration
    WAPISENDER_API_URL = os.getenv('WAPISENDER_API_URL')
    WAPISENDER_API_KEY = os.getenv('WAPISENDER_API_KEY')
    WAPISENDER_DEVICE_KEY = os.getenv('WAPISENDER_DEVICE_KEY')