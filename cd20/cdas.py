

descriptions = {
    "Oslom": "Oslom",  # non-free
    "Infomap": "Infomap (Edler and Rosvall)",
    "LinkCommunities": "Link Communities",
    "CliquePerc": "Clique Percolation",
    "IgraphModularity": "Modularity optimization",
    "SeqCliquePerc": "SequentialCliquePercolation",

    "IgraphCNM": "Clauset-Newman-Moore",
    "IgraphGN": "Girvan-Newman (Edge betweenness)",
    "IgraphInfomap": "Infomap (from igraph)",
    "IgraphLabelPropagation": "RAK label propagation",
    "IgraphLouvain": "Louvain",
    "IgraphModularity": "Modularity optimization",
    "IgraphModEV": "Mod. matrix eigenvector",
    "IgraphModEVNaive": "Mod. matrix eigenvector (naive)",
    "IgraphSpinglass": "Potts model methods",
    "IgraphWalktrap": "Walktrap method",

    "NullCD": "NullCD (do not detect anything)",
    }


methods = [("General-purpose",
            [("IgraphLouvain", ),
             #("Oslom", "Oslom"),  # non-free
             ("Infomap", ),
             ("LinkCommunities", ),
             ("CliquePerc", ),
             ("IgraphModularity", ),
             ("SeqCliquePerc", ),
             ]),
           ("From igraph",
            [("IgraphCNM", ),
             ("IgraphGN", ),
             ("IgraphInfomap", ),
             ("IgraphLabelPropagation", ),
             ("IgraphLouvain", ),
             ("IgraphModularity", ),
             ("IgraphModEV", ),
             ("IgraphModEVNaive", ),
             ("IgraphSpinglass", ),
             ("IgraphWalktrap", ),
             ]),
           ("Special methods",
            [("NullCD", ),
             ]),
           ]

for group, meths in methods:
    for i in range(len(meths)):
        if isinstance(meths[i], str):
            meths[i] = (meths[i], descriptions.get(meths[i], meths[i]))
        elif len(meths[i]) == 1:
            meths[i] = (meths[i][0], descriptions.get(meths[i][0],meths[i][0]))
        else:
            pass

