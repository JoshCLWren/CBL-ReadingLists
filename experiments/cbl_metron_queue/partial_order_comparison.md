# Partial-order comparison

- **new_ultimate_universe**: {'node_count': 94, 'edge_count': 788, 'hard_edge_count': 81, 'soft_edge_count': 707, 'optional_node_count': 0, 'parallel_lane_count': 0, 'alternate_orders_generated': 20, 'original_order_valid': True, 'same_series_order_preserved': True, 'freedom_ratio': 1.0}
- **absolute_universe**: {'node_count': 59, 'edge_count': 478, 'hard_edge_count': 53, 'soft_edge_count': 425, 'optional_node_count': 0, 'parallel_lane_count': 0, 'alternate_orders_generated': 1, 'original_order_valid': True, 'same_series_order_preserved': True, 'freedom_ratio': 0.05}
- **fourth_world**: {'node_count': 11, 'edge_count': 11, 'hard_edge_count': 11, 'soft_edge_count': 0, 'optional_node_count': 0, 'parallel_lane_count': 0, 'alternate_orders_generated': 0, 'original_order_valid': False, 'same_series_order_preserved': False, 'freedom_ratio': 0.0}
- **onslaught**: {'node_count': 93, 'edge_count': 805, 'hard_edge_count': 25, 'soft_edge_count': 780, 'optional_node_count': 0, 'parallel_lane_count': 0, 'alternate_orders_generated': 20, 'original_order_valid': False, 'same_series_order_preserved': False, 'freedom_ratio': 1.0}
- **cosmic_marvel**: {'node_count': 33, 'edge_count': 216, 'hard_edge_count': 27, 'soft_edge_count': 189, 'optional_node_count': 0, 'parallel_lane_count': 0, 'alternate_orders_generated': 1, 'original_order_valid': True, 'same_series_order_preserved': True, 'freedom_ratio': 0.05}

## Production recommendation
Use a small graph vocabulary: hard edge, soft edge, optional membership, phase/gate, provenance, and confidence. Same-series spines are hard structural edges; cross-series CBL order is soft unless repeated across independent source families. Identity conflicts should block automatic graph inference.

The graph can answer what is readable now by checking unsatisfied hard predecessors, expose parallel threads where no cross-thread edge exists, identify gates when explicit phase nodes are added, and offer strict versus loose modes by including or ignoring soft edges. The five cases do not support one universal profile: universe chronologies and focused crossovers need parallel/gate profiles, while Fourth World needs identity correction first.
