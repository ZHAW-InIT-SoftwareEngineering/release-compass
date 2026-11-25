import rdflib


g = rdflib.Graph()
g.parse("ontology/release-compass.ttl", format="turtle")
print(g)
