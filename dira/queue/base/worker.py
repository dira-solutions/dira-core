from rq.defaults import DEFAULT_LOGGING_DATE_FORMAT, DEFAULT_LOGGING_FORMAT
from rq.worker import DequeueStrategy, Worker, worker_registration, StopRequested, WorkerStatus, logger
from rq.timeouts import UnixSignalDeathPenalty, JobTimeoutException
from rq.connections import push_connection, pop_connection
from rq.logutils import green, yellow, blue
from rq.utils import utcnow, as_text


from .job import AscJob
from .queue import AscQueue

import redis
import os
import time
import sys
import traceback
import random

class AscWorker(Worker):
    redis_worker_namespace_prefix = 'rq:worker:'
    redis_workers_keys = worker_registration.REDIS_WORKER_KEYS
    death_penalty_class = UnixSignalDeathPenalty
    queue_class = AscQueue
    job_class = AscJob

    async def awork(self, burst: bool = False, logging_level: str = "INFO", date_format: str = ..., log_format: str = ..., max_jobs: int | None = None, max_idle_time: int | None = None, with_scheduler: bool = False, dequeue_strategy: DequeueStrategy = DequeueStrategy.DEFAULT) -> bool:
        """Starts the work loop.

        Pops and performs all jobs on the current list of queues.  When all
        queues are empty, block and wait for new jobs to arrive on any of the
        queues, unless `burst` mode is enabled.
        If `max_idle_time` is provided, worker will die when it's idle for more than the provided value.

        The return value indicates whether any jobs were processed.

        Args:
            burst (bool, optional): Whether to work on burst mode. Defaults to False.
            logging_level (str, optional): Logging level to use. Defaults to "INFO".
            date_format (str, optional): Date Format. Defaults to DEFAULT_LOGGING_DATE_FORMAT.
            log_format (str, optional): Log Format. Defaults to DEFAULT_LOGGING_FORMAT.
            max_jobs (Optional[int], optional): Max number of jobs. Defaults to None.
            max_idle_time (Optional[int], optional): Max seconds for worker to be idle. Defaults to None.
            with_scheduler (bool, optional): Whether to run the scheduler in a separate process. Defaults to False.
            dequeue_strategy (DequeueStrategy, optional): Which strategy to use to dequeue jobs.
                Defaults to DequeueStrategy.DEFAULT

        Returns:
            worked (bool): Will return True if any job was processed, False otherwise.
        """
        self.bootstrap(logging_level, date_format, log_format)
        self._dequeue_strategy = dequeue_strategy
        completed_jobs = 0
        if with_scheduler:
            self._start_scheduler(burst, logging_level, date_format, log_format)

        self._install_signal_handlers()
        try:
            while True:
                try:
                    self.check_for_suspension(burst)

                    if self.should_run_maintenance_tasks:
                        self.run_maintenance_tasks()

                    if self._stop_requested:
                        self.log.info('Worker %s: stopping on request', self.key)
                        break

                    timeout = None if burst else self.dequeue_timeout
                    result = self.dequeue_job_and_maintain_ttl(timeout, max_idle_time)
                    if result is None:
                        if burst:
                            self.log.info('Worker %s: done, quitting', self.key)
                        elif max_idle_time is not None:
                            self.log.info('Worker %s: idle for %d seconds, quitting', self.key, max_idle_time)
                        break

                    job, queue = result
                    await self.aexecute_job(job, queue)
                    self.heartbeat()

                    completed_jobs += 1
                    if max_jobs is not None:
                        if completed_jobs >= max_jobs:
                            self.log.info('Worker %s: finished executing %d jobs, quitting', self.key, completed_jobs)
                            break

                except redis.exceptions.TimeoutError:
                    self.log.error('Worker %s: Redis connection timeout, quitting...', self.key)
                    break

                except StopRequested:
                    break

                except SystemExit:
                    # Cold shutdown detected
                    raise

                except:  # noqa
                    self.log.error('Worker %s: found an unhandled exception, quitting...', self.key, exc_info=True)
                    break
        finally:
            self.teardown()
        return bool(completed_jobs)
    
    async def aexecute_job(self, job: 'AscJob', queue: 'AscQueue'):
        """Spawns a work horse to perform the actual work and passes it a job.
        The worker will wait for the work horse and make sure it executes
        within the given timeout bounds, or will end the work horse with
        SIGALRM.
        """
        self.set_state(WorkerStatus.BUSY)
        await self.afork_work_horse(job, queue)
        self.monitor_work_horse(job, queue)
        self.set_state(WorkerStatus.IDLE)

    async def afork_work_horse(self, job: 'AscJob', queue: 'AscQueue'):
        """Spawns a work horse to perform the actual work and passes it a job.
        This is where the `fork()` actually happens.

        Args:
            job (Job): The Job that will be ran
            queue (Queue): The queue
        """
        child_pid = os.fork()
        os.environ['RQ_WORKER_ID'] = self.name
        os.environ['RQ_JOB_ID'] = job.id
        if child_pid == 0:
            os.setsid()
            await self.amain_work_horse(job, queue)
            os._exit(0)  # just in case
        else:
            self._horse_pid = child_pid
            self.procline('Forked {0} at {1}'.format(child_pid, time.time()))

    async def amain_work_horse(self, job: 'AscJob', queue: 'AscQueue'):
        """This is the entry point of the newly spawned work horse.
        After fork()'ing, always assure we are generating random sequences
        that are different from the worker.

        os._exit() is the way to exit from childs after a fork(), in
        contrast to the regular sys.exit()
        """
        random.seed()
        self.setup_work_horse_signals()
        self._is_horse = True
        self.log = logger
        try:
            await self.aperform_job(job, queue)
        except:  # noqa
            os._exit(1)
        os._exit(0)

    async def aperform_job(self, job: 'AscJob', queue: 'AscQueue') -> bool:
        """Performs the actual work of a job.  Will/should only be called
        inside the work horse's process.

        Args:
            job (Job): The Job
            queue (Queue): The Queue

        Returns:
            bool: True after finished.
        """
        push_connection(self.connection)
        started_job_registry = queue.started_job_registry
        self.log.debug('Started Job Registry set.')

        try:
            remove_from_intermediate_queue = len(self.queues) == 1
            self.prepare_job_execution(job, remove_from_intermediate_queue)

            job.started_at = utcnow()
            timeout = job.timeout or self.queue_class.DEFAULT_TIMEOUT
            with self.death_penalty_class(timeout, JobTimeoutException, job_id=job.id):
                self.log.debug('Performing Job...')
                rv = job.perform()
                self.log.debug('Finished performing Job ID %s', job.id)

            job.ended_at = utcnow()

            # Pickle the result in the same try-except block since we need
            # to use the same exc handling when pickling fails
            job._result = rv

            job.heartbeat(utcnow(), job.success_callback_timeout)
            job.execute_success_callback(self.death_penalty_class, rv)

            self.handle_job_success(job=job, queue=queue, started_job_registry=started_job_registry)
        except:  # NOQA
            self.log.debug('Job %s raised an exception.', job.id)
            job.ended_at = utcnow()
            exc_info = sys.exc_info()
            exc_string = ''.join(traceback.format_exception(*exc_info))

            try:
                job.heartbeat(utcnow(), job.failure_callback_timeout)
                job.execute_failure_callback(self.death_penalty_class, *exc_info)
            except:  # noqa
                exc_info = sys.exc_info()
                exc_string = ''.join(traceback.format_exception(*exc_info))

            self.handle_job_failure(
                job=job, exc_string=exc_string, queue=queue, started_job_registry=started_job_registry
            )
            self.handle_exception(job, *exc_info)
            return False

        finally:
            pop_connection()

        self.log.info('%s: %s (%s)', green(job.origin), blue('Job OK'), job.id)
        if rv is not None:
            self.log.debug('Result: %r', yellow(as_text(str(rv))))

        if self.log_result_lifespan:
            result_ttl = job.get_result_ttl(self.default_result_ttl)
            if result_ttl == 0:
                self.log.info('Result discarded immediately')
            elif result_ttl > 0:
                self.log.info('Result is kept for %s seconds', result_ttl)
            else:
                self.log.info('Result will never expire, clean up result key manually')

        return True