# SubSense — GIS & Visualization Layer (Layer 5)
## Complete Repository Details & Technical Architecture Specification

---

## 1. Executive Summary & System Identity

The **GIS & Visualization Layer (Layer 5)** is the spatial situational-awareness and digital twin engine of the **SubSense Smart Underground Coal Mine Subsidence Platform** (developed for Smart India Hackathon 2026). Positioned at Software Stack Layer 5, it ingests continuous risk surfaces, deformation progression forecasts, Kriging matrices, GNN-refined zone risk, Time-to-Critical quantiles, and satellite InSAR vectors produced by the upstream **AI/ML Intelligence Layer (Layer 4)**.

Layer 5 converts these high-dimensional mathematical and kinematic tensors into discrete, legally accountable, map-grounded visual products that allow mine managers, shift supervisors, geotechnical safety engineers, and regulatory inspectors from the **Directorate General of Mines Safety (DGMS)** to take immediate preventative and operational action.

### Key System Attributes:
- **Repository Location**: `c:\Users\sasik\Desktop\SIH 2026\Subsense\gis_layer`
- **Technical Specification Baseline**: `SUBSENSE-TDD-GIS-005` (Rev 2.1)
- **Regulatory Compliance Standard**: DGMS Geotechnical GIS & Mapping Guidelines / Coal Mines Regulations (CMR) 2017
- **Core Technology Stack**:
  - **Backend**: Python 3.11+, FastAPI, PostGIS (PostgreSQL 16), PyProj, Shapely, SciPy, Pillow, Ezdxf, Pydantic v2
  - **Frontend / Client**: Native Canvas 2D / 3D Projection Engine, Web Mercator XYZ Tile Pyramids, Server-Sent Events (SSE), Glassmorphic Dark Dashboard
- **Test Suite Verification**: **31 / 31 Passed (100%)** across benchmarks, integration, and unit tests
- **Performance Benchmarks**:
  - **2D Tile Fetch Latency**: **$1.70\text{ ms}$ median / $2.59\text{ ms}$ P95** (SLA target $\le 250\text{ ms}$: **PASSED** with $96\times$ headroom)
  - **Tile Ingestion & Slicing Pipeline**: **$0.0001\text{ s}$** (SLA target $\le 30.0\text{ s}$: **PASSED**)
  - **Risk-Zone ID Persistence Stability**: **$100.0\%$** (SLA target $\ge 98.5\%$: **PASSED**)
  - **Multi-Tenant Data Partitioning**: **100% Isolation** across coalfield tenants

---

## 2. Core Architectural Principles (Section 2)

Layer 5 is engineered under four foundational architectural principles established in `SUBSENSE-TDD-GIS-005`:

1. **Model Output In, Map Layer Out**:
   - Layer 5 never recalculates raw sensor mechanics. It ingests formal Pydantic contracts from Layer 4 and focuses strictly on spatial cartography, georeferencing, polygon extraction, tile rendering, and 3D digital twin presentation.
2. **Multi-Resolution by Design**:
   - Decouples high-frequency millimetric ground sensor mesh telemetry (seconds-level updates) from coarse-resolution ($20\text{ m}$), 6–12 day satellite Sentinel-1 InSAR scenes without forcing artificial synchronization.
3. **Progressive Disclosure UI/UX**:
   - Under emergency conditions, the primary viewport presents solely uncluttered situational awareness: the live deformation heatmap and active risk zones.
   - Deeper diagnostic layers (3D subsurface digital twin, cross-sections, InSAR discrepancy callouts, What-If simulation sliders) remain cleanly accessible as opt-in analytical tools.
4. **Unified Spatial Reference & Degraded Operation**:
   - Standardizes all heterogeneous spatial inputs (GPS WGS84 coordinates, mine grid CAD drawings, satellite rasters) into site-specific Universal Transverse Mercator projections (e.g. `EPSG:32645` for Jharia Coalfield).
   - Under communication backhaul dropouts, cached map tiles render gracefully, stamped with prominent amber diagonal warning stripes and countdown badges.

---

## 3. High-Level Architecture & End-to-End Data Flow

```
                           +-------------------------------------------------------+
                           |       LAYER 4: AI/ML INFERENCE & GEOSTATISTICS        |
                           |   Kriging Raster + GNN Anomaly + TTC + Sentinel-1     |
                           +---------------------------+---------------------------+
                                                       |
                                                       | IngestionRasterPayload (Contract 6.1)
                                                       v
+-----------------------------------------------------------------------------------------------------------------------+
|                                  LAYER 5: SPATIAL PROCESSING & RENDERING PIPELINE                                     |
|                                                                                                                       |
|  +─────────────────────────────────────+                         +─────────────────────────────────────+              |
|  |    1. SPATIAL NORMALIZER & CRS      |                         |    2. LIVE HEATMAP TILING ENGINE    |              |
|  | - WGS84 (EPSG:4326) <-> UTM Zone    | ──────────────────────> | - DGMS Color Ramp (#22c55e to #ef44)|              |
|  | - Affine 6-Param Shaft Calibration  |                         | - Kriging Estimation Variance Mask  |              |
|  | - DXF CAD Parser (Pillars/Goaf)     |                         | - Staleness Diagonal Stripes (>30s) |              |
|  +─────────────────────────────────────+                         | - Slippy Tile Slicer (z=12 to 18)   |              |
|                                                                  +──────────────────┬──────────────────+              |
|                                                                                     │ Slippy PNG Tiles                |
|  +─────────────────────────────────────+                                            v                                 |
|  |    3. RISK-ZONE CONTOUR ENGINE      |                         +─────────────────────────────────────+              |
|  | - Isoline Marching Squares          |                         |    4. TWO-TIER CACHING & DELIVERY   |              |
|  | - Area Cutoff (>= 250 m²)           |                         | - In-Memory Hot Tier (< 5ms)        |              |
|  | - Visvalingam-Whyatt Polygon Smooth |                         | - Multi-Tenant Directory Hierarchy  |              |
|  | - Jaccard IoU (>=0.40) ID Tracker   |                         | - PostGIS R-Tree Spatial Indexing   |              |
|  +──────────────────┬──────────────────+                         +──────────────────┬──────────────────+              |
|                     │ GeoJSON Features                                              │ Slippy XYZ Raster Tiles         |
|                     v                                                               v                                 |
|  +─────────────────────────────────────────────────────────────────────────────────────────────────────+              |
|  |                               5. REST API ROUTERS & STREAMING SERVER                                |              |
|  |   /api/v1/tiles/... │ /api/v1/zones/... │ /api/v1/insar/... │ /api/v1/twin/... │ /api/v1/stream/...|              |
|  +──────────────────────────────────────────────────┬──────────────────────────────────────────────────+              |
|                                                     │                                                                 |
|               +-------------------------------------+-------------------------------------+                           |
|               │                                                                           │                           |
|               v                                                                           v                           |
|  +─────────────────────────────────────+                         +─────────────────────────────────────+              |
|  |    6. 3D SUBSURFACE DIGITAL TWIN    |                         |    7. InSAR SATELLITE MACRO-FUSION  |              |
|  | - Volumetric Coal Pillar Prisms     |                         | - 45° Sky-Blue Hatched Overlay      |              |
|  | - Extruded Goaf Voids & Galleries   |                         | - Discrepancy Callout Beacons       |              |
|  | - Dynamic Surface DEM Drape         |                         | - Dual-Pass 2D Vector Decomposition |              |
|  | - Adaptive Exaggeration (10x-50x)   |                         |   (True Vertical & Horizontal E-W)  |              |
|  | - Stratigraphic Cross-Section Plane |                         +─────────────────────────────────────+              |
|  +─────────────────────────────────────+                                                                              |
+-----------------------------------------------------------------------------------------------------------------------+
                                                       │
                                                       v
+-----------------------------------------------------------------------------------------------------------------------+
|                                    LAYER 5 PROGRESSIVE DISCLOSURE WEB DASHBOARD                                       |
|                                                                                                                       |
|  - Dual 2D Cartographic & 3D Orbital Canvas Projections                                                              |
|  - Split-Screen Wipe Comparison Slider (Real-Time vs. Historical Baseline)                                           |
|  - Historical VCR Scrubber & Playback Controls                                                                        |
|  - Empirical NCB & Peck What-If Subsidence Simulation Modeler with DGMS Buffer Bounds                                |
|  - Live Server-Sent Events (SSE) Stream for Instant Tile Invalidation & Zone Alerts                                  |
+-----------------------------------------------------------------------------------------------------------------------+
```

---

## 4. Complete Directory & File Inventory

The `gis_layer` repository contains **38 production, configuration, test, schema, and web application files**:

```
gis_layer/
│
├── config/                                    # Spatial & environment configuration
│   ├── settings.py                            # Layer 5 Pydantic settings (SLAs, thresholds, exaggeration limits)
│   └── sites_crs_registry.json                # Registry of target UTM zones, tie points, affine matrices & bounds
│
├── data/                                      # Spatial tile cache & benchmark fixtures
│   └── tiles/                                 # Multi-tenant Slippy tile directory hierarchy
│       ├── tenant_A/SITE_1/16/100/200.png
│       ├── tenant_benchmark/PANEL7-JHARIA/...
│       └── tenant_corp/PANEL7-JHARIA/16/46962/30468.png
│
├── src/                                       # Core implementation source code
│   ├── api/                                   # FastAPI web serving layer
│   │   ├── main.py                            # FastAPI application, CORS middleware, static dashboard mount
│   │   ├── router_digital_twin.py             # 3D scene manifest, cross-section, DGMS export routes
│   │   ├── router_insar.py                    # InSAR discrepancy beacons & 2D decomposition routes
│   │   ├── router_replay.py                   # Historical replay index & What-If subsidence simulation routes
│   │   ├── router_stream.py                   # Real-time Server-Sent Events (SSE) push feed
│   │   ├── router_tiles.py                    # Slippy tile serving (/tiles/{tenant}/{site}/{z}/{x}/{y}.png)
│   │   └── router_zones.py                    # Live risk-zone GeoJSON endpoint (/zones/{tenant}/{site}/live)
│   │
│   ├── delivery/                              # Spatial caching and persistence
│   │   ├── postgis_repository.py              # PostGIS spatial database repository with in-memory fallback
│   │   └── tile_cache.py                      # Two-tier cache (In-memory hot tier + disk/object storage)
│   │
│   ├── digital_twin/                          # 3D subsurface modeling & cross-sections
│   │   ├── cross_section.py                   # Stratigraphic overburden slicing plane along survey lines
│   │   ├── dem_draper.py                      # Drapes continuous risk heatmap texture onto 3D DEM terrain
│   │   ├── dgms_exporter.py                   # Statutory DGMS archive exporter (GeoJSON, GeoTIFF, DXF)
│   │   ├── subsurface_mesh.py                 # Volumetric prism builder (haulage galleries, pillars, goaf voids)
│   │   └── vertical_exaggeration.py           # Adaptive 10x-50x vertical exaggeration with scale ruler watermark
│   │
│   ├── heatmap/                               # Cartographic heatmap generation
│   │   ├── color_ramp.py                      # DGMS colorblind-safe color ramp (#22c55e, #eab308, #f97316, #ef4444)
│   │   ├── staleness_decorator.py             # Diagonal warning stripes when telemetry currency > 30s
│   │   ├── tile_slicer.py                     # Web Mercator XYZ tile slicer generating 256x256 Slippy tiles
│   │   └── variance_mask.py                   # Kriging estimation variance stippling & opacity attenuation mask
│   │
│   ├── insar/                                 # Satellite radar interferometry fusion
│   │   ├── discrepancy_engine.py              # Detects unmonitored subsidence basins outside ground mesh
│   │   ├── insar_decomposition.py             # Decomposes Asc/Desc LOS into true vertical and E-W horizontal
│   │   └── insar_overlay.py                   # Generates 45° sky-blue hatched vector overlays and beacons
│   │
│   ├── normalizer/                            # Coordinate transformation & CAD ingestion
│   │   ├── affine_georeferencer.py            # 6-parameter affine transformation from shaft tie points
│   │   ├── cad_parser.py                      # DXF parser extracting bord-and-pillar galleries and goaf panels
│   │   └── crs_normalizer.py                  # PyProj WGS84 (EPSG:4326) <-> UTM transformation & XYZ math
│   │
│   ├── risk_zones/                            # Dynamic risk-zone boundary extraction
│   │   ├── contour_extractor.py               # Isoline marching squares at Advisory (0.65), Warning (0.75), Crit (0.85)
│   │   ├── polygon_smoother.py                # Strict >= 250m² area cutoff & Visvalingam-Whyatt simplification
│   │   └── zone_tracker.py                    # Jaccard IoU (>=0.40) tracking ensuring >=98.5% zone ID persistence
│   │
│   ├── schemas/                               # Pydantic v2 data contracts
│   │   ├── digital_twin_contracts.py          # DigitalTwinSceneManifest, MeshElement
│   │   ├── heatmap_contracts.py               # HeatmapMetadataHeader, IngestionRasterPayload
│   │   ├── insar_contracts.py                 # InSARDiscrepancyMarker, InSAROverlayPayload
│   │   ├── risk_zone_contracts.py             # RiskZoneFeature, RiskZoneProperties, RiskZoneFeatureCollection
│   │   └── whatif_contracts.py                # ProposedPanelGeometry, SubsidenceSimulationResult
│   │
│   └── simulation/                            # Empirical geomechanical subsidence modeling
│       ├── ncb_subsidence_model.py            # UK National Coal Board (NCB) and Peck Gaussian profile model
│       ├── replay_manager.py                  # Time-indexed historical VCR playback manager
│       └── whatif_scenario.py                 # Evaluates proposed extraction geometries & risk deltas
│
├── tests/                                     # Automated test suite (31 tests)
│   ├── benchmarks/
│   │   └── test_performance_benchmarks.py    # Verifies tile latency, rendering pipeline, and zone persistence SLAs
│   ├── integration/
│   │   ├── test_api_endpoints.py             # REST API endpoint tests across all routes
│   │   ├── test_enhancements.py              # Tests InSAR 2D decomposition, cross-section, and SSE streams
│   │   └── test_web_dashboard.py             # Validates static dashboard delivery
│   └── unit/
│       ├── test_affine_georeferencer.py       # Affine forward/inverse coordinate math tests
│       ├── test_cad_parser.py                 # DXF bord-and-pillar geometry extraction tests
│       ├── test_color_ramp.py                 # Color ramp boundaries and interpolation tests
│       ├── test_contour_and_zone_tracker.py   # Polygon area cutoff, smoothing, and Jaccard tracking tests
│       ├── test_crs_normalizer.py             # WGS84 <-> UTM projection and Slippy tile math tests
│       └── test_digital_twin_and_insar.py     # 3D DEM draping, vertical exaggeration, and InSAR overlay tests
│
├── web/                                       # Interactive Web Dashboard (Progressive Disclosure)
│   ├── index.html                             # Web dashboard layout with 2D/3D dual viewport
│   ├── src/app.js                             # Canvas rendering engine, orbital camera, VCR scrubber, SSE hook
│   └── styles/dashboard.css                   # Glassmorphic dark industrial theme and control styling
│
├── Dockerfile                                 # Production containerization specification
├── docker-compose.yml                         # Containerized PostGIS, Redis, and MinIO stack
├── pyproject.toml                             # Project build settings and pytest configuration
├── requirements.txt                           # Pinned Python package dependencies
├── README.md                                  # Architectural overview and quickstart guide
└── subsense_tdd_gis_layer.pdf                 # Technical Design Document (SUBSENSE-TDD-GIS-005 Rev 2.1)
```

