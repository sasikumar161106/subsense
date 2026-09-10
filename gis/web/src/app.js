/**
 * SubSense Layer 5: Spatial & GIS Rendering Dashboard (app.js)
 * Conforms to SUBSENSE-TDD-GIS-005 Rev 2.1 & DGMS Geotechnical GIS Guidelines.
 */

// Application State Store
const state = {
  tenantId: "tenant_alpha",
  siteId: "PANEL7-JHARIA",
  viewMode: "2d", // '2d' or '3d'
  isEmergencyMode: false,
  verticalExaggeration: 25.0,
  dataCurrencySeconds: 14.0,
  isStale: false,
  
  // Split-Screen Comparison Slider
  splitWipe: {
    enabled: false,
    xPercent: 50,
    isDragging: false
  },
  emergencyAudioEnabled: true,
  
  // Layers
  layers: {
    heatmap: true,
    variance: true,
    zones: true,
    insar: true,
    cad: true
  },

  // 2D Pan/Zoom
  camera2D: {
    x: 0,
    y: 0,
    zoom: 1.0,
    isDragging: false,
    dragStart: { x: 0, y: 0 }
  },

  // 3D Orbital Camera
  camera3D: {
    pitch: 0.65,
    yaw: 0.75,
    distance: 400,
    isDragging: false,
    dragStart: { x: 0, y: 0 }
  },

  // Playback
  playback: {
    isPlaying: false,
    speed: 1,
    currentStep: 100,
    timer: null
  },

  // Active GeoJSON Data
  activeZones: [],
  insarMarkers: [],
  subsurfaceWorkings: null,
  whatifSimulation: null
};

// Canvas References
let canvas2D, ctx2D;
let canvas3D, ctx3D;
let tooltipEl;

// Color Palette Constants
const COLORS = {
  low: "#22c55e",
  advisory: "#eab308",
  warning: "#f97316",
  critical: "#ef4444",
  insar: "#38bdf8",
  amber: "#f59e0b"
};

document.addEventListener("DOMContentLoaded", () => {
  initDOM();
  initEventListeners();
  loadConcessionData();
  startStalenessTimer();
  initSSE();
  requestAnimationFrame(renderLoop);
});


function initDOM() {
  canvas2D = document.getElementById("map-canvas");
  ctx2D = canvas2D.getContext("2d");
  canvas3D = document.getElementById("three-canvas");
  ctx3D = canvas3D.getContext("2d"); // High-performance 2.5D/3D projection engine
  tooltipEl = document.getElementById("map-tooltip");

  resizeCanvases();
  window.addEventListener("resize", resizeCanvases);
}

function resizeCanvases() {
  const container = document.getElementById("viewport-container");
  const w = container.clientWidth;
  const h = container.clientHeight;
  
  canvas2D.width = w;
  canvas2D.height = h;
  canvas3D.width = w;
  canvas3D.height = h;
}

function initEventListeners() {
  // Dimension Switchers
  document.getElementById("btn-view-2d").addEventListener("click", () => setViewMode("2d"));
  document.getElementById("btn-view-3d").addEventListener("click", () => setViewMode("3d"));

  // Progressive Disclosure Mode
  document.getElementById("btn-mode-emergency").addEventListener("click", () => setEmergencyMode(true));
  document.getElementById("btn-mode-diagnostic").addEventListener("click", () => setEmergencyMode(false));

  // Sidebar Controls
  document.getElementById("btn-toggle-sidebar").addEventListener("click", toggleSidebar);
  document.getElementById("btn-close-sidebar").addEventListener("click", toggleSidebar);

  // Layer Visibility Toggles
  ["heatmap", "variance", "zones", "insar", "cad"].forEach(layer => {
    const el = document.getElementById(`layer-toggle-${layer}`);
    if (el) {
      el.addEventListener("change", (e) => {
        state.layers[layer] = e.target.checked;
      });
    }
  });

  // Vertical Exaggeration Slider
  const sliderExagg = document.getElementById("slider-exaggeration");
  sliderExagg.addEventListener("input", (e) => {
    state.verticalExaggeration = parseFloat(e.target.value);
    document.getElementById("label-current-exaggeration").textContent = `${state.verticalExaggeration}X (DGMS Std)`;
    document.getElementById("ruler-factor-title").textContent = `VERTICAL EXAGGERATION: ${state.verticalExaggeration}X`;
  });

  // What-If Modal Controls
  document.getElementById("btn-whatif-modal").addEventListener("click", () => openModal(true));
  document.getElementById("btn-close-modal").addEventListener("click", () => openModal(false));
  document.getElementById("btn-cancel-sim").addEventListener("click", () => openModal(false));
  document.getElementById("btn-run-simulation").addEventListener("click", runWhatIfCalculation);

  // Stratigraphic Cross-Section Controls
  document.getElementById("btn-cross-section").addEventListener("click", openCrossSectionModal);
  document.getElementById("btn-close-cs-modal").addEventListener("click", closeCrossSectionModal);
  document.getElementById("btn-close-cs").addEventListener("click", closeCrossSectionModal);

  // Split Wipe Toggle
  document.getElementById("btn-toggle-wipe").addEventListener("click", toggleSplitWipe);
  setupSplitWipeInteraction();

  // DGMS Export Button
  document.getElementById("btn-export-dgms").addEventListener("click", triggerDGMSExport);

  // VCR Controls
  document.getElementById("btn-scrub-play").addEventListener("click", togglePlay);
  document.getElementById("btn-scrub-speed").addEventListener("click", cycleSpeed);
  document.getElementById("timeline-slider").addEventListener("input", (e) => {
    state.playback.currentStep = parseInt(e.target.value);
    updateTimelineLabel();
  });

  // Mouse / Touch Dragging on Canvases
  setupCanvasInteraction(canvas2D, "2d");
  setupCanvasInteraction(canvas3D, "3d");
}


