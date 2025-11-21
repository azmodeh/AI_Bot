import asyncio
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime
from collections import deque

logger = logging.getLogger(__name__)


@dataclass
class AIJob:
    """Represents an AI processing job"""
    user_id: int
    job_type: str  # "photo" or "chat"
    payload: Dict[str, Any]
    message_id: int
    created_at: datetime = field(default_factory=datetime.utcnow)
    job_id: str = field(default_factory=lambda: f"{datetime.utcnow().timestamp()}")


class AIJobQueue:
    """
    Global async job queue for all AI requests.
    
    Features:
    - Unlimited queue capacity
    - Configurable worker concurrency (default: 3)
    - FIFO processing
    - Per-user ordering maintained
    - Non-blocking async workers
    """
    
    def __init__(self, max_concurrent_jobs: int = 3):
        self.queue: deque[AIJob] = deque()
        self.max_concurrent_jobs = max_concurrent_jobs
        self.active_workers = 0
        self.lock = asyncio.Lock()
        self.queue_event = asyncio.Event()
        self.user_active_jobs: Dict[int, bool] = {}
        
        logger.info(f"[QUEUE] Initialized with max_concurrent_jobs={max_concurrent_jobs}")
    
    async def enqueue(self, job: AIJob) -> int:
        """
        Add a job to the queue.
        
        Args:
            job: AIJob instance
            
        Returns:
            Queue position (1-indexed)
        """
        async with self.lock:
            self.queue.append(job)
            position = len(self.queue)
            
            logger.info(f"[QUEUE] Job enqueued: user={job.user_id}, type={job.job_type}, position={position}")
            
            # Signal that a new job is available
            self.queue_event.set()
            
            return position
    
    async def dequeue(self) -> Optional[AIJob]:
        """
        Get the next job from the queue.
        
        Returns:
            Next AIJob or None if queue is empty
        """
        async with self.lock:
            if not self.queue:
                return None
            
            job = self.queue.popleft()
            logger.info(f"[QUEUE] Job dequeued: user={job.user_id}, type={job.job_type}")
            
            return job
    
    def get_queue_length(self) -> int:
        """Get current queue length"""
        return len(self.queue)
    
    def get_user_position(self, user_id: int) -> Optional[int]:
        """
        Get the position of the first job for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            Position (1-indexed) or None if user has no jobs
        """
        for i, job in enumerate(self.queue, 1):
            if job.user_id == user_id:
                return i
        return None
    
    async def wait_for_job(self):
        """Wait until a job is available"""
        await self.queue_event.wait()
        self.queue_event.clear()
    
    def is_user_active(self, user_id: int) -> bool:
        """Check if user has an active job being processed"""
        return self.user_active_jobs.get(user_id, False)
    
    def set_user_active(self, user_id: int, active: bool):
        """Set user's active job status"""
        self.user_active_jobs[user_id] = active
        if not active and user_id in self.user_active_jobs:
            del self.user_active_jobs[user_id]


class AIWorkerPool:
    """
    Manages a pool of AI workers that process jobs from the queue.
    """
    
    def __init__(self, queue: AIJobQueue, job_processor):
        self.queue = queue
        self.job_processor = job_processor
        self.workers = []
        self.running = False
        
        logger.info(f"[WORKER_POOL] Initialized")
    
    async def start(self):
        """Start the worker pool"""
        if self.running:
            logger.warning("[WORKER_POOL] Already running")
            return
        
        self.running = True
        
        # Start worker tasks
        for i in range(self.queue.max_concurrent_jobs):
            worker = asyncio.create_task(self._worker_loop(i))
            self.workers.append(worker)
        
        logger.info(f"[WORKER_POOL] Started {len(self.workers)} workers")
    
    async def stop(self):
        """Stop the worker pool"""
        self.running = False
        
        # Cancel all workers
        for worker in self.workers:
            worker.cancel()
        
        # Wait for workers to finish
        await asyncio.gather(*self.workers, return_exceptions=True)
        
        self.workers.clear()
        logger.info("[WORKER_POOL] Stopped")
    
    async def _worker_loop(self, worker_id: int):
        """
        Worker loop that processes jobs from the queue.
        
        Args:
            worker_id: Worker identifier
        """
        logger.info(f"[WORKER_{worker_id}] Started")
        
        while self.running:
            try:
                # Wait for a job to be available
                if self.queue.get_queue_length() == 0:
                    await self.queue.wait_for_job()
                
                # Get next job
                job = await self.queue.dequeue()
                
                if job is None:
                    await asyncio.sleep(0.1)
                    continue
                
                # Mark user as active
                self.queue.set_user_active(job.user_id, True)
                
                logger.info(f"[WORKER_{worker_id}] Processing job: user={job.user_id}, type={job.job_type}")
                
                # Process the job
                try:
                    await self.job_processor(job)
                    logger.info(f"[WORKER_{worker_id}] Job completed: user={job.user_id}")
                except Exception as e:
                    logger.exception(f"[WORKER_{worker_id}] Job failed: user={job.user_id}, error={e}")
                finally:
                    # Mark user as inactive
                    self.queue.set_user_active(job.user_id, False)
                
            except asyncio.CancelledError:
                logger.info(f"[WORKER_{worker_id}] Cancelled")
                break
            except Exception as e:
                logger.exception(f"[WORKER_{worker_id}] Unexpected error: {e}")
                await asyncio.sleep(1)
        
        logger.info(f"[WORKER_{worker_id}] Stopped")


# Global queue instance
global_queue: Optional[AIJobQueue] = None
worker_pool: Optional[AIWorkerPool] = None


def initialize_queue(max_concurrent_jobs: int = 3):
    """Initialize the global queue"""
    global global_queue
    global_queue = AIJobQueue(max_concurrent_jobs)
    logger.info("[QUEUE] Global queue initialized")
    return global_queue


def get_queue() -> AIJobQueue:
    """Get the global queue instance"""
    if global_queue is None:
        raise RuntimeError("Queue not initialized. Call initialize_queue() first.")
    return global_queue


async def start_workers(job_processor):
    """Start the worker pool"""
    global worker_pool
    
    queue = get_queue()
    worker_pool = AIWorkerPool(queue, job_processor)
    await worker_pool.start()
    
    logger.info("[QUEUE] Workers started")


async def stop_workers():
    """Stop the worker pool"""
    global worker_pool
    
    if worker_pool:
        await worker_pool.stop()
        worker_pool = None
    
    logger.info("[QUEUE] Workers stopped")
