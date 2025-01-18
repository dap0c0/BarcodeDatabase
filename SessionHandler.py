class SessionHandler():
    def __init__(self):
        self._sessions = set()

    def verify_session(self, cookie: str):
        '''Check that the session exists
            in the current pool.'''
        assert isinstance(cookie, str)
        return cookie in self._sessions

    def add_session(self, cookie: str):
        if cookie not in self._sessions:
            self._sessions.add(cookie)

    def _close_session(self, uid: str):
        print("Session", uid, "has expired.")
        self._sessions.remove(uid)
