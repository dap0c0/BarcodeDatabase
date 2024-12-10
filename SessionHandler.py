from twisted.web.server import Session

class SessionHandler():
    def __init__(self):
        self._sessions = set()

    def verify_session(self, session: Session):
        '''Check that the session exists
            in the current pool.'''
        assert isinstance(session, Session)
        return session.uid in self._sessions

    def add_session(self, session):
        if session.uid not in self._sessions:
            self._sessions.add(session.uid)
            session.notifyOnExpire(lambda: self._close_session(session.uid))

    def _close_session(self, uid):
        print("Session", uid, "has expired.")
        self._sessions.remove(uid)