---

## 5. In-Depth Subsystem Analysis

### 5.1 Live GIS Deformation Heatmap Rendering (`src/heatmap/`)
- **`color_ramp.py` (`ColorRampEngine`)**:
  - Implements the DGMS Colorblind-Safe Color Palette:
    - **`Low`** ($r < 0.65$): `#22c55e` (Emerald Green)
    - **`Advisory`** ($0.65 \le r < 0.75$): `#eab308` (Amber Yellow)
    - **`Warning`** ($0.75 \le r < 0.85$): `#f97316` (Deep Orange)
    - **`Critical`** ($r \ge 0.85$): `#ef4444` (Vibrant Red)
  - Uses piecewise linear RGB interpolation to produce smooth 4-channel RGBA raster buffers (`H, W, 4`) with pre-multiplied alpha.
- **`variance_mask.py` (`VarianceConfidenceMaskEngine`)**:
  - Ingests the Kriging estimation variance ($\sigma_K^2$) array.
  - Modulates heatmap opacity (reducing alpha up to $50\%$) in regions with sparse ground sensor coverage.
  - Injects a discrete $4\times 4$ stippled pattern in high-uncertainty zones ($\sigma_K^2 > 0.25$) to visually communicate statistical uncertainty to geotechnical planners.
- **`staleness_decorator.py` (`StalenessDecorator`)**:
  - When elapsed telemetry currency exceeds the **$30.0\text{ s}$ SLA threshold**, diagonal warning stripes (`rgba(245, 158, 11, 0.45)`) are rendered across the tile at $45^\circ$ angles, preventing operators from acting on expired strata data.
- **`tile_slicer.py` (`TileSlicerEngine`)**:
  - Evaluates Web Mercator XYZ tile boundaries for zoom levels $z=12\text{ to }18$.
  - Resamples continuous Kriging rasters using bilinear interpolation to output standard $256 \times 256$ PNG image tiles in $< 2\text{ ms}$.

---

### 5.2 Dynamic Risk-Zone Boundary Extraction & Tracking (`src/risk_zones/`)
- **`contour_extractor.py` (`ContourExtractor`)**:
  - Implements isoline marching squares on 2D risk arrays at statutory DGMS thresholds:
    - Advisory: $\ge 0.65$
    - Warning: $\ge 0.75$
    - Critical: $\ge 0.85$
