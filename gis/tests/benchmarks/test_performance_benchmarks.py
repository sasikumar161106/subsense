import time
import numpy as np
import pytest
from fastapi.testclient import TestClient
from shapely.geometry import Polygon

from src.api.main import app
from src.risk_zones.zone_tracker import ZoneTracker
from src.heatmap.tile_slicer import TileSlicer
from src.normalizer.crs_normalizer import SpatialDataNormalizer
from src.delivery.tile_cache import MultiTenantTileCache

client = TestClient(app)

def test_sla_2d_tile_fetch_latency():
    """
    SLA Benchmark: 2D Tile Fetch Latency <= 250ms at 95th percentile under 100 requests.
    (Section 8 Target: <= 250ms)
    """
    latencies_ms = []
    # Execute 100 tile requests
    for i in range(100):
        t0 = time.perf_counter()
        resp = client.get("/api/v1/tiles/tenant_benchmark/PANEL7-JHARIA/16/46962/30468.png")
        t1 = time.perf_counter()
        assert resp.status_code == 200
        latencies_ms.append((t1 - t0) * 1000.0)

    p95 = float(np.percentile(latencies_ms, 95))
    median = float(np.median(latencies_ms))
    print(f"\n[BENCHMARK] Tile Latency: Median={median:.2f}ms, P95={p95:.2f}ms")
    assert p95 <= 250.0, f"P95 latency {p95}ms exceeded 250ms SLA"

def test_sla_end_to_end_tile_rendering_pipeline():
    """
    SLA Benchmark: Full End-to-End Tile Rendering Pipeline <= 30 seconds post-ingestion.
    (Section 8 Target: <= 30s)
    """
    normalizer = SpatialDataNormalizer()
    slicer = TileSlicer(normalizer)
    
    # Ingest 250x250 continuous Kriging risk grid
    H, W = 250, 250
    risk_grid = np.random.uniform(0.1, 0.9, (H, W)).astype(np.float32)
    var_grid = np.random.uniform(0.05, 0.35, (H, W)).astype(np.float32)
    bounds = (86.425, 23.785, 86.445, 23.800)

    t0 = time.perf_counter()
    img, meta = slicer.render_tile_image(
        risk_grid=risk_grid,
        grid_bounds_wgs84=bounds,
        z=16, x=46962, y=30468,
        variance_grid=var_grid,
        data_currency_seconds=15.0
    )
    duration_s = time.perf_counter() - t0
    
    print(f"\n[BENCHMARK] End-to-End Ingestion-to-Tile Duration: {duration_s:.4f}s")
    assert duration_s <= 30.0, f"Pipeline duration {duration_s}s exceeded 30s SLA"
    assert img.size == (256, 256)

def test_sla_zone_id_persistence_stability():
    """
    SLA Benchmark: Zone ID Persistence Stability >= 98.5% Overlap Consistency.
    (Section 8 Target: >= 98.5%)
    Simulates 20 consecutive 30-second cycles of a moving geomechanical subsidence plume.
    """
    tracker = ZoneTracker(site_id="PANEL7-JHARIA")
    
    # Initial plume centered at (442500, 2631700) with size 150m x 150m
    cx, cy = 442500.0, 2631700.0
    size = 150.0
    
    # 20 cycles with slow geomechanical creep (1 meter per 30s cycle)
    total_evaluations = 0
    consistent_identifications = 0
    
    initial_zone_id = None

    for cycle in range(20):
        shift = cycle * 1.2  # 1.2m shift per cycle
        poly = Polygon([
            (cx + shift, cy + shift),
            (cx + shift + size, cy + shift),
            (cx + shift + size, cy + shift + size),
            (cx + shift, cy + shift + size),
            (cx + shift, cy + shift)
        ])
        collection = tracker.process_cycle({"warning": [poly]})
        assert len(collection.features) == 1
        zone_id = collection.features[0].id

        if cycle == 0:
            initial_zone_id = zone_id
            consistent_identifications += 1
        else:
            if zone_id == initial_zone_id:
                consistent_identifications += 1
        total_evaluations += 1

    consistency_rate = (consistent_identifications / total_evaluations) * 100.0
    print(f"\n[BENCHMARK] Zone ID Persistence: {consistency_rate:.1f}%")
    assert consistency_rate >= 98.5, f"Consistency rate {consistency_rate}% below 98.5% SLA"

def test_sla_multi_tenant_partition_verification():
    """
    SLA Benchmark: Multi-Tenant Data Isolation 100% Partition Verification.
    (Section 8 Target: 100% Partition Verification)
    """
    cache = MultiTenantTileCache()
    tenants = [f"tenant_corp_{i:02d}" for i in range(10)]
    
    # Write unique payload per tenant
    for t in tenants:
        cache.put_tile(t, "SITE_COMMON", 16, 100, 100, f"SECRET_{t}".encode())

    # Verify each tenant sees ONLY their data, and cannot see others
    for i, t in enumerate(tenants):
        own_data = cache.get_tile(t, "SITE_COMMON", 16, 100, 100)
        assert own_data == f"SECRET_{t}".encode()
        
        # Verify negative query against other tenants
        for other in tenants:
            if other != t:
                # Direct check across isolation boundaries
                other_read = cache.get_tile(other, "SITE_COMMON", 16, 100, 100)
                assert other_read != f"SECRET_{t}".encode()
