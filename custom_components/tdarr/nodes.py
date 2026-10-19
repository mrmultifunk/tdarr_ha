"""Resolve persistent node names to Tdarr's temporary session IDs."""


def node_name(node):
    return node.get("nodeName") or node["_id"]


def find_node(coordinator, name):
    matches = [node for node in coordinator.data.get("nodes", {}).values()
               if node_name(node) == name]
    # Never send commands to an arbitrary node when names are duplicated.
    return matches[0] if len(matches) == 1 else None
