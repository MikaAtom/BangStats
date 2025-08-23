from bangstats.config.defaults import Defaults


class Config:
    _instance = None
    _config = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Config, cls).__new__(cls)
            cls._config = Defaults()
        return cls._instance

    @classmethod
    def get(cls, key, default=None):
        if cls._config is None:
            cls._config = Defaults()

        return getattr(cls._config, key, default)

    def retrieve_config(self):
        return self._config

config = Config()