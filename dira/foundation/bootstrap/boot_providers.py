from dira.contracts.foundation.application import Application

class BootProviders:
    async def bootstrap(self, app: Application):
        await app.boot()