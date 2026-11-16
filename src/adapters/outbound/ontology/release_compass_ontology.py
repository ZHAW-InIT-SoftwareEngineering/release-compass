"""Release Compass ontology namespaces and graph setup (ADR 0013)."""

from rdflib import Graph, Namespace

_BASE = "https://github.com/ZHAW-InIT-SoftwareEngineering/release-compass/"

# Vocabulary terms, declared in ontology/release-compass.ttl.
RELEASE_COMPASS = Namespace(f"{_BASE}ontology#")
# Instance IRIs, e.g. <…/data/report/{uuid}>.
RELEASE_COMPASS_DATA = Namespace(f"{_BASE}data/")


def new_graph() -> Graph:
    graph = Graph()
    graph.bind("release-compass", RELEASE_COMPASS)
    return graph
