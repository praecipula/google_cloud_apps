"""This module is for utilities that are useful across environments - for instance, we don't know what timezone our environments will be in, so this module contains a method to work with Unix timestamps exclusively in UTC."""

from datetime import datetime
import pytz

def utc_from_epoch_ms(unix_timestamp):
    return datetime.utcfromtimestamp(unix_timestamp).replace(tzinfo=pytz.utc)