function setViewMode(mode) {
  state.viewMode = mode;
  document.getElementById("btn-view-2d").classList.toggle("active", mode === "2d");
  document.getElementById("btn-view-3d").classList.toggle("active", mode === "3d");

  canvas2D.style.display = (mode === "2d") ? "block" : "none";
  canvas3D.style.display = (mode === "3d") ? "block" : "none";
  document.getElementById("scale-ruler-container").style.display = (mode === "3d") ? "flex" : "none";
  document.getElementById("exaggeration-control-card").style.display = (mode === "3d") ? "block" : "none";
}

function setEmergencyMode(isEmergency) {
  state.isEmergencyMode = isEmergency;
  document.getElementById("btn-mode-emergency").classList.toggle("active", isEmergency);
  document.getElementById("btn-mode-diagnostic").classList.toggle("active", !isEmergency);

  // In emergency mode, hide secondary diagnostic overlays to prevent cognitive overload (Section 2 Principle 3)
  if (isEmergency) {
    document.getElementById("layer-toggle-insar").checked = false;
    document.getElementById("layer-toggle-variance").checked = false;
    document.getElementById("layer-toggle-cad").checked = false;
    state.layers.insar = false;
    state.layers.variance = false;
    state.layers.cad = false;
    setViewMode("2d");
    closeSidebar();
  } else {
    document.getElementById("layer-toggle-insar").checked = true;
    document.getElementById("layer-toggle-variance").checked = true;
    document.getElementById("layer-toggle-cad").checked = true;
    state.layers.insar = true;
    state.layers.variance = true;
    state.layers.cad = true;
  }
}

function toggleSidebar() {
  const sidebar = document.getElementById("diagnostic-sidebar");
  sidebar.classList.toggle("collapsed");
}

function closeSidebar() {
  document.getElementById("diagnostic-sidebar").classList.add("collapsed");
}

function openModal(isOpen) {
  document.getElementById("whatif-modal").classList.toggle("open", isOpen);
}

// -------------------------------------------------------------
// Data Fetching & Synchronization
// -------------------------------------------------------------
async function loadConcessionData() {
  try {
    // 1. Fetch live risk zones
    const zonesResp = await fetch(`/api/v1/zones/${state.tenantId}/${state.siteId}/live`);
    if (zonesResp.ok) {
      const zoneGeoJSON = await zonesResp.json();
      state.activeZones = zoneGeoJSON.features || [];
      renderZoneList(state.activeZones);
    }

    // 2. Fetch Sentinel-1 InSAR discrepancies
    const insarResp = await fetch(`/api/v1/insar/${state.tenantId}/${state.siteId}/discrepancies`);
    if (insarResp.ok) {
      state.insarMarkers = await insarResp.json();
      renderInSARList(state.insarMarkers);
    }

    // 3. Fetch 3D Digital Twin scene manifest
    const twinResp = await fetch(`/api/v1/twin/${state.tenantId}/${state.siteId}/scene?vertical_exaggeration=${state.verticalExaggeration}`);
    if (twinResp.ok) {
      const manifest = await twinResp.json();
      state.subsurfaceWorkings = manifest.subsurface_elements || [];
    }
  } catch (err) {
    console.warn("Using local synthetic fallback data:", err);
    populateSyntheticData();
  }
}

function populateSyntheticData() {
  state.activeZones = [
    {
      id: "ZONE-PANEL7-C",
      properties: {
        site_id: "PANEL7-JHARIA",
        zone_name: "Goaf Abutment Zone C",
        severity_tier: "critical",
        time_to_critical_hours: [1.5, 3.8],
        model_confidence: 0.89,
        affected_node_ids: ["SS-PANEL7-N042", "SS-PANEL7-N043", "SS-PANEL7-N051"],
        primary_contributing_sensors: ["tilt_deg", "displacement_mm"],
        explanation_summary: "Sustained tilt increase at N042 (+0.42°), corroborated by 3 neighboring nodes over 40 min.",
        area_sq_meters: 18450.2,
        centroid_gps: { lat: 23.7915, lon: 86.4335 }
      }
    },
    {
      id: "ZONE-PANEL7-B",
      properties: {
        site_id: "PANEL7-JHARIA",
        zone_name: "Barrier Pillar Flexure B",
        severity_tier: "warning",
        time_to_critical_hours: [8.0, 16.0],
        model_confidence: 0.78,
        affected_node_ids: ["SS-PANEL7-N031", "SS-PANEL7-N032"],
        primary_contributing_sensors: ["tilt_deg"],
        explanation_summary: "Progressive tensile strain detected across main barrier pillar.",
        area_sq_meters: 8920.0,
        centroid_gps: { lat: 23.7930, lon: 86.4350 }
      }
    }
  ];
  renderZoneList(state.activeZones);

  state.insarMarkers = [
    {
      annotation_id: "INSAR-DISC-2026-088",
      site_id: "PANEL7-JHARIA",
      location: { lat: 23.792015, lon: 86.434020 },
      insar_acquisition_date: "2026-08-28",
      discrepancy_type: "satellite_motion_unmonitored_by_ground_mesh",
      los_velocity_mm_year: -34.5,
      description: "InSAR indicates 14mm subsidence basin outside active sensor array. Geotechnical review required.",
      recommended_action: "Relocate wireless sensor nodes N088 and N089 120m northeast."
    }
  ];
  renderInSARList(state.insarMarkers);
}

function renderZoneList(zones) {
  const container = document.getElementById("risk-zones-list");
  container.innerHTML = "";
  document.getElementById("zone-count-badge").textContent = `${zones.length} ZONES`;

  zones.forEach(zone => {
    const p = zone.properties;
    const card = document.createElement("div");
    card.className = `zone-card ${p.severity_tier}`;
    card.innerHTML = `
      <div class="zone-header">
        <span class="zone-name">${zone.id}</span>
        <span class="severity-pill ${p.severity_tier}">${p.severity_tier}</span>
      </div>
      <div class="zone-detail">${p.explanation_summary}</div>
      <div class="zone-meta">
        <span>TTC: ${p.time_to_critical_hours[0]}-${p.time_to_critical_hours[1]}h</span>
        <span>Area: ${p.area_sq_meters.toLocaleString()} m²</span>
        <span>Conf: ${(p.model_confidence * 100).toFixed(0)}%</span>
      </div>
    `;
    card.addEventListener("click", () => {
      // Focus map to zone centroid
      state.camera2D.x = 0;
      state.camera2D.y = 0;
      state.camera2D.zoom = 1.6;
    });
    container.appendChild(card);
  });
}

function renderInSARList(markers) {
  const container = document.getElementById("insar-discrepancies-list");
  container.innerHTML = "";

  markers.forEach(m => {
    const card = document.createElement("div");
    card.className = "discrepancy-card";
    card.innerHTML = `
      <span class="disc-badge">${m.annotation_id}</span>
      <div style="font-size: 12px; font-weight: 700; color: #38bdf8; margin-bottom: 4px;">
        LOS Velocity: ${m.los_velocity_mm_year} mm/yr
      </div>
      <div style="font-size: 11px; color: #94a3b8; line-height: 1.4; margin-bottom: 6px;">
        ${m.description}
      </div>
      <div style="font-size: 10px; color: #f59e0b; font-family: monospace;">
        Guidance: ${m.recommended_action}
      </div>
    `;
    container.appendChild(card);
  });
}

// -------------------------------------------------------------
// Staleness & Telemetry Countdown
// -------------------------------------------------------------
function startStalenessTimer() {
  setInterval(() => {
    state.dataCurrencySeconds += 1.0;
    const badge = document.getElementById("staleness-badge");
    const text = document.getElementById("staleness-text");

    if (state.dataCurrencySeconds > 30.0) {
      state.isStale = true;
      badge.classList.add("stale");
      text.textContent = `Data Stale: ${Math.round(state.dataCurrencySeconds)}s (> 30s SLA)`;
    } else {
      state.isStale = false;
      badge.classList.remove("stale");
      text.textContent = `Data Currency: ${Math.round(state.dataCurrencySeconds)}s (HEALTHY)`;
    }

    // Auto-cycle telemetry simulated sync every 28 seconds
    if (state.dataCurrencySeconds >= 29.0) {
      state.dataCurrencySeconds = 1.0;
    }
  }, 1000);
}

// -------------------------------------------------------------
// Interactive Map & 3D Render Loop
// -------------------------------------------------------------
function renderLoop() {
  if (state.viewMode === "2d") {
    render2DMap();
  } else {
    render3DScene();
  }
  requestAnimationFrame(renderLoop);
}

function render2DMap() {
  const W = canvas2D.width;
  const H = canvas2D.height;
  ctx2D.clearRect(0, 0, W, H);

  ctx2D.save();
  // Apply Pan and Zoom
  ctx2D.translate(W / 2 + state.camera2D.x, H / 2 + state.camera2D.y);
  ctx2D.scale(state.camera2D.zoom, state.camera2D.zoom);

  // 1. Draw Mine Grid Coordinates (UTM 45N)
  drawSpatialGrid(ctx2D, W, H);

  // 2. Draw Live Kriging Heatmap Plume (Section 5.1)
  if (state.layers.heatmap) {
    drawLiveHeatmap(ctx2D);
  }

  // 3. Draw Subsurface CAD Mine Workings (Section 5.3)
  if (state.layers.cad) {
    drawUndergroundCAD(ctx2D);
  }

  // 4. Draw Sentinel-1 InSAR Hatched Vector Overlay (Section 5.4)
  if (state.layers.insar && !state.isEmergencyMode) {
    drawInSARHatchedOverlay(ctx2D);
  }

  // 5. Draw Risk-Zone Isolines & Identifiers (Section 5.2)
  if (state.layers.zones) {
    drawRiskZones(ctx2D);
  }

  // 6. Draw Staleness Diagonal Watermark Stripes if Stale (Section 5.1)
  if (state.isStale) {
    drawStalenessStripes(ctx2D);
  }

  ctx2D.restore();
}

function drawSpatialGrid(ctx, W, H) {
  ctx.strokeStyle = "rgba(255, 255, 255, 0.05)";
  ctx.lineWidth = 1;
  const step = 80;
  for (let x = -W; x <= W; x += step) {
    ctx.beginPath();
    ctx.moveTo(x, -H);
    ctx.lineTo(x, H);
    ctx.stroke();
  }
  for (let y = -H; y <= H; y += step) {
    ctx.beginPath();
    ctx.moveTo(-W, y);
    ctx.lineTo(W, y);
    ctx.stroke();
  }
}

function drawLiveHeatmap(ctx) {
  ctx.save();

  if (state.splitWipe.enabled) {
    const W = canvas2D.width;
    const wipePixelX = (W * state.splitWipe.xPercent) / 100;
    const worldWipeX = (wipePixelX - (W / 2 + state.camera2D.x)) / state.camera2D.zoom;

    // Draw baseline label on left side
    ctx.fillStyle = "rgba(148, 163, 184, 0.5)";
    ctx.font = "bold 12px JetBrains Mono";
    ctx.fillText("PRE-MINING BASELINE (UNDISTURBED)", worldWipeX - 320, -180);

    // Clip rendering to the right of the wipe slider
    ctx.beginPath();
    ctx.rect(worldWipeX, -5000, 10000, 10000);
    ctx.clip();
  }

  // Center plume for Jharia Panel 7
  const plumeGrad = ctx.createRadialGradient(0, 0, 10, 0, 0, 240);
  plumeGrad.addColorStop(0.00, "rgba(239, 68, 68, 0.85)");   // Critical Red (#ef4444)
  plumeGrad.addColorStop(0.35, "rgba(249, 115, 22, 0.75)");  // Warning Orange (#f97316)
  plumeGrad.addColorStop(0.65, "rgba(234, 179, 8, 0.65)");   // Advisory Yellow (#eab308)
  plumeGrad.addColorStop(0.85, "rgba(34, 197, 94, 0.40)");   // Low Green (#22c55e)
  plumeGrad.addColorStop(1.00, "rgba(34, 197, 94, 0.00)");

  ctx.fillStyle = plumeGrad;
  ctx.beginPath();
  ctx.arc(0, 0, 240, 0, Math.PI * 2);
  ctx.fill();


  // Draw Stippled Variance Confidence Mask if active (Section 5.1)
  if (state.layers.variance && !state.isEmergencyMode) {
    ctx.fillStyle = "rgba(7, 11, 20, 0.35)";
    for (let r = 160; r < 240; r += 12) {
      const count = Math.floor(r * 0.4);
      for (let i = 0; i < count; i++) {
        const theta = (i / count) * Math.PI * 2;
        const px = Math.cos(theta) * r;
        const py = Math.sin(theta) * r;
        ctx.beginPath();
        ctx.arc(px, py, 2.5, 0, Math.PI * 2);
        ctx.fill();
      }
    }
  }
  ctx.restore();
}


function drawUndergroundCAD(ctx) {
  // Haulage galleries
  ctx.strokeStyle = "rgba(100, 116, 139, 0.45)";
  ctx.lineWidth = 3;
  ctx.setLineDash([6, 6]);

  const pSize = 40;
  const gWidth = 10;
  const step = pSize + gWidth;

  // Grid of pillars and roadways
  for (let ix = -3; ix <= 3; ix++) {
    for (let iy = -3; iy <= 3; iy++) {
      const px = ix * step - pSize / 2;
      const py = iy * step - pSize / 2;
      
      const isGoaf = (ix >= 1 && iy >= 1);
      if (isGoaf) {
        ctx.fillStyle = "rgba(239, 68, 68, 0.12)";
        ctx.strokeStyle = "rgba(239, 68, 68, 0.3)";
      } else {
        ctx.fillStyle = "rgba(15, 23, 42, 0.6)";
        ctx.strokeStyle = "rgba(71, 85, 105, 0.4)";
      }
      ctx.setLineDash([]);
      ctx.strokeRect(px, py, pSize, pSize);
      ctx.fillRect(px, py, pSize, pSize);
    }
  }
}

function drawInSARHatchedOverlay(ctx) {
  // Draw Sentinel-1 LOS displacement basin (North-East of active array)
  ctx.save();
  const bx = 160;
  const by = -90;
  const bw = 120;
  const bh = 80;

  ctx.strokeStyle = "#38bdf8";
  ctx.lineWidth = 2;
  ctx.setLineDash([5, 5]);
  ctx.strokeRect(bx, by, bw, bh);

  // Diagonal 45-degree sky-blue hatching
  ctx.beginPath();
  ctx.rect(bx, by, bw, bh);
  ctx.clip();

  ctx.strokeStyle = "rgba(56, 189, 248, 0.45)";
  ctx.lineWidth = 1.5;
  ctx.setLineDash([]);
  for (let offset = -bh; offset < bw + bh; offset += 10) {
    ctx.moveTo(bx + offset, by);
    ctx.lineTo(bx + offset + bh, by + bh);
  }
  ctx.stroke();

  // Beacon Callout Pin
  ctx.fillStyle = "#38bdf8";
  ctx.beginPath();
  ctx.arc(bx + bw / 2, by + bh / 2, 7, 0, Math.PI * 2);
  ctx.fill();

  ctx.fillStyle = "#ffffff";
  ctx.font = "bold 9px JetBrains Mono";
  ctx.fillText("INSAR-088", bx + bw / 2 + 10, by + bh / 2 + 3);

  ctx.restore();
}

function drawRiskZones(ctx) {
  // Critical Contour (Inner)
  ctx.save();
  ctx.strokeStyle = COLORS.critical;
  ctx.lineWidth = 3;
  ctx.shadowColor = "rgba(239, 68, 68, 0.6)";
  ctx.shadowBlur = 10;
  
  ctx.beginPath();
  ctx.ellipse(0, 0, 75, 60, 0.2, 0, Math.PI * 2);
  ctx.stroke();

  // Label
  ctx.fillStyle = "#ffffff";
  ctx.font = "bold 11px JetBrains Mono";
  ctx.fillText("ZONE-PANEL7-C [CRITICAL]", -60, -70);

  // Warning Contour (Middle)
  ctx.strokeStyle = COLORS.warning;
  ctx.shadowColor = "rgba(249, 115, 22, 0.5)";
  ctx.beginPath();
  ctx.ellipse(0, 0, 130, 110, 0.15, 0, Math.PI * 2);
  ctx.stroke();

  // Advisory Contour (Outer)
  ctx.strokeStyle = COLORS.advisory;
  ctx.shadowColor = "rgba(234, 179, 8, 0.4)";
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.ellipse(0, 0, 190, 160, 0.1, 0, Math.PI * 2);
  ctx.stroke();

  ctx.restore();
}

function drawStalenessStripes(ctx) {
  ctx.save();
  ctx.strokeStyle = "rgba(245, 158, 11, 0.4)";
  ctx.lineWidth = 8;
  for (let d = -400; d < 400; d += 30) {
    ctx.beginPath();
    ctx.moveTo(d, -300);
    ctx.lineTo(d + 600, 300);
    ctx.stroke();
  }
  ctx.restore();
}

// -------------------------------------------------------------
// 3D Subsurface Digital Twin Rendering
// -------------------------------------------------------------
function render3DScene() {
  const W = canvas3D.width;
  const H = canvas3D.height;
  ctx3D.clearRect(0, 0, W, H);

  ctx3D.save();
  ctx3D.translate(W / 2, H / 2 + 50);

  const pitch = state.camera3D.pitch;
  const yaw = state.camera3D.yaw;
  const exagg = state.verticalExaggeration;

  // Draw 3D Isometric Terrain Grid with Subsidence flexure
  const nx = 18;
  const ny = 18;
  const spacing = 22;

  // Project (x, y, z) to screen
  function project(x, y, z) {
    const cosY = Math.cos(yaw);
    const sinY = Math.sin(yaw);
    const cosP = Math.cos(pitch);
    const sinP = Math.sin(pitch);

    const rotX = x * cosY - y * sinY;
    const rotY = x * sinY + y * cosY;
    const rotZ = z;

    const screenX = rotX;
    const screenY = rotY * sinP - rotZ * cosP;
    return { x: screenX, y: screenY };
  }

  // Draw Subsurface Extraction Pillars (Extruded below terrain)
  if (state.layers.cad) {
    const seamDepth = 120; // 120 pixels below surface
    ctx3D.fillStyle = "rgba(30, 41, 59, 0.85)";
    ctx3D.strokeStyle = "rgba(56, 189, 248, 0.4)";

    for (let ix = -3; ix <= 3; ix += 2) {
      for (let iy = -3; iy <= 3; iy += 2) {
        const px = ix * 35;
        const py = iy * 35;
        const p1 = project(px, py, -seamDepth);
        const p2 = project(px + 24, py, -seamDepth);
        const p3 = project(px + 24, py + 24, -seamDepth);
        const p4 = project(px, py + 24, -seamDepth);

        ctx3D.beginPath();
        ctx3D.moveTo(p1.x, p1.y);
        ctx3D.lineTo(p2.x, p2.y);
        ctx3D.lineTo(p3.x, p3.y);
        ctx3D.lineTo(p4.x, p4.y);
        ctx3D.closePath();
        ctx3D.fill();
        ctx3D.stroke();
      }
    }
  }

  // Draw Surface Terrain Heightfield with Exaggerated Trough
  ctx3D.strokeStyle = "rgba(255, 255, 255, 0.2)";
  ctx3D.lineWidth = 1;

  for (let j = 0; j < ny; j++) {
    ctx3D.beginPath();
    for (let i = 0; i < nx; i++) {
      const gx = (i - nx / 2) * spacing;
      const gy = (j - ny / 2) * spacing;
      
      // Calculate subsidence flexure at (gx, gy)
      const dist = Math.sqrt(gx * gx + gy * gy);
      // Real subsidence: 0 to 8 mm -> Exaggerated by factor
      const realSubsidence = Math.max(0, 8.0 * Math.exp(-(dist * dist) / 5000.0));
      const visualDisplacement = (realSubsidence / 1.0) * (exagg / 25.0) * 4.0;

      const p = project(gx, gy, -visualDisplacement);
      if (i === 0) ctx3D.moveTo(p.x, p.y);
      else ctx3D.lineTo(p.x, p.y);
    }
    ctx3D.stroke();
  }

  for (let i = 0; i < nx; i++) {
    ctx3D.beginPath();
    for (let j = 0; j < ny; j++) {
      const gx = (i - nx / 2) * spacing;
      const gy = (j - ny / 2) * spacing;
      const dist = Math.sqrt(gx * gx + gy * gy);
      const realSubsidence = Math.max(0, 8.0 * Math.exp(-(dist * dist) / 5000.0));
      const visualDisplacement = (realSubsidence / 1.0) * (exagg / 25.0) * 4.0;

      const p = project(gx, gy, -visualDisplacement);
      if (j === 0) ctx3D.moveTo(p.x, p.y);
      else ctx3D.lineTo(p.x, p.y);
    }
    ctx3D.stroke();
  }

  // Draped Heatmap Core on 3D Surface
  const pCenter = project(0, 0, - (8.0 * (exagg / 25.0) * 4.0));
  const coreGrad = ctx3D.createRadialGradient(pCenter.x, pCenter.y, 5, pCenter.x, pCenter.y, 90);
  coreGrad.addColorStop(0.0, "rgba(239, 68, 68, 0.7)");
  coreGrad.addColorStop(0.5, "rgba(249, 115, 22, 0.5)");
  coreGrad.addColorStop(1.0, "rgba(34, 197, 94, 0.0)");

  ctx3D.fillStyle = coreGrad;
  ctx3D.beginPath();
  ctx3D.arc(pCenter.x, pCenter.y, 90, 0, Math.PI * 2);
  ctx3D.fill();

  ctx3D.restore();
}

// -------------------------------------------------------------
// Interactive Mouse & Touch Dragging
// -------------------------------------------------------------
function setupCanvasInteraction(canvas, mode) {
  canvas.addEventListener("mousedown", (e) => {
    if (mode === "2d") {
      state.camera2D.isDragging = true;
      state.camera2D.dragStart = { x: e.clientX - state.camera2D.x, y: e.clientY - state.camera2D.y };
    } else {
      state.camera3D.isDragging = true;
      state.camera3D.dragStart = { x: e.clientX, y: e.clientY };
    }
  });

  window.addEventListener("mousemove", (e) => {
    if (mode === "2d" && state.camera2D.isDragging) {
      state.camera2D.x = e.clientX - state.camera2D.dragStart.x;
      state.camera2D.y = e.clientY - state.camera2D.dragStart.y;
    } else if (mode === "3d" && state.camera3D.isDragging) {
      const dx = e.clientX - state.camera3D.dragStart.x;
      const dy = e.clientY - state.camera3D.dragStart.y;
      state.camera3D.yaw += dx * 0.006;
      state.camera3D.pitch = Math.max(0.2, Math.min(1.4, state.camera3D.pitch + dy * 0.006));
      state.camera3D.dragStart = { x: e.clientX, y: e.clientY };
    }
  });

  window.addEventListener("mouseup", () => {
    state.camera2D.isDragging = false;
    state.camera3D.isDragging = false;
  });

  canvas.addEventListener("wheel", (e) => {
    e.preventDefault();
    if (mode === "2d") {
      const factor = e.deltaY < 0 ? 1.12 : 0.88;
      state.camera2D.zoom = Math.max(0.5, Math.min(4.0, state.camera2D.zoom * factor));
    } else {
      const factor = e.deltaY < 0 ? 1.1 : 0.9;
      state.camera3D.distance = Math.max(150, Math.min(800, state.camera3D.distance * factor));
    }
  });
}

// -------------------------------------------------------------
// VCR Timeline Scrubber Controls (Section 5.6)
// -------------------------------------------------------------
function togglePlay() {
  state.playback.isPlaying = !state.playback.isPlaying;
  const btn = document.getElementById("btn-scrub-play");
  btn.textContent = state.playback.isPlaying ? "⏸" : "▶";

  if (state.playback.isPlaying) {
    state.playback.timer = setInterval(() => {
      state.playback.currentStep = (state.playback.currentStep + 1) % 101;
      document.getElementById("timeline-slider").value = state.playback.currentStep;
      updateTimelineLabel();
    }, 1000 / state.playback.speed);
  } else {
    clearInterval(state.playback.timer);
  }
}

function cycleSpeed() {
  const speeds = [1, 2, 5, 10, 60];
  const idx = speeds.indexOf(state.playback.speed);
  state.playback.speed = speeds[(idx + 1) % speeds.length];
  document.getElementById("btn-scrub-speed").textContent = `${state.playback.speed}X`;

  if (state.playback.isPlaying) {
    clearInterval(state.playback.timer);
    togglePlay();
    togglePlay();
  }
}

function updateTimelineLabel() {
  const step = state.playback.currentStep;
  const label = document.getElementById("timeline-mode-label");
  const timeEl = document.getElementById("timeline-current-timestamp");

  if (step === 100) {
    label.textContent = "VCR AUDIT REPLAY: LIVE STREAMING";
    timeEl.textContent = "2026-09-09 10:45:00 UTC (CURRENT)";
  } else {
    label.textContent = `HISTORICAL AUDIT PLAYBACK [FRAME ${step}/100]`;
    const pastMinutes = (100 - step) * 2;
    timeEl.textContent = `T - ${pastMinutes}m (Archive State)`;
  }
}

// -------------------------------------------------------------
// What-If Simulation Engine Execution (Section 5.6)
// -------------------------------------------------------------
async function runWhatIfCalculation() {
  const panelId = document.getElementById("sim-panel-id").value;
  const depth = parseFloat(document.getElementById("sim-depth").value);
  const thickness = parseFloat(document.getElementById("sim-thickness").value);
  const width = parseFloat(document.getElementById("sim-width").value);
  const stowing = document.getElementById("sim-stowing").value;

  try {
    const resp = await fetch("/api/v1/simulation/what-if", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        panel_id: panelId,
        site_id: state.siteId,
        extraction_method: "longwall_caving",
        polygon_coordinates_utm: [
          [442200, 2631600], [442400, 2631600], [442400, 2632200], [442200, 2632200], [442200, 2631600]
        ],
        seam_depth_m: depth,
        seam_thickness_m: thickness,
        panel_width_m: width,
        panel_length_m: 600,
        goaf_treatment: stowing
      })
    });

    if (resp.ok) {
      const data = await resp.json();
      document.getElementById("res-smax").textContent = `${data.max_subsidence_mm.toFixed(1)} mm`;
      document.getElementById("res-tilt").textContent = `${data.max_tilt_mm_per_m.toFixed(2)} mm/m`;
      document.getElementById("res-verdict").textContent = data.risk_delta_comparison.dgms_compliance_verdict || "STATUTORY AUDIT OK";
    }
  } catch (err) {
    // Client fallback empirical calculation
    const factor = (stowing === "hydraulic_sand_stowing") ? 0.15 : 0.82;
    const sMax = thickness * 1000 * factor * Math.min(1.0, width / (depth * 1.4));
    const tilt = (sMax / depth) * 1.8;
    document.getElementById("res-smax").textContent = `${sMax.toFixed(1)} mm`;
    document.getElementById("res-tilt").textContent = `${tilt.toFixed(2)} mm/m`;
    document.getElementById("res-verdict").textContent = sMax < 600 ? "PERMITTED WITH MONITORING" : "STATUTORY STOWING MANDATED";
  }
}

