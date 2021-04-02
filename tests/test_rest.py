import pytest

# json utils
import json
from http import HTTPStatus

# temporary directory for each test config
import tempfile
import os

# copy test config
from copy import deepcopy

# testing context
from context import amplipi

def base_config():
  return amplipi.ctrl.Api._DEFAULT_CONFIG

def base_config_copy():
  return deepcopy(base_config())

def base_config_no_presets():
  cfg = base_config_copy()
  del cfg['presets']
  return cfg

def base_config_no_groups():
  cfg = base_config_copy()
  del cfg['groups']
  return cfg

def status_copy(client):
  rv = client.get('/api/')
  jrv = rv.get_json()
  assert jrv != None
  return jrv # jrv was already serialized so it should be a copy

def find(list, id):
  for i in list:
    if i['id'] == id:
      return i
  return None

@pytest.fixture(params=[base_config_copy(), base_config_no_presets(), base_config_no_groups()])
def client(request):
  cfg = request.param
  config_dir = tempfile.mkdtemp()
  config_file = os.path.join(config_dir, 'house.json')
  with open(config_file, 'w') as cfg_file:
    cfg_file.write(json.dumps(cfg))
  app = amplipi.app.create_app(mock_ctrl=True, mock_streams=True, config_file=config_file)
  app.testing = True
  c = app.test_client()
  c.original_config = deepcopy(cfg) # add the loaded config so we can remember what was loaded
  return c

# TODO: the web view test should be added to its own testfile once we add more functionality to the site
@pytest.mark.parametrize('path', [',' , '/'] + [ '/{}'.format(i) for i in range(4) ])
def test_view(client, path):
  rv = client.get('/')
  assert rv.status_code == HTTPStatus.OK

@pytest.mark.parametrize('path', ['/api', '/api/'])
def test_base(client, path):
    """Start with a basic controller and just check if it gives a real response"""
    rv = client.get(path)
    assert rv.status_code in [ HTTPStatus.OK, HTTPStatus.PERMANENT_REDIRECT] # flask inserts a redirect here for some reason
    if rv.status_code == HTTPStatus.OK:
      jrv = rv.get_json()
      assert jrv != None
      og_config = client.original_config
      for t in ['sources', 'streams', 'zones', 'groups', 'presets']:
        if t in og_config:
          assert len(jrv[t]) == len(og_config[t])
    else:
      assert path == '/api'
      assert '/api/' in rv.location

# To reduce the amount of boilerplate we use test parameters.
# Examples: https://docs.pytest.org/en/stable/example/parametrize.html#paramexamples

# TODO: test sources
# TODO: /sources/{sourceId} get-source
# TODO: /sources/{sourceId} patch-source

# TODO: test zones
# TODO: /zones/{zoneId} get-zone
# TODO: /zones/{zoneId} patch-zone

# TODO: test groups
# TODO: /group post-group
# TODO: /groups/{groupId} get-group
# TODO: /groups/{groupId} patch-group
# TODO: /groups/{groupId} delete-group

# test streams
def base_stream_ids():
  """ Return all of the stream IDs belonging to each of the streams in the base config """
  return [ s['id'] for s in base_config()['streams']]

# /stream post-stream
def test_create_pandora(client):
  m_and_k = { 'name': 'Matt and Kim Radio', 'type':'pandora', 'user': 'lincoln@micro-nova.com', 'password': ''}
  rv = client.post('/api/stream', json=m_and_k)
  # check that the stream has an id added to it and that all of the fields are still there
  assert rv.status_code == HTTPStatus.OK
  jrv = rv.get_json()
  assert 'id' in jrv
  assert type(jrv['id']) == int
  for k, v in m_and_k.items():
    assert jrv[k] == v

# /streams/{streamId} get-stream
@pytest.mark.parametrize('sid', base_stream_ids())
def test_get_stream(client, sid):
  rv = client.get('/api/streams/{}'.format(sid))
  assert rv.status_code == HTTPStatus.OK
  jrv = rv.get_json()
  s = find(base_config()['streams'], sid)
  assert s != None
  assert s['name'] == jrv['name']

# /streams/{streamId} patch-stream
@pytest.mark.parametrize('sid', base_stream_ids())
def test_patch_stream_rename(client, sid):
  rv = client.patch('/api/streams/{}'.format(sid), json={'name': 'patched-name'})
  assert rv.status_code == HTTPStatus.OK
  jrv = rv.get_json() # get the system state returned
  # TODO: check that the system state is valid
  # make sure the stream was renamed
  s = find(jrv['streams'], sid)
  assert s != None
  assert s['name'] == 'patched-name'

# /streams/{streamId} delete-stream
@pytest.mark.parametrize('sid', base_stream_ids())
def test_delete_stream(client, sid):
  rv = client.delete('/api/streams/{}'.format(sid))
  assert rv.status_code == HTTPStatus.OK
  jrv = rv.get_json() # get the system state returned
  # TODO: check that the system state is valid
  # make sure the stream was deleted
  s = find(jrv['streams'], sid)
  assert s == None
  # make sure the rest of the streams are still there
  for other_sid in base_stream_ids():
    if other_sid != sid:
      assert find(jrv['streams'], other_sid) != None

# TODO: /streams/{streamId}/{streamCmd} post-stream-command
# TODO: mocked streams do not currently handle state changes from commands
#       these tests will require either a real system with passwords and account info or a better mock

