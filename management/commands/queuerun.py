from os.path import dirname, join

from django.core.management.base import BaseCommand, CommandError
from django.core.files.base import ContentFile

import cd20
from ... import queue

class Command(BaseCommand):
    args = ''
    help = 'Run queue'
    def handle(self, *args, **options):
        queue.run()
