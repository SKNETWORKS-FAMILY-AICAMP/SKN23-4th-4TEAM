"""
WSGI config for config project.
"""

import os
import sys
from pathlib import Path

from django.core.wsgi import get_wsgi_application

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "services.django_web.config.settings")

application = get_wsgi_application()
