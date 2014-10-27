ROOTDIR = '/srv/jako-data/'


MAX_NETWORK_BYTES =  512 * 2**10  # 64 KiB
MAX_NETWORK_NODES = 1000
MAX_NETWORK_EDGES = 10000

import pcd.support.algorithms as algs

# Call cda.name() (to normalize names) and create a set (to remove
# duplicates).
CDMETHODS = set(cda.name() for (name, cda) in vars(algs).iteritems()
                if isinstance(cda, type) and issubclass(cda, algs.CDMethod)
                and not name.startswith('_'))
CDMETHODS = sorted(CDMETHODS)

del algs

