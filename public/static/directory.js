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
    const boundaryElement = document.querySelector("#park-boundary-data");
    if (!section || !mapElement || !dataElement || !boundaryElement) return;

    let benches;
    let parkBoundary;
    try {
      benches = JSON.parse(dataElement.textContent);
      parkBoundary = JSON.parse(boundaryElement.textContent);
    } catch (_error) {
      mapElement.textContent = "Bench locations could not be loaded.";
      return;
    }

    if (!window.L) {
      mapElement.textContent = "The interactive map could not be loaded. Use the bench list below instead.";
      return;
    }

    const map = window.L.map(mapElement, {
      minZoom: 13,
      maxZoom: 18,
      maxBoundsViscosity: 0.8,
      scrollWheelZoom: true,
    });
    window.L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(map);

    const boundaryLayer = window.L.geoJSON(parkBoundary, {
      interactive: false,
      style: {
        color: "#315f49",
        weight: 2,
        opacity: 0.85,
        fillColor: "#8fbd7c",
        fillOpacity: 0.08,
      },
    }).addTo(map);
    const parkBounds = boundaryLayer.getBounds();
    map.setMaxBounds(parkBounds.pad(0.2));
    map.fitBounds(parkBounds, { padding: [20, 20] });

    const selection = document.querySelector("#map-selection");
    const count = document.querySelector("#map-result-count");
    const countLabel = document.querySelector("#map-result-label");
    const filterButtons = [...section.querySelectorAll("[data-map-filter]")];
    const listRows = [...section.querySelectorAll("[data-list-status]")];
    const renderedMarkers = window.L.layerGroup().addTo(map);
    let visibleBenches = benches;
    let clusterIndex = null;

    const markerIcon = (available) => window.L.divIcon({
      className: "bench-marker-shell",
      html: `<span class="bench-marker ${available ? "bench-marker-available" : "bench-marker-adopted"}" aria-hidden="true"></span>`,
      iconSize: [24, 24],
      iconAnchor: [12, 12],
    });

    const clusterIcon = (total, availableCount) => {
      const adoptedCount = total - availableCount;
      const availableShare = availableCount / total * 100;
      return window.L.divIcon({
        className: "bench-cluster-shell",
        html: `<span class="bench-cluster" style="--available-share:${availableShare}%" aria-label="${availableCount} available and ${adoptedCount} adopted"><b aria-hidden="true">${total}</b></span>`,
        iconSize: [42, 42],
        iconAnchor: [21, 21],
      });
    };

    const clearSelection = () => {
      selection.replaceChildren();
      const eyebrow = document.createElement("p");
      eyebrow.className = "eyebrow";
      eyebrow.textContent = "SELECT A BENCH";
      const heading = document.createElement("h3");
      heading.textContent = "Choose a marker";
      const message = document.createElement("p");
      message.textContent = "Adopt a bench today to support our operations.";
      selection.append(eyebrow, heading, message);
    };

    const showBench = (bench) => {
      selection.replaceChildren();

      let image = null;
      if (bench.image_url) {
        image = document.createElement("img");
        image.className = "map-selection-image";
        image.src = bench.image_url;
        image.alt = `Representative view of ${bench.id} at ${bench.location}`;
        image.decoding = "async";
      }
      const eyebrow = document.createElement("p");
      eyebrow.className = "eyebrow";
      eyebrow.textContent = bench.available
        ? "AVAILABLE NOW"
        : `ADOPTED UNTIL ${bench.adoption_end_date}`;
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

      if (image) selection.append(image);
      selection.append(eyebrow, heading, location, status, action);
    };

    const createBenchMarker = (bench) => {
      const marker = window.L.marker([bench.latitude, bench.longitude], {
        icon: markerIcon(bench.available),
        title: `${bench.id}, ${bench.available ? "available" : "adopted"}`,
        keyboard: true,
      });
      marker.bindTooltip(bench.id, { direction: "top", offset: [0, -9] });
      marker.on("click", () => showBench(bench));
      return marker;
    };

    const renderMarkers = () => {
      renderedMarkers.clearLayers();
      if (!clusterIndex) {
        visibleBenches.forEach((bench) => renderedMarkers.addLayer(createBenchMarker(bench)));
        return;
      }

      const bounds = map.getBounds();
      const features = clusterIndex.getClusters(
        [bounds.getWest(), bounds.getSouth(), bounds.getEast(), bounds.getNorth()],
        Math.floor(map.getZoom()),
      );
      features.forEach((feature) => {
        const [longitude, latitude] = feature.geometry.coordinates;
        if (feature.properties.cluster) {
          const total = feature.properties.point_count;
          const availableCount = feature.properties.availableCount;
          const marker = window.L.marker([latitude, longitude], {
            icon: clusterIcon(total, availableCount),
            title: `${total} benches`,
            keyboard: true,
          });
          marker.on("click", () => {
            const expansionZoom = clusterIndex.getClusterExpansionZoom(
              feature.properties.cluster_id,
            );
            map.setView([latitude, longitude], Math.min(expansionZoom, map.getMaxZoom()));
          });
          renderedMarkers.addLayer(marker);
        } else {
          renderedMarkers.addLayer(
            createBenchMarker(visibleBenches[feature.properties.benchIndex]),
          );
        }
      });
    };

    const rebuildClusterIndex = () => {
      if (!window.Supercluster) {
        clusterIndex = null;
        return;
      }
      clusterIndex = new window.Supercluster({
        radius: 120,
        maxZoom: 17,
        minPoints: 6,
        map: (properties) => ({ availableCount: properties.available ? 1 : 0 }),
        reduce: (accumulated, properties) => {
          accumulated.availableCount += properties.availableCount;
        },
      });
      clusterIndex.load(visibleBenches.map((bench, benchIndex) => ({
        type: "Feature",
        properties: { benchIndex, available: bench.available },
        geometry: {
          type: "Point",
          coordinates: [bench.longitude, bench.latitude],
        },
      })));
    };

    const applyFilter = (status) => {
      visibleBenches = benches.filter((bench) => (
        status === "all" || (status === "available" ? bench.available : !bench.available)
      ));
      rebuildClusterIndex();
      renderedMarkers.clearLayers();
      if (visibleBenches.length) {
        map.fitBounds(
          window.L.latLngBounds(
            visibleBenches.map((bench) => [bench.latitude, bench.longitude]),
          ),
          { padding: [25, 25], maxZoom: 15 },
        );
      }
      renderMarkers();
      clearSelection();

      filterButtons.forEach((button) => {
        const selected = button.dataset.mapFilter === status;
        button.classList.toggle("selected", selected);
        button.setAttribute("aria-pressed", String(selected));
      });
      listRows.forEach((row) => {
        row.hidden = status !== "all" && row.dataset.listStatus !== status;
      });
      count.textContent = String(visibleBenches.length);
      countLabel.textContent = visibleBenches.length === 1 ? "bench shown" : "benches shown";

      const url = new URL(window.location.href);
      if (status === "all") url.searchParams.delete("status");
      else url.searchParams.set("status", status);
      history.replaceState({}, "", `${url.pathname}${url.search}${url.hash}`);
    };

    filterButtons.forEach((button) => {
      button.addEventListener("click", () => applyFilter(button.dataset.mapFilter));
    });
    map.on("moveend", renderMarkers);
    applyFilter(section.dataset.initialStatus || "all");
  };

  initializeTimelineScroll();
  initializeGeographicMap();
})();
