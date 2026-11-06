"""Fixture: every import form the extractor must find. Line numbers matter."""
import os
import app.core.db
from app import core
from . import helpers
from ..core import db as database
import importlib

try:
    import json
except ImportError:
    json = None


def load():
    import csv
    return csv


def plugin(name):
    importlib.import_module("app.plugins.alpha")
    importlib.import_module(name)
    importlib.import_module(".beta", package=__name__)
    __import__("app.plugins.gamma")


from app.core import (
    db,
    helpers_x,
)

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import decimal
