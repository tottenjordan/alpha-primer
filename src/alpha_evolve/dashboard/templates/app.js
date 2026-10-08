    (function() {
      "use strict";

      // 1. Safe DOM Helpers (strictly zero dangerous property assignments)
      function el(tag, className, text) {
        const node = document.createElement(tag);
        if (className) node.className = className;
        if (text !== undefined && text !== null) node.textContent = String(text);
        return node;
      }

      // 2. Parse Embedded Telemetry
      const dataScript = document.getElementById("master-trajectory-data");
      if (!dataScript) return;
      let masterData = {};
      try {
        masterData = JSON.parse(dataScript.textContent);
      } catch (err) {
        console.error("Failed to parse master-trajectory-data", err);
        return;
      }

      let currentUseCaseId = "inventory_replenishment";
      let uc = (masterData.use_cases && masterData.use_cases[currentUseCaseId]) || null;
      if (!uc && masterData.use_cases) {
        currentUseCaseId = Object.keys(masterData.use_cases)[0];
        uc = masterData.use_cases[currentUseCaseId];
      }
      if (!uc) return;

      let trajectories = uc.trajectory_generations || [];
      let archetypes = uc.sku_archetypes || [];
      let baselineSum = uc.baseline_summary || {};
      let championSum = uc.champion_summary || {};
      let milestones = uc.milestones || {};
      let ribbonMilestones = uc.ribbon_milestones || [];
      let costWaterfall = uc.cost_waterfall || null;
      let paretoFrontier = uc.pareto_frontier || [];
      let spatialTopology = uc.spatial_topology || null;
      let dispatchSnapshots = uc.dispatch_snapshots || null;
      let canvas1Mode = "topology"; // "topology" or "trajectory"
      let fleetMapFilter = "all";
      let hoveredCustomerId = null;
      let fleetHitRegions = [];
      let maxGen = Math.max(0, trajectories.length - 1);

      // 3. Tab Switching (with WAI-ARIA role="tab" sync)
      const tabBtns = document.querySelectorAll(".tab-btn");
      const tabPanes = document.querySelectorAll(".tab-pane");

      tabBtns.forEach(btn => {
        btn.addEventListener("click", () => {
          tabBtns.forEach(b => {
            b.classList.remove("active");
            b.setAttribute("aria-selected", "false");
          });
          tabPanes.forEach(p => p.classList.remove("active"));
          btn.classList.add("active");
          btn.setAttribute("aria-selected", "true");
          const targetId = btn.getAttribute("data-tab");
          const target = document.getElementById(targetId);
          if (target) target.classList.add("active");

          if (targetId !== "tab-replay") {
            pauseReplay();
          }

          if (targetId === "tab-replay") {
            drawTrajectoryChart(currentGen);
            drawCanvas2Chart();
          } else if (targetId === "tab-whatif") {
            updateWhatIfSimulation();
          } else if (targetId === "tab-diffs") {
            renderCurrentDiff();
          }
        });
      });

      // 4. Render Archetype Table Header & Body via Safe DOM
      const tbody = document.getElementById("tbody-archetypes");
      const theadRow = document.getElementById("thead-archetypes-row");
      const tableTitleEl = document.getElementById("table-archetypes-title");

      function renderArchetypesTable() {
        if (!tbody) return;
        tbody.replaceChildren();

        if (theadRow) {
          theadRow.replaceChildren();
          const cols = currentUseCaseId === "fleet_routing"
            ? [
                "Vehicle Archetype",
                "Capacity",
                "Avg Speed",
                "Cost / km",
                "Fixed Dispatch Cost",
                "On-Time SLA",
                "Fleet Status",
                "Guardrail"
              ]
            : [
                "SKU Category Archetype",
                "Shelf Life",
                "Lead Time",
                "Baseline Spoilage",
                "Champion Spoilage",
                "Holding Cost",
                "Spoilage Cost",
                "Stockout Penalty"
              ];
          cols.forEach(colText => {
            theadRow.appendChild(el("th", null, colText));
          });
        }

        if (tableTitleEl) {
          tableTitleEl.textContent = currentUseCaseId === "fleet_routing"
            ? "Fleet Vehicle Archetype Dispatch & SLA Performance Breakdown"
            : "SKU Archetype Cost & Spoilage Performance Breakdown";
        }

        if (currentUseCaseId === "fleet_routing") {
          const fleetRows = [
            { type: "Standard Delivery Van", cap: "120 boxes", speed: "45 km/h", costPerKm: "$1.85", fixedCost: "$120.00", slaRate: "97.2%" },
            { type: "Refrigerated Transit Van", cap: "90 boxes", speed: "40 km/h", costPerKm: "$2.40", fixedCost: "$160.00", slaRate: "98.5%" },
            { type: "Express Cargo Courier", cap: "45 boxes", speed: "55 km/h", costPerKm: "$1.50", fixedCost: "$95.00", slaRate: "96.8%" }
          ];
          fleetRows.forEach(r => {
            const tr = el("tr");
            tr.appendChild(el("td", null, r.type));
            tr.appendChild(el("td", null, r.cap));
            tr.appendChild(el("td", null, r.speed));
            tr.appendChild(el("td", null, r.costPerKm));
            tr.appendChild(el("td", null, r.fixedCost));
            tr.appendChild(el("td", null, r.slaRate));
            tr.appendChild(el("td", null, "Active"));
            tr.appendChild(el("td", null, "SLA Guarded"));
            tbody.appendChild(tr);
          });
        } else {
          archetypes.forEach(a => {
            const tr = el("tr");
            tr.appendChild(el("td", null, a.category));
            tr.appendChild(el("td", null, a.shelf_life_days + " days"));
            tr.appendChild(el("td", null, a.lead_time_days + " days"));
            tr.appendChild(el("td", null, a.baseline_spoilage_rate + "%"));
            tr.appendChild(el("td", null, a.champion_spoilage_rate + "%"));
            tr.appendChild(el("td", null, "$" + a.holding_cost.toFixed(2)));
            tr.appendChild(el("td", null, "$" + a.spoilage_cost.toFixed(2)));
            tr.appendChild(el("td", null, "$" + a.stockout_penalty.toFixed(2)));
            tbody.appendChild(tr);
          });
        }
      }
      renderArchetypesTable();

      // 4b. Multi-Domain Controls & Benchmark Content Synchronization (Safe DOM)
      function updateDomainControls() {
        const isFleet = currentUseCaseId === "fleet_routing";
        const skuLabel = document.getElementById("whatif-sku-label");
        const skuSel = document.getElementById("whatif-sku");
        if (skuLabel) {
          skuLabel.textContent = isFleet ? "Fleet Route & SLA Archetype" : "SKU Category Archetype";
        }
        if (skuSel) {
          const prevVal = skuSel.value || "0";
          skuSel.replaceChildren();
          const options = isFleet
            ? [
                "Tight-Window Urban Stops (1-hr SLA)",
                "Commercial Metro Deliveries (2-hr SLA)",
                "Suburban Perimeter Bulk Routes (4-hr SLA)"
              ]
            : [
                "Ultra-Perishables (Berries / Pre-cut Salads - 3 Days)",
                "Chilled Dairy & Fresh Meats (7 Days)",
                "Ambient Grocery & Packaged Goods (21 Days)"
              ];
          options.forEach((optText, idx) => {
            const opt = el("option", null, optText);
            opt.value = String(idx);
            skuSel.appendChild(opt);
          });
          if (prevVal === "0" || prevVal === "1" || prevVal === "2") {
            skuSel.value = prevVal;
          }
        }

        const l1 = document.getElementById("label-slide-1");
        const l2 = document.getElementById("label-slide-2");
        const l3 = document.getElementById("label-slide-3");
        const l4 = document.getElementById("label-slide-4");
        if (l1) l1.textContent = isFleet ? "Urban Traffic Congestion Delay" : "Supplier Lead Time Delay";
        if (l2) l2.textContent = isFleet ? "Dynamic Order Surge" : "Promotional Demand Spike";
        if (l3) l3.textContent = isFleet ? "SLA Tardiness Penalty Multiplier" : "Spoilage Cost Multiplier";
        if (l4) l4.textContent = isFleet ? "Unserved / Overtime Multiplier" : "Stockout Penalty Multiplier";

        const whatifCardTitle = document.getElementById("whatif-card-title");
        if (whatifCardTitle) {
          whatifCardTitle.textContent = isFleet
            ? "Dual-Policy Stress Simulation: Greedy Nearest-Neighbor vs AlphaEvolve Regret-2"
            : "Dual-Policy Stress Simulation: Baseline (s, S) vs AlphaEvolve Champion";
        }
        const baseTitle = document.getElementById("whatif-base-title");
        const champTitle = document.getElementById("whatif-champ-title");
        if (baseTitle) baseTitle.textContent = isFleet ? "1. Baseline Greedy Dispatch" : "1. Baseline Static (s, S)";
        if (champTitle) champTitle.textContent = isFleet ? "2. AlphaEvolve Regret-2 + 2-Opt" : "2. AlphaEvolve Champion";

        const bStat1 = document.getElementById("label-base-stat1");
        const bStat2 = document.getElementById("label-base-stat2");
        const bStat4 = document.getElementById("label-base-stat4");
        const cStat1 = document.getElementById("label-champ-stat1");
        const cStat2 = document.getElementById("label-champ-stat2");
        const cStat4 = document.getElementById("label-champ-stat4");
        if (bStat1) bStat1.textContent = isFleet ? "On-Time SLA:" : "Fill Rate:";
        if (cStat1) cStat1.textContent = isFleet ? "On-Time SLA:" : "Fill Rate:";
        if (bStat2) bStat2.textContent = isFleet ? "Late / Tardiness:" : "Daily Spoilage:";
        if (cStat2) cStat2.textContent = isFleet ? "Late / Tardiness:" : "Daily Spoilage:";
        if (bStat4) bStat4.textContent = isFleet ? "Active Fleet Load:" : "Order-Up-To Level:";
        if (cStat4) cStat4.textContent = isFleet ? "Active Fleet Load:" : "Order-Up-To Level:";

        // Benchmark & Math Tab updates via Safe DOM
        const benchTitle = document.getElementById("benchmark-title");
        const benchDesc = document.getElementById("benchmark-desc");
        const benchFormula = document.getElementById("benchmark-formula");
        const benchList = document.getElementById("benchmark-phases-list");

        if (benchTitle) {
          benchTitle.textContent = isFleet
            ? "VRPTW Dispatch Objective & Dynamic Traffic Digital Twin"
            : "Evaluation Objective & Digital Twin Architecture";
        }
        if (benchDesc) {
          benchDesc.textContent = isFleet
            ? "The dynamic Vehicle Routing Problem with Time Windows (VRPTW) digital twin simulates 50 customer delivery stops across urban, metro, and suburban zones under time-varying rush-hour congestion."
            : "The multi-echelon replenishment digital twin models stochastic customer demand across 50 heterogeneous SKU nodes over a 90-day causal horizon. The evaluation strictly enforces causal isolation: policy functions only have access to history t <= now.";
        }
        if (benchFormula) {
          benchFormula.replaceChildren();
          benchFormula.appendChild(el("b", null, "Objective Function:"));
          benchFormula.appendChild(el("br"));
          benchFormula.appendChild(
            document.createTextNode(
              isFleet
                ? "Score = Cost_Reduction_% - 60.0 × max(0, 0.95 - OnTime_SLA)^2"
                : "Score = Cost_Reduction_% - 50.0 × max(0, 0.95 - Fill_Rate)^2"
            )
          );
          benchFormula.appendChild(el("br"));
          benchFormula.appendChild(el("br"));
          benchFormula.appendChild(
            document.createTextNode(
              isFleet
                ? "Total_Cost = C_distance + C_tardiness + C_overtime + C_dispatch"
                : "Total_Cost = C_holding + C_spoilage + C_stockout + C_ordering"
            )
          );
        }
        if (benchList) {
          benchList.replaceChildren();
          const phases = isFleet
            ? [
                ["Morning Rush (06:00..09:30):", "Peak highway congestion factor (1.35x); champion clusters tight-window depot stops first."],
                ["Midday Window (09:30..15:30):", "Regret-2 dynamic stop insertion serves commercial and suburban bulk routes at peak velocity."],
                ["Evening Wave (15:30..18:00):", "2-opt trajectory uncrossing eliminates route crisscrossing before shift overtime cutoff."]
              ]
            : [
                ["Days 0..29 (Warmup):", "Digital twin initializes FIFO age cohorts and in-transit pipelines under fixed seed demand."],
                ["Days 30..65 (Validation Window):", "AlphaEvolve scores candidate policies over 35 active business days."],
                ["Days 66..89 (Holdout Window):", "Out-of-sample stress test with promotional demand surges and lead-time shocks."]
              ];
          phases.forEach(pair => {
            const li = el("li");
            li.appendChild(el("b", null, pair[0] + " "));
            li.appendChild(document.createTextNode(pair[1]));
            benchList.appendChild(li);
          });
        }

        const c1ModeToggles = document.getElementById("canvas1-mode-toggles");
        const fleetMapCtrl = document.getElementById("fleet-map-controls");
        const c1SubEl = document.getElementById("canvas1-subtitle");
        const c1ContainerEl = document.getElementById("canvas1-container");
        const isTopologyMode = isFleet && canvas1Mode === "topology";
        if (c1ModeToggles) {
          c1ModeToggles.classList.toggle("hidden", !isFleet);
        }
        if (fleetMapCtrl) {
          fleetMapCtrl.classList.toggle("hidden", !isTopologyMode);
        }
        if (c1SubEl) {
          c1SubEl.classList.toggle("hidden", isTopologyMode);
        }
        if (c1ContainerEl) {
          c1ContainerEl.classList.toggle("fleet-spatial-mode", isTopologyMode);
        }
      }

      const btnModeTopology = document.getElementById("btn-mode-topology");
      const btnModeTrajectory = document.getElementById("btn-mode-trajectory");
      if (btnModeTopology && btnModeTrajectory) {
        btnModeTopology.addEventListener("click", () => {
          canvas1Mode = "topology";
          btnModeTopology.classList.add("active");
          btnModeTrajectory.classList.remove("active");
          hoveredDayIdx = null;
          const tipEl = document.getElementById("tooltip-trajectory");
          if (tipEl) tipEl.classList.remove("visible");
          updateDomainControls();
          drawTrajectoryChart(currentGen, null);
        });
        btnModeTrajectory.addEventListener("click", () => {
          canvas1Mode = "trajectory";
          btnModeTrajectory.classList.add("active");
          btnModeTopology.classList.remove("active");
          hoveredCustomerId = null;
          const tipEl = document.getElementById("tooltip-trajectory");
          if (tipEl) tipEl.classList.remove("visible");
          updateDomainControls();
          drawTrajectoryChart(currentGen, null);
        });
      }

      document.querySelectorAll(".btn-fleet-filter").forEach(btn => {
        btn.addEventListener("click", () => {
          fleetMapFilter = btn.getAttribute("data-fleet-filter") || "all";
          document.querySelectorAll(".btn-fleet-filter").forEach(b => {
            b.classList.toggle("active", b === btn);
          });
          drawTrajectoryChart(currentGen, hoveredDayIdx);
        });
      });

      // 4c. Use Case Switching Engine (Strict Safe DOM)
      let diffViewMode = "split"; // "split" or "unified"
      let diffFoldUnchanged = true;
      let leftMilestoneKey = "0";
      let rightMilestoneKey = "8";

      const diffTableBody = document.getElementById("diff-table-body");
      const diffTableHeader = document.getElementById("diff-table-header");
      const btnViewSplit = document.getElementById("btn-view-split");
      const btnViewUnified = document.getElementById("btn-view-unified");
      const btnToggleFold = document.getElementById("btn-toggle-fold");
      const diffSelectBase = document.getElementById("diff-select-base");
      const diffSelectEvolved = document.getElementById("diff-select-evolved");

      function updateDiffStepperOptions() {
        if (!diffSelectBase || !diffSelectEvolved) return;
        diffSelectBase.replaceChildren();
        diffSelectEvolved.replaceChildren();

        const keys = Object.keys(milestones).sort((a, b) => parseInt(a, 10) - parseInt(b, 10));
        keys.forEach(k => {
          const m = milestones[k];
          const label = "Gen " + k + (m.badge ? " (" + m.badge.replace(/Gen \d+ ?/, "").trim() + ")" : "");
          const opt1 = el("option", null, label);
          opt1.value = k;
          diffSelectBase.appendChild(opt1);

          const opt2 = el("option", null, label);
          opt2.value = k;
          diffSelectEvolved.appendChild(opt2);
        });

        const pairButtons = document.querySelectorAll(".diff-stepper-btn[data-pair]");
        if (pairButtons.length === 4 && keys.length >= 4) {
          const pairs = [
            [keys[0], keys[1], "Gen " + keys[0] + " \u2194 Gen " + keys[1]],
            [keys[1], keys[2], "Gen " + keys[1] + " \u2194 Gen " + keys[2]],
            [keys[2], keys[3], "Gen " + keys[2] + " \u2194 Gen " + keys[3]],
            [keys[0], keys[3], "Gen " + keys[0] + " \u2194 Gen " + keys[3] + " (Full)"]
          ];
          pairButtons.forEach((btn, idx) => {
            btn.setAttribute("data-pair", pairs[idx][0] + "-" + pairs[idx][1]);
            btn.textContent = pairs[idx][2];
            btn.classList.toggle("active", idx === 0);
          });
        }

        const presetBtns = document.querySelectorAll(".btn-preset[data-gen]");
        if (presetBtns.length === 4 && keys.length >= 4) {
          presetBtns.forEach((btn, idx) => {
            btn.setAttribute("data-gen", keys[idx]);
            btn.textContent = "Gen " + keys[idx];
          });
        }

        leftMilestoneKey = keys[0] || "0";
        rightMilestoneKey = keys.length > 1 ? keys[1] : (keys[0] || "0");
        diffSelectBase.value = leftMilestoneKey;
        diffSelectEvolved.value = rightMilestoneKey;
        renderCurrentDiff();
      }

      function switchUseCase(useCaseId) {
        if (!masterData.use_cases || !masterData.use_cases[useCaseId]) return;
        currentUseCaseId = useCaseId;
        uc = masterData.use_cases[currentUseCaseId];

        document.querySelectorAll(".use-case-btn").forEach(btn => {
          if (btn.getAttribute("data-use-case") === useCaseId) {
            btn.classList.add("active");
          } else {
            btn.classList.remove("active");
          }
        });

        trajectories = uc.trajectory_generations || [];
        archetypes = uc.sku_archetypes || [];
        baselineSum = uc.baseline_summary || {};
        championSum = uc.champion_summary || {};
        milestones = uc.milestones || {};
        ribbonMilestones = uc.ribbon_milestones || [];
        costWaterfall = uc.cost_waterfall || null;
        paretoFrontier = uc.pareto_frontier || [];
        spatialTopology = uc.spatial_topology || null;
        dispatchSnapshots = uc.dispatch_snapshots || null;
        hoveredCustomerId = null;
        hoveredDayIdx = null;
        if (useCaseId === "fleet_routing") {
          canvas1Mode = "topology";
          if (btnModeTopology && btnModeTrajectory) {
            btnModeTopology.classList.add("active");
            btnModeTrajectory.classList.remove("active");
          }
        }
        maxGen = Math.max(0, trajectories.length - 1);

        const titleEl = document.getElementById("active-use-case-title");
        if (titleEl) {
          titleEl.textContent = uc.title || (useCaseId === "fleet_routing"
            ? "Dynamic Fleet Routing & Dispatch with Time Windows (VRPTW)"
            : "Autonomous Multi-Echelon & Perishable Inventory Replenishment");
        }
        const horizonEl = document.getElementById("meta-horizon");
        if (horizonEl) {
          horizonEl.textContent = useCaseId === "fleet_routing" ? "12 Hours (Traffic)" : "90 Days (Causal)";
        }

        renderArchetypesTable();
        updateDomainControls();
        renderMilestoneRibbon();
        updateDiffStepperOptions();
        updateWhatIfSimulation();

        if (scrubber) {
          scrubber.max = maxGen;
          scrubber.value = maxGen;
        }
        currentGen = maxGen;
        updateDisplay(currentGen);
      }

      document.querySelectorAll(".use-case-btn").forEach(btn => {
        btn.addEventListener("click", () => {
          pauseReplay();
          const targetUc = btn.getAttribute("data-use-case");
          if (targetUc && targetUc !== currentUseCaseId) {
            switchUseCase(targetUc);
          }
        });
      });

      // 5. Interactive Milestone Ribbon (Zero inline styles)
      const ribbonContainer = document.getElementById("milestone-ribbon-nodes");
      function renderMilestoneRibbon() {
        if (!ribbonContainer) return;
        ribbonContainer.replaceChildren();

        ribbonMilestones.forEach(item => {
          const node = el("button", "ribbon-node");
          if (item.is_star) node.classList.add("star");
          if (item.is_champ) node.classList.add("champ");
          if (item.generation === currentGen) node.classList.add("active");

          node.setAttribute("data-gen", String(item.generation));
          node.appendChild(el("span", null, item.badge || item.label));

          const reducSpan = el("span", "badge-diff " + (item.cost_reduc > 0 ? "positive" : "neutral"), (item.cost_reduc > 0 ? "-" : "") + item.cost_reduc.toFixed(1) + "%");
          node.appendChild(reducSpan);

          // Tooltip (Safe DOM with CSS classes)
          const tip = el("div", "ribbon-tooltip");
          const tipHeader = el("div", "ribbon-tip-title", item.title);
          tip.appendChild(tipHeader);

          const slaLabel = currentUseCaseId === "fleet_routing" ? "On-Time: " : "Fill Rate: ";
          const tipStats = el(
            "div",
            "ribbon-tip-stats",
            "Cost Reduc: " + item.cost_reduc.toFixed(1) + "% | " + slaLabel + item.fill_rate.toFixed(1) + "%"
          );
          tip.appendChild(tipStats);

          const tipInn = el("div", "ribbon-tip-inn", item.innovation);
          tip.appendChild(tipInn);

          node.appendChild(tip);

          node.addEventListener("click", () => {
            pauseReplay();
            updateDisplay(item.generation);
          });

          ribbonContainer.appendChild(node);
        });
      }

      function updateMilestoneRibbonActive() {
        if (!ribbonContainer) return;
        const nodes = ribbonContainer.querySelectorAll(".ribbon-node");
        let closestGen = 0;
        let minDiff = 999;
        ribbonMilestones.forEach(m => {
          const diff = Math.abs(m.generation - currentGen);
          if (diff < minDiff) {
            minDiff = diff;
            closestGen = m.generation;
          }
        });

        nodes.forEach(n => {
          const g = parseInt(n.getAttribute("data-gen"), 10);
          if (g === closestGen) {
            n.classList.add("active");
          } else {
            n.classList.remove("active");
          }
        });
      }

      // 6. State, Replay Scrubber, Speed Toggle & Keyboard Navigation
      let currentGen = maxGen;
      let isPlaying = false;
      let playInterval = null;
      let playSpeedMultiplier = 1; // 1x (400ms) or 2x (180ms)
      let canvas2Mode = "pareto"; // "pareto" or "waterfall"

      const scrubber = document.getElementById("scrubber");
      const scrubberLabel = document.getElementById("scrubber-label");
      const playBtn = document.getElementById("btn-play");
      const speedBtn = document.getElementById("btn-speed-toggle");

      function getIntervalMs() {
        return playSpeedMultiplier === 2 ? 180 : 400;
      }

      function pauseReplay() {
        if (isPlaying) {
          isPlaying = false;
          if (playBtn) playBtn.textContent = "▶ Play Evolution";
          if (playInterval) clearInterval(playInterval);
          playInterval = null;
        }
      }

      function startReplayTimer() {
        if (playInterval) clearInterval(playInterval);
        playInterval = setInterval(() => {
          currentGen++;
          if (currentGen > maxGen) {
            currentGen = maxGen;
            pauseReplay();
          }
          updateDisplay(currentGen);
        }, getIntervalMs());
      }

      function updateDisplay(genIdx) {
        currentGen = Math.max(0, Math.min(maxGen, genIdx));
        if (scrubber) scrubber.value = currentGen;
        if (scrubberLabel) scrubberLabel.textContent = "GEN " + currentGen + " / " + maxGen;

        const frame = trajectories[currentGen];
        if (!frame) return;

        const m = frame.metrics;
        const fitVal = m.score !== undefined ? m.score : (m.fitness_score || 0);
        const fitBadgeEl = document.getElementById("kpi-fitness-badge");
        if (fitBadgeEl) {
          fitBadgeEl.textContent = (fitVal >= 0 ? "+" : "") + fitVal.toFixed(2) + " pts";
        }
        const latencyEl = document.getElementById("kpi-latency-val");
        if (latencyEl) {
          latencyEl.textContent = currentUseCaseId === "fleet_routing" ? "64 ms" : "79 ms";
        }

        if (currentUseCaseId === "fleet_routing") {
          const kpi1Label = document.getElementById("kpi-label-1");
          if (kpi1Label) kpi1Label.textContent = "Total Fleet Cost";
          const totalCostEl = document.getElementById("kpi-total-cost");
          if (totalCostEl) totalCostEl.textContent = "$" + Math.round(m.total_cost).toLocaleString();
          const costReducEl = document.getElementById("kpi-cost-reduc");
          if (costReducEl) costReducEl.textContent = (m.cost_reduction_pct > 0 ? "-" : "") + m.cost_reduction_pct.toFixed(1) + "%";
          const baselineCompEl = document.getElementById("kpi-baseline-comp");
          if (baselineCompEl) baselineCompEl.textContent = "vs. $" + Math.round(baselineSum.total_cost || 4099).toLocaleString() + " baseline";

          const kpi2Label = document.getElementById("kpi-label-2");
          if (kpi2Label) kpi2Label.textContent = "Fleet Distance Traveled";
          const spoilCostEl = document.getElementById("kpi-spoilage-cost");
          if (spoilCostEl) spoilCostEl.textContent = Math.round(m.total_distance_km || 0).toLocaleString() + " km";
          const spoilRateEl = document.getElementById("kpi-spoilage-rate");
          if (spoilRateEl) spoilRateEl.textContent = (m.vehicles_used || 5) + " vehicles";
          const subComp2El = document.getElementById("kpi-sub-comp-2");
          if (subComp2El) subComp2El.textContent = "vs. " + Math.round(baselineSum.total_distance_km || 1433) + " km baseline";

          const kpi3Label = document.getElementById("kpi-label-3");
          if (kpi3Label) kpi3Label.textContent = "On-Time Delivery Rate";
          const fillRateEl = document.getElementById("kpi-fill-rate");
          if (fillRateEl) fillRateEl.textContent = (m.on_time_delivery_pct || m.fill_rate_pct || 0).toFixed(1) + "%";
          const badge3El = document.getElementById("kpi-badge-3");
          if (badge3El) badge3El.textContent = "Target: ≥95.0%";
          const subComp3El = document.getElementById("kpi-sub-comp-3");
          if (subComp3El) subComp3El.textContent = "tardiness: " + (m.total_tardiness_hours || 0).toFixed(1) + " hrs";

          const kpi4Label = document.getElementById("kpi-label-4");
          if (kpi4Label) kpi4Label.textContent = "VRPTW Optimization Score";
          const fitScoreEl = document.getElementById("kpi-fitness-score");
          if (fitScoreEl) fitScoreEl.textContent = fitVal.toFixed(2);
        } else {
          const kpi1Label = document.getElementById("kpi-label-1");
          if (kpi1Label) kpi1Label.textContent = "Total Supply Chain Cost";
          const totalCostEl = document.getElementById("kpi-total-cost");
          if (totalCostEl) totalCostEl.textContent = "$" + Math.round(m.total_cost).toLocaleString();
          const costReducEl = document.getElementById("kpi-cost-reduc");
          if (costReducEl) costReducEl.textContent = (m.cost_reduction_pct > 0 ? "-" : "") + m.cost_reduction_pct.toFixed(1) + "%";
          const baselineCompEl = document.getElementById("kpi-baseline-comp");
          if (baselineCompEl) baselineCompEl.textContent = "vs. $68,410 baseline";

          const kpi2Label = document.getElementById("kpi-label-2");
          if (kpi2Label) kpi2Label.textContent = "Perishable Spoilage Waste";
          const spoilCostEl = document.getElementById("kpi-spoilage-cost");
          if (spoilCostEl) spoilCostEl.textContent = "$" + Math.round(m.spoilage_cost || 0).toLocaleString();
          const spoilRateEl = document.getElementById("kpi-spoilage-rate");
          if (spoilRateEl) spoilRateEl.textContent = (m.spoilage_rate_pct || 0).toFixed(2) + "% rate";
          const subComp2El = document.getElementById("kpi-sub-comp-2");
          if (subComp2El) subComp2El.textContent = "vs. 14.6% baseline";

          const kpi3Label = document.getElementById("kpi-label-3");
          if (kpi3Label) kpi3Label.textContent = "Service Fill Rate";
          const fillRateEl = document.getElementById("kpi-fill-rate");
          if (fillRateEl) fillRateEl.textContent = (m.fill_rate_pct || 0).toFixed(2) + "%";
          const badge3El = document.getElementById("kpi-badge-3");
          if (badge3El) badge3El.textContent = "SLA: ≥95.0%";
          const subComp3El = document.getElementById("kpi-sub-comp-3");
          if (subComp3El) {
            subComp3El.replaceChildren();
            subComp3El.appendChild(document.createTextNode("stockout penalty: "));
            const stockSpan = el("span", null, "$" + Math.round(m.stockout_penalty || 0).toLocaleString());
            stockSpan.id = "kpi-stockout-cost";
            subComp3El.appendChild(stockSpan);
          }

          const kpi4Label = document.getElementById("kpi-label-4");
          if (kpi4Label) kpi4Label.textContent = "Evaluation Fitness Score";
          const fitScoreEl = document.getElementById("kpi-fitness-score");
          if (fitScoreEl) fitScoreEl.textContent = (m.fitness_score || 0).toFixed(2);
        }

        document.getElementById("milestone-title").textContent = "GEN " + currentGen + (currentGen === 30 ? " CHAMPION" : (currentGen === 0 ? " SEED BASELINE" : " BREAKTHROUGH"));
        document.getElementById("milestone-desc").textContent = frame.event_summary || (currentUseCaseId === "fleet_routing" ? (currentGen === 30 ? "Champion Regret-2 + 2-opt traffic-aware heuristic (-39.7% cost)" : (currentGen === 0 ? "Greedy nearest-neighbor baseline dispatch" : "Breakthrough candidate")) : "");

        updateMilestoneRibbonActive();
        drawTrajectoryChart(currentGen);
        drawCanvas2Chart();
      }

      if (scrubber) {
        scrubber.addEventListener("input", (e) => {
          pauseReplay();
          updateDisplay(parseInt(e.target.value, 10));
        });
      }

      document.querySelectorAll(".btn-preset").forEach(btn => {
        btn.addEventListener("click", () => {
          pauseReplay();
          const g = parseInt(btn.getAttribute("data-gen"), 10);
          updateDisplay(g);
        });
      });

      if (playBtn) {
        playBtn.addEventListener("click", () => {
          isPlaying = !isPlaying;
          if (isPlaying) {
            playBtn.textContent = "⏸ Pause Replay";
            if (currentGen >= maxGen) currentGen = 0;
            startReplayTimer();
          } else {
            pauseReplay();
          }
        });
      }

      if (speedBtn) {
        speedBtn.addEventListener("click", () => {
          playSpeedMultiplier = playSpeedMultiplier === 1 ? 2 : 1;
          speedBtn.textContent = playSpeedMultiplier + "x";
          if (isPlaying) {
            startReplayTimer();
          }
        });
      }

      // Keyboard navigation (Space to toggle play/pause, Left/Right arrows to scrub)
      window.addEventListener("keydown", (e) => {
        const activeTag = document.activeElement ? document.activeElement.tagName : "";
        if (activeTag === "INPUT" || activeTag === "SELECT" || activeTag === "TEXTAREA") return;
        const replayPane = document.getElementById("tab-replay");
        if (!replayPane || !replayPane.classList.contains("active")) return;

        if (e.code === "Space") {
          e.preventDefault();
          if (playBtn) playBtn.click();
        } else if (e.code === "ArrowLeft") {
          e.preventDefault();
          pauseReplay();
          updateDisplay(currentGen - 1);
        } else if (e.code === "ArrowRight") {
          e.preventDefault();
          pauseReplay();
          updateDisplay(currentGen + 1);
        }
      });

      // Canvas 2 Mode Switching
      const btnModePareto = document.getElementById("btn-mode-pareto");
      const btnModeWaterfall = document.getElementById("btn-mode-waterfall");
      const canvas2Title = document.getElementById("canvas2-title");

      if (btnModePareto && btnModeWaterfall) {
        btnModePareto.addEventListener("click", () => {
          canvas2Mode = "pareto";
          btnModePareto.classList.add("active");
          btnModeWaterfall.classList.remove("active");
          if (canvas2Title) canvas2Title.textContent = "Mode A: 2D Pareto Frontier Evolution";
          drawCanvas2Chart();
        });

        btnModeWaterfall.addEventListener("click", () => {
          canvas2Mode = "waterfall";
          btnModeWaterfall.classList.add("active");
          btnModePareto.classList.remove("active");
          if (canvas2Title) canvas2Title.textContent = "Mode B: 31-Gen Stacked Cost Waterfall";
          drawCanvas2Chart();
        });
      }

      function drawCanvas2Chart(hoverIdx) {
        if (canvas2Mode === "pareto") {
          drawParetoChart(hoverIdx);
        } else {
          drawWaterfallChart(hoverIdx);
        }
      }

      // 7. Retina Canvas 2D Trajectory Chart & Synchronized 2D Fleet Spatial Topology Map
      let hoveredDayIdx = null;
      const FLEET_VEHICLE_COLORS = ["#06B6D4", "#10B981", "#3B82F6", "#F59E0B", "#F43F5E"];

      function drawFleetSpatialCanvas(genIdx) {
        const canvas = document.getElementById("canvas-trajectory");
        if (!canvas || !spatialTopology || !dispatchSnapshots) return;
        const ctx = canvas.getContext("2d");
        const rect = canvas.getBoundingClientRect();
        if (rect.width === 0 || rect.height === 0) return;

        const dpr = window.devicePixelRatio || 1;
        canvas.width = rect.width * dpr;
        canvas.height = rect.height * dpr;
        ctx.scale(dpr, dpr);

        const w = rect.width;
        const h = rect.height;
        ctx.clearRect(0, 0, w, h);

        const c1Title = document.getElementById("canvas1-title");
        if (c1Title) {
          c1Title.textContent = "2D Route Topology Map: Greedy Nearest-Neighbor vs Evolved Regret-2 + 2-Opt";
        }

        const frame = trajectories[genIdx] || trajectories[0];
        const mKey = (frame && frame.milestone_key)
          ? String(frame.milestone_key)
          : (genIdx < 7 ? "0" : (genIdx < 16 ? "7" : (genIdx < 30 ? "16" : "30")));
        const leftSnap = dispatchSnapshots["0"];
        const rightSnap = dispatchSnapshots[mKey] || dispatchSnapshots["30"] || leftSnap;
        if (!leftSnap || !rightSnap) return;

        fleetHitRegions = [];

        const padSide = w < 360 ? 3 : 6;
        const centerW = Math.min(116, Math.max(48, Math.round(w * 0.16)));
        const boxW = Math.max(36, Math.floor((w - centerW - padSide * 4) / 2));
        const leftBoxX = padSide;
        const centerX = leftBoxX + boxW + padSide;
        const rightBoxX = centerX + centerW + padSide;
        const mapTop = 24;
        const mapBot = h - 8;
        const mapH = Math.max(80, mapBot - mapTop);

        const bounds = spatialTopology.grid_bounds_km || [0.0, 100.0, 0.0, 100.0];
        const minXKm = Number(bounds[0]) || 0.0;
        const spanXKm = Math.max(1e-6, (Number(bounds[1]) || 100.0) - minXKm);
        const minYKm = Number(bounds[2]) || 0.0;
        const spanYKm = Math.max(1e-6, (Number(bounds[3]) || 100.0) - minYKm);

        function projX(boxX, xKm) {
          return boxX + 10 + ((xKm - minXKm) / spanXKm) * (boxW - 20);
        }
        function projY(yKm) {
          return mapBot - 10 - ((yKm - minYKm) / spanYKm) * (mapH - 20);
        }

        const custById = {};
        (spatialTopology.customers || []).forEach(c => {
          custById[c.id] = c;
        });

        function buildVehLookup(snap) {
          const lookup = {};
          const seqMap = snap.route_sequences || {};
          Object.keys(seqMap).forEach(vKey => {
            const vNum = parseInt(vKey, 10) || 0;
            (seqMap[vKey] || []).forEach((cid, sIdx) => {
              lookup[String(cid)] = { vehicle_id: vNum, stop_seq: sIdx, status: "on_time" };
            });
          });
          return lookup;
        }

        const leftFallbackStops = buildVehLookup(leftSnap);
        const rightFallbackStops = buildVehLookup(rightSnap);

        function renderViewport(boxX, snap, fallbackStops, titleText, accentColor) {
          const sum = snap.summary || {};
          // Viewport background & border
          ctx.fillStyle = "rgba(15, 23, 42, 0.55)";
          ctx.fillRect(boxX, mapTop, boxW, mapH);
          ctx.strokeStyle = "rgba(148, 163, 184, 0.18)";
          ctx.lineWidth = 1;
          ctx.strokeRect(boxX, mapTop, boxW, mapH);

          // Header banner
          ctx.fillStyle = accentColor;
          ctx.font = "bold 10px JetBrains Mono, monospace";
          ctx.fillText(titleText, boxX + 4, 12);

          ctx.fillStyle = "#94A3B8";
          ctx.font = "9px JetBrains Mono, monospace";
          const subStats = "$" + Math.round(sum.total_cost || 0).toLocaleString() +
            " | " + Math.round(sum.total_distance_km || 0) + "km | " +
            (sum.intra_route_crossings || 0) + " cross";
          ctx.fillText(subStats, boxX + 4, 21);

          // Quadrant cluster rings
          const quads = spatialTopology.cluster_centers || [];
          const qRadPx = (14.0 / spanXKm) * Math.min(boxW - 20, mapH - 20);
          ctx.strokeStyle = "rgba(148, 163, 184, 0.13)";
          ctx.lineWidth = 1;
          ctx.setLineDash([2, 3]);
          quads.forEach(q => {
            const qx = projX(boxX, q.x_km);
            const qy = projY(q.y_km);
            ctx.beginPath();
            ctx.arc(qx, qy, qRadPx, 0, Math.PI * 2);
            ctx.stroke();
            ctx.fillStyle = "rgba(148, 163, 184, 0.35)";
            ctx.font = "8px JetBrains Mono, monospace";
            ctx.fillText((q.label || "").slice(0, 2), qx - 6, qy - qRadPx + 9);
          });
          ctx.setLineDash([]);

          const depot = spatialTopology.depot || { x_km: 50, y_km: 50 };
          const hubX = projX(boxX, depot.x_km !== undefined ? depot.x_km : depot.x);
          const hubY = projY(depot.y_km !== undefined ? depot.y_km : depot.y);
          const outcomes = snap.stop_outcomes || {};

          // Layer 1: Vehicle Route Polylines & Directional Chevrons
          const tourList = (snap.tours && snap.tours.length > 0)
            ? snap.tours
            : Object.keys(snap.route_sequences || {}).map(vid => ({
                vehicle_id: parseInt(vid, 10) || 0,
                wave_index: 0,
                stops: snap.route_sequences[vid] || []
              }));
          tourList.forEach(tour => {
            const vid = tour.vehicle_id || 0;
            const vColor = FLEET_VEHICLE_COLORS[vid % FLEET_VEHICLE_COLORS.length];
            const isVehFilter = fleetMapFilter.indexOf("v") === 0;
            const vehSelected = !isVehFilter || fleetMapFilter === ("v" + vid);
            const isDynamicWave = (tour.wave_index || 0) > 0;

            let prevX = hubX;
            let prevY = hubY;
            const stops = tour.stops || [];

            stops.forEach(cid => {
              const cust = custById[cid];
              if (!cust) return;
              const out = outcomes[String(cid)] || fallbackStops[String(cid)] || {};
              const currX = projX(boxX, cust.x_km !== undefined ? cust.x_km : cust.x);
              const currY = projY(cust.y_km !== undefined ? cust.y_km : cust.y);
              const isDynamicStop = isDynamicWave || Boolean(cust.is_dynamic);

              let legActive = vehSelected;
              if (fleetMapFilter === "wave0" && isDynamicStop) legActive = false;
              if (fleetMapFilter === "dynamic" && !isDynamicStop) legActive = false;
              if (fleetMapFilter === "late" && out.status !== "late") legActive = false;

              ctx.strokeStyle = vColor;
              ctx.lineWidth = legActive ? 1.65 : 0.55;
              if (isDynamicStop) {
                ctx.setLineDash([3, 3]);
              } else {
                ctx.setLineDash([]);
              }

              if (legActive) {
                ctx.beginPath();
                ctx.moveTo(prevX, prevY);
                ctx.lineTo(currX, currY);
                ctx.stroke();

                // Midpoint directional chevron triangle
                const mx = (prevX + currX) * 0.5;
                const my = (prevY + currY) * 0.5;
                const dx = currX - prevX;
                const dy = currY - prevY;
                const segLen = Math.hypot(dx, dy);
                if (segLen > 16) {
                  const ux = dx / segLen;
                  const uy = dy / segLen;
                  const px = -uy;
                  const py = ux;
                  const tipX = mx + ux * 3.2;
                  const tipY = my + uy * 3.2;
                  const lx = mx - ux * 2.4 + px * 2.2;
                  const ly = my - uy * 2.4 + py * 2.2;
                  const rx = mx - ux * 2.4 - px * 2.2;
                  const ry = my - uy * 2.4 - py * 2.2;
                  ctx.fillStyle = vColor;
                  ctx.beginPath();
                  ctx.moveTo(tipX, tipY);
                  ctx.lineTo(lx, ly);
                  ctx.lineTo(rx, ry);
                  ctx.lineTo(tipX, tipY);
                  ctx.fill();
                }
              }

              prevX = currX;
              prevY = currY;
            });

            // Return leg to depot
            ctx.setLineDash([2, 3]);
            if (vehSelected && fleetMapFilter === "all" && stops.length > 0) {
              ctx.strokeStyle = "rgba(148, 163, 184, 0.22)";
              ctx.lineWidth = 0.9;
              ctx.beginPath();
              ctx.moveTo(prevX, prevY);
              ctx.lineTo(hubX, hubY);
              ctx.stroke();
            }
            ctx.setLineDash([]);
          });

          // Layer 2: Intra-Route Self-Crossing Conflict Rings
          (snap.crossings || []).forEach(cr => {
            const cx = projX(boxX, cr.x_km);
            const cy = projY(cr.y_km);
            ctx.strokeStyle = "rgba(244, 63, 94, 0.92)";
            ctx.lineWidth = 1.5;
            ctx.beginPath();
            ctx.arc(cx, cy, 5.5, 0, Math.PI * 2);
            ctx.stroke();

            ctx.fillStyle = "#F43F5E";
            ctx.beginPath();
            ctx.arc(cx, cy, 1.8, 0, Math.PI * 2);
            ctx.fill();
          });

          // Layer 3 & 4: Time-Window Urgency / SLA Breach Halos & Customer Glyphs
          (spatialTopology.customers || []).forEach(c => {
            const cx = projX(boxX, c.x_km !== undefined ? c.x_km : c.x);
            const cy = projY(c.y_km !== undefined ? c.y_km : c.y);
            const st = outcomes[String(c.id)] || fallbackStops[String(c.id)] || null;
            const vid = st ? st.vehicle_id : 0;
            const isLate = st && st.status === "late";

            let nodeActive = true;
            if (fleetMapFilter === "wave0" && c.is_dynamic) nodeActive = false;
            if (fleetMapFilter === "dynamic" && !c.is_dynamic) nodeActive = false;
            if (fleetMapFilter === "late" && !isLate) nodeActive = false;
            if (fleetMapFilter.indexOf("v") === 0 && ("v" + vid) !== fleetMapFilter) nodeActive = false;

            if (isLate) {
              const haloR = Math.min(9.5, 5.0 + ((st.tardiness_hours || 0) * 1.3));
              ctx.strokeStyle = nodeActive ? "rgba(244, 63, 94, 0.88)" : "rgba(244, 63, 94, 0.18)";
              ctx.lineWidth = 1.5;
              ctx.beginPath();
              ctx.arc(cx, cy, haloR, 0, Math.PI * 2);
              ctx.stroke();
            } else if ((c.tw_width || 2.0) <= 1.65 && nodeActive) {
              ctx.strokeStyle = "rgba(245, 158, 11, 0.45)";
              ctx.lineWidth = 1;
              ctx.beginPath();
              ctx.arc(cx, cy, 5.0, 0, Math.PI * 2);
              ctx.stroke();
            }

            const baseColor = isLate ? "#F43F5E" : FLEET_VEHICLE_COLORS[vid % FLEET_VEHICLE_COLORS.length];
            ctx.fillStyle = nodeActive ? baseColor : "rgba(148, 163, 184, 0.22)";

            if (c.is_dynamic) {
              const s = nodeActive ? 3.8 : 2.5;
              ctx.beginPath();
              ctx.moveTo(cx, cy - s);
              ctx.lineTo(cx + s, cy);
              ctx.lineTo(cx, cy + s);
              ctx.lineTo(cx - s, cy);
              ctx.lineTo(cx, cy - s);
              ctx.fill();
            } else {
              const rNode = nodeActive ? 3.0 : 2.0;
              ctx.beginPath();
              ctx.arc(cx, cy, rNode, 0, Math.PI * 2);
              ctx.fill();
            }

            if (hoveredCustomerId === c.id) {
              ctx.strokeStyle = "#06B6D4";
              ctx.lineWidth = 2.2;
              ctx.beginPath();
              ctx.arc(cx, cy, 8.5, 0, Math.PI * 2);
              ctx.stroke();

              ctx.fillStyle = "#F8FAFC";
              ctx.font = "bold 9px JetBrains Mono, monospace";
              ctx.fillText("#" + c.id, cx + 8, cy - 6);
            }

            fleetHitRegions.push({
              customer: c,
              leftStop: (leftSnap.stop_outcomes || {})[String(c.id)] || leftFallbackStops[String(c.id)] || null,
              rightStop: (rightSnap.stop_outcomes || {})[String(c.id)] || rightFallbackStops[String(c.id)] || null,
              active: nodeActive,
              x: cx,
              y: cy
            });
          });

          // Layer 5: Central Depot Hub (50, 50)
          ctx.fillStyle = "rgba(6, 182, 212, 0.25)";
          ctx.beginPath();
          ctx.arc(hubX, hubY, 7.5, 0, Math.PI * 2);
          ctx.fill();

          ctx.fillStyle = "#F8FAFC";
          ctx.fillRect(hubX - 3.5, hubY - 3.5, 7, 7);
          ctx.strokeStyle = "#06B6D4";
          ctx.lineWidth = 1.5;
          ctx.strokeRect(hubX - 3.5, hubY - 3.5, 7, 7);
        }

        const rightModeLabel = genIdx >= 30
          ? "REGRET-2 + 2-OPT"
          : (genIdx >= 16 ? "TRAFFIC + 2-OPT" : (genIdx >= 7 ? "SLACK URGENCY" : "GREEDY SEED"));
        renderViewport(leftBoxX, leftSnap, leftFallbackStops, "GEN 0: GREEDY BASELINE", "#F43F5E");
        renderViewport(
          rightBoxX,
          rightSnap,
          rightFallbackStops,
          "GEN " + genIdx + ": " + rightModeLabel,
          "#10B981"
        );

        // Center Telemetry Delta Strip
        const lSum = leftSnap.summary || {};
        const rSum = rightSnap.summary || {};
        ctx.fillStyle = "rgba(15, 23, 42, 0.78)";
        ctx.fillRect(centerX, mapTop, centerW, mapH);
        ctx.strokeStyle = "rgba(148, 163, 184, 0.2)";
        ctx.lineWidth = 1;
        ctx.strokeRect(centerX, mapTop, centerW, mapH);

        ctx.fillStyle = "#06B6D4";
        ctx.font = "bold 9px JetBrains Mono, monospace";
        ctx.fillText("DELTA HUD", centerX + 8, mapTop + 14);

        const rows = [
          ["Crossings", (lSum.intra_route_crossings || 0) + " \u2192 " + (rSum.intra_route_crossings || 0), (rSum.intra_route_crossings || 0) === 0 ? "#10B981" : "#F59E0B"],
          ["Late Stops", (lSum.late_stops_count || 0) + " \u2192 " + (rSum.late_stops_count || 0), (rSum.late_stops_count || 0) < (lSum.late_stops_count || 0) ? "#10B981" : "#F43F5E"],
          ["On-Time", Math.round(lSum.on_time_delivery_pct || 0) + "% \u2192 " + Math.round(rSum.on_time_delivery_pct || 0) + "%", "#06B6D4"],
          ["Distance", Math.round(lSum.total_distance_km || 0) + "\u2192" + Math.round(rSum.total_distance_km || 0) + "km", "#CBD5E1"]
        ];
        rows.forEach((r, idx) => {
          const ry = mapTop + 30 + idx * 32;
          ctx.fillStyle = "#94A3B8";
          ctx.font = "8px JetBrains Mono, monospace";
          ctx.fillText(r[0], centerX + 8, ry);
          ctx.fillStyle = r[2];
          ctx.font = "bold 9.5px JetBrains Mono, monospace";
          ctx.fillText(r[1], centerX + 8, ry + 12);
        });

        // Vehicle utilization bars in center column
        ctx.fillStyle = "#94A3B8";
        ctx.font = "8px JetBrains Mono, monospace";
        ctx.fillText("PEAK WAVE LOAD", centerX + 8, mapTop + 162);

        for (let vIdx = 0; vIdx < 5; vIdx++) {
          const vy = mapTop + 174 + vIdx * 16;
          if (vy + 8 > mapBot) break;
          const vCol = FLEET_VEHICLE_COLORS[vIdx % FLEET_VEHICLE_COLORS.length];
          ctx.fillStyle = vCol;
          ctx.font = "8px JetBrains Mono, monospace";
          ctx.fillText("V" + vIdx, centerX + 8, vy + 6);

          const barMaxW = Math.max(16, centerW - 32);
          ctx.fillStyle = "rgba(148, 163, 184, 0.16)";
          ctx.fillRect(centerX + 24, vy, barMaxW, 6);

          const vTours = (rightSnap.tours || []).filter(t => t.vehicle_id === vIdx);
          let peakCap = vTours.reduce((mx, t) => Math.max(mx, t.capacity_pct || 0), 0);
          if (peakCap === 0 && rightSnap.route_sequences && rightSnap.route_sequences[String(vIdx)]) {
            const stopIds = rightSnap.route_sequences[String(vIdx)] || [];
            const totalDem = stopIds.reduce((acc, sid) => acc + ((custById[sid] && custById[sid].demand) || 4.0), 0);
            peakCap = Math.min(100, Math.round((totalDem / 45.0) * 100));
          }
          const fillW = Math.min(barMaxW, Math.round((peakCap / 100.0) * barMaxW));
          ctx.fillStyle = vCol;
          ctx.fillRect(centerX + 24, vy, fillW, 6);
        }
      }

      function drawTrajectoryChart(genIdx, hoverDay) {
        if (
          currentUseCaseId === "fleet_routing" &&
          canvas1Mode === "topology" &&
          spatialTopology &&
          dispatchSnapshots
        ) {
          drawFleetSpatialCanvas(genIdx);
          return;
        }

        const canvas = document.getElementById("canvas-trajectory");
        if (!canvas) return;
        const ctx = canvas.getContext("2d");
        const rect = canvas.getBoundingClientRect();
        if (rect.width === 0 || rect.height === 0) return;

        const dpr = window.devicePixelRatio || 1;
        canvas.width = rect.width * dpr;
        canvas.height = rect.height * dpr;
        ctx.scale(dpr, dpr);

        const w = rect.width;
        const h = rect.height;
        const padL = 46, padR = 18, padT = 20, padB = 30;

        ctx.clearRect(0, 0, w, h);

        const frame = trajectories[genIdx];
        if (!frame || !frame.daily_series) return;
        const series = frame.daily_series;
        const isFleet = currentUseCaseId === "fleet_routing";

        const c1Title = document.getElementById("canvas1-title");
        const c1Sub = document.getElementById("canvas1-subtitle");
        if (c1Title) {
          c1Title.textContent = isFleet
            ? "90-Step Fleet Active Route Load, In-Transit Stops & Late Events"
            : "90-Day Digital Twin Inventory Trajectory & Spoilage Stack";
        }
        if (c1Sub) {
          c1Sub.textContent = isFleet
            ? "Steps 0..29 Morning Rush | 30..65 Midday | 66..89 Evening Wave"
            : "Days 0..29 Warmup | 30..65 Eval | 66..89 Holdout";
        }

        // Visual phase shading
        const dayW = (w - padL - padR) / 90;
        ctx.fillStyle = "rgba(148, 163, 184, 0.05)";
        ctx.fillRect(padL, padT, dayW * 30, h - padT - padB);
        ctx.fillStyle = "rgba(6, 182, 212, 0.06)";
        ctx.fillRect(padL + dayW * 30, padT, dayW * 36, h - padT - padB);
        ctx.fillStyle = "rgba(245, 158, 11, 0.06)";
        ctx.fillRect(padL + dayW * 66, padT, dayW * 24, h - padT - padB);

        // Grid lines
        ctx.strokeStyle = "rgba(148, 163, 184, 0.1)";
        ctx.lineWidth = 1;
        for (let i = 0; i <= 4; i++) {
          const y = padT + (i / 4) * (h - padT - padB);
          ctx.beginPath();
          ctx.moveTo(padL, y);
          ctx.lineTo(w - padR, y);
          ctx.stroke();
        }

        // Dynamic Y-axis scaling for multi-domain telemetry
        let peakVal = 0;
        series.forEach(pt => {
          peakVal = Math.max(peakVal, pt.on_hand || 0, (pt.in_transit || 0) * 2.5);
        });
        const maxOnHand = isFleet ? Math.max(150, Math.ceil(peakVal * 1.15 / 10) * 10) : 12000;
        const maxSpoilBar = isFleet ? 10 : 400;

        function mapX(day) { return padL + (day / 89) * (w - padL - padR); }
        function mapY(val) { return (h - padB) - (Math.min(maxOnHand, val) / maxOnHand) * (h - padT - padB); }

        // On-hand / Active Load curve
        ctx.strokeStyle = "#06B6D4";
        ctx.lineWidth = 2;
        ctx.beginPath();
        series.forEach((pt, idx) => {
          const x = mapX(pt.day);
          const y = mapY(pt.on_hand);
          if (idx === 0) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        });
        ctx.stroke();

        // In-transit curve
        ctx.strokeStyle = "#F59E0B";
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        series.forEach((pt, idx) => {
          const x = mapX(pt.day);
          const y = mapY(pt.in_transit * 2.5);
          if (idx === 0) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        });
        ctx.stroke();

        // Spoilage / Late-Stop bar indicators
        ctx.fillStyle = "rgba(244, 63, 94, 0.8)";
        series.forEach(pt => {
          if (pt.spoilage_units > 0) {
            const x = mapX(pt.day);
            const barH = Math.min(48, (pt.spoilage_units / maxSpoilBar) * 40);
            ctx.fillRect(x - 1, h - padB - barH, 2, barH);
          }
        });

        // Hover crosshair & inspection dot
        const activeHover = hoverDay !== undefined ? hoverDay : hoveredDayIdx;
        if (activeHover !== null && activeHover >= 0 && activeHover < series.length) {
          const hPt = series[activeHover];
          const hx = mapX(hPt.day);
          const hy = mapY(hPt.on_hand);

          ctx.strokeStyle = "rgba(6, 182, 212, 0.45)";
          ctx.lineWidth = 1;
          ctx.setLineDash([3, 3]);
          ctx.beginPath();
          ctx.moveTo(hx, padT);
          ctx.lineTo(hx, h - padB);
          ctx.stroke();
          ctx.setLineDash([]);

          ctx.fillStyle = "#06B6D4";
          ctx.beginPath();
          ctx.arc(hx, hy, 4.5, 0, Math.PI * 2);
          ctx.fill();
        }

        // Axes labels
        ctx.fillStyle = "#94A3B8";
        ctx.font = "10px JetBrains Mono, monospace";
        ctx.fillText("0", padL - 14, h - padB + 3);
        ctx.fillText(isFleet ? String(maxOnHand) : "12k", padL - 30, padT + 10);
        ctx.fillText(isFleet ? "Step 0" : "Day 0", padL, h - 10);
        ctx.fillText(isFleet ? "Step 30" : "Day 30", padL + dayW * 30 - 15, h - 10);
        ctx.fillText(isFleet ? "Step 65" : "Day 65", padL + dayW * 66 - 15, h - 10);
        ctx.fillText(isFleet ? "Step 89" : "Day 89", w - padR - 38, h - 10);
      }

      // Wire interactive hover on #canvas-trajectory
      const canvasTrajEl = document.getElementById("canvas-trajectory");
      const tooltipTrajEl = document.getElementById("tooltip-trajectory");
      if (canvasTrajEl && tooltipTrajEl) {
        canvasTrajEl.addEventListener("mousemove", (e) => {
          const rect = canvasTrajEl.getBoundingClientRect();
          const relX = e.clientX - rect.left;
          const relY = e.clientY - rect.top;

          if (
            currentUseCaseId === "fleet_routing" &&
            canvas1Mode === "topology" &&
            spatialTopology &&
            dispatchSnapshots
          ) {
            let bestHit = null;
            let bestDist = 14;
            fleetHitRegions.forEach(reg => {
              if (!reg.active) return;
              const d = Math.hypot(relX - reg.x, relY - reg.y);
              if (d <= bestDist) {
                bestDist = d;
                bestHit = reg;
              }
            });
            if (!bestHit) {
              fleetHitRegions.forEach(reg => {
                const d = Math.hypot(relX - reg.x, relY - reg.y);
                if (d <= bestDist) {
                  bestDist = d;
                  bestHit = reg;
                }
              });
            }

            if (bestHit) {
              if (hoveredCustomerId !== bestHit.customer.id) {
                hoveredCustomerId = bestHit.customer.id;
                drawFleetSpatialCanvas(currentGen);
              }
              const c = bestHit.customer;
              const ls = bestHit.leftStop;
              const rs = bestHit.rightStop;
              const g0Status = ls
                ? ("V" + ls.vehicle_id + " #" + ls.stop_seq + (ls.status === "late" ? " (+" + Math.round((ls.tardiness_hours || 0) * 60) + "m LATE)" : " (ON-TIME)"))
                : "Unassigned";
              const gnStatus = rs
                ? ("V" + rs.vehicle_id + " #" + rs.stop_seq + (rs.status === "late" ? " (+" + Math.round((rs.tardiness_hours || 0) * 60) + "m LATE)" : " (ON-TIME)"))
                : "Unassigned";

              tooltipTrajEl.replaceChildren();
              tooltipTrajEl.appendChild(
                el(
                  "span",
                  null,
                  "Stop #" + c.id + " (" + c.quadrant + " | Wave " + c.wave_index + " | TW " + c.tw_start.toFixed(1) + "-" + c.tw_end.toFixed(1) + "h) — " +
                  "Gen 0: " + g0Status + " \u2192 Gen " + currentGen + ": " + gnStatus
                )
              );
              tooltipTrajEl.classList.add("visible");
            } else if (hoveredCustomerId !== null) {
              hoveredCustomerId = null;
              tooltipTrajEl.classList.remove("visible");
              drawFleetSpatialCanvas(currentGen);
            }
            return;
          }

          const padL = 46, padR = 18;
          const ratio = (relX - padL) / Math.max(1, rect.width - padL - padR);
          const dayIdx = Math.max(0, Math.min(89, Math.round(ratio * 89)));
          hoveredDayIdx = dayIdx;
          drawTrajectoryChart(currentGen, dayIdx);

          const frame = trajectories[currentGen];
          const pt = frame && frame.daily_series ? frame.daily_series[dayIdx] : null;
          if (pt) {
            const isFleet = currentUseCaseId === "fleet_routing";
            tooltipTrajEl.replaceChildren();
            tooltipTrajEl.appendChild(
              el(
                "span",
                null,
                (isFleet ? "Step " : "Day ") + pt.day +
                " | " + (isFleet ? "Load: " : "On-Hand: ") + Math.round(pt.on_hand).toLocaleString() +
                " | " + (isFleet ? "Transit: " : "In-Transit: ") + Math.round(pt.in_transit).toLocaleString() +
                " | " + (isFleet ? "Late: " : "Spoil: ") + pt.spoilage_units
              )
            );
            tooltipTrajEl.classList.add("visible");
          }
        });

        canvasTrajEl.addEventListener("mouseleave", () => {
          hoveredDayIdx = null;
          hoveredCustomerId = null;
          tooltipTrajEl.classList.remove("visible");
          drawTrajectoryChart(currentGen, null);
        });
      }

      // 8. Retina Canvas 2D: Mode A 2D Pareto Frontier Evolution (Multi-Domain Scaled)
      let hoveredParetoGen = null;

      function drawParetoChart(hoverGen) {
        const canvas = document.getElementById("canvas-convergence");
        if (!canvas) return;
        const ctx = canvas.getContext("2d");
        const rect = canvas.getBoundingClientRect();
        if (rect.width === 0 || rect.height === 0) return;

        const dpr = window.devicePixelRatio || 1;
        canvas.width = rect.width * dpr;
        canvas.height = rect.height * dpr;
        ctx.scale(dpr, dpr);

        const w = rect.width;
        const h = rect.height;
        const padL = 44, padR = 24, padT = 24, padB = 34;

        ctx.clearRect(0, 0, w, h);

        const isFleet = currentUseCaseId === "fleet_routing";
        // Dynamic bounds: Fleet Routing spans 60%..97.2% SLA, Inventory spans 90.8%..94.0%
        let minX = 0, maxX = 36;
        let minY = 90.8, maxY = 94.0;
        let minSpoil = 8.45, maxSpoil = 14.6;

        if (isFleet && trajectories.length > 0) {
          const xVals = trajectories.map(t => t.metrics.cost_reduction_pct || 0);
          const yVals = trajectories.map(t => t.metrics.fill_rate_pct || 0);
          const sVals = trajectories.map(t => t.metrics.spoilage_rate_pct || 0);
          minX = 0;
          maxX = Math.max(30, Math.ceil(Math.max(...xVals) + 2));
          minY = Math.max(0, Math.floor(Math.min(...yVals) - 2));
          maxY = Math.min(100, Math.ceil(Math.max(...yVals) + 1));
          minSpoil = Math.min(...sVals);
          maxSpoil = Math.max(minSpoil + 1, Math.max(...sVals));
        }

        function mapX(val) { return padL + ((val - minX) / Math.max(1e-6, maxX - minX)) * (w - padL - padR); }
        function mapY(val) { return (h - padB) - ((val - minY) / Math.max(1e-6, maxY - minY)) * (h - padT - padB); }

        // Grid lines
        ctx.strokeStyle = "rgba(148, 163, 184, 0.08)";
        ctx.lineWidth = 1;
        for (let i = 0; i <= 4; i++) {
          const y = padT + (i / 4) * (h - padT - padB);
          ctx.beginPath();
          ctx.moveTo(padL, y);
          ctx.lineTo(w - padR, y);
          ctx.stroke();

          const x = padL + (i / 4) * (w - padL - padR);
          ctx.beginPath();
          ctx.moveTo(x, padT);
          ctx.lineTo(x, h - padB);
          ctx.stroke();
        }

        // Full reference envelope (faint dotted guide to Gen 30)
        const allPareto = paretoFrontier.filter(p => p.is_pareto);
        allPareto.sort((a, b) => a.cost_reduction_pct - b.cost_reduction_pct);
        ctx.strokeStyle = "rgba(16, 185, 129, 0.2)";
        ctx.lineWidth = 1.5;
        ctx.setLineDash([2, 3]);
        ctx.beginPath();
        allPareto.forEach((p, idx) => {
          const px = mapX(p.cost_reduction_pct);
          const py = mapY(p.fill_rate_pct);
          if (idx === 0) ctx.moveTo(px, py);
          else ctx.lineTo(px, py);
        });
        ctx.stroke();
        ctx.setLineDash([]);

        // Dynamic Non-Dominated Pareto Frontier Envelope (active up to currentGen)
        const activePareto = allPareto.filter(p => p.generation <= currentGen);
        if (activePareto.length > 0) {
          const currPt = trajectories[currentGen];
          if (currPt && !activePareto.some(p => p.generation === currentGen)) {
            activePareto.push({
              generation: currentGen,
              cost_reduction_pct: currPt.metrics.cost_reduction_pct,
              fill_rate_pct: currPt.metrics.fill_rate_pct
            });
            activePareto.sort((a, b) => a.cost_reduction_pct - b.cost_reduction_pct);
          }

          ctx.strokeStyle = "#10B981";
          ctx.lineWidth = 2.5;
          ctx.setLineDash([4, 3]);
          ctx.beginPath();
          activePareto.forEach((p, idx) => {
            const px = mapX(p.cost_reduction_pct);
            const py = mapY(p.fill_rate_pct);
            if (idx === 0) ctx.moveTo(px, py);
            else ctx.lineTo(px, py);
          });
          ctx.stroke();
          ctx.setLineDash([]);
        }

        const keySet = new Set(Object.keys(milestones).map(k => parseInt(k, 10)));

        // Plot 31-Generation Bubbles with Spoilage / Penalty Gradient
        trajectories.forEach((t, gen) => {
          const m = t.metrics;
          const px = mapX(m.cost_reduction_pct);
          const py = mapY(m.fill_rate_pct);
          const isPassed = gen <= currentGen;

          const spoilNorm = Math.max(0, Math.min(1, (m.spoilage_rate_pct - minSpoil) / Math.max(1e-6, maxSpoil - minSpoil)));
          const r = Math.round(16 + spoilNorm * (244 - 16));
          const g = Math.round(185 - spoilNorm * (185 - 63));
          const b = Math.round(129 - spoilNorm * (129 - 94));
          const alpha = isPassed ? 0.85 : 0.2;

          const radius = gen === currentGen ? 7 : (keySet.has(gen) ? 5.5 : 4);

          ctx.fillStyle = "rgba(" + r + "," + g + "," + b + "," + alpha + ")";
          ctx.beginPath();
          ctx.arc(px, py, radius, 0, Math.PI * 2);
          ctx.fill();

          if (isPassed && keySet.has(gen)) {
            ctx.fillStyle = "#CBD5E1";
            ctx.font = "9px JetBrains Mono, monospace";
            ctx.fillText("G" + gen, px + 6, py - 4);
          }
        });

        // Hover ring if inspecting a specific generation bubble
        const targetGen = hoverGen !== undefined && hoverGen !== null ? hoverGen : hoveredParetoGen;
        if (targetGen !== null && trajectories[targetGen]) {
          const hm = trajectories[targetGen].metrics;
          const hx = mapX(hm.cost_reduction_pct);
          const hy = mapY(hm.fill_rate_pct);
          ctx.strokeStyle = "#F59E0B";
          ctx.lineWidth = 2;
          ctx.beginPath();
          ctx.arc(hx, hy, 9, 0, Math.PI * 2);
          ctx.stroke();
        }

        // Active Playhead Ring
        const currFrame = trajectories[currentGen];
        if (currFrame) {
          const cm = currFrame.metrics;
          const cx = mapX(cm.cost_reduction_pct);
          const cy = mapY(cm.fill_rate_pct);

          ctx.strokeStyle = "#06B6D4";
          ctx.lineWidth = 2.5;
          ctx.beginPath();
          ctx.arc(cx, cy, 10, 0, Math.PI * 2);
          ctx.stroke();

          ctx.fillStyle = "#06B6D4";
          ctx.font = "bold 10px JetBrains Mono, monospace";
          ctx.fillText("Gen " + currentGen, cx - 18, cy - 14);
        }

        // Axes and Labels
        ctx.fillStyle = "#94A3B8";
        ctx.font = "10px JetBrains Mono, monospace";
        ctx.fillText(minY.toFixed(1) + "%", padL - 38, h - padB + 3);
        ctx.fillText(maxY.toFixed(1) + "%", padL - 38, padT + 8);
        ctx.fillText("0%", padL, h - padB + 16);
        ctx.fillText("+" + maxX + "%", w - padR - 26, h - padB + 16);

        ctx.fillStyle = "#CBD5E1";
        ctx.font = "10px Plus Jakarta Sans, sans-serif";
        ctx.fillText("Cost Reduction % →", padL + (w - padL - padR) / 2 - 45, h - 8);

        ctx.fillStyle = "#10B981";
        ctx.fillText("● Active Pareto Envelope", padL + 10, padT + 12);
        ctx.fillStyle = "#F43F5E";
        ctx.fillText(isFleet ? "■ Late Penalty Gradient" : "■ Spoilage Gradient", padL + 10, padT + 26);
      }

      // 9. Retina Canvas 2D: Mode B 31-Generation Stacked Cost Component Waterfall
      function drawWaterfallChart(hoverColIdx) {
        const canvas = document.getElementById("canvas-convergence");
        if (!canvas) return;
        const ctx = canvas.getContext("2d");
        const rect = canvas.getBoundingClientRect();
        if (rect.width === 0 || rect.height === 0) return;

        const dpr = window.devicePixelRatio || 1;
        canvas.width = rect.width * dpr;
        canvas.height = rect.height * dpr;
        ctx.scale(dpr, dpr);

        const w = rect.width;
        const h = rect.height;
        const padL = 42, padR = 20, padT = 24, padB = 32;

        ctx.clearRect(0, 0, w, h);

        // Dynamic Columns from telemetry data
        const baseTot = (costWaterfall && costWaterfall.baseline_total) || 68410;
        const champTot = (costWaterfall && costWaterfall.champion_total) || 45238;
        const isFleet = currentUseCaseId === "fleet_routing";
        const maxCost = isFleet
          ? Math.ceil((Math.max(baseTot, champTot) * 1.15) / 500) * 500
          : 72000;

        function mapY(val) { return (h - padB) - (val / maxCost) * (h - padT - padB); }

        // Grid
        ctx.strokeStyle = "rgba(148, 163, 184, 0.08)";
        ctx.lineWidth = 1;
        for (let i = 0; i <= 4; i++) {
          const y = padT + (i / 4) * (h - padT - padB);
          ctx.beginPath();
          ctx.moveTo(padL, y);
          ctx.lineTo(w - padR, y);
          ctx.stroke();
        }

        const components = (costWaterfall && costWaterfall.components) || [
          { category: "Spoilage Waste", key: "spoilage", savings: 11945, savings_label: "-$11.9k", color: "#F43F5E" },
          { category: "Stockout Penalty", key: "stockout", savings: 9627, savings_label: "-$9.6k", color: "#F59E0B" },
          { category: "Holding Cost", key: "holding", savings: 1205, savings_label: "-$1.2k", color: "#38BDF8" },
          { category: "Ordering Cost", key: "ordering", savings: 395, savings_label: "-$395", color: "#14B8A6" }
        ];

        const fmtTotal = (v) => v >= 10000 ? "$" + (v / 1000).toFixed(1) + "k" : "$" + Math.round(v).toLocaleString();

        const cols = [
          { label: "Baseline", val: baseTot, isTotal: true, color: "#64748B", text: fmtTotal(baseTot) }
        ];

        const fleetKeyLabels = {
          holding: "Distance",
          spoilage: "Tardiness",
          stockout: "Overtime",
          ordering: "Dispatch"
        };

        components.forEach(c => {
          const colColor = c.color === "#A855F7" ? "#14B8A6" : c.color;
          const shortLabel = isFleet
            ? (fleetKeyLabels[c.key] || (c.key.charAt(0).toUpperCase() + c.key.slice(1)))
            : (c.key.charAt(0).toUpperCase() + c.key.slice(1));
          cols.push({
            label: shortLabel,
            category: c.category,
            delta: -Math.abs(c.savings),
            color: colColor,
            text: c.savings_label || ("-$" + Math.round(c.savings))
          });
        });

        cols.push({ label: "Champion", val: champTot, isTotal: true, color: "#10B981", text: fmtTotal(champTot) });

        const colW = (w - padL - padR) / cols.length;
        const barW = Math.min(38, colW - 12);

        let runningVal = baseTot;

        cols.forEach((col, idx) => {
          const x = padL + idx * colW + (colW - barW) / 2;

          if (hoverColIdx === idx) {
            ctx.fillStyle = "rgba(6, 182, 212, 0.08)";
            ctx.fillRect(padL + idx * colW, padT, colW, h - padT - padB);
          }

          if (col.isTotal) {
            const topY = mapY(col.val);
            const botY = mapY(0);
            ctx.fillStyle = col.color;
            ctx.fillRect(x, topY, barW, botY - topY);

            ctx.fillStyle = "#FFFFFF";
            ctx.font = "bold 10px JetBrains Mono, monospace";
            ctx.textAlign = "center";
            ctx.fillText(col.text, x + barW / 2, topY - 6);
          } else {
            const prevY = mapY(runningVal);
            const nextVal = runningVal + col.delta;
            const nextY = mapY(nextVal);
            const barH = Math.max(3, nextY - prevY);

            ctx.fillStyle = col.color;
            ctx.fillRect(x, prevY, barW, barH);

            ctx.strokeStyle = "rgba(148, 163, 184, 0.3)";
            ctx.setLineDash([2, 2]);
            ctx.beginPath();
            ctx.moveTo(x - (colW - barW) / 2, prevY);
            ctx.lineTo(x, prevY);
            ctx.stroke();
            ctx.setLineDash([]);

            ctx.fillStyle = col.color;
            ctx.font = "bold 9.5px JetBrains Mono, monospace";
            ctx.textAlign = "center";
            ctx.fillText(col.text, x + barW / 2, nextY + 12);

            runningVal = nextVal;
          }

          ctx.fillStyle = "#94A3B8";
          ctx.font = "9.5px Plus Jakarta Sans, sans-serif";
          ctx.textAlign = "center";
          ctx.fillText(col.label, x + barW / 2, h - 10);
        });
        ctx.textAlign = "start";

        // Axis
        ctx.fillStyle = "#94A3B8";
        ctx.font = "10px JetBrains Mono, monospace";
        ctx.fillText("$0", padL - 24, h - padB + 3);
        ctx.fillText(isFleet ? "$" + (maxCost / 1000).toFixed(1) + "k" : "$70k", padL - 38, padT + 8);
      }

      // Wire interactive hover on #canvas-convergence
      const canvasConvEl = document.getElementById("canvas-convergence");
      const tooltipConvEl = document.getElementById("tooltip-convergence");
      if (canvasConvEl && tooltipConvEl) {
        canvasConvEl.addEventListener("mousemove", (e) => {
          const rect = canvasConvEl.getBoundingClientRect();
          const relX = e.clientX - rect.left;
          const relY = e.clientY - rect.top;

          if (canvas2Mode === "pareto") {
            const padL = 44, padR = 24, padT = 24, padB = 34;
            const isFleet = currentUseCaseId === "fleet_routing";
            let minX = 0, maxX = 36, minY = 90.8, maxY = 94.0;
            if (isFleet && trajectories.length > 0) {
              const xVals = trajectories.map(t => t.metrics.cost_reduction_pct || 0);
              const yVals = trajectories.map(t => t.metrics.fill_rate_pct || 0);
              maxX = Math.max(30, Math.ceil(Math.max(...xVals) + 2));
              minY = Math.max(0, Math.floor(Math.min(...yVals) - 2));
              maxY = Math.min(100, Math.ceil(Math.max(...yVals) + 1));
            }
            let bestGen = null;
            let bestDist = 400;
            trajectories.forEach((t, g) => {
              const px = padL + ((t.metrics.cost_reduction_pct - minX) / Math.max(1e-6, maxX - minX)) * (rect.width - padL - padR);
              const py = (rect.height - padB) - ((t.metrics.fill_rate_pct - minY) / Math.max(1e-6, maxY - minY)) * (rect.height - padT - padB);
              const d2 = (relX - px) * (relX - px) + (relY - py) * (relY - py);
              if (d2 < bestDist) {
                bestDist = d2;
                bestGen = g;
              }
            });
            hoveredParetoGen = bestGen;
            drawParetoChart(bestGen);
            if (bestGen !== null && trajectories[bestGen]) {
              const m = trajectories[bestGen].metrics;
              tooltipConvEl.replaceChildren();
              tooltipConvEl.appendChild(
                el(
                  "span",
                  null,
                  "Gen " + bestGen +
                  " | Cost: -" + m.cost_reduction_pct.toFixed(1) + "%" +
                  " | SLA: " + m.fill_rate_pct.toFixed(1) + "%"
                )
              );
              tooltipConvEl.classList.add("visible");
            } else {
              tooltipConvEl.classList.remove("visible");
            }
          } else {
            const padL = 42, padR = 20;
            const colCount = 6;
            const colW = (rect.width - padL - padR) / colCount;
            const colIdx = Math.floor((relX - padL) / Math.max(1, colW));
            if (colIdx >= 0 && colIdx < colCount) {
              drawWaterfallChart(colIdx);
              const comps = (costWaterfall && costWaterfall.components) || [];
              let labelText = "";
              if (colIdx === 0) {
                labelText = "Baseline Total: $" + Math.round((costWaterfall && costWaterfall.baseline_total) || 68410).toLocaleString();
              } else if (colIdx === colCount - 1) {
                labelText = "Champion Total: $" + Math.round((costWaterfall && costWaterfall.champion_total) || 45238).toLocaleString();
              } else if (comps[colIdx - 1]) {
                const c = comps[colIdx - 1];
                labelText = c.category + ": " + c.savings_label + " (" + c.pct_of_total_savings + "% of savings)";
              }
              if (labelText) {
                tooltipConvEl.replaceChildren();
                tooltipConvEl.appendChild(el("span", null, labelText));
                tooltipConvEl.classList.add("visible");
              }
            }
          }
        });

        canvasConvEl.addEventListener("mouseleave", () => {
          hoveredParetoGen = null;
          tooltipConvEl.classList.remove("visible");
          drawCanvas2Chart(null);
        });
      }

      // 10. Dual-Policy What-If Simulation Sandbox (Multi-Domain Aware)
      const skuSelect = document.getElementById("whatif-sku");
      const slideLead = document.getElementById("slide-leadtime");
      const slidePromo = document.getElementById("slide-promo");
      const slideSpoil = document.getElementById("slide-spoil");
      const slideStock = document.getElementById("slide-stockout");

      let whatIfReqSeq = 0;
      let whatIfDebounceTimer = null;

      function applyWhatIfMetrics(
        isFleet,
        baseFillRate,
        baseSpoilUnits,
        baseSpoilCost,
        baseDailyCost,
        baseOrderUp,
        champFillRate,
        champSpoilUnits,
        champSpoilCost,
        champDailyCost,
        champOrderUp,
        resilienceText
      ) {
        const unitLabel = isFleet ? " hrs ($" : " units ($";
        const loadSuffix = isFleet ? " stops" : " units";
        document.getElementById("val-base-fill").textContent = baseFillRate.toFixed(1) + "%";
        document.getElementById("val-base-spoil").textContent =
          baseSpoilUnits.toFixed(1) + unitLabel + Math.round(baseSpoilCost) + ")";
        document.getElementById("val-base-cost").textContent =
          "$" + Math.round(baseDailyCost).toLocaleString() + " / day";
        document.getElementById("val-base-orderup").textContent = baseOrderUp + loadSuffix;

        const baseSlaBadge = document.getElementById("badge-base-sla");
        if (baseSlaBadge) {
          if (baseFillRate >= 95.0) {
            baseSlaBadge.textContent = "SLA Compliant";
            baseSlaBadge.className = "badge-diff positive";
          } else {
            baseSlaBadge.textContent = "SLA Breach (-" + (95.0 - baseFillRate).toFixed(1) + "%)";
            baseSlaBadge.className = "badge-diff negative";
          }
        }

        document.getElementById("val-champ-fill").textContent = champFillRate.toFixed(1) + "%";
        document.getElementById("val-champ-spoil").textContent =
          champSpoilUnits.toFixed(1) + unitLabel + Math.round(champSpoilCost) + ")";
        document.getElementById("val-champ-cost").textContent =
          "$" + Math.round(champDailyCost).toLocaleString() + " / day";
        document.getElementById("val-champ-orderup").textContent =
          champOrderUp + loadSuffix + " (dynamic)";

        if (resilienceText) {
          document.getElementById("whatif-resilience-text").textContent = resilienceText;
        } else {
          const savedPerDay = Math.max(0, Math.round(baseDailyCost - champDailyCost));
          const fillDiff = champFillRate - baseFillRate;
          const metricWord = isFleet ? "on-time SLA" : "fill rate";
          document.getElementById("whatif-resilience-text").textContent =
            "Champion prevents SLA deficit (+" +
            fillDiff.toFixed(1) +
            "% " +
            metricWord +
            ") and saves +$" +
            savedPerDay.toLocaleString() +
            "/day under disruption.";
        }

        drawWhatIfDualCanvas(
          baseFillRate,
          champFillRate,
          baseSpoilUnits,
          champSpoilUnits,
          baseDailyCost,
          champDailyCost
        );
      }

      function updateWhatIfSimulation() {
        const skuIdx = parseInt((skuSelect && skuSelect.value) || "0", 10);
        const sku = archetypes[skuIdx] || archetypes[0] || {
          shelf_life_days: 3,
          lead_time_days: 1,
          holding_cost: 0.4,
          spoilage_cost: 5.5,
          stockout_penalty: 9.0
        };

        const leadDelay = parseInt((slideLead && slideLead.value) || "0", 10);
        const promoPct = parseInt((slidePromo && slidePromo.value) || "0", 10);
        const spoilMult = parseInt((slideSpoil && slideSpoil.value) || "10", 10) / 10.0;
        const stockMult = parseInt((slideStock && slideStock.value) || "10", 10) / 10.0;
        const isFleet = currentUseCaseId === "fleet_routing";

        document.getElementById("val-leadtime").textContent = isFleet
          ? "+" + leadDelay * 12 + " mins"
          : "+" + leadDelay + " days";
        document.getElementById("val-promo").textContent = "+" + promoPct + "%";
        document.getElementById("val-spoil").textContent = spoilMult.toFixed(1) + "x";
        document.getElementById("val-stockout").textContent = stockMult.toFixed(1) + "x";

        // 1) Immediate Client-Side Fallback Calculation (Offline-Ready, Domain-Calibrated)
        let baseOrderUp, baseFillRate, baseSpoilUnits, baseSpoilCost, baseDailyCost;
        let champOrderUp, champFillRate, champSpoilUnits, champSpoilCost, champDailyCost;

        if (isFleet) {
          baseOrderUp = 50;
          baseFillRate = Math.max(
            42.0,
            70.0 - skuIdx * 2.0 - leadDelay * 4.2 - (promoPct / 100.0) * 9.5
          );
          baseSpoilUnits = Math.max(
            4.0,
            22.0 - skuIdx * 4.5 + leadDelay * 3.8 + (promoPct / 100.0) * 8.5
          );
          baseSpoilCost = baseSpoilUnits * sku.spoilage_cost * spoilMult;
          baseDailyCost = Math.round(
            1433.0 * sku.holding_cost * (0.7 + 0.3 * stockMult) +
              baseSpoilCost +
              300.0 +
              Math.max(0, 95.0 - baseFillRate) * 0.35 * stockMult * sku.stockout_penalty
          );

          champOrderUp = 50;
          champFillRate = Math.min(
            98.5,
            Math.max(78.0, 96.0 - skuIdx * 0.8 - leadDelay * 1.4 - (promoPct / 100.0) * 3.2)
          );
          champSpoilUnits = Math.max(
            0.5,
            2.8 - skuIdx * 0.6 + leadDelay * 0.9 + (promoPct / 100.0) * 2.4
          );
          champSpoilCost = champSpoilUnits * sku.spoilage_cost * spoilMult;
          champDailyCost = Math.round(
            1118.0 * sku.holding_cost * (0.7 + 0.3 * stockMult) +
              champSpoilCost +
              300.0 +
              Math.max(0, 95.0 - champFillRate) * 0.15 * stockMult * sku.stockout_penalty
          );
        } else {
          baseOrderUp = Math.round(
            32.0 * (sku.lead_time_days + 1) + 1.65 * 14.0 * Math.sqrt(sku.lead_time_days + 1)
          );
          baseFillRate = Math.max(68.0, 91.2 - leadDelay * 4.4 - (promoPct / 150.0) * 8.2);
          baseSpoilUnits = Math.max(
            1.5,
            (4.8 + leadDelay * 1.6 + (promoPct / 100.0) * 2.2) *
              spoilMult *
              (14.0 / sku.shelf_life_days)
          );
          baseSpoilCost = baseSpoilUnits * sku.spoilage_cost;
          baseDailyCost = Math.round(
            28.0 * (sku.holding_cost / 0.25) +
              baseSpoilCost +
              Math.max(0, 95.0 - baseFillRate) * 22.0 * stockMult * sku.stockout_penalty
          );

          champOrderUp = Math.round(
            32.0 * (1.0 + promoPct / 100.0) * (sku.lead_time_days + leadDelay + 1) + 38.0
          );
          champFillRate = Math.min(
            98.8,
            Math.max(92.2, 94.8 - leadDelay * 0.7 + (promoPct / 200.0) * 1.2)
          );
          champSpoilUnits = Math.max(
            0.6,
            (1.8 + leadDelay * 0.4 + (promoPct / 100.0) * 0.8) *
              spoilMult *
              (7.0 / sku.shelf_life_days)
          );
          champSpoilCost = champSpoilUnits * sku.spoilage_cost;
          champDailyCost = Math.round(
            24.0 * (sku.holding_cost / 0.25) +
              champSpoilCost +
              Math.max(0, 95.0 - champFillRate) * 22.0 * stockMult * sku.stockout_penalty
          );
        }

        applyWhatIfMetrics(
          isFleet,
          baseFillRate,
          baseSpoilUnits,
          baseSpoilCost,
          baseDailyCost,
          baseOrderUp,
          champFillRate,
          champSpoilUnits,
          champSpoilCost,
          champDailyCost,
          champOrderUp,
          null
        );

        // 2) Live Backend Digital Twin Simulation (POST /api/simulate) when online
        if (
          typeof fetch === "function" &&
          window.location &&
          (window.location.protocol === "http:" || window.location.protocol === "https:")
        ) {
          whatIfReqSeq += 1;
          const reqId = whatIfReqSeq;
          const targetUseCase = currentUseCaseId;
          if (whatIfDebounceTimer) {
            clearTimeout(whatIfDebounceTimer);
          }
          whatIfDebounceTimer = setTimeout(() => {
            fetch("/api/simulate", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                use_case: targetUseCase,
                archetype_index: skuIdx,
                lead_time_delay: leadDelay,
                promo_spike_pct: promoPct,
                spoilage_multiplier: spoilMult,
                stockout_multiplier: stockMult
              })
            })
              .then(res => (res.ok ? res.json() : Promise.reject(new Error("Simulate HTTP error"))))
              .then(sim => {
                if (reqId !== whatIfReqSeq || targetUseCase !== currentUseCaseId) return;
                if (!sim || !sim.baseline || !sim.champion) return;
                const b = sim.baseline;
                const c = sim.champion;
                const comp = sim.comparison || {};
                applyWhatIfMetrics(
                  targetUseCase === "fleet_routing",
                  Number(b.fill_rate_pct ?? baseFillRate),
                  Number(b.spoilage_units ?? baseSpoilUnits),
                  Number(b.spoilage_cost ?? baseSpoilCost),
                  Number(b.daily_cost ?? baseDailyCost),
                  Number(b.order_up_to ?? baseOrderUp),
                  Number(c.fill_rate_pct ?? champFillRate),
                  Number(c.spoilage_units ?? champSpoilUnits),
                  Number(c.spoilage_cost ?? champSpoilCost),
                  Number(c.daily_cost ?? champDailyCost),
                  Number(c.order_up_to ?? champOrderUp),
                  comp.resilience_summary || null
                );
              })
              .catch(() => {
                // Keep client-side fallback metrics when offline
              });
          }, 50);
        }
      }

      function drawWhatIfDualCanvas(bFill, cFill, bSpoil, cSpoil, bCost, cCost) {
        const canvas = document.getElementById("canvas-whatif");
        if (!canvas) return;
        const ctx = canvas.getContext("2d");
        const rect = canvas.getBoundingClientRect();
        if (rect.width === 0 || rect.height === 0) return;

        const dpr = window.devicePixelRatio || 1;
        canvas.width = rect.width * dpr;
        canvas.height = rect.height * dpr;
        ctx.scale(dpr, dpr);

        const w = rect.width;
        const h = rect.height;
        ctx.clearRect(0, 0, w, h);

        const padL = 40, padR = 20, padT = 20, padB = 28;
        const groupW = (w - padL - padR) / 3;
        const barW = groupW * 0.34;
        const isFleet = currentUseCaseId === "fleet_routing";

        const maxSpoil = Math.max(20, Math.ceil(Math.max(bSpoil, cSpoil) * 1.25));
        const maxCost = Math.max(2000, Math.ceil(Math.max(bCost, cCost) * 1.25));

        const groups = [
          { label: isFleet ? "On-Time SLA %" : "Fill Rate %", bVal: bFill, cVal: cFill, maxVal: 100, bText: bFill.toFixed(1) + "%", cText: cFill.toFixed(1) + "%" },
          { label: isFleet ? "Tardiness (hrs)" : "Spoilage Units", bVal: bSpoil, cVal: cSpoil, maxVal: maxSpoil, bText: bSpoil.toFixed(1), cText: cSpoil.toFixed(1) },
          { label: "Cost ($/day)", bVal: bCost, cVal: cCost, maxVal: maxCost, bText: "$" + Math.round(bCost).toLocaleString(), cText: "$" + Math.round(cCost).toLocaleString() }
        ];

        groups.forEach((g, idx) => {
          const gx = padL + idx * groupW;

          const bh = Math.min(h - padT - padB, (g.bVal / g.maxVal) * (h - padT - padB));
          ctx.fillStyle = "#64748B";
          ctx.fillRect(gx + 12, (h - padB) - bh, barW, bh);

          const ch = Math.min(h - padT - padB, (g.cVal / g.maxVal) * (h - padT - padB));
          ctx.fillStyle = "#10B981";
          ctx.fillRect(gx + 16 + barW, (h - padB) - ch, barW, ch);

          ctx.fillStyle = "#CBD5E1";
          ctx.font = "9.5px JetBrains Mono, monospace";
          ctx.fillText(g.bText, gx + 10, Math.max(padT - 2, (h - padB) - bh - 4));
          ctx.fillStyle = "#10B981";
          ctx.fillText(g.cText, gx + 16 + barW, Math.max(padT - 2, (h - padB) - ch - 4));

          ctx.fillStyle = "#94A3B8";
          ctx.font = "10.5px Plus Jakarta Sans, sans-serif";
          ctx.fillText(g.label, gx + 18, h - 8);
        });

        const slaY = (h - padB) - (95.0 / 100.0) * (h - padT - padB);
        ctx.strokeStyle = "rgba(244, 63, 94, 0.7)";
        ctx.setLineDash([3, 2]);
        ctx.beginPath();
        ctx.moveTo(padL, slaY);
        ctx.lineTo(padL + groupW - 10, slaY);
        ctx.stroke();
        ctx.setLineDash([]);

        ctx.fillStyle = "#F43F5E";
        ctx.font = "9px JetBrains Mono, monospace";
        ctx.fillText("95% SLA", padL + groupW - 55, slaY - 3);

        ctx.fillStyle = "#64748B";
        ctx.fillText(isFleet ? "■ Baseline (Greedy)" : "■ Baseline (s,S)", w - padR - 205, padT - 4);
        ctx.fillStyle = "#10B981";
        ctx.fillText("■ Champion", w - padR - 80, padT - 4);
      }

      skuSelect?.addEventListener("change", updateWhatIfSimulation);
      [skuSelect, slideLead, slidePromo, slideSpoil, slideStock].forEach(ctrl => {
        ctrl?.addEventListener("input", updateWhatIfSimulation);
      });

      // 11. Zero-Dependency Stateful Python Syntax Lexer & Client-Side LCS Diff Engine
      const PY_KEYWORDS = new Set([
        "and", "as", "assert", "async", "await", "break", "class", "continue",
        "def", "del", "elif", "else", "except", "finally", "for", "from",
        "global", "if", "import", "in", "is", "lambda", "nonlocal", "not",
        "or", "pass", "raise", "return", "try", "while", "with", "yield",
        "True", "False", "None"
      ]);

      const PY_BUILTINS = new Set([
        "abs", "all", "any", "bool", "dict", "enumerate", "float", "int",
        "len", "list", "map", "max", "min", "print", "range", "round",
        "set", "str", "sum", "tuple", "zip", "np", "numpy", "zeros", "ones",
        "where", "clip", "maximum", "minimum", "mean", "std", "ceil", "roll",
        "copy", "shape", "ndarray", "float64", "arange"
      ]);

      function tokenizePythonLine(line, lexerState) {
        const tokens = [];
        let i = 0;
        const len = line.length;

        if (lexerState.inDocstring) {
          const closeIdx = line.indexOf(lexerState.docDelim, i);
          if (closeIdx === -1) {
            tokens.push({ text: line, type: "docstring" });
            return tokens;
          } else {
            const end = closeIdx + 3;
            tokens.push({ text: line.slice(0, end), type: "docstring" });
            lexerState.inDocstring = false;
            lexerState.docDelim = null;
            i = end;
          }
        }

        while (i < len) {
          const wsMatch = line.slice(i).match(/^\s+/);
          if (wsMatch) {
            tokens.push({ text: wsMatch[0], type: "plain" });
            i += wsMatch[0].length;
            continue;
          }

          const tri3 = line.slice(i, i + 3);
          if (tri3 === '"""' || tri3 === "'''") {
            const delim = tri3;
            const closeIdx = line.indexOf(delim, i + 3);
            if (closeIdx === -1) {
              tokens.push({ text: line.slice(i), type: "docstring" });
              lexerState.inDocstring = true;
              lexerState.docDelim = delim;
              break;
            } else {
              tokens.push({ text: line.slice(i, closeIdx + 3), type: "docstring" });
              i = closeIdx + 3;
              continue;
            }
          }

          if (line[i] === "#") {
            tokens.push({ text: line.slice(i), type: "comment" });
            break;
          }

          if (line[i] === '"' || line[i] === "'") {
            const q = line[i];
            let j = i + 1;
            while (j < len && line[j] !== q) {
              if (line[j] === "\\") j++;
              j++;
            }
            tokens.push({ text: line.slice(i, j + 1), type: "str" });
            i = j + 1;
            continue;
          }

          const numMatch = line.slice(i).match(/^[0-9]+(\.[0-9]+)?([eE][+-]?[0-9]+)?/);
          if (numMatch && (i === 0 || !/[a-zA-Z_]/.test(line[i - 1]))) {
            tokens.push({ text: numMatch[0], type: "num" });
            i += numMatch[0].length;
            continue;
          }

          const wordMatch = line.slice(i).match(/^[a-zA-Z_][a-zA-Z0-9_]*/);
          if (wordMatch) {
            const word = wordMatch[0];
            if (PY_KEYWORDS.has(word)) {
              tokens.push({ text: word, type: "kw" });
            } else if (PY_BUILTINS.has(word)) {
              tokens.push({ text: word, type: "builtin" });
            } else {
              tokens.push({ text: word, type: "ident" });
            }
            i += word.length;
            continue;
          }

          const op2Match = line.slice(i).match(/^(==|!=|<=|>=|\+=|-=|\*=|\/=|->|\*\*|\/\/)/);
          if (op2Match) {
            tokens.push({ text: op2Match[0], type: "op" });
            i += op2Match[0].length;
            continue;
          }

          const ch = line[i];
          if ("=+-*/%<>@&|^~".includes(ch)) {
            tokens.push({ text: ch, type: "op" });
          } else if ("()[]{}:,.;".includes(ch)) {
            tokens.push({ text: ch, type: "punct" });
          } else {
            tokens.push({ text: ch, type: "plain" });
          }
          i++;
        }

        return tokens;
      }

      function tokenizePythonCode(code) {
        const lines = code.split(/\r?\n/);
        const state = { inDocstring: false, docDelim: null };
        return lines.map(line => tokenizePythonLine(line, state));
      }

      function computeLcsDiff(linesA, linesB) {
        const n = linesA.length;
        const m = linesB.length;
        const dp = Array.from({ length: n + 1 }, () => new Int32Array(m + 1));

        for (let i = 1; i <= n; i++) {
          for (let j = 1; j <= m; j++) {
            if (linesA[i - 1] === linesB[j - 1]) {
              dp[i][j] = dp[i - 1][j - 1] + 1;
            } else {
              dp[i][j] = Math.max(dp[i - 1][j], dp[i][j - 1]);
            }
          }
        }

        let i = n, j = m;
        const diff = [];
        while (i > 0 || j > 0) {
          if (i > 0 && j > 0 && linesA[i - 1] === linesB[j - 1]) {
            diff.push({ type: "same", lineA: i, lineB: j, textA: linesA[i - 1], textB: linesB[j - 1] });
            i--; j--;
          } else if (j > 0 && (i === 0 || dp[i][j - 1] >= dp[i - 1][j])) {
            diff.push({ type: "add", lineB: j, textB: linesB[j - 1] });
            j--;
          } else {
            diff.push({ type: "del", lineA: i, textA: linesA[i - 1] });
            i--;
          }
        }

        diff.reverse();
        return diff;
      }

      function computeTokenLcs(tokensA, tokensB) {
        const nonWsA = [];
        tokensA.forEach((tok, idx) => {
          if (tok.type !== "plain") nonWsA.push({ tok, idx });
        });

        const nonWsB = [];
        tokensB.forEach((tok, idx) => {
          if (tok.type !== "plain") nonWsB.push({ tok, idx });
        });

        const n = nonWsA.length;
        const m = nonWsB.length;
        const dp = Array.from({ length: n + 1 }, () => new Int32Array(m + 1));

        for (let i = 1; i <= n; i++) {
          for (let j = 1; j <= m; j++) {
            if (nonWsA[i - 1].tok.text === nonWsB[j - 1].tok.text) {
              dp[i][j] = dp[i - 1][j - 1] + 1;
            } else {
              dp[i][j] = Math.max(dp[i - 1][j], dp[i][j - 1]);
            }
          }
        }

        const matchedA = new Set();
        const matchedB = new Set();
        let i = n, j = m;
        while (i > 0 && j > 0) {
          if (nonWsA[i - 1].tok.text === nonWsB[j - 1].tok.text) {
            matchedA.add(nonWsA[i - 1].idx);
            matchedB.add(nonWsB[j - 1].idx);
            i--; j--;
          } else if (dp[i][j - 1] >= dp[i - 1][j]) {
            j--;
          } else {
            i--;
          }
        }

        return { matchedA, matchedB };
      }

      function renderTokensToSpan(tokens, container, wordDiffClass, matchedSet) {
        tokens.forEach((tok, idx) => {
          if (!tok.text) return;
          const span = el("span", "tok-" + tok.type, tok.text);
          if (wordDiffClass && matchedSet && tok.type !== "plain" && !matchedSet.has(idx)) {
            span.classList.add(wordDiffClass);
          }
          container.appendChild(span);
        });
      }

      function updateStepperActivePreset() {
        const pairKey = leftMilestoneKey + "-" + rightMilestoneKey;
        document.querySelectorAll(".diff-stepper-btn[data-pair]").forEach(b => {
          if (b.getAttribute("data-pair") === pairKey) {
            b.classList.add("active");
          } else {
            b.classList.remove("active");
          }
        });
      }

      function renderCurrentDiff() {
        if (!diffTableBody) return;
        diffTableBody.replaceChildren();

        const baseM = milestones[leftMilestoneKey] || milestones["0"];
        const evoM = milestones[rightMilestoneKey] || milestones["30"];

        const codeA = baseM.evolve_block || "";
        const codeB = evoM.evolve_block || "";

        const linesA = codeA.split(/\r?\n/);
        const linesB = codeB.split(/\r?\n/);

        const allTokensA = tokenizePythonCode(codeA);
        const allTokensB = tokenizePythonCode(codeB);

        const rawDiff = computeLcsDiff(linesA, linesB);

        let addCount = 0, delCount = 0, sameCount = 0;
        rawDiff.forEach(d => {
          if (d.type === "add") addCount++;
          else if (d.type === "del") delCount++;
          else sameCount++;
        });

        document.getElementById("diff-stat-add").textContent = "+" + addCount + " additions";
        document.getElementById("diff-stat-del").textContent = "-" + delCount + " deletions";
        document.getElementById("diff-stat-same").textContent = sameCount + " unchanged";

        document.getElementById("diff-banner-title").textContent = baseM.title + " ➔ " + evoM.title;
        document.getElementById("diff-banner-desc").textContent = evoM.description;

        const innContainer = document.getElementById("diff-innovations-pills");
        if (innContainer) {
          innContainer.replaceChildren();
          const inns = evoM.key_innovations || [];
          inns.forEach(inn => {
            innContainer.appendChild(el("span", "pill-inn", "★ " + inn));
          });
        }

        document.getElementById("diff-header-left").textContent = baseM.title;
        document.getElementById("diff-header-right").textContent = evoM.title;

        if (diffTableHeader) {
          diffTableHeader.className = "diff-table-header " + (diffViewMode === "split" ? "split" : "unified");
          const rightHeader = document.getElementById("diff-header-right");
          if (rightHeader) rightHeader.classList.toggle("is-hidden", diffViewMode !== "split");
        }

        updateStepperActivePreset();

        const renderRows = [];
        let k = 0;
        while (k < rawDiff.length) {
          const item = rawDiff[k];
          if (item.type === "same") {
            renderRows.push({ type: "same", item: item });
            k++;
          } else {
            const dels = [];
            const adds = [];
            while (k < rawDiff.length && rawDiff[k].type === "del") {
              dels.push(rawDiff[k]);
              k++;
            }
            while (k < rawDiff.length && rawDiff[k].type === "add") {
              adds.push(rawDiff[k]);
              k++;
            }

            if (diffViewMode === "split") {
              const maxLen = Math.max(dels.length, adds.length);
              for (let r = 0; r < maxLen; r++) {
                renderRows.push({
                  type: "change",
                  delItem: dels[r] || null,
                  addItem: adds[r] || null
                });
              }
            } else {
              dels.forEach(d => renderRows.push({ type: "change-del", delItem: d }));
              adds.forEach(a => renderRows.push({ type: "change-add", addItem: a }));
            }
          }
        }

        let idx = 0;
        while (idx < renderRows.length) {
          if (renderRows[idx].type === "same") {
            let runEnd = idx;
            while (runEnd < renderRows.length && renderRows[runEnd].type === "same") {
              runEnd++;
            }
            const runLen = runEnd - idx;

            if (diffFoldUnchanged && runLen >= 7) {
              const foldStart = idx + 2;
              const foldEnd = runEnd - 2;
              const foldCount = foldEnd - foldStart;

              for (let i = idx; i < foldStart; i++) {
                diffTableBody.appendChild(buildDiffRowElement(renderRows[i], allTokensA, allTokensB));
              }

              const foldRow = el("div", "diff-fold-row");
              foldRow.textContent = "↕ ... " + foldCount + " unchanged lines hidden (click to expand) ...";
              const hiddenRows = renderRows.slice(foldStart, foldEnd);
              foldRow.addEventListener("click", () => {
                const frag = document.createDocumentFragment();
                hiddenRows.forEach(hr => {
                  frag.appendChild(buildDiffRowElement(hr, allTokensA, allTokensB));
                });
                diffTableBody.insertBefore(frag, foldRow);
                foldRow.remove();
              });
              diffTableBody.appendChild(foldRow);

              for (let i = foldEnd; i < runEnd; i++) {
                diffTableBody.appendChild(buildDiffRowElement(renderRows[i], allTokensA, allTokensB));
              }

              idx = runEnd;
              continue;
            }
          }

          diffTableBody.appendChild(buildDiffRowElement(renderRows[idx], allTokensA, allTokensB));
          idx++;
        }
      }

      function buildDiffRowElement(rRow, allTokensA, allTokensB) {
        const rowEl = el("div", "diff-row " + diffViewMode);

        if (diffViewMode === "split") {
          const leftCell = el("div", "diff-cell split-left");
          const rightCell = el("div", "diff-cell split-right");

          if (rRow.type === "same") {
            const it = rRow.item;
            const toksA = allTokensA[it.lineA - 1] || [];
            const toksB = allTokensB[it.lineB - 1] || [];

            leftCell.appendChild(el("span", "diff-gutter-num", it.lineA));
            leftCell.appendChild(el("span", "diff-gutter-badge", " "));
            const codeLeft = el("span", "diff-line-code");
            renderTokensToSpan(toksA, codeLeft, null, null);
            leftCell.appendChild(codeLeft);

            rightCell.appendChild(el("span", "diff-gutter-num", it.lineB));
            rightCell.appendChild(el("span", "diff-gutter-badge", " "));
            const codeRight = el("span", "diff-line-code");
            renderTokensToSpan(toksB, codeRight, null, null);
            rightCell.appendChild(codeRight);
          } else {
            const del = rRow.delItem;
            const add = rRow.addItem;

            let tokenLcs = null;
            if (del && add) {
              const toksA = allTokensA[del.lineA - 1] || [];
              const toksB = allTokensB[add.lineB - 1] || [];
              tokenLcs = computeTokenLcs(toksA, toksB);
            }

            if (del) {
              const toksA = allTokensA[del.lineA - 1] || [];
              leftCell.classList.add("diff-row-del");
              leftCell.appendChild(el("span", "diff-gutter-num", del.lineA));
              leftCell.appendChild(el("span", "diff-gutter-badge", "-"));
              const codeLeft = el("span", "diff-line-code");
              renderTokensToSpan(toksA, codeLeft, "diff-word-del", tokenLcs ? tokenLcs.matchedA : null);
              leftCell.appendChild(codeLeft);
            } else {
              leftCell.classList.add("diff-cell-empty");
            }

            if (add) {
              const toksB = allTokensB[add.lineB - 1] || [];
              rightCell.classList.add("diff-row-add");
              rightCell.appendChild(el("span", "diff-gutter-num", add.lineB));
              rightCell.appendChild(el("span", "diff-gutter-badge", "+"));
              const codeRight = el("span", "diff-line-code");
              renderTokensToSpan(toksB, codeRight, "diff-word-add", tokenLcs ? tokenLcs.matchedB : null);
              rightCell.appendChild(codeRight);
            } else {
              rightCell.classList.add("diff-cell-empty");
            }
          }

          rowEl.appendChild(leftCell);
          rowEl.appendChild(rightCell);
        } else {
          if (rRow.type === "same") {
            const it = rRow.item;
            const toks = allTokensA[it.lineA - 1] || [];
            const cell = el("div", "diff-cell unified");
            cell.appendChild(el("span", "diff-gutter-num", it.lineA));
            cell.appendChild(el("span", "diff-gutter-num", it.lineB));
            cell.appendChild(el("span", "diff-gutter-badge", " "));
            const code = el("span", "diff-line-code");
            renderTokensToSpan(toks, code, null, null);
            cell.appendChild(code);
            rowEl.appendChild(cell);
          } else if (rRow.type === "change-del") {
            const del = rRow.delItem;
            const toks = allTokensA[del.lineA - 1] || [];
            const cellDel = el("div", "diff-cell unified diff-row-del");
            cellDel.appendChild(el("span", "diff-gutter-num", del.lineA));
            cellDel.appendChild(el("span", "diff-gutter-num", " "));
            cellDel.appendChild(el("span", "diff-gutter-badge", "-"));
            const code = el("span", "diff-line-code");
            renderTokensToSpan(toks, code, null, null);
            cellDel.appendChild(code);
            rowEl.appendChild(cellDel);
          } else if (rRow.type === "change-add") {
            const add = rRow.addItem;
            const toks = allTokensB[add.lineB - 1] || [];
            const cellAdd = el("div", "diff-cell unified diff-row-add");
            cellAdd.appendChild(el("span", "diff-gutter-num", " "));
            cellAdd.appendChild(el("span", "diff-gutter-num", add.lineB));
            cellAdd.appendChild(el("span", "diff-gutter-badge", "+"));
            const code = el("span", "diff-line-code");
            renderTokensToSpan(toks, code, null, null);
            cellAdd.appendChild(code);
            rowEl.appendChild(cellAdd);
          }
        }

        return rowEl;
      }

      document.querySelectorAll(".diff-stepper-btn[data-pair]").forEach(btn => {
        btn.addEventListener("click", () => {
          const pair = btn.getAttribute("data-pair").split("-");
          leftMilestoneKey = pair[0];
          rightMilestoneKey = pair[1];

          if (diffSelectBase) diffSelectBase.value = leftMilestoneKey;
          if (diffSelectEvolved) diffSelectEvolved.value = rightMilestoneKey;

          renderCurrentDiff();
        });
      });

      if (diffSelectBase && diffSelectEvolved) {
        diffSelectBase.addEventListener("change", () => {
          leftMilestoneKey = diffSelectBase.value;
          renderCurrentDiff();
        });
        diffSelectEvolved.addEventListener("change", () => {
          rightMilestoneKey = diffSelectEvolved.value;
          renderCurrentDiff();
        });
      }

      if (btnViewSplit && btnViewUnified) {
        btnViewSplit.addEventListener("click", () => {
          diffViewMode = "split";
          btnViewSplit.classList.add("active");
          btnViewUnified.classList.remove("active");
          renderCurrentDiff();
        });
        btnViewUnified.addEventListener("click", () => {
          diffViewMode = "unified";
          btnViewUnified.classList.add("active");
          btnViewSplit.classList.remove("active");
          renderCurrentDiff();
        });
      }

      if (btnToggleFold) {
        btnToggleFold.addEventListener("click", () => {
          diffFoldUnchanged = !diffFoldUnchanged;
          btnToggleFold.textContent = diffFoldUnchanged ? "Collapse Unchanged" : "Expand All";
          renderCurrentDiff();
        });
      }

      const btnCopy = document.getElementById("btn-copy-diff");
      if (btnCopy) {
        btnCopy.addEventListener("click", () => {
          const evoM = milestones[rightMilestoneKey] || milestones["30"];
          const textToCopy = evoM.evolve_block || "";
          if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(textToCopy).then(() => {
              const origText = btnCopy.textContent;
              btnCopy.textContent = "✓ Copied!";
              setTimeout(() => { btnCopy.textContent = origText; }, 1500);
            }).catch(err => {
              console.warn("Clipboard write failed", err);
            });
          }
        });
      }

      // 12. Real-Time Telemetry & Server-Sent Events (SSE) Client
      const pillStreamStatus = document.getElementById("pill-stream-status");
      const dotStreamStatus = document.getElementById("dot-stream-status");
      const textStreamStatus = document.getElementById("text-stream-status");
      const btnTriggerEvolution = document.getElementById("btn-trigger-evolution");
      const liveToast = document.getElementById("live-toast");
      const liveToastText = document.getElementById("live-toast-text");
      let toastTimer = null;
      let isEvolutionRunning = false;

      function showLiveToast(msg) {
        if (!liveToast || !liveToastText) return;
        liveToastText.textContent = msg;
        liveToast.classList.add("show");
        if (toastTimer) clearTimeout(toastTimer);
        toastTimer = setTimeout(() => {
          liveToast.classList.remove("show");
        }, 4000);
      }

      function setStreamStatus(statusMode, labelText) {
        if (!pillStreamStatus || !dotStreamStatus || !textStreamStatus) return;
        pillStreamStatus.className = "pill " + (statusMode === "streaming" ? "status-streaming" : (statusMode === "connected" ? "status-live" : "status-archive"));
        dotStreamStatus.className = "status-dot" + (statusMode === "streaming" ? " pulse" : "");
        textStreamStatus.textContent = labelText;
      }

      function setEvolutionButtonState(running) {
        isEvolutionRunning = Boolean(running);
        if (!btnTriggerEvolution) return;
        btnTriggerEvolution.disabled = isEvolutionRunning;
        btnTriggerEvolution.classList.toggle("is-running", isEvolutionRunning);
        btnTriggerEvolution.textContent = isEvolutionRunning
          ? "⏳ Evolving..."
          : "⚡ Run Live Evolution";
      }

      function triggerLiveEvolution() {
        if (isEvolutionRunning || typeof fetch !== "function") return;
        pauseReplay();
        setEvolutionButtonState(true);
        setStreamStatus("streaming", "STARTING DRY-RUN...");

        fetch("/api/experiments/start", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            use_case: currentUseCaseId,
            max_programs: 4
          })
        })
          .then(res => {
            return res.json().catch(() => ({})).then(data => ({
              ok: res.ok,
              status: res.status,
              data: data
            }));
          })
          .then(result => {
            if (!result.ok) {
              setEvolutionButtonState(false);
              const errMsg = (result.data && result.data.detail) || "Evolution request rate-limited or failed";
              setStreamStatus("connected", result.status === 429 ? "RATE LIMITED (WAIT)" : "REQUEST FAILED");
              showLiveToast("⚠️ " + errMsg);
              return;
            }
            const expTitle = (result.data && result.data.experiment_name) || currentUseCaseId;
            setStreamStatus("streaming", "LIVE: " + expTitle);
            showLiveToast("🚀 Triggered Dry-Run: " + expTitle);
          })
          .catch(() => {
            setEvolutionButtonState(false);
            setStreamStatus("archive", "OFFLINE ARCHIVE");
            showLiveToast("⚠️ Unable to reach server for live evolution");
          });
      }

      if (btnTriggerEvolution) {
        btnTriggerEvolution.addEventListener("click", triggerLiveEvolution);
      }

      function connectTelemetryStream() {
        if (typeof window.EventSource === "undefined") {
          setStreamStatus("archive", "ARCHIVE DATA (NO SSE)");
          return;
        }

        setStreamStatus("connected", "CONNECTING STREAM...");
        let sse = null;
        try {
          sse = new EventSource("/api/stream/events");
        } catch (err) {
          console.warn("Could not instantiate EventSource", err);
          setStreamStatus("archive", "OFFLINE ARCHIVE");
          return;
        }

        sse.onopen = function() {
          setStreamStatus("streaming", "LIVE STREAMING (SSE)");
        };

        sse.addEventListener("state_snapshot", function(e) {
          try {
            const snapshot = JSON.parse(e.data);
            if (snapshot.status === "RUNNING") {
              setEvolutionButtonState(true);
              setStreamStatus("streaming", "LIVE: " + (snapshot.experiment_name || "RUNNING") + " (" + snapshot.evaluated_count + " EVALUATED)");
            } else if (snapshot.status === "COMPLETED") {
              setEvolutionButtonState(false);
              setStreamStatus("connected", "RUN COMPLETED (" + snapshot.evaluated_count + " EVALUATED)");
            } else {
              setEvolutionButtonState(false);
              setStreamStatus("connected", "ADC VERIFIED (IDLE)");
            }
          } catch (err) {
            console.warn("Failed to parse state_snapshot", err);
          }
        });

        sse.addEventListener("run_started", function(e) {
          try {
            const runData = JSON.parse(e.data);
            setEvolutionButtonState(true);
            setStreamStatus("streaming", "LIVE: " + (runData.experiment_name || "OPTIMIZING"));
            showLiveToast("🚀 AlphaEvolve Run Started: " + (runData.experiment_name || "New Run"));
          } catch (err) {
            console.warn("Failed to parse run_started event", err);
          }
        });

        sse.addEventListener("candidate_evaluated", function(e) {
          try {
            const cand = JSON.parse(e.data);
            const iter = cand.iteration !== undefined ? cand.iteration : trajectories.length;
            const scoreVal = typeof cand.score === "number" ? cand.score : 0.0;
            const isBest = cand.is_best || false;

            const baseFrame = trajectories[Math.min(iter, trajectories.length - 1)] || trajectories[0];
            const defaultMilestoneKey = currentUseCaseId === "fleet_routing"
              ? (iter < 7 ? "0" : (iter < 16 ? "7" : (iter < 30 ? "16" : "30")))
              : (iter < 8 ? "0" : (iter < 17 ? "8" : (iter < 30 ? "17" : "30")));
            const iterMilestoneKey = (baseFrame && baseFrame.generation === iter && baseFrame.milestone_key)
              ? String(baseFrame.milestone_key)
              : defaultMilestoneKey;
            const newFrame = {
              generation: iter,
              milestone_key: iterMilestoneKey,
              event_summary: isBest
                ? ("★ New Breakthrough Candidate (Iter " + iter + ") | Score: " + scoreVal.toFixed(2) + "%")
                : ("Evaluated Candidate (Iter " + iter + ") | Score: " + scoreVal.toFixed(2) + "%"),
              metrics: {
                total_cost: (cand.scores && cand.scores.total_cost) || (baseFrame.metrics ? baseFrame.metrics.total_cost : 45238),
                spoilage_cost: baseFrame.metrics ? baseFrame.metrics.spoilage_cost : 16145,
                holding_cost: baseFrame.metrics ? baseFrame.metrics.holding_cost : 14120,
                stockout_penalty: baseFrame.metrics ? baseFrame.metrics.stockout_penalty : 14573,
                fill_rate_pct: (cand.scores && cand.scores.fill_rate_pct) || (baseFrame.metrics ? baseFrame.metrics.fill_rate_pct : 93.49),
                spoilage_rate_pct: (cand.scores && cand.scores.spoilage_rate_pct) || (baseFrame.metrics ? baseFrame.metrics.spoilage_rate_pct : 8.45),
                total_distance_km: (cand.scores && cand.scores.total_distance_km) || (baseFrame.metrics ? baseFrame.metrics.total_distance_km : 1388),
                on_time_delivery_pct: (cand.scores && cand.scores.on_time_delivery_pct) || (baseFrame.metrics ? baseFrame.metrics.on_time_delivery_pct : 86.0),
                total_tardiness_hours: (cand.scores && cand.scores.total_tardiness_hours) || (baseFrame.metrics ? baseFrame.metrics.total_tardiness_hours : 8.0),
                vehicles_used: (cand.scores && cand.scores.vehicles_used) || (baseFrame.metrics ? baseFrame.metrics.vehicles_used : 5),
                cost_reduction_pct: scoreVal,
                fitness_score: scoreVal
              },
              daily_series: baseFrame.daily_series
            };

            if (iter >= trajectories.length) {
              while (trajectories.length < iter) {
                const fillIdx = trajectories.length;
                const fillKey = currentUseCaseId === "fleet_routing"
                  ? (fillIdx < 7 ? "0" : (fillIdx < 16 ? "7" : (fillIdx < 30 ? "16" : "30")))
                  : (fillIdx < 8 ? "0" : (fillIdx < 17 ? "8" : (fillIdx < 30 ? "17" : "30")));
                trajectories.push({
                  generation: fillIdx,
                  milestone_key: fillKey,
                  event_summary: baseFrame.event_summary || ("Gen " + fillIdx),
                  metrics: Object.assign({}, baseFrame.metrics),
                  daily_series: baseFrame.daily_series
                });
              }
              trajectories.push(newFrame);
            } else {
              trajectories[iter] = newFrame;
            }

            maxGen = trajectories.length - 1;
            if (scrubber) {
              scrubber.max = maxGen;
            }

            if (!paretoFrontier.some(p => p.generation === iter)) {
              paretoFrontier.push({
                generation: iter,
                cost_reduction_pct: scoreVal,
                fill_rate_pct: newFrame.metrics.fill_rate_pct,
                spoilage_rate_pct: newFrame.metrics.spoilage_rate_pct,
                is_pareto: isBest
              });
            }

            if (isBest && !ribbonMilestones.some(m => m.generation === iter)) {
              ribbonMilestones.push({
                generation: iter,
                label: "Gen " + iter,
                badge: "★ Gen " + iter,
                title: "Breakthrough Candidate (Iter " + iter + ")",
                cost_reduc: scoreVal,
                fill_rate: newFrame.metrics.fill_rate_pct,
                innovation: "Evolved Program Candidate with +" + scoreVal.toFixed(1) + "% cost reduction"
              });
              renderMilestoneRibbon();
            }

            updateDisplay(iter);
            showLiveToast((isBest ? "🏆 NEW BEST! " : "⚡ Evaluated: ") + "Gen " + iter + " (" + (scoreVal > 0 ? "+" : "") + scoreVal.toFixed(2) + "%)");
          } catch (err) {
            console.warn("Failed to parse candidate_evaluated event", err);
          }
        });

        sse.addEventListener("run_completed", function(e) {
          try {
            const finishData = JSON.parse(e.data);
            setEvolutionButtonState(false);
            setStreamStatus("connected", "RUN COMPLETED (Best: " + (finishData.best_score || 0).toFixed(2) + "%)");
            showLiveToast("🏁 Optimization Run Completed! Best Score: " + (finishData.best_score || 0).toFixed(2) + "%");
          } catch (err) {
            console.warn("Failed to parse run_completed event", err);
          }
        });

        sse.onerror = function() {
          setEvolutionButtonState(false);
          setStreamStatus("archive", "ARCHIVE MODE (OFFLINE)");
        };
      }

      // 13. Initial Mount & Resize Handlers
      updateDomainControls();
      renderMilestoneRibbon();
      updateDisplay(maxGen);
      updateWhatIfSimulation();
      renderCurrentDiff();
      connectTelemetryStream();

      window.addEventListener("resize", () => {
        drawTrajectoryChart(currentGen);
        drawCanvas2Chart();
        updateWhatIfSimulation();
      });

    })();
