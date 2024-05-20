from .contracts.foundation.application import Application as ApplicationContract
from app.http.kernel import Kernel
from .contracts.kernel import Kernel as KernelContract
from .main import app

app.singleton(ApplicationContract, lambda: app)
app.singleton(KernelContract, Kernel)
kernel = app.make(KernelContract)
kernel.handle()

serve = kernel.send()
