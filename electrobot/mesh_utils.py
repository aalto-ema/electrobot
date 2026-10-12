def connected_solids(mesh):
    """Count connected mesh components without optional scipy dependency."""
    parent=list(range(len(mesh.vertices)))
    def root(i):
        while parent[i]!=i:
            parent[i]=parent[parent[i]]; i=parent[i]
        return i
    used=set()
    for a,b,c in mesh.faces:
        a,b,c=int(a),int(b),int(c); used.update((a,b,c))
        parent[root(b)]=root(a); parent[root(c)]=root(a)
    return len({root(i) for i in used})