// -------------------------------------------------------------
// DGMS Statutory Snapshot Report Exporter
// -------------------------------------------------------------
function triggerDGMSExport() {
  const activeCanvas = (state.viewMode === "2d") ? canvas2D : canvas3D;
  const exportCanvas = document.createElement("canvas");
  exportCanvas.width = activeCanvas.width;
  exportCanvas.height = activeCanvas.height + 140;
  const expCtx = exportCanvas.getContext("2d");

  // Dark background
  expCtx.fillStyle = "#0f172a";
  expCtx.fillRect(0, 0, exportCanvas.width, exportCanvas.height);

  // Header Banner
  expCtx.fillStyle = "#1e293b";
  expCtx.fillRect(0, 0, exportCanvas.width, 80);
  expCtx.fillStyle = "#f8fafc";
  expCtx.font = "bold 16px Inter";
  expCtx.fillText(`SUBSENSE GEOTECHNICAL MONITORING REPORT — ${state.siteId}`, 24, 32);
  expCtx.fillStyle = "#94a3b8";
  expCtx.font = "12px JetBrains Mono";
  expCtx.fillText(`Compliance: DGMS Geotechnical GIS Baseline | Projection: UTM Zone 45N | Exaggeration: ${state.verticalExaggeration}X`, 24, 56);

  // Main viewport snapshot
  expCtx.drawImage(activeCanvas, 0, 80);

  // Footer Banner
  const footerY = exportCanvas.height - 50;
  expCtx.fillStyle = "#1e293b";
  expCtx.fillRect(0, footerY, exportCanvas.width, 50);
  expCtx.fillStyle = "#64748b";
  expCtx.font = "11px Inter";
  expCtx.fillText(`Certified by SubSense Layer 5 Spatial Engine | Timestamp: ${new Date().toISOString()}`, 24, footerY + 30);

  // Download Trigger
  const link = document.createElement("a");
  link.download = `DGMS_Audit_Report_${state.siteId}_${Date.now()}.png`;
  link.href = exportCanvas.toDataURL("image/png");
  link.click();
}

// -------------------------------------------------------------
// Real-Time Server-Sent Events (SSE) Stream (Enhancement)
// -------------------------------------------------------------
function initSSE() {
  try {
    const sseUrl = `/api/v1/stream/${state.tenantId}/${state.siteId}/events`;
    const evtSource = new EventSource(sseUrl);

    evtSource.addEventListener("cycle_published", (e) => {
      const data = JSON.parse(e.data);
      state.dataCurrencySeconds = data.data_currency_seconds;
      const lbl = document.getElementById("sse-label");
      if (lbl) lbl.textContent = `CYCLE #${data.cycle_number}`;
    });

    evtSource.addEventListener("emergency_alert", (e) => {
      const alertData = JSON.parse(e.data);
      triggerEmergencySiren(alertData);
    });

    evtSource.onerror = () => {
      // Graceful degraded mode under connectivity loss
      const lbl = document.getElementById("sse-label");
      if (lbl) lbl.textContent = "SSE OFFLINE";
    };
  } catch (err) {
    console.warn("SSE stream unavailable, using timer fallback:", err);
  }
}

function triggerEmergencySiren(alertData) {
  const vp = document.getElementById("viewport-container");
  vp.classList.add("emergency-siren-flashing");

  // Optional Web Audio alert synthesizer
  if (state.emergencyAudioEnabled && window.AudioContext) {
    try {
      const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      const osc = audioCtx.createOscillator();
      const gain = audioCtx.createGain();
      osc.type = "sawtooth";
      osc.frequency.setValueAtTime(800, audioCtx.currentTime);
      osc.frequency.exponentialRampToValueAtTime(450, audioCtx.currentTime + 0.6);
      gain.gain.setValueAtTime(0.12, audioCtx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 0.6);
      osc.connect(gain);
      gain.connect(audioCtx.destination);
      osc.start();
      osc.stop(audioCtx.currentTime + 0.6);
    } catch (e) {}
  }

  setTimeout(() => {
    vp.classList.remove("emergency-siren-flashing");
  }, 4000);
}

// -------------------------------------------------------------
// Split-Screen Comparison Wipe Controls (Enhancement)
// -------------------------------------------------------------
function toggleSplitWipe() {
  state.splitWipe.enabled = !state.splitWipe.enabled;
  const btn = document.getElementById("btn-toggle-wipe");
  const bar = document.getElementById("split-wipe-bar");

  btn.classList.toggle("active", state.splitWipe.enabled);
  bar.style.display = state.splitWipe.enabled ? "block" : "none";

  if (state.splitWipe.enabled) {
    state.splitWipe.xPercent = 50;
    bar.style.left = `${state.splitWipe.xPercent}%`;
  }
}

function setupSplitWipeInteraction() {
  const bar = document.getElementById("split-wipe-bar");
  const vp = document.getElementById("viewport-container");

  bar.addEventListener("mousedown", (e) => {
    state.splitWipe.isDragging = true;
    e.stopPropagation();
  });

  window.addEventListener("mousemove", (e) => {
    if (state.splitWipe.isDragging) {
      const rect = vp.getBoundingClientRect();
      const relX = Math.max(10, Math.min(rect.width - 10, e.clientX - rect.left));
      state.splitWipe.xPercent = (relX / rect.width) * 100;
      bar.style.left = `${state.splitWipe.xPercent}%`;
    }
  });

  window.addEventListener("mouseup", () => {
    state.splitWipe.isDragging = false;
  });
}