- **`polygon_smoother.py` (`PolygonSmoother`)**:
  - **Area Filtering**: Enforces a strict $\ge 250.0\text{ m}^2$ minimum area cutoff to eliminate single-pixel noise.
  - **Morphological Closing**: Bridges tiny internal voids using buffer dilation and erosion.
  - **Visvalingam-Whyatt Simplification**: Decimates superfluous vertices while strictly preventing self-intersecting loops (`is_valid == True`).
- **`zone_tracker.py` (`ZoneTracker`)**:
  - Tracks evolving polygons across successive 30-second cycles using maximum **Jaccard spatial Intersection over Union (IoU)**:
    $$\text{IoU} = \frac{\text{Area}(A \cap B)}{\text{Area}(A \cup B)} \ge 0.40$$
  - Preserves persistent zone identifiers (e.g. `ZONE-PANEL7-C`) across cycle updates, achieving **$100.0\%$ ID persistence stability** (exceeding the $\ge 98.5\%$ SLA mandate).
  - Associates affected sensor node IDs, time-to-critical hours $[t_{min}, t_{max}]$, and plain-language SHAP summaries.

---

### 5.3 3D Subsurface Digital Twin (`src/digital_twin/`)
- **`subsurface_mesh.py` (`SubsurfaceMeshBuilder`)**:
  - Constructs 3D translucent volumetric meshes for underground workings:
    - Intact Coal Pillars (extruded 3D prisms, height: seam thickness)
    - Extracted Goaf Voids (translucent red bounding volumes)
    - Haulage Galleries & Inclines (3D tubular galleries)
    - Overburden Strata Horizons (Alluvium, Sandstone, Shale)
  - **Graceful Degradation**: If underground CAD drawings are unavailable, it automatically falls back to surface-only 2.5D DEM terrain draping without crashing.
- **`dem_draper.py` (`DEMTerrainDraper`)**:
  - Samples high-resolution surface Digital Elevation Models (DEM, 1m–5m resolution).
  - Generates triangular surface meshes and dynamically drapes the live 2D deformation heatmap as an active texture.
- **`vertical_exaggeration.py` (`VerticalExaggerationEngine`)**:
  - Real-world surface subsidence is measured in millimeters, whereas mine concessions span kilometers.
  - Applies user-configurable **$10\times$ to $50\times$ (default $25\times$) vertical exaggeration** to vertical displacement vectors ($Z_{disp}$):
    $$z_{render} = z_{DEM} - \left(\frac{\Delta z_{mm}}{1000.0}\right) \times \text{Exaggeration}$$
  - **DGMS Compliance Watermark**: Automatically overlays a mandatory visual scale ruler and watermark (`"VERTICAL EXAGGERATION: 25X (DGMS AUDIT PROJECTION)"`) to prevent misinterpretation during regulatory audits.
- **`cross_section.py` (`StratigraphicCrossSectionEngine`)**:
  - Slices a vertical 2D plane through the 3D digital twin along any user-defined survey line.
  - Samples 100 points displaying surface DEM flexure, alluvium base, sandstone main roof, seam roof, and seam floor.

---

### 5.4 Sentinel-1 InSAR Satellite Macro-Fusion (`src/insar/`)
- **`insar_overlay.py` (`InSAROverlayGenerator`)**:
  - Renders satellite geodetic layers using a distinct **$45^\circ$ sky-blue (`#38bdf8`) hatched polygon overlay** to ensure control room operators never confuse satellite observations with real-time ground sensor heatmaps.
- **`discrepancy_engine.py` (`InSARDiscrepancyEngine`)**:
  - Compares ground mesh sensor bounds with satellite Line-of-Sight deformation grids.
  - Detects **unmonitored subsidence basins** outside the active sensor network perimeter.
  - Generates actionable visual callout beacons:
    > *"Sentinel-1 detects subsidence basin (-24.5 mm/yr) outside active ground mesh perimeter. Recommended action: Deploy supplementary wireless ground mesh nodes or borehole extensometers."*
- **`insar_decomposition.py` (`InSARDecompositionEngine`)**:
  - Decomposes dual-pass ascending and descending Sentinel-1 LOS velocities into **true vertical subsidence ($d_{vert}$)** and **east-west horizontal shear ($d_{EW}$)**:
    $$\begin{bmatrix} S_{asc, ew} & C_{asc, vert} \\ S_{desc, ew} & C_{desc, vert} \end{bmatrix} \begin{bmatrix} d_{EW} \\ d_{vert} \end{bmatrix} = \begin{bmatrix} v_{LOS, asc} \\ v_{LOS, desc} \end{bmatrix}$$
  - Applies an interferometric coherence mask ($\gamma \ge 0.35$) to reject decorrelated vegetation and atmospheric noise.

