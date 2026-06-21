from pathlib import Path
import sys
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from src.persistence import init_db, authenticate_user, create_session, validate_session, revoke_session

init_db()
print('DB initialized')
user = authenticate_user('admin','admin')
print('auth admin:', user)
if user:
    token = create_session(user['username'], user['role'])
    print('created token len', len(token))
    sess = validate_session(token)
    print('validated session:', sess)
    revoke_session(token)
    print('revoked')
    sess2 = validate_session(token)
    print('validated after revoke (should be None):', sess2)
else:
    print('failed to authenticate admin')
