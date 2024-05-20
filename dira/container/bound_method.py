import inspect
import types

class BoundMethod:
    @staticmethod
    async def call(container, callback, parameters=None, default_method=None):
        if parameters is None:
            parameters = []

        if isinstance(callback, str) and not default_method and hasattr(callback, '__call__'):
            default_method = '__call__'
        if BoundMethod.is_callable_with_at_sign(callback) or default_method:
            return BoundMethod.call_class(container, callback, parameters, default_method)
        
        default_method = BoundMethod.get_call(container, callback, parameters)
        
        return await BoundMethod.call_bound_method(container, callback, default_method)

    @staticmethod
    def call_class(container, target, parameters=None, default_method=None):
        if parameters is None:
            parameters = []

        segments = target.split('@')
        method = segments[1] if len(segments) == 2 else default_method

        if method is None:
            raise ValueError('Method not provided.')

        return BoundMethod.call(container, [container.make(segments[0]), method], parameters)

    @staticmethod
    async def call_bound_method(container, callback, default):
        if not isinstance(callback, list):
            return default()
        
        method = BoundMethod.normalize_method(callback)

        if container.has_method_binding(method):
            return container.call_method_binding(method, callback[0])
        if inspect.iscoroutinefunction(default):
            return await default()
        return default()

    @staticmethod
    def normalize_method(callback):
        if isinstance(callback[0], str):
            class_name = callback[0]
        else:
            class_name = callback[0].__class__.__name__

        return f"{class_name}@{callback[1]}"

    @staticmethod
    def is_callable_with_at_sign(callback):
        return isinstance(callback, str) and '@' in callback
    
    @staticmethod
    def get_method_dependencies(container, callback, parameters=[]):
        dependencies = []
        if not isinstance(callback, list) and callable(callback):
            for parameter in inspect.signature(callback).parameters.values():
                BoundMethod.add_dependency_for_call_parameter(container, parameter, parameters, dependencies)

        return dependencies + list(parameters)
    
    @staticmethod
    def add_dependency_for_call_parameter(container, parameter, parameters, dependencies):
        param_name = parameter.name

        if param_name in parameters:
            dependencies.append(parameters[param_name])
            del parameters[param_name]
        elif param_class := BoundMethod.get_parameter_class_name(parameter):
            if param_class in parameters:
                dependencies.append(parameters[param_class])
                del parameters[param_class]
            elif parameter.default is inspect.Parameter.empty and not parameter.default_factory:
                message = f"Unable to resolve dependency [{param_name}] in class {parameter.default_owner.__name__}"
                raise BindingResolutionException(message)
            else:
                dependencies.append(container.make(param_class))
        elif parameter.default is not inspect.Parameter.empty:
            dependencies.append(parameter.default)

    @staticmethod
    def get_parameter_class_name(parameter):
        annotation = parameter.annotation

        if isinstance(annotation, str):
            return annotation

        if isinstance(annotation, types.FunctionType):
            return annotation.__name__

        return None

    @staticmethod
    def is_callable_with_at_sign(callback):
        return isinstance(callback, str) and '@' in callback
        
    @staticmethod
    def get_call(container, callback, parameters):
        if isinstance(callback, list):
            obj = callback[0]
            method = callback[1]
            callback = getattr(obj, method)

        if inspect.iscoroutinefunction(callback):
            async def method():
                return await callback(*BoundMethod.get_method_dependencies(container, callback, parameters))
        else:
            method = lambda: callback(*BoundMethod.get_method_dependencies(container, callback, parameters))

        return method