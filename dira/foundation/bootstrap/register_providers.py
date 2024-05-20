from dira.contracts.foundation.application import Application

class RegisterProviders:
    async def bootstrap(self, app: Application):
        await app.register_configured_providers()