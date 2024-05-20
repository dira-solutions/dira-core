from typing import Any, Dict, Callable, Union, List, Tuple, Optional, Type

from rq.types import FunctionReferenceType, JobDependencyType

from redis import Redis

from rq.defaults import UNSERIALIZABLE_RETURN_VALUE_PAYLOAD
from rq.utils import parse_timeout, decode_redis_hash, str_to_date, as_text, ensure_list
from rq.exceptions import NoSuchJobError
from rq.job import Job, JobStatus, Dependency, logger, _job_stack
from rq.timeouts import BaseDeathPenalty, JobTimeoutException

from .callback import Callback, AscCallback

import warnings
import json
import zlib
import inspect
import asyncio


class AscJob(Job):
    def __init__(self, id: str | None = None, connection: Redis | None = None, serializer=None):
        super().__init__(id, connection, serializer)
        self._success_callback_args = None
        self._failure_callback_args = None
        self._stopped_callback_args = None

    def _execute(self) -> Any:
        """Actually runs the function with it's *args and **kwargs.
        It will use the `func` property, which was already resolved and ready to run at this point.
        If the function is a coroutine (it's an async function/method), then the `result`
        will have to be awaited within an event loop.

        Returns:
            result (Any): The function result
        """
        result = self.func(*self.args, **self.kwargs)
        if asyncio.iscoroutine(result):
            
            loop = asyncio.new_event_loop()
            coro_result = loop.run_until_complete(result)
            for task in asyncio.all_tasks(loop):
                task.cancel()
            return coro_result
        return result


    def to_dict(self, include_meta: bool = True, include_result: bool = True) -> dict:
        import pickle
        obj = super().to_dict(include_meta, include_result)
        obj['success_callback_args'] = pickle.dumps(self._success_callback_args) if self._success_callback_args else ''
        obj['failure_callback_args'] = pickle.dumps(self._failure_callback_args) if self._failure_callback_args else ''
        obj['stopped_callback_args'] = pickle.dumps(self._stopped_callback_args) if self._stopped_callback_args else ''
        return obj
    
    def restore(self, raw_data) -> Any:
        """Overwrite properties with the provided values stored in Redis.

        Args:
            raw_data (_type_): The raw data to load the job data from

        Raises:
            NoSuchJobError: If there way an error getting the job data
        """
        obj = decode_redis_hash(raw_data)
        try:
            raw_data = obj['data']
        except KeyError:
            raise NoSuchJobError('Unexpected job format: {0}'.format(obj))

        try:
            self.data = zlib.decompress(raw_data)
        except zlib.error:
            # Fallback to uncompressed string
            self.data = raw_data

        self.created_at = str_to_date(obj.get('created_at'))
        self.origin = as_text(obj.get('origin')) if obj.get('origin') else ''
        self.worker_name = obj.get('worker_name').decode() if obj.get('worker_name') else None
        self.description = as_text(obj.get('description')) if obj.get('description') else None
        self.enqueued_at = str_to_date(obj.get('enqueued_at'))
        self.started_at = str_to_date(obj.get('started_at'))
        self.ended_at = str_to_date(obj.get('ended_at'))
        self.last_heartbeat = str_to_date(obj.get('last_heartbeat'))
        result = obj.get('result')
        if result:
            try:
                self._result = self.serializer.loads(result)
            except Exception:
                self._result = UNSERIALIZABLE_RETURN_VALUE_PAYLOAD
        self.timeout = parse_timeout(obj.get('timeout')) if obj.get('timeout') else None
        self.result_ttl = int(obj.get('result_ttl')) if obj.get('result_ttl') else None
        self.failure_ttl = int(obj.get('failure_ttl')) if obj.get('failure_ttl') else None
        self._status = obj.get('status').decode() if obj.get('status') else None
        import pickle
        if obj.get('success_callback_name'):
            self._success_callback_name = obj.get('success_callback_name').decode()

        if obj.get('success_callback_args'):
            self._success_callback_args = pickle.loads(obj.get('success_callback_args'))
        if obj.get('failure_callback_args'):
            self._failure_callback_args = pickle.loads(obj.get('failure_callback_args'))
        if obj.get('stopped_callback_args'):
            self._stopped_callback_args = pickle.loads(obj.get('stopped_callback_args'))

        if 'success_callback_timeout' in obj:
            self._success_callback_timeout = int(obj.get('success_callback_timeout'))

        if obj.get('failure_callback_name'):
            self._failure_callback_name = obj.get('failure_callback_name').decode()

        if 'failure_callback_timeout' in obj:
            self._failure_callback_timeout = int(obj.get('failure_callback_timeout'))

        if obj.get('stopped_callback_name'):
            self._stopped_callback_name = obj.get('stopped_callback_name').decode()

        if 'stopped_callback_timeout' in obj:
            self._stopped_callback_timeout = int(obj.get('stopped_callback_timeout'))

        dep_ids = obj.get('dependency_ids')
        dep_id = obj.get('dependency_id')  # for backwards compatibility
        self._dependency_ids = json.loads(dep_ids.decode()) if dep_ids else [dep_id.decode()] if dep_id else []
        allow_failures = obj.get('allow_dependency_failures')
        self.allow_dependency_failures = bool(int(allow_failures)) if allow_failures else None
        self.enqueue_at_front = bool(int(obj['enqueue_at_front'])) if 'enqueue_at_front' in obj else None
        self.ttl = int(obj.get('ttl')) if obj.get('ttl') else None
        try:
            self.meta = self.serializer.loads(obj.get('meta')) if obj.get('meta') else {}
        except Exception:  # depends on the serializer
            self.meta = {'unserialized': obj.get('meta', {})}

        self.retries_left = int(obj.get('retries_left')) if obj.get('retries_left') else None
        if obj.get('retry_intervals'):
            self.retry_intervals = json.loads(obj.get('retry_intervals').decode())

        raw_exc_info = obj.get('exc_info')
        if raw_exc_info:
            try:
                self._exc_info = as_text(zlib.decompress(raw_exc_info))
            except zlib.error:
                # Fallback to uncompressed string
                self._exc_info = as_text(raw_exc_info)

    @classmethod
    def create(
        cls,
        func: FunctionReferenceType,
        args: Union[List[Any], Optional[Tuple]] = None,
        kwargs: Optional[Dict[str, Any]] = None,
        connection: Optional['Redis'] = None,
        result_ttl: Optional[int] = None,
        ttl: Optional[int] = None,
        status: Optional[JobStatus] = None,
        description: Optional[str] = None,
        depends_on: Optional[JobDependencyType] = None,
        timeout: Optional[int] = None,
        id: Optional[str] = None,
        origin: str = '',
        meta: Optional[Dict[str, Any]] = None,
        failure_ttl: Optional[int] = None,
        serializer=None,
        *,
        on_success: Optional[Union['Callback', Callable[..., Any]]] = None,  # Callable is deprecated
        on_failure: Optional[Union['Callback', Callable[..., Any]]] = None,  # Callable is deprecated
        on_stopped: Optional[Union['Callback', Callable[..., Any]]] = None,  # Callable is deprecated
    ) -> 'Job':
        """Creates a new Job instance for the given function, arguments, and
        keyword arguments.

        Args:
            func (FunctionReference): The function/method/callable for the Job. This can be
                a reference to a concrete callable or a string representing the  path of function/method to be
                imported. Effectively this is the only required attribute when creating a new Job.
            args (Union[List[Any], Optional[Tuple]], optional): A Tuple / List of positional arguments to pass the
                callable.  Defaults to None, meaning no args being passed.
            kwargs (Optional[Dict], optional): A Dictionary of keyword arguments to pass the callable.
                Defaults to None, meaning no kwargs being passed.
            connection (Optional[Redis], optional): The Redis connection to use. Defaults to None.
                This will be "resolved" using the `resolve_connection` function when initialzing the Job Class.
            result_ttl (Optional[int], optional): The amount of time in seconds the results should live.
                Defaults to None.
            ttl (Optional[int], optional): The Time To Live (TTL) for the job itself. Defaults to None.
            status (JobStatus, optional): The Job Status. Defaults to None.
            description (Optional[str], optional): The Job Description. Defaults to None.
            depends_on (Union['Dependency', List[Union['Dependency', 'Job']]], optional): What the jobs depends on.
                This accepts a variaty of different arguments including a `Dependency`, a list of `Dependency` or a
                `Job` list of `Job`. Defaults to None.
            timeout (Optional[int], optional): The amount of time in seconds that should be a hardlimit for a job
                execution. Defaults to None.
            id (Optional[str], optional): An Optional ID (str) for the Job. Defaults to None.
            origin (Optional[str], optional): The queue of origin. Defaults to None.
            meta (Optional[Dict[str, Any]], optional): Custom metadata about the job, takes a dictioanry.
                Defaults to None.
            failure_ttl (Optional[int], optional): THe time to live in seconds for failed-jobs information.
                Defaults to None.
            serializer (Optional[str], optional): The serializer class path to use. Should be a string with the import
                path for the serializer to use. eg. `mymodule.myfile.MySerializer` Defaults to None.
            on_success (Optional[Union['Callback', Callable[..., Any]]], optional): A callback to run when/if the Job
                finishes sucessfully. Defaults to None. Passing a callable is deprecated.
            on_failure (Optional[Union['Callback', Callable[..., Any]]], optional): A callback to run when/if the Job
                fails. Defaults to None. Passing a callable is deprecated.
            on_stopped (Optional[Union['Callback', Callable[..., Any]]], optional): A callback to run when/if the Job
                is stopped. Defaults to None. Passing a callable is deprecated.

        Raises:
            TypeError: If `args` is not a tuple/list
            TypeError: If `kwargs` is not a dict
            TypeError: If the `func` is something other than a string or a Callable reference
            ValueError: If `on_failure` is not a Callback or function or string
            ValueError: If `on_success` is not a Callback or function or string
            ValueError: If `on_stopped` is not a Callback or function or string

        Returns:
            Job: A job instance.
        """
        if args is None:
            args = ()
        if kwargs is None:
            kwargs = {}

        if not isinstance(args, (tuple, list)):
            raise TypeError('{0!r} is not a valid args list'.format(args))
        if not isinstance(kwargs, dict):
            raise TypeError('{0!r} is not a valid kwargs dict'.format(kwargs))

        job = cls(connection=connection, serializer=serializer)
        if id is not None:
            job.set_id(id)

        if origin:
            job.origin = origin

        # Set the core job tuple properties
        job._instance = None
        if inspect.ismethod(func):
            job._instance = func.__self__
            job._func_name = func.__name__
        elif inspect.isfunction(func) or inspect.isbuiltin(func):
            job._func_name = '{0}.{1}'.format(func.__module__, func.__qualname__)
        elif isinstance(func, str):
            job._func_name = as_text(func)
        elif not inspect.isclass(func) and hasattr(func, '__call__'):  # a callable class instance
            job._instance = func
            job._func_name = '__call__'
        else:
            raise TypeError('Expected a callable or a string, but got: {0}'.format(func))
        job._args = args
        job._kwargs = kwargs

        if on_success:
            if not (isinstance(on_success, Callback) or isinstance(on_success, AscCallback)):
                warnings.warn(
                    'Passing a string or function for `on_success` is deprecated, pass `Callback` instead',
                    DeprecationWarning,
                )
                on_success = Callback(on_success)  # backward compatibility
            if hasattr(on_success, 'params'):
                job._success_callback_args = on_success.params

            job._success_callback_name = on_success.name
            job._success_callback_timeout = on_success.timeout

        if on_failure:
            print('on_failure\n\n\n\n', on_failure)
            if not (isinstance(on_failure, Callback) or isinstance(on_failure, AscCallback)):
                warnings.warn(
                    'Passing a string or function for `on_failure` is deprecated, pass `Callback` instead',
                    DeprecationWarning,
                )
                on_failure = Callback(on_failure)  # backward compatibility
            if hasattr(on_failure, 'params'):
                job._failure_callback_args = on_failure.params
            job._failure_callback_name = on_failure.name
            job._failure_callback_timeout = on_failure.timeout

        if on_stopped:
            if not (isinstance(on_stopped, Callback) or isinstance(on_stopped, AscCallback)):
                warnings.warn(
                    'Passing a string or function for `on_stopped` is deprecated, pass `Callback` instead',
                    DeprecationWarning,
                )
                on_stopped = Callback(on_stopped)  # backward compatibility
            if hasattr(on_stopped, 'params'):
                job._stopped_callback_args = on_stopped.params
            job._stopped_callback_name = on_stopped.name
            job._stopped_callback_timeout = on_stopped.timeout

        # Extra meta data
        job.description = description or job.get_call_string()
        job.result_ttl = parse_timeout(result_ttl)
        job.failure_ttl = parse_timeout(failure_ttl)
        job.ttl = parse_timeout(ttl)
        job.timeout = parse_timeout(timeout)
        job._status = status
        job.meta = meta or {}

        # dependency could be job instance or id, or iterable thereof
        if depends_on is not None:
            depends_on = ensure_list(depends_on)
            depends_on_list = []
            for depends_on_item in depends_on:
                if isinstance(depends_on_item, Dependency):
                    # If a Dependency has enqueue_at_front or allow_failure set to True, these behaviors are used for
                    # all dependencies.
                    job.enqueue_at_front = job.enqueue_at_front or depends_on_item.enqueue_at_front
                    job.allow_dependency_failures = job.allow_dependency_failures or depends_on_item.allow_failure
                    depends_on_list.extend(depends_on_item.dependencies)
                else:
                    depends_on_list.extend(ensure_list(depends_on_item))
            job._dependency_ids = [dep.id if isinstance(dep, Job) else dep for dep in depends_on_list]

        return job
    
    async def aexecute_success_callback(self, death_penalty_class: Type[BaseDeathPenalty], result: Any):
        """Executes success_callback for a job.
        with timeout .

        Args:
            death_penalty_class (Type[BaseDeathPenalty]): The penalty class to use for timeout
            result (Any): The job's result.
        """
        if not self.success_callback:
            return

        logger.debug('Running success callbacks for %s', self.id)
        with death_penalty_class(self.success_callback_timeout, JobTimeoutException, job_id=self.id):
            args = self._success_callback_args
            await self.success_callback(args, self, self.connection, result)

    def execute_success_callback(self, death_penalty_class: Type[BaseDeathPenalty], result: Any):
        """Executes success_callback for a job.
        with timeout .

        Args:
            death_penalty_class (Type[BaseDeathPenalty]): The penalty class to use for timeout
            result (Any): The job's result.
        """
        if not self.success_callback:
            return

        logger.debug('Running success callbacks for %s', self.id)
        with death_penalty_class(self.success_callback_timeout, JobTimeoutException, job_id=self.id):
            args = self._success_callback_args
            r = self.success_callback(args, self, self.connection, result)

    def execute_failure_callback(self, death_penalty_class: Type[BaseDeathPenalty], *exc_info):
        """Executes failure_callback with possible timeout"""
        if not self.failure_callback:
            return

        logger.debug('Running failure callbacks for %s', self.id)
        try:
            with death_penalty_class(self.failure_callback_timeout, JobTimeoutException, job_id=self.id):
                args = self._failure_callback_args
                self.failure_callback(args, self, self.connection, *exc_info)
        except Exception:  # noqa
            logger.exception(f'Job {self.id}: error while executing failure callback')
            raise

    def execute_stopped_callback(self, death_penalty_class: Type[BaseDeathPenalty]):
        """Executes stopped_callback with possible timeout"""
        logger.debug('Running stopped callbacks for %s', self.id)
        try:
            with death_penalty_class(self.stopped_callback_timeout, JobTimeoutException, job_id=self.id):
                args = self._failure_callback_args
                self.stopped_callback(args, self, self.connection)
        except Exception:  # noqa
            logger.exception(f'Job {self.id}: error while executing stopped callback')
            raise

    @classmethod
    def fetch(cls, id: str, connection: Optional['Redis'] = None, serializer=None) -> 'Job':
        """Fetches a persisted Job from its corresponding Redis key and instantiates it

        Args:
            id (str): The Job to fetch
            connection (Optional[&#39;Redis&#39;], optional): An optional Redis connection. Defaults to None.
            serializer (_type_, optional): The serializer to use. Defaults to None.

        Returns:
            Job: The Job instance
        """
        job = cls(id, connection=connection, serializer=serializer)
        job.refresh()
        return job
    

    # Job execution
    async def aperform(self) -> Any:  # noqa
        """The main execution method. Invokes the job function with the job arguments.
        This is the method that actually performs the job - it's what its called by the worker.

        Returns:
            result (Any): The job result
        """
        self.connection.persist(self.key)
        _job_stack.push(self)
        try:
            self._result = await self._aexecute()
        finally:
            assert self is _job_stack.pop()
        return self._result