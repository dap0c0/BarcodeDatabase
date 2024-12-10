from twisted.web.server import Session

class SessionHandler():
    def __init__(self):
        self._sessions = set()

    def add_session(self, session):
        if session.uid not in self._sessions:
            self._sessions.add(session.uid)

    def _close_session(self, uid):
        print("Session", uid, "has expired.")
        self._sessions.remove(uid)
