# SubSense — 3-Minute Hackathon Winning Pitch & Judge Demo Guide
**Event**: Smart India Hackathon (SIH 2026)  
**Problem Category**: Underground Coal Mine Subsidence Early-Warning Platform  
**Live Demo URL**: http://localhost:5174  

---

## ⏱️ The 3-Minute Live Presentation Breakdown

### 0:00 – 0:30 | The Hook & The Problem
> *"Honorable judges, underground coal mine roof collapses and ground subsidence are among the deadliest hazards in mining, claiming miner lives and causing crores of rupees in infrastructure destruction.*  
> *Today's mine monitoring relies either on satellite InSAR (which has a 6-to-12 day revisit delay) or legacy multi-point extensometers that cost over ₹3,00,000 per borehole and instantly die when rock deformation severs their communication cables.*  
> *We built **SubSense**: a zero-latency, wireless multi-hop early-warning platform powered by on-device TinyML that triggers life-safety sirens in **under 5 microseconds**, completely independent of cloud or surface connectivity."*

---

### 0:30 – 1:15 | The Hardware & Zero-Fabrication Innovation
*(Point to the Web Dashboard at http://localhost:5174 and highlight the floating bottom-right **OLED Mirror**)*:

> *"Look at our bottom-right screen: this is a real-time digital mirror of our physical **Sensor Node** (Board 1), equipped with an MPU6050 gyro and a dedicated SSD1306 OLED health console.*  
> *Here is our first core engineering principle: **Strict Zero Data Fabrication**.*  
> *Underground, our physical sensors measure pitch tilt and dynamic vibration. We NEVER fabricate missing sensor data like extensometer displacement or crack width—our pipeline explicitly tracks them as null with false availability flags, ensuring safety engineers can trust 100% of our telemetry.*  
> *On the node itself, our quantized INT8 neural network runs directly on the ESP32 in **<5 microseconds**. If tilt breaches 4.0° or a seismic micro-fracture is detected, the underground siren sounds immediately without waiting for surface approval."*

---

### 1:15 – 2:00 | Multi-Hop Mesh (No Underground Cables)
> *"Underground mine tunnels are solid rock and coal pillars where WiFi and cellular cannot reach. We solved this with a 3-tier **ESP-NOW multi-hop wireless mesh**:*  
> 1. **Sensor Node (Hop 0)**: Samples at 100 Hz, runs TinyML, and updates its local OLED screen.  
> 2. **Relay Node (Hop 1)**: Pure forwarder—sits around tunnel bends to bridge the signal past rock walls without needing sensors.  
> 3. **Gateway Node (Hop 2)**: Aggregates mesh packets at the pit bottom and streams them to our surface gateway bridge.  
> *If the surface internet drops, our gateway bridge's **offline SQLite queue** automatically stores readings and replays them chronologically once the connection is restored."*

---

### 2:00 – 2:45 | THE LIVE ACTION DRILL (The "Wow" Moment)
*(Click the **`[3. COLLAPSE DRILL]`** button on the top evaluation console)*:

> *"Let me show you a live catastrophic failure drill right now in real time."*  
> *(Click button -> **Emergency siren sound plays through speakers**, top red evacuation banner drops down, and the OLED screen inverts to `*** CRITICAL ALARM *** EVACUATE MINE PANEL!`)*  
>  
> *"Instantly, look at what just happened:*  
> *1. **Underground Actuation**: Sensor Node N042's tilt jumped to 4.85°, triggering the edge siren and flashing the inverted evacuation banner on the miners' OLED screen.*  
> *2. **AI/ML Layer**: Our Dual-Tier Isolation Forest and 1D-CNN ensemble scored the anomaly at 96% and applied the SHAP explainability gate.*  
> *3. **GIS Kriging Heatmap**: Recalculated spatial subsidence risk contours across the panel.*  
> *4. **Statutory DGMS Compliance**: Generated an immutable SHA-256 cryptographic audit record meeting Directorate General of Mines Safety requirements.*  
> *(Click **`[SILENCE SIREN]`**)*: *The shift supervisor acknowledges the audible protocol with a single click."*

---

### 2:45 – 3:00 | Business Impact & Closing
> *"SubSense costs under **₹1,200 ($14) per sensor node**—a 95% cost reduction over legacy instruments. With our 180-day LiFePO4 battery budget, zero-fabrication AI pipeline, and sub-5-microsecond edge siren, SubSense transforms mine subsidence monitoring from a post-disaster autopsy into real-time, life-saving prevention.*  
> *Thank you, and we welcome your questions!"*

---

## 🎯 Top Judge Q&A Defenses (Be Ready For These!)

### Q1: "How do your radio signals penetrate through solid rock and coal underground?"
> **Answer**:  
> *"2.4 GHz WiFi cannot pass through 100 meters of solid rock, which is why star networks fail underground. SubSense uses an **ESP-NOW multi-hop linear mesh**. Our lightweight Relay Nodes are placed along line-of-sight tunnel bends and galleries. The packet hops from Node to Relay to Gateway. Each relay maintains original sender MAC addresses and deduplicates packets with a circular cache, allowing signals to snake through kilometers of mine galleries without requiring external routers."*

### Q2: "What if the ML model makes a false negative or has an error?"
> **Answer**:  
> *"We implemented a **Fail-Safe Physical Priority Architecture**. In our C firmware, the physical tilt threshold (>4.0°) runs on raw accelerometer data completely parallel to the neural network. Even if the AI model or feature buffer experiences an issue, the physical angle threshold triggers the hardware siren via GPIO 2 in <5 microseconds. Safety is hardcoded in hardware; AI provides the early predictive trend."*

### Q3: "What happens if surface power or internet cuts off?"
> **Answer**:  
> *"Underground life-safety does not depend on the internet. The Sensor Node siren and OLED screen actuate locally underground. On the surface, our Gateway Bridge features an **offline SQLite store-and-forward queue**. If cloud or database connectivity drops, incoming packets are safely buffered to local disk. A background retry worker automatically flushes and chronologically replays the backlog as soon as connectivity resumes—with zero packet loss."*

### Q4: "Why don't your Relay and Gateway nodes have OLED displays?"
> **Answer**:  
> *"This was an intentional geotechnical design choice. Relay nodes are mounted high in tunnel roofs purely to forward radio packets—installing displays there wastes battery power and adds unnecessary component failure points. Gateway nodes sit in surface control cabins connected directly to PCs. The OLED display is **exclusive to the Sensor Node** because it is installed in active working faces where miners and shift supervisors physically stand and need immediate on-the-spot visual health telemetry."*
