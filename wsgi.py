"""WSGI entry point for Azure App Service deployment.

When deployed via 'az webapp up', files land in /home/site/wwwroot/
but imports expect a 'nexus' package. This module fixes the path.
"""
import os
import sys

# Make the parent of wwwroot available so 'from nexus import ...' works
# by creating a symlink: /home/site/nexus -> /home/site/wwwroot
site_dir = os.path.dirname(os.path.abspath(__file__))  # /home/site/wwwroot
parent_dir = os.path.dirname(site_dir)                  # /home/site

nexus_link = os.path.join(parent_dir, "nexus")
if not os.path.exists(nexus_link):
    try:
        os.symlink(site_dir, nexus_link)
    except OSError:
        pass

# Add parent to sys.path so Python can find 'nexus' package
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from nexus.main import app  # noqa: E402
