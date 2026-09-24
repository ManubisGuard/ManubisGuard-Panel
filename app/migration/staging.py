from __future__ import annotations

import gzip
import json
import posixpath
import re
import shutil
import stat
import subprocess
import tarfile
import tempfile
import zipfile

# NOTE: preserve the existing file body; this update intentionally targets only
# candidate selection below.
