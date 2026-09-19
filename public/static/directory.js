(() => {
  const initializeTimelineScroll = () => {
    const frame = document.querySelector(".map-frame");
    const todayLine = frame?.querySelector(".today-line");
    if (!frame || !todayLine) return;
    frame.scrollLeft = Math.max(0, todayLine.offsetLeft - 16);
  };

  const initializeGeographicMap = () => {
    const section = document.querySelector("#bench-map");
    const mapElement = document.querySelector("#geographic-map");
    const dataElement = document.querySelector("#bench-map-data");
    if (!section || !mapElement || !dataElement) return;

    let benches;
    try {
      benches = JSON.parse(dataElement.textContent);
    } catch (_error) {
      mapElement.textContent = "Bench locations could not be loaded.";
      return;
    }

    if (!window.L) {
      mapElement.textContent = "The interactive map could not be loaded. Use the bench list below instead.";
      return;
    }

    const map = window.L.map(mapElement, {
      center: [40.8975, -73.8945],
      zoom: 14,
      minZoom: 13,
      maxZoom: 18,
      maxBounds: [[40.878, -73.918], [40.916, -73.867]],
      maxBoundsViscosity: 0.8,
      scrollWheelZoom: true,
    });
    window.L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(map);

    const clusterIcon = (cluster) => {
      const markers = cluster.getAllChildMarkers();
      const availableCount = markers.filter((marker) => marker.options.benchAvailable).length;
      const adoptedCount = markers.length - availableCount;
      const availableShare = availableCount / markers.length * 100;
      return window.L.divIcon({
        className: "bench-cluster-shell",
        html: `<span class="bench-cluster" style="--available-share:${availableShare}%" aria-label="${availableCount} available and ${adoptedCount} adopted"><b aria-hidden="true">${markers.length}</b></span>`,
        iconSize: [42, 42],
        iconAnchor: [21, 21],
      });
    };

    const markerLayer = window.L.markerClusterGroup
      ? window.L.markerClusterGroup({
        showCoverageOnHover: false,
        maxClusterRadius: 44,
        iconCreateFunction: clusterIcon,
      })
      : window.L.layerGroup();
    markerLayer.addTo(map);

    const selection = document.querySelector("#map-selection");
    const count = document.querySelector("#map-result-count");
    const countLabel = document.querySelector("#map-result-label");
    const filterButtons = [...section.querySelectorAll("[data-map-filter]")];
    const listRows = [...section.querySelectorAll("[data-list-status]")];

    const markerIcon = (available) => window.L.divIcon({
      className: "bench-marker-shell",
      html: `<span class="bench-marker ${available ? "bench-marker-available" : "bench-marker-adopted"}" aria-hidden="true"></span>`,
      iconSize: [24, 24],
      iconAnchor: [12, 12],
    });

    const clearSelection = () => {
      selection.replaceChildren();
      const eyebrow = document.createElement("p");
      eyebrow.className = "eyebrow";
      eyebrow.textContent = "SELECT A BENCH";
      const heading = document.createElement("h3");
      heading.textContent = "Choose a marker";
      const help = document.createElement("p");
      help.textContent = "Select any marker to see its status and open the bench details.";
      selection.append(eyebrow, heading, help);
    };

    const showBench = (bench) => {
      selection.replaceChildren();

      const eyebrow = document.createElement("p");
      eyebrow.className = "eyebrow";
      eyebrow.textContent = bench.available ? "AVAILABLE NOW" : "ADOPTED OR RESERVED";
      const heading = document.createElement("h3");
      heading.textContent = bench.id;
      const location = document.createElement("p");
      location.className = "map-selection-location";
      location.textContent = bench.location;
      const status = document.createElement("span");
      status.className = `status ${bench.available ? "status-available" : "status-adopted"}`;
      status.textContent = bench.available ? "Available" : "Adopted";
      const action = document.createElement("a");
      action.className = "button button-dark wide";
      action.href = bench.action_url;
      action.textContent = bench.action_label;

      selection.append(eyebrow, heading, location, status, action);
    };

    benches.forEach((bench) => {
      bench.marker = window.L.marker([bench.latitude, bench.longitude], {
        benchAvailable: bench.available,
        icon: markerIcon(bench.available),
        title: `${bench.id}, ${bench.available ? "available" : "adopted"}`,
        keyboard: true,
      });
      bench.marker.bindTooltip(bench.id, { direction: "top", offset: [0, -9] });
      bench.marker.on("click", () => showBench(bench));
    });

    const applyFilter = (status) => {
      markerLayer.clearLayers();
      const visible = benches.filter((bench) => (
        status === "all" || (status === "available" ? bench.available : !bench.available)
      ));
      markerLayer.addLayers(visible.map((bench) => bench.marker));
      if (visible.length) {
        map.fitBounds(
          window.L.latLngBounds(
            visible.map((bench) => [bench.latitude, bench.longitude]),
          ),
          { padding: [25, 25], maxZoom: 15 },
        );
      }
      clearSelection();

      filterButtons.forEach((button) => {
        const selected = button.dataset.mapFilter === status;
        button.classList.toggle("selected", selected);
        button.setAttribute("aria-pressed", String(selected));
      });
      listRows.forEach((row) => {
        row.hidden = status !== "all" && row.dataset.listStatus !== status;
      });
      count.textContent = String(visible.length);
      countLabel.textContent = visible.length === 1 ? "bench shown" : "benches shown";

      const url = new URL(window.location.href);
      if (status === "all") url.searchParams.delete("status");
      else url.searchParams.set("status", status);
      history.replaceState({}, "", `${url.pathname}${url.search}${url.hash}`);
    };

    filterButtons.forEach((button) => {
      button.addEventListener("click", () => applyFilter(button.dataset.mapFilter));
    });
    applyFilter(section.dataset.initialStatus || "all");
  };

  initializeTimelineScroll();
  initializeGeographicMap();
})();
