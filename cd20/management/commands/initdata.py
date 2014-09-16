from os.path import dirname, join

from django.core.management.base import BaseCommand, CommandError
from django.core.files.base import ContentFile

import cd20
from cd20.models import Dataset

class Command(BaseCommand):
    args = ''
    help = 'Add karate club as dataset id=10'
    def handle(self, *args, **options):
        fname = join(dirname(cd20.__file__), 'data', 'karate.gml')
        # Get existing (or new) dataset #10:
        ds = Dataset.objects.get_or_create(id=10)[0]
        if ds.netfile: ds.netfile.delete()
        # We must use ContentFile to avoid SuspiciousOperation errors.
        # We read the data outside of django and pass it as a string.
        f = ContentFile(open(fname).read())
        f.name = 'karate.gml'
        f.path = 'karate.gml'
        ds.set_network(f)
        ds.save()