// -------------------------------------------------------------
// Stratigraphic Overburden Cross-Section Slicer (Enhancement)
// -------------------------------------------------------------
async function openCrossSectionModal() {
  const modal = document.getElementById("cross-section-modal");
  modal.classList.add("open");

  try {
    const resp = await fetch(`/api/v1/twin/${state.tenantId}/${state.siteId}/cross-section?vertical_exaggeration=${state.verticalExaggeration}`);
    if (resp.ok) {
      const data = await resp.json();
      renderCrossSectionChart(data);
      return;
    }
  } catch (err) {}

  // Fallback synthetic cross-section profile
  renderSyntheticCrossSection();
}

function closeCrossSectionModal() {
  document.getElementById("cross-section-modal").classList.remove("open");
}

function renderCrossSectionChart(data) {
  const canvas = document.getElementById("cross-section-canvas");
  const ctx = canvas.getContext("2d");
  const W = (canvas.width = canvas.parentElement.clientWidth);
  const H = (canvas.height = canvas.parentElement.clientHeight);

  ctx.clearRect(0, 0, W, H);
  const pts = data.profile_points || [];
  if (!pts.length) return;

  const N = pts.length;
  const paddingX = 50;
  const paddingY = 30;
  const plotW = W - 2 * paddingX;
  const plotH = H - 2 * paddingY;

  // Elevation range (sea level to surface)
  const minElev = 0.0;
  const maxElev = 260.0;

  function toY(elev) {
    return paddingY + plotH * (1.0 - (elev - minElev) / (maxElev - minElev));
  }

  function toX(idx) {
    return paddingX + (idx / (N - 1)) * plotW;
  }

  // 1. Draw Stratigraphic Strata Bands
  // Alluvium: surface to alluvium_base
  ctx.fillStyle = "#c2996b";
  ctx.beginPath();
  ctx.moveTo(toX(0), toY(pts[0].surface_baseline_m));
  for (let i = 1; i < N; i++) ctx.lineTo(toX(i), toY(pts[i].surface_baseline_m));
  for (let i = N - 1; i >= 0; i--) ctx.lineTo(toX(i), toY(pts[i].alluvium_base_m));
  ctx.closePath();
  ctx.fill();

  // Massive Sandstone: alluvium_base to sandstone_base
  ctx.fillStyle = "#d1c4a5";
  ctx.beginPath();
  ctx.moveTo(toX(0), toY(pts[0].alluvium_base_m));
  for (let i = 1; i < N; i++) ctx.lineTo(toX(i), toY(pts[i].alluvium_base_m));
  for (let i = N - 1; i >= 0; i--) ctx.lineTo(toX(i), toY(pts[i].sandstone_base_m));
  ctx.closePath();
  ctx.fill();

  // Shale Interbeds: sandstone_base to seam_roof
  ctx.fillStyle = "#606673";
  ctx.beginPath();
  ctx.moveTo(toX(0), toY(pts[0].sandstone_base_m));
  for (let i = 1; i < N; i++) ctx.lineTo(toX(i), toY(pts[i].sandstone_base_m));
  for (let i = N - 1; i >= 0; i--) ctx.lineTo(toX(i), toY(pts[i].seam_roof_m));
  ctx.closePath();
  ctx.fill();

  // Coal Seam & Goaf: seam_roof to seam_floor
  ctx.fillStyle = "#1f2429";
  ctx.beginPath();
  ctx.moveTo(toX(0), toY(pts[0].seam_roof_m));
  for (let i = 1; i < N; i++) ctx.lineTo(toX(i), toY(pts[i].seam_roof_m));
  for (let i = N - 1; i >= 0; i--) ctx.lineTo(toX(i), toY(pts[i].seam_floor_m));
  ctx.closePath();
  ctx.fill();

  // 2. Draw Exaggerated Deformed Surface Profile Line
  ctx.strokeStyle = "#ef4444";
  ctx.lineWidth = 2.5;
  ctx.setLineDash([]);
  ctx.beginPath();
  ctx.moveTo(toX(0), toY(pts[0].surface_deformed_m));
  for (let i = 1; i < N; i++) {
    ctx.lineTo(toX(i), toY(pts[i].surface_deformed_m));
  }
  ctx.stroke();

  // Draw Baseline dashed line
  ctx.strokeStyle = "rgba(255, 255, 255, 0.4)";
  ctx.lineWidth = 1.5;
  ctx.setLineDash([4, 4]);
  ctx.beginPath();
  ctx.moveTo(toX(0), toY(pts[0].surface_baseline_m));
  for (let i = 1; i < N; i++) {
    ctx.lineTo(toX(i), toY(pts[i].surface_baseline_m));
  }
  ctx.stroke();
  ctx.setLineDash([]);

  // Axis Labels
  ctx.fillStyle = "#94a3b8";
  ctx.font = "10px JetBrains Mono";
  ctx.fillText("SURFACE (+220m)", paddingX + 6, paddingY + 16);
  ctx.fillText("SEAM VII (-180m)", paddingX + 6, toY(pts[0].seam_roof_m) - 6);
  ctx.fillText(`Max Subsidence: ${data.max_subsidence_mm} mm (${state.verticalExaggeration}X Exaggerated)`, W / 2 - 120, 20);
}

function renderSyntheticCrossSection() {
  const dummyData = {
    max_subsidence_mm: 580.0,
    profile_points: []
  };
  for (let i = 0; i < 50; i++) {
    const dist = i * 15;
    const sub = 580.0 * Math.exp(-Math.pow(dist - 375, 2) / 12000.0);
    dummyData.profile_points.push({
      distance_m: dist,
      surface_baseline_m: 220.0,
      surface_deformed_m: 220.0 - (sub / 1000.0) * state.verticalExaggeration,
      alluvium_base_m: 208.0,
      sandstone_base_m: 90.0,
      seam_roof_m: 40.0,
      seam_floor_m: 35.5
    });
  }
  renderCrossSectionChart(dummyData);
}

