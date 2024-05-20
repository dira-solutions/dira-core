from diracore.container.bound_method import BoundMethod
import inspect
from typing import TypeVar

ABSTRACT = TypeVar('ABSTRACT')
DEFAULT = TypeVar('DEFAULT')

class Container:
    bindings:dict
    instances:dict

    _instance = None
    _build_stack: list = []
    _method_bindings: dict = {}
    
    def __init__(self):
        self.bindings = {}
        self.instances = {} 

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Container, cls).__new__(cls)
        return cls._instance

    def singleton(self, abstract, concrete=None):
        self.bind(abstract, concrete, shared=True)

    def bind(self, abstract, concrete=None, shared=False):
        if concrete is None:
            concrete = abstract
        if isinstance(concrete, str):
            concrete = self.get_closure(concrete)

        self.bindings[abstract] = {'concrete': concrete, 'shared': shared}

        if self.resolved(abstract):
            self.rebound(abstract)
    
    def instance(self, abstract, instance):
        self.instances[abstract] = instance
        return instance

    def get_closure(self, concrete):
        def closure():
            return concrete
        return closure()

    def make(self, abstract: ABSTRACT, *params, default=DEFAULT|None) -> ABSTRACT|DEFAULT|None:
        return self.resolve(abstract, params, default)
    
    def resolve(self, abstract, params=None, default=None):
        concrete = self.get_concrete(abstract)
        if isinstance(concrete, str): 
            return default

        if not self.is_shared(abstract):
            _object =  self.build(concrete, params)
        elif abstract not in self.instances:
            self.instances[abstract] = self.build(concrete, params)
            _object =  self.instances[abstract]
        elif abstract in self.instances:
            _object = self.instances[abstract]
        else:
            _object = default

        return _object
    
    def is_shared(self, abstract) -> bool:
        is_binding_shared = abstract in self.bindings and self.bindings[abstract].get('shared', False) == True
        return is_binding_shared
    
    def get_concrete(self, abstract):
        if abstract in self.bindings:
            return self.bindings[abstract]["concrete"]
        
        if abstract in self.instances:
            return self.instances[abstract]
        return abstract
        
    def build(self, concrete, args = None):
        if isinstance(args, tuple) and args:
            if inspect.iscoroutinefunction(concrete):
                concrete(*args)
            return concrete(*args)
        args = self.get_params(concrete)
        return concrete(**args)

    def get_params(self, concrete, default = None):
        init_args = {}
        has_init = hasattr(concrete, '__init__')
        if inspect.isfunction(concrete):
            init_args = inspect.signature(concrete).parameters
        elif has_init and hasattr(concrete.__init__, '__annotations__'):
            init_args: dict = concrete.__init__.__annotations__
            init_args.pop('return', None)

        args = {}
        for name, abstract in init_args.items():
            # abstract: inspect.Parameter = abstract
            if isinstance(abstract, inspect.Parameter):
                abstract = abstract.annotation
            if abstract in self.bindings:
                args[name] = self.make(abstract)
            else:
                pass
        return args

    def resolved(self, abstract):
        return abstract in self.instances

    def rebound(self, abstract):
        pass

    async def call(self, callback, params: list = [], default_method = None):
        pushed_to_build_stack = False
        class_name = self.get_class_for_callable(callback)
        
        if class_name and not class_name in self._build_stack:
            self._build_stack.append(class_name)
            pushed_to_build_stack = True

        result = await BoundMethod.call(self, callback, params, default_method)
        
        if pushed_to_build_stack:
            self._build_stack.pop()

        return result        

    def get_class_for_callable(self, callback):
        if type(callback) == callable and callback.__name__ != "<lambda>":
            return callback.__name__
        if not isinstance(callback, list):
            return False
        if isinstance(callback[0], str):
            return callback[0]
        return type(callback[0]).__name__

    def has_method_binding(self, method) -> bool:
        return method in self._method_bindings
    
    def call_method_binding(self, method, instance):
        bound_method = self._method_bindings[method]
        return bound_method(instance, self)