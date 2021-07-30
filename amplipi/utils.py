# AmpliPi Home Audio
# Copyright (C) 2021 MicroNova LLC
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""Utility functions

This module contains helper functions are used across the amplipi python library.
"""

import json
import os
import functools
import subprocess
import re
from typing import List, Dict, Union, Optional, Tuple, TypeVar, Iterable

import pkg_resources # version

import amplipi.models as models

# pylint: disable=bare-except

# Helper functions
def encode(pydata):
  """ Encode a dictionary as JSON """
  return json.dumps(pydata)

def decode(j):
  """ Decode JSON into dictionary """
  return json.loads(j)

def parse_int(i, options):
  """ Parse an integer into one of the given options """
  if int(i) in options:
    return int(i)
  raise ValueError('{} is not in [{}]'.format(i, options))

def error(msg):
  """ wrap the error message specified by msg into an error """
  print('Error: {}'.format(msg))
  return {'error': msg}

VT = TypeVar("VT")

def updated_val(update: Optional[VT], val: VT) -> Tuple[VT, bool]:
  """ get the potentially updated value, @update, defaulting to the current value, @val, if it is None """
  if update is None:
    return val, False
  return update, update != val

BT = TypeVar("BT", bound='models.Base', covariant=True)

def find(items: Iterable[BT], item_id: int, key='id') -> Union[Tuple[int, BT], Tuple[None, None]]:
  """ Find an item by id """
  for i, item in enumerate(items):
    if item.__dict__[key] == item_id:
      return i, item
  return None, None

def next_available_id(items: Iterable[BT], default: int = 0) -> int:
  """ Get a new unique id among @items """
  # TODO; use `largest_item = max(items, key=lambda item: item.id, default=None)` to find max if models.Base changes id to be required
  largest_id = None
  for item in items:
    if item.id is not None:
      if largest_id is not None:
        largest_id = max(largest_id, item.id)
      else:
        largest_id = item.id
  if largest_id is not None:
    return largest_id + 1
  return default

def clamp(xval, xmin, xmax):
  """ Clamp and value between min and max """
  return max(xmin, min(xval, xmax))

def compact_str(list_:List):
  """ stringify a compact list"""
  return str(list_).replace(' ', '')

def max_len(items, len_determiner=len):
  """ Determine the item with the max len, based on the @len_determiner's definition of length

  Args:
    items: iterable items
    len_determiner: function that returns an integer

  Returns:
    len: integer

  This is useful for lining up lists printed in a table-like format
  """
  largest = max(items, key=len_determiner)
  return len_determiner(largest)

def abbreviate_src(src_type):
  """ Abbreviate source's type for pretty printing """
  return src_type[0].upper() if src_type else '_'

def src_zones(status: models.Status) -> Dict[int, List[int]]:
  """ Get a mapping from source ids to zones """
  return { src.id : [ zone.id for zone in status.zones if zone.id is not None and zone.source_id == src.id] for src in status.sources if src.id is not None}

@functools.lru_cache(1)
def available_outputs():
  """ get the available alsa outputs (we are expecting ch0-ch3).

  Returns:
    outputs: iterable list of alsa outputs

  This will cache the result since alsa outputs do not change dynamically (unless you edit a config file).
  """
  try:
    outputs = [ o for o in subprocess.check_output('aplay -L'.split()).decode().split('\n') if o and o[0] != ' ' ]
  except:
    outputs = []
  if 'ch0' not in outputs:
    print('WARNING: ch0, ch1, ch2, ch3 audio devices not found. Is this running on an AmpliPi?')
  return outputs

def output_device(sid: int) -> str:
  """ Get a source's corresponding ALSA output device string """
  dev = 'ch' + str(sid)
  if dev in available_outputs():
    return dev
  return 'default' # fallback to default

@functools.lru_cache(maxsize=8)
def get_folder(folder):
  """ Get a directory
  Abstracts the directory structure """
  if not os.path.exists(folder):
    try:
      os.mkdir(folder)
    except:
      print(f'Error creating dir: {folder}')
  return os.path.abspath(folder)

TOML_VERSION_STR = re.compile(r'version\s*=\s*"(.*)"')

def detect_version() -> str:
  """ Get the AmpliPi software version from the project TOML file """
  version = 'unknown'
  try:
    version = pkg_resources.get_distribution('amplipi').version
  except:
    pass
  if 'unknown' in version:
    # assume the application is running in its base directory and check the pyproject.toml file to determine the version
    # this is needed for a straight github checkout (the common developement paradigm at MicroNova)
    script_folder = os.path.dirname(os.path.realpath(__file__))
    try:
      with open(os.path.join(script_folder, '..', 'pyproject.toml')) as proj_file:
        for line in proj_file.readlines():
          if 'version' in line:
            match = TOML_VERSION_STR.search(line)
            if match is not None:
              version = match.group(1)
    except:
      pass
  return version