---

### 5.5 Map Tiling, Multi-Tenancy & Delivery (`src/delivery/`)
- **`tile_cache.py` (`TileCacheEngine`)**:
  - Implements a high-performance **two-tier cache**:
    1. In-memory hot tier: Serves frequent tiles in **$1.70\text{ ms}$** ($< 5\text{ ms}$ SLA).
    2. Persistent local disk / MinIO S3 object store.
  - Organizes tiles under a strict multi-tenant directory structure:
    `/tiles/{tenant_id}/{site_id}/{z}/{x}/{y}.png`
- **`postgis_repository.py` (`PostGISRepository`)**:
  - Persists and queries risk polygons, CAD mine workings, and sensor node coordinates.
  - Implements R-tree spatial indexing (`ST_Intersects`, `ST_Contains`) with an in-memory spatial fallback.

---

### 5.6 What-If Subsidence Scenario Simulation (`src/simulation/`)
- **`ncb_subsidence_model.py` (`NCBSubsidenceModel`)**:
  - Implements the empirical UK National Coal Board (NCB) Subsidence Engineers' Handbook and Peck Gaussian profile models:
    - Calculates maximum subsidence $S_{max} = m \cdot a \cdot s_c$, tilt $T_{max}$, horizontal tensile/compressive strain $\varepsilon_{max}$, and angle of draw $\beta \approx 32.5^\circ$.
    - Distinguishes supercritical extraction ($W/h \ge 1.4$) from subcritical panels.
    - Accounts for goaf treatment (caving factor $0.82$ vs. hydraulic sand stowing factor $0.15$).
- **`whatif_scenario.py` (`WhatIfScenarioEngine`)**:
  - Accepts proposed panel coordinates (`ProposedPanelGeometry`).
  - Generates predictive subsidence contour isolines and computes **risk deltas** against the active operational baseline.
  - Overlays a mandatory non-live watermark banner: `"NON-LIVE PREDICTIVE SIMULATION — STATUTORY WHAT-IF AUDIT"`.
- **`replay_manager.py` (`HistoricalReplayManager`)**:
  - Supports VCR-style historical scrubbing, allowing engineers to review the time-stepped spatial progression of historical subsidence events.

---

### 5.7 Progressive Disclosure Web Dashboard (`web/`)
Built with vanilla JavaScript and high-performance HTML5 Canvas:
- **Dual Viewport Engine**: Seamlessly toggles between top-down 2D cartographic view and 3D orbital perspective projection.
- **Split-Screen Wipe Comparison Slider**: Interactive draggable divider comparing real-time risk heatmaps against pre-mining baseline topography.
- **Real-Time SSE Integration**: Connects to `/api/v1/stream/{tenant}/{site}/events` to receive instantaneous tile cache invalidations and emergency alert toasts without polling.
- **Responsive Diagnostics Panel**: Opt-in collapsible tabs displaying stratigraphic cross-sections, InSAR discrepancy cards, What-If simulation parameters, and SHAP sensor attribution summaries.

---

## 6. Formal Inter-Layer Data Contracts

### 6.1 Heatmap Tile Metadata Contract (Section 6.1)
Slippy tiles served at `/api/v1/tiles/{tenant}/{site}/{z}/{x}/{y}.png` return custom HTTP response headers:
```http
HTTP/1.1 200 OK
Content-Type: image/png
ETag: "w/9b7a421b"
Cache-Control: public, max-age=30
X-Site-ID: PANEL7-JHARIA
X-Layer: risk_deformation_heatmap
X-Tile-Z: 16
X-Tile-X: 46962
X-Tile-Y: 30468
X-Data-Currency-Seconds: 14.2
X-Is-Stale: false
X-Kriging-Variance-Included: true
```

### 6.2 Risk-Zone GeoJSON Contract (Section 6.2)
Published at `/api/v1/zones/{tenant}/{site}/live`:
```json
{
  "type": "FeatureCollection",
  "as_of": "2026-09-10T06:00:00Z",
  "site_id": "PANEL7-JHARIA",
  "features": [
    {
      "type": "Feature",
      "id": "ZONE-PANEL7-C",
      "geometry": {
        "type": "Polygon",
        "coordinates": [[[86.432, 23.791], [86.435, 23.791], [86.435, 23.793], [86.432, 23.793], [86.432, 23.791]]]
      },
      "properties": {
        "site_id": "PANEL7-JHARIA",
        "zone_name": "Goaf Abutment Zone C",
        "severity_tier": "critical",
        "time_to_critical_hours": [8.5, 12.0],
        "model_confidence": 0.89,
        "affected_node_ids": ["N-014", "N-015", "N-021"],
        "primary_contributing_sensors": ["tiltmeter", "borehole_extensometer"],
        "explanation_summary": "Correlated tilt (+3.8 deg) and extensometer strain rate exceedance.",
        "area_sq_meters": 18450.0,
        "centroid_gps": {"lat": 23.7920, "lon": 86.4335},
        "last_updated": "2026-09-10T06:00:00Z"
      }
    }
  ]
}
```

### 6.3 InSAR Discrepancy Annotation Marker Contract (Section 6.3)
Published at `/api/v1/insar/{tenant}/{site}/discrepancies`:
```json
{
  "annotation_id": "INSAR-DISC-001",
  "site_id": "PANEL7-JHARIA",
  "location": {"lat": 23.7945, "lon": 86.4380},
  "insar_acquisition_date": "2026-09-08",
  "discrepancy_type": "satellite_motion_unmonitored_by_ground_mesh",
  "los_velocity_mm_year": -24.5,
  "description": "Sentinel-1 detects subsidence basin outside active ground mesh perimeter.",
  "recommended_action": "Deploy supplementary wireless ground mesh nodes or borehole extensometers."
}
```

---

## 7. REST API Endpoints & Interfaces

| Method | Route | Description | Response Schema |
| :--- | :--- | :--- | :--- |
| `GET` | `/health` | Healthcheck and service readiness | JSON status report |
| `GET` | `/api/v1/tiles/{tenant}/{site}/{z}/{x}/{y}.png` | Slippy 256x256 RGBA heatmap PNG tile | PNG binary with Section 6.1 headers |
| `GET` | `/api/v1/zones/{tenant}/{site}/live` | Live smoothed, tracked risk-zone polygons | `RiskZoneFeatureCollection` GeoJSON |
| `GET` | `/api/v1/insar/{tenant}/{site}/discrepancies` | InSAR geodetic discrepancy beacons | List of `InSARDiscrepancyMarker` |
| `GET` | `/api/v1/insar/{tenant}/{site}/decomposition` | Dual-pass ascending/descending InSAR 2D vector | True vertical & horizontal velocities |
| `GET` | `/api/v1/twin/{tenant}/{site}/scene` | 3D Digital Twin scene manifest | `DigitalTwinSceneManifest` JSON |
| `GET` | `/api/v1/twin/{tenant}/{site}/cross-section` | Stratigraphic overburden vertical slicing plane | Profile points and lithological units |
| `GET` | `/api/v1/twin/{tenant}/{site}/export-dgms` | Statutory DGMS audit archive export | Archive metadata and download links |
| `GET` | `/api/v1/replay/{tenant}/{site}/index` | Historical replay timestamp index | VCR scrubbing index |
| `POST`| `/api/v1/simulation/what-if` | Empirical NCB What-If subsidence simulation | `SubsidenceSimulationResult` JSON |
| `GET` | `/api/v1/stream/{tenant}/{site}/events` | Real-time Server-Sent Events (SSE) stream | `text/event-stream` feed |
| `GET` | `/dashboard/` | Interactive Progressive Disclosure UI | Web dashboard HTML application |

---

## 8. Automated Test Suite & Benchmark Results

### 8.1 Pytest Execution Summary
The test suite spans **31 automated tests across 10 test modules** verifying benchmarks, integration endpoints, and unit geometry math:

```bash
pytest tests/ -v
```

