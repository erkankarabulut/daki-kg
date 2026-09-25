"""Loads the DAKI-KG .ttls files into a networkx.MultiDiGraph. Requires: pip install pyoxigraph networkx"""
import sys
from pathlib import Path

import networkx as nx
import pyoxigraph as ox

_REIFIES = ox.NamedNode("http://www.w3.org/1999/02/22-rdf-syntax-ns#reifies")
_RDF_TYPE = ox.NamedNode("http://www.w3.org/1999/02/22-rdf-syntax-ns#type")
_SUBCLASS_OF = ox.NamedNode("http://www.w3.org/2000/01/rdf-schema#subClassOf")
_NODE_TYPES = (ox.NamedNode, ox.BlankNode)
_XSD_BOOLEAN = ox.NamedNode("http://www.w3.org/2001/XMLSchema#boolean")
_XSD_NUMERIC = {
    ox.NamedNode("http://www.w3.org/2001/XMLSchema#decimal"),
    ox.NamedNode("http://www.w3.org/2001/XMLSchema#integer"),
    ox.NamedNode("http://www.w3.org/2001/XMLSchema#double"),
    ox.NamedNode("http://www.w3.org/2001/XMLSchema#float"),
}


def _local_name(iri):
    return iri.rsplit("#", 1)[-1].rsplit("/", 1)[-1]


def _value(term):
    if term.datatype == _XSD_BOOLEAN:
        return term.value.lower() in ("true", "1")
    if term.datatype in _XSD_NUMERIC:
        return float(term.value)
    return term.value


def load_daki_kg(graph_dir):
    store = ox.Store()
    for path in sorted(Path(graph_dir).glob("*.ttls")):
        with open(path, "rb") as f:
            store.load(f, ox.RdfFormat.TURTLE)

    reified = {}
    literals = {}
    for q in store:
        if q.predicate == _REIFIES:
            reified[q.subject] = q.object
        elif not isinstance(q.object, _NODE_TYPES):
            literals.setdefault(q.subject, {})[_local_name(q.predicate.value)] = _value(q.object)

    graph = nx.MultiDiGraph()
    folded = set()
    for q in store:
        if q.predicate == _REIFIES:
            continue
        s, p, o = q.subject, q.predicate, q.object
        if s in reified:
            if isinstance(o, _NODE_TYPES):
                base = reified[s]
                graph.add_edge(base.subject.value, base.object.value, key=(p.value, o.value),
                               predicate=p.value, target=o.value, **literals.get(o, {}))
                folded.add(o.value)
        elif p == _RDF_TYPE and isinstance(o, _NODE_TYPES):
            graph.add_node(s.value)
            graph.nodes[s.value].setdefault("type", []).append(_local_name(o.value))
        elif p == _SUBCLASS_OF:
            graph.add_node(s.value)
            graph.nodes[s.value].setdefault("subclass_of", []).append(_local_name(o.value))
        elif isinstance(o, _NODE_TYPES):
            graph.add_edge(s.value, o.value, key=p.value, predicate=p.value)
        else:
            graph.add_node(s.value, **{_local_name(p.value): _value(o)})

    for statement, edge in reified.items():
        key = (edge.subject.value, edge.object.value, edge.predicate.value)
        if statement in literals and graph.has_edge(*key):
            graph.edges[key].update(literals[statement])

    graph.remove_nodes_from([n for n in folded if n in graph and graph.degree(n) == 0])
    return graph


if __name__ == "__main__":
    graph_dir = sys.argv[1] if len(sys.argv) > 1 else "graph"
    g = load_daki_kg(graph_dir)
    print("nodes:", g.number_of_nodes())
    print("edges:", g.number_of_edges())
