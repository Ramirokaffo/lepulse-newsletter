from email.mime.image import MIMEImage
from functools import lru_cache

from django.conf import settings


@lru_cache(maxsize=1)
def _brand_logo_bytes():
    logo_path = settings.BASE_DIR / 'static' / 'images' / 'logo-ACCENT.png'
    return logo_path.read_bytes()


def attach_brand_logo(message):
    """Embarque le logo dans l'e-mail pour éviter les images distantes bloquées."""
    logo = MIMEImage(_brand_logo_bytes(), _subtype='png')
    logo.add_header('Content-ID', '<accent-logo>')
    logo.add_header('Content-Disposition', 'inline', filename='logo-ACCENT.png')
    message.attach(logo)