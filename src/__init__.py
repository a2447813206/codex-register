import os
from flask import Flask
from src.routes.api import api_bp
from src.routes.pages import pages_bp
from src.services.logger import init_logger

def create_app():
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    app = Flask(__name__, 
                static_folder=os.path.join(BASE_DIR, 'dist'),
                static_url_path='/',
                template_folder=os.path.join(BASE_DIR, 'dist'))
    
    app.config['TEMPLATES_AUTO_RELOAD'] = True
    app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
    app.jinja_env.auto_reload = True
    
    app.register_blueprint(api_bp, url_prefix="/api")
    app.register_blueprint(pages_bp)
    
    init_logger()
    
    return app
