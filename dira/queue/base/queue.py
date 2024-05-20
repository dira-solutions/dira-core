from typing import Any, List, Tuple, Optional, Type, Iterable


from redis import Redis

from rq.types import FunctionReferenceType
from rq.utils import as_text, get_version, backend_class
from rq.exceptions import NoSuchJobError, DequeueTimeout
from rq.job import Job, JobStatus, logger
from rq.connections import resolve_connection
from rq.timeouts import BaseDeathPenalty
from rq.queue import Queue
from rq.logutils import green
from rq.intermediate_queue import IntermediateQueue

from datetime import timedelta, datetime, timezone

from .job import AscJob

import traceback
import sys

class AscQueue(Queue):
    job_class = AscJob

    def enqueue_in(self, time_delta: timedelta, func: 'FunctionReferenceType', *args, **kwargs) -> 'Job':
        """Schedules a job to be executed in a given `timedelta` object

        Args:
            time_delta (timedelta): The timedelta object
            func (FunctionReferenceType): The function reference

        Returns:
            job (Job): The enqueued Job
        """
        return self.enqueue_at(datetime.now(timezone.utc) + time_delta, func, *args, **kwargs)

    def run_sync(self, job: 'Job') -> 'Job':
        """Run a job synchronously, meaning on the same process the method was called.

        Args:
            job (Job): The job to run

        Returns:
            Job: The job instance
        """
        with self.connection.pipeline() as pipeline:
            job.prepare_for_execution('sync', pipeline)
        try:
            job = self.run_job(job)
        except:  # noqa
            with self.connection.pipeline() as pipeline:
                job.set_status(JobStatus.FAILED, pipeline=pipeline)
                exc_string = ''.join(traceback.format_exception(*sys.exc_info()))
                job._handle_failure(exc_string, pipeline)
                pipeline.execute()

            if job.failure_callback:
                job.failure_callback(job, self.connection, *sys.exc_info())  # type: ignore
        else:
            if job.success_callback:
                job.success_callback(job, self.connection, job.return_value())  # type: ignore

        return job
    
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
    
    @classmethod
    def dequeue_any(
        cls,
        queues: List['Queue'],
        timeout: Optional[int],
        connection: Optional['Redis'] = None,
        job_class: Optional['Job'] = None,
        serializer: Any = None,
        death_penalty_class: Optional[Type[BaseDeathPenalty]] = None,
    ) -> Tuple['Job', 'Queue']:
        """Class method returning the job_class instance at the front of the given
        set of Queues, where the order of the queues is important.

        When all of the Queues are empty, depending on the `timeout` argument,
        either blocks execution of this function for the duration of the
        timeout or until new messages arrive on any of the queues, or returns
        None.

        See the documentation of cls.lpop for the interpretation of timeout.

        Args:
            queues (List[Queue]): List of queue objects
            timeout (Optional[int]): Timeout for the LPOP
            connection (Optional[Redis], optional): Redis Connection. Defaults to None.
            job_class (Optional[Type[Job]], optional): The job class. Defaults to None.
            serializer (Any, optional): Serializer to use. Defaults to None.
            death_penalty_class (Optional[Type[BaseDeathPenalty]], optional): The death penalty class. Defaults to None.

        Raises:
            e: Any exception

        Returns:
            job, queue (Tuple[Job, Queue]): A tuple of Job, Queue
        """
        job_class: Job = backend_class(cls, 'job_class', override=job_class)
        while True:
            queue_keys = [q.key for q in queues]
            if len(queue_keys) == 1 and get_version(connection) >= (6, 2, 0):
                result = cls.lmove(connection, queue_keys[0], timeout)
            else:
                result = cls.lpop(queue_keys, timeout, connection=connection)
            if result is None:
                return None
            queue_key, job_id = map(as_text, result)
            queue = cls.from_queue_key(
                queue_key,
                connection=connection,
                job_class=job_class,
                serializer=serializer,
                death_penalty_class=death_penalty_class,
            )
            try:
                job = job_class.fetch(job_id, connection=connection, serializer=serializer)
            except NoSuchJobError:
                # Silently pass on jobs that don't exist (anymore),
                # and continue in the look
                continue
            except Exception as e:
                # Attach queue information on the exception for improved error
                # reporting
                e.job_id = job_id
                e.queue = queue
                raise e
            return job, queue
        return None, None
    
    @classmethod
    def lpop(cls, queue_keys: List[str], timeout: Optional[int], connection: Optional['Redis'] = None):
        """Helper method to abstract away from some Redis API details
        where LPOP accepts only a single key, whereas BLPOP
        accepts multiple.  So if we want the non-blocking LPOP, we need to
        iterate over all queues, do individual LPOPs, and return the result.

        Until Redis receives a specific method for this, we'll have to wrap it
        this way.

        The timeout parameter is interpreted as follows:
            None - non-blocking (return immediately)
             > 0 - maximum number of seconds to block

        Args:
            queue_keys (_type_): _description_
            timeout (Optional[int]): _description_
            connection (Optional[Redis], optional): _description_. Defaults to None.

        Raises:
            ValueError: If timeout of 0 was passed
            DequeueTimeout: BLPOP Timeout

        Returns:
            _type_: _description_
        """
        connection = connection or resolve_connection()
        if timeout is not None:  # blocking variant
            if timeout == 0:
                raise ValueError('RQ does not support indefinite timeouts. Please pick a timeout value > 0')
            colored_queues = ', '.join(map(str, [green(str(queue)) for queue in queue_keys]))
            logger.debug(f"Starting BLPOP operation for queues {colored_queues} with timeout of {timeout}")
            result = connection.blpop(queue_keys, timeout)
            if result is None:
                logger.debug(f"BLPOP timeout, no jobs found on queues {colored_queues}")
                raise DequeueTimeout(timeout, queue_keys)
            queue_key, job_id = result
            return queue_key, job_id
        else:  # non-blocking variant
            for queue_key in queue_keys:
                blob = connection.lpop(queue_key)
                if blob is not None:
                    return queue_key, blob
            return None

    @classmethod
    def lmove(cls, connection: 'Redis', queue_key: str, timeout: Optional[int]):
        """Similar to lpop, but accepts only a single queue key and immediately pushes
        the result to an intermediate queue.
        """
        intermediate_queue = IntermediateQueue(queue_key, connection)
        if timeout is not None:  # blocking variant
            if timeout == 0:
                raise ValueError('RQ does not support indefinite timeouts. Please pick a timeout value > 0')
            colored_queue = green(queue_key)
            logger.debug(f"Starting BLMOVE operation for {colored_queue} with timeout of {timeout}")
            result = connection.blmove(queue_key, intermediate_queue.key, timeout)
            if result is None:
                logger.debug(f"BLMOVE timeout, no jobs found on {colored_queue}")
                raise DequeueTimeout(timeout, queue_key)
            return queue_key, result
        else:  # non-blocking variant
            result = connection.lmove(queue_key, intermediate_queue.key)
            if result is not None:
                return queue_key, result
            return None

    @classmethod
    def fetch_many(cls, job_ids: Iterable[str], connection: 'Redis', serializer=None) -> List['Job']:
        """
        Bulk version of Job.fetch

        For any job_ids which a job does not exist, the corresponding item in
        the returned list will be None.

        Args:
            job_ids (Iterable[str]): A list of job ids.
            connection (Redis): Redis connection
            serializer (Callable): A serializer

        Returns:
            jobs (list[Job]): A list of Jobs instances.
        """
        with connection.pipeline() as pipeline:
            for job_id in job_ids:
                pipeline.hgetall(cls.key_for(job_id))
            results = pipeline.execute()

        jobs: List[Optional['Job']] = []
        for i, job_id in enumerate(job_ids):
            if not results[i]:
                jobs.append(None)
                continue

            job = cls(job_id, connection=connection, serializer=serializer)
            job.restore(results[i])
            jobs.append(job)

        return jobs