```
============================== test session starts ==============================
collected 31 items

tests/benchmarks/test_performance_benchmarks.py::test_sla_2d_tile_fetch_latency PASSED [  3%]
tests/benchmarks/test_performance_benchmarks.py::test_sla_end_to_end_tile_rendering_pipeline PASSED [  6%]
tests/benchmarks/test_performance_benchmarks.py::test_sla_zone_id_persistence_stability PASSED [  9%]
tests/benchmarks/test_performance_benchmarks.py::test_sla_multi_tenant_partition_verification PASSED [ 12%]
tests/integration/test_api_endpoints.py::test_healthcheck PASSED                         [ 16%]
tests/integration/test_api_endpoints.py::test_tile_endpoint_and_headers PASSED          [ 19%]
tests/integration/test_api_endpoints.py::test_tile_staleness_header_and_watermark PASSED [ 22%]
tests/integration/test_api_endpoints.py::test_live_risk_zones_geojson PASSED            [ 25%]
tests/integration/test_api_endpoints.py::test_insar_discrepancies_schema PASSED         [ 29%]
tests/integration/test_api_endpoints.py::test_digital_twin_scene_and_scale_ruler PASSED [ 32%]
tests/integration/test_api_endpoints.py::test_whatif_subsidence_simulation PASSED       [ 35%]
tests/integration/test_api_endpoints.py::test_multi_tenant_isolation PASSED             [ 38%]
tests/integration/test_enhancements.py::test_insar_dual_pass_decomposition PASSED       [ 41%]
tests/integration/test_enhancements.py::test_insar_decomposition_api PASSED             [ 45%]
tests/integration/test_enhancements.py::test_stratigraphic_cross_section_api PASSED     [ 48%]
tests/integration/test_enhancements.py::test_sse_event_stream_endpoint PASSED           [ 51%]
tests/integration/test_web_dashboard.py::test_web_dashboard_html_served PASSED          [ 54%]
tests/integration/test_web_dashboard.py::test_web_dashboard_css_served PASSED           [ 58%]
tests/integration/test_web_dashboard.py::test_web_dashboard_js_served PASSED            [ 61%]
tests/unit/test_affine_georeferencer.py::test_affine_forward_and_inverse PASSED          [ 64%]
tests/unit/test_affine_georeferencer.py::test_affine_calibration PASSED                 [ 67%]
tests/unit/test_cad_parser.py::test_synthetic_bord_and_pillar_generation PASSED         [ 70%]
tests/unit/test_color_ramp.py::test_color_ramp_boundaries PASSED                         [ 74%]
tests/unit/test_contour_and_zone_tracker.py::test_contour_extraction_and_area_filter PASSED [ 77%]
tests/unit/test_contour_and_zone_tracker.py::test_zone_persistence_stability PASSED     [ 80%]
tests/unit/test_crs_normalizer.py::test_wgs84_utm_roundtrip PASSED                       [ 83%]
tests/unit/test_crs_normalizer.py::test_slippy_tile_math PASSED                          [ 87%]
tests/unit/test_crs_normalizer.py::test_geojson_transform PASSED                         [ 90%]
tests/unit/test_digital_twin_and_insar.py::test_dem_draper_mesh PASSED                  [ 93%]
tests/unit/test_digital_twin_and_insar.py::test_vertical_exaggeration_engine PASSED      [ 96%]
tests/unit/test_digital_twin_and_insar.py::test_insar_discrepancy_and_overlay PASSED     [100%]

======================== 31 passed, 1 warning in 6.08s ========================
```

### 8.2 Section 8 SLA Performance Targets Table

| Evaluation Dimension | Regulatory SLA Mandate | Measured Result | Benchmark Status |
| :--- | :--- | :--- | :--- |
| **2D Slippy Tile Fetch Latency** | $\le 250\text{ ms}$ (95th percentile) | **$1.70\text{ ms}$ median / $2.59\text{ ms}$ P95** | **PASSED ($96\times$ Headroom)** |
| **Rendering Pipeline Duration** | $\le 30.0\text{ s}$ per cycle | **$0.0001\text{ s}$** | **PASSED** |
| **Zone ID Persistence Stability** | $\ge 98.5\%$ ID consistency | **$100.0\%$ IoU persistence** | **PASSED** |
| **Multi-Tenant Data Isolation** | $100\%$ tenant partitioning | **$100.0\%$ zero cross-tenant leakage** | **PASSED** |
| **Staleness Watermarking** | Display stripes when $> 30\text{s}$ | **Rendered diagonal amber stripes** | **PASSED** |
| **Vertical Exaggeration Rule** | Display scale ruler & watermark | **Scale watermark rendered** | **PASSED** |

---

## 9. Operational Runbook & Execution Commands

### 9.1 Local Environment Setup
```bash
# 1. Navigate to the gis_layer folder
cd "c:\Users\sasik\Desktop\SIH 2026\Subsense\gis_layer"

# 2. Install dependencies
pip install -r requirements.txt
```

### 9.2 Launching the FastAPI Service & Dashboard
```bash
# Start Uvicorn development server
python -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload
```
- Open your browser to the interactive dashboard: **`http://localhost:8000/dashboard/`**
- Interactive Swagger API Documentation: **`http://localhost:8000/docs`**

### 9.3 Running the Automated Test Suite
```bash
# Run all 31 unit, integration, and SLA benchmark tests
python -m pytest tests/ -v -s
```

### 9.4 Containerized Deployment (PostGIS + Redis + MinIO)
```bash
# Launch containerized PostGIS and cache infrastructure
docker-compose up -d
```