# test presets
def base_preset_ids():
  """ Return all of the preset IDs belonging to each of the presets in the base config """
  return [ s['id'] for s in base_config()['presets']]

# /preset post-preset
def test_create_mute_all_preset(client):
  mute_some = { 'name' : 'Mute some', 'zones' : [ { 'id' : 1, 'mute': True}, { 'id' : 4, 'mute': True} ]}
  rv = client.post('/api/preset', json=mute_some)
  # check that the stream has an id added to it and that all of the fields are still there
  assert rv.status_code == HTTPStatus.OK
  jrv = rv.get_json()
  assert 'id' in jrv
  assert type(jrv['id']) == int
  for k, v in mute_some.items():
    assert jrv[k] == v

# /presets/{presetId} get-preset
@pytest.mark.parametrize('pid', base_preset_ids())
def test_get_preset(client, pid):
  last_state = status_copy(client)
  rv = client.get('/api/presets/{}'.format(pid))
  if find(last_state['presets'], pid):
    assert rv.status_code == HTTPStatus.OK
  else:
    assert rv.status_code != HTTPStatus.OK
    return
  jrv = rv.get_json()
  s = find(base_config()['presets'], pid)
  assert s != None
  assert s['name'] == jrv['name']

# /presets/{presetId} patch-preset
@pytest.mark.parametrize('pid', base_preset_ids())
def test_patch_preset_name(client, pid):
  last_state = status_copy(client)
  rv = client.patch('/api/presets/{}'.format(pid), json={'name': 'patched-name'})
  if find(last_state['presets'], pid):
    assert rv.status_code == HTTPStatus.OK
  else:
    assert rv.status_code != HTTPStatus.OK
    return
  jrv = rv.get_json() # get the system state returned
  # TODO: check that the system state is valid
  # make sure the stream was renamed
  s = find(jrv['presets'], pid)
  assert s != None
  assert s['name'] == 'patched-name'

# /presets/{presetId} delete-preset
@pytest.mark.parametrize('pid', base_preset_ids())
def test_delete_preset(client, pid):
  rv = client.delete('/api/presets/{}'.format(pid))
  if 'presets' in client.original_config and find(client.original_config['presets'], pid):
    assert rv.status_code == HTTPStatus.OK
  else:
    assert rv.status_code != HTTPStatus.OK
    return
  jrv = rv.get_json() # get the system state returned
  # TODO: check that the system state is valid
  # make sure the preset was deleted
  s = find(jrv['presets'], pid)
  assert s == None
  # make sure the rest of the presets are still there
  for other_pid in base_preset_ids():
    if other_pid != pid:
      assert find(jrv['presets'], other_pid) != None

# /presets/{presetId}/load load-preset
# TODO: use combinations of base_preset_ids and suggested
@pytest.mark.parametrize('pid', base_preset_ids())
def test_load_preset(client, pid, unmuted=[1,2,3]):
  # unmute some of the zones
  for zid in unmuted:
    client.patch('/api/zones/{}'.format(zid), json={'mute': False})
  # save the preloaded state
  last_state = status_copy(client)
  # load the preset (in some configurations it won't exist; make sure it fails in that case)
  rv = client.post('/api/presets/{}/load'.format(pid))
  p = find(last_state['presets'], pid)
  if p:
    # check if all of the needed groups exist (it will fail if one of the needed groups doesn't exist')
    effected_groups = { g['id'] for g in p['state'].get('groups', [])}
    missing = False
    for g in effected_groups:
      if not find(last_state['groups'], g):
        missing = True
    if missing:
      assert rv.status_code != HTTPStatus.OK
      return
    else:
      assert rv.status_code == HTTPStatus.OK
  else:
    assert rv.status_code != HTTPStatus.OK
    return
  jrv = rv.get_json() # get the system state returned
  # TODO: check that the system state is valid
  # make sure the rest of the config got loaded
  for mod, configs in p['state'].items():
    for cfg in configs:
      # each of the keys in the configuration should match
      updated_cfg = find(jrv[mod], cfg['id'])
      assert updated_cfg is not None
      for k, v in cfg.items():
        assert updated_cfg[k] == v
  # verify all of the zones mute levels remained the same (unless they were changed by the preset configuration)
  preset_zones_changes = p['state'].get('zones', None) # TODO: this doesn't handle group changes
  for z in jrv['zones']:
    expected_mute = last_state['zones'][z['id']]['mute']
    if preset_zones_changes:
      pz = find(preset_zones_changes, z['id'])
      if pz and 'mute' in pz:
        expected_mute = pz['mute']
    assert z['mute'] == expected_mute
  # load the saved config and verify that the sources, zones, and groups are the same as initial state (before the preset was loaded)
  LAST_CONFIG_PRESET = 9999
  rv = client.post('/api/presets/{}/load'.format(LAST_CONFIG_PRESET))
  assert rv.status_code == HTTPStatus.OK
  jrv = rv.get_json() # get the system state returned
  for name, mod in jrv.items():
    prev_mod = last_state[name]
    for cfg in mod:
      if cfg['id'] != LAST_CONFIG_PRESET:
        prev_cfg = find(prev_mod, cfg['id'])
        # last used field will be different, just remmove them
        if 'last_used' in prev_cfg:
          prev_cfg.pop('last_used')
        if 'last_used' in cfg:
          cfg.pop('last_used')
        assert cfg == prev_cfg
