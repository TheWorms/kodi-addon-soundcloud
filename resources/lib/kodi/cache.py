import time


class Cache:
    def __init__(self, settings, vfs):
        self.settings = settings
        self.vfs = vfs

    def get(self, filename, age=60):
        """
        Get a cached file.
        :param filename: str
        :type age: int Minutes
        """
        file = self.vfs.read(filename)

        if file:
            mtime = self.vfs.get_mtime(filename)
            if (int(time.time()) - age * 60) > mtime:
                # Entree expiree : on la supprime au passage pour que le
                # dossier cache ne grossisse pas indefiniment.
                try:
                    self.vfs.delete(filename)
                except Exception:
                    pass
                return None

        return file

    def add(self, filename, data):
        return self.vfs.write(filename, data)

    def purge_older_than(self, days):
        """
        Delete every cached file older than the given number of days.
        Called once per plugin process (see _purge_cache_once in
        plugin.py): Kodi never cleans special://profile/cache on its
        own between sessions (notably on CoreELEC/LibreELEC), so
        without this the folder grows forever. Returns the number of
        deleted files; errors on individual entries are ignored.
        """
        try:
            days = int(days)
        except (TypeError, ValueError):
            days = 30
        cutoff = int(time.time()) - days * 86400
        removed = 0
        for name in self.vfs.listdir():
            try:
                if self.vfs.get_mtime(name) < cutoff:
                    if self.vfs.delete(name):
                        removed += 1
            except Exception:
                pass
        return removed
