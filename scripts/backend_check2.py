import sys
import traceback
from pathlib import Path

project_root = Path(__file__).resolve().parents[1]
print('Project root:', project_root)
sys.path.insert(0, str(project_root))

try:
    import importlib.util
    path = project_root / 'src' / 'api.py'
    spec = importlib.util.spec_from_file_location('local_api', str(path))
    api = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(api)
    print('module_loaded')
    print('has _bounds_for_city:', hasattr(api, '_bounds_for_city'))
    print('has _city_seed_events:', hasattr(api, '_city_seed_events'))
    print('has _alerts_from_hotspots:', hasattr(api, '_alerts_from_hotspots'))

    if hasattr(api, '_bounds_for_city'):
        try:
            print('bounds ->', api._bounds_for_city())
        except Exception:
            print('bounds error:')
            traceback.print_exc()

    if hasattr(api, '_city_seed_events'):
        try:
            df = api._city_seed_events()
            print('seed rows ->', len(df))
        except Exception:
            print('seed error:')
            traceback.print_exc()

    if hasattr(api, '_alerts_from_hotspots'):
        try:
            alerts = api._alerts_from_hotspots()
            print('alerts count ->', len(alerts))
            print('sample alert ->', alerts[0] if alerts else None)
        except Exception:
            print('alerts error:')
            traceback.print_exc()
except Exception:
    print('fatal error')
    traceback.print_exc()
