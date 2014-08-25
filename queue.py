import os
import resource
import subprocess
import sys
import time

from django.db import transaction

from .models import Dataset, CD

QUEUE_LIMIT = 1
LIMIT_SEC = 60

def run(which=None):
    """Look through queue and run anything that needs to be"""
    while True:

        if queue_full():
            # Queue is full.  According to our semantics, we don't
            # need to poll or anyting.  After every job finishes, it
            # will start the next job.
            print "queue.py: Queue is full"
            return False

        # Find the job that should be run next.
        next = queue_next()
        if next is None:
            # No objects left to run.
            print "queue.py: No objects are queued"
            return False

        if which:
            # We have to run only one item.  Return after attempting
            # to run this item, True if run and False if not.
            # Regardless, after this run, if we are at this point then
            # we have the ability to run something in the queue.
            # Spawn a child process to run it.
            print "queue.py: Requested to run %s"%which
            if which != next:
                print "queue.py: Requested CD is not next in queue, spawning queuerunner"%which
                os.spawnl(os.P_NOWAIT, *run_queue_command())
                return False

            # Run `which` in current process and block for its completion.
            print "queue.py: Running requested CD."%which
            ret = runCD(which)
            print "queue.py: Done running requested CD."%which

            # Done running the passed object.  Fork to start new queue runner, and return
            print "queue.py: Spawning queuerunner."
            os.spawnl(os.P_NOWAIT, *run_queue_command())
            return ret

        runCD(next)

def queue_full():
    """Return True if queue is full (no more runners should be launched)"""
    if CD.objects.filter(state='R').count() < QUEUE_LIMIT:
        return False
    return True
def queue_next():
    """Return the next object in the queue"""
    #CD.objects.filter(state='Q').order_by('qtime').first()  # django 1.6 feature
    try:
        return CD.objects.filter(state='Q').order_by('qtime')[0]
    except IndexError:
        return None
def run_queue_command():
    """Return the command that must be run in order to initialize a queue runner."""
    return [sys.executable, sys.executable,
            '/srv/jako/jako/manage.py', 'queuerun']



def runCD(cd):
    """Run a single CD method and return.

    Use `run()` as the main entry point."""
    print "runCD:", cd
    def preexec():
        resource.setrlimit(resource.RLIMIT_CPU, (LIMIT_SEC, LIMIT_SEC))

    #with transaction.atomic():
    if cd.state != 'Q':
        raise RuntimeError("This CD is not in state queued! (%s)"%cd)
    cd.state = 'R'
    cd.save()

    # Fork and run in child process, for safety (any Python segfaults
    # or exceptions are encapsulated)
    pid = os.fork()
    if pid == 0:
        # child process
        preexec()
        cd._run()
        os._exit(0)  # exit after the fork
    # parent process
    _waited_pid, status = os.waitpid(pid, 0)
    signal = status % 256
    exitstatus = status // 256

    print "runCD: done running", cd, _waited_pid, signal, exitstatus

    if exitstatus == 0:
        cd.state = 'D'
        cd.save()
        time.sleep(2)
        return True
    else:
        cd.state = 'X'
        cd.save()
        message = 'CD(%s) died, signal=%s, exitstatus=%s'%(cd.id, signal, exitstatus)
        print message
        return False


if __name__ == '__main__':
    if sys.argv[1] == 'queuerun':
        run()
