from pathlib import Path
import sys
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from importlib import import_module
api = import_module('src.api')
import src.persistence as persistence

# ensure DB and preload
persistence.init_db()
# create session for admin
token = persistence.create_session('admin', 'Admin')
print('created token len', len(token))

# find a hotspot id
hotspots = api._hotspots_response(mode='LIVE')
if not hotspots:
    print('no hotspots found, aborting')
else:
    h = hotspots[0]
    print('using hotspot', h['id'], h['name'])
    payload = type('P', (), {})()
    payload.hotspot_id = h['id']
    payload.officers = 3
    payload.patrol_vehicles = 1
    payload.notes = 'Test dispatch'
    # call dispatch_assign
    result = api.dispatch_assign(payload, token)
    print('dispatch_assign result:', result)

    # list deployments
    deps = api.dispatch_deployments(token)
    print('deployments count:', len(deps))
    print('first deployment:', deps[0] if deps else None)
