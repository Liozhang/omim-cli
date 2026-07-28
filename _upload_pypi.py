"""Upload to PyPI, patching rich progress bar to avoid GBK encoding issues."""
import os
import sys

os.environ['PYTHONIOENCODING'] = 'utf-8'
os.environ['TWINE_TERMINAL_PROGRESS_BAR'] = 'off'

# Patch rich.progress before twine imports it
import rich.progress
_orig = rich.progress.Progress.update

def _patched_update(self, *args, **kwargs):
    try:
        return _orig(self, *args, **kwargs)
    except Exception:
        pass

rich.progress.Progress.update = _patched_update

# Now run twine upload
from twine.cli import twine
sys.argv = [
    'twine', 'upload',
    '--disable-progress-bar',
    '-c', 'upload v2.1.4',
    'dist/omim_cli-2.1.4-py3-none-any.whl',
    'dist/omim_cli-2.1.4.tar.gz',
]
twine()
