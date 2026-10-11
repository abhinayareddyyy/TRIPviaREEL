/* TripViaReel front-end. Plain JavaScript, no build step.
   All text from the server or the user is inserted with textContent (never innerHTML). */
(function () {
  "use strict";

  var DAY_COLORS = ["#0f6b5c", "#c2410c", "#6d28d9", "#0369a1", "#be185d", "#4d7c0f", "#a16207"];
  var $ = function (id) { return document.getElementById(id); };

  function el(tag, attrs, children) {
    var node = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) {
      if (k === "class") node.className = attrs[k];
      else if (k === "text") node.textContent = attrs[k];
      else node.setAttribute(k, attrs[k]);
    });
    (children || []).forEach(function (c) {
      if (c == null) return;
      node.appendChild(typeof c === "string" ? document.createTextNode(c) : c);
    });
    return node;
  }
  var inr = function (n) { return "₹" + Number(n).toLocaleString("en-IN"); };

  var state = { files: [], candidates: [], catalog: null, selectedInterests: new Set() };

  /* ---------------- map ---------------- */
  var map = L.map("map", { scrollWheelZoom: false }).setView([22.5, 79], 4);
  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 18,
    attribution: "&copy; <a href='https://www.openstreetmap.org/copyright'>OpenStreetMap</a> contributors"
  }).addTo(map);
  var mapLayer = L.layerGroup().addTo(map);

  function drawMap(it) {
    mapLayer.clearLayers();
    var bounds = [];
    if (it.origin) {
      L.marker([it.origin.lat, it.origin.lon], {
        title: "Starting location: " + it.origin.name
      }).addTo(mapLayer).bindPopup(el("strong", { text: "Starting location: " + it.origin.name }));
      bounds.push([it.origin.lat, it.origin.lon]);
    }
    it.days.forEach(function (day, di) {
      var color = DAY_COLORS[di % DAY_COLORS.length];
      if (day.path.length > 1) {
        L.polyline(day.path, { color: color, weight: 4, opacity: 0.8 }).addTo(mapLayer);
      }
      day.stops.forEach(function (s) {
        var icon = L.divIcon({
          className: "",
          html: '<div class="num-icon" style="background:' + color + '">' + s.order + "</div>",
          iconSize: [26, 26], iconAnchor: [13, 13]
        });
        var m = L.marker([s.lat, s.lon], { icon: icon, title: s.name }).addTo(mapLayer);
        var pop = el("div", {}, [el("strong", { text: s.name }), el("br"), document.createTextNode("Day " + day.day + " · " + s.arrive + "–" + s.depart)]);
        m.bindPopup(pop);
        bounds.push([s.lat, s.lon]);
      });
    });
    if (bounds.length) map.fitBounds(bounds, { padding: [30, 30], maxZoom: 15 });
    setTimeout(function () { map.invalidateSize(); }, 50);
  }

  /* ---------------- messages ---------------- */
  function say(id, text, kind) {
    var n = $(id);
    n.textContent = text || "";
    n.className = "msg" + (kind ? " " + kind : "");
  }

  /* ---------------- uploads ---------------- */
  var fileInput = $("files"), drop = $("drop");
  drop.addEventListener("click", function () { fileInput.click(); });
  drop.addEventListener("keydown", function (e) { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); fileInput.click(); } });
  ["dragenter", "dragover"].forEach(function (ev) {
    drop.addEventListener(ev, function (e) { e.preventDefault(); drop.classList.add("over"); });
  });
  ["dragleave", "drop"].forEach(function (ev) {
    drop.addEventListener(ev, function (e) { e.preventDefault(); drop.classList.remove("over"); });
  });
  drop.addEventListener("drop", function (e) { addFiles(e.dataTransfer.files); });
  fileInput.addEventListener("change", function () { addFiles(fileInput.files); fileInput.value = ""; });

  function addFiles(list) {
    Array.prototype.forEach.call(list, function (f) {
      if (state.files.length < 5) state.files.push(f);
    });
    renderFiles();
  }
  function renderFiles() {
    var ul = $("file-list");
    ul.textContent = "";
    state.files.forEach(function (f, i) {
      var rm = el("button", { type: "button", "aria-label": "Remove " + f.name, text: "remove" });
      rm.addEventListener("click", function () { state.files.splice(i, 1); renderFiles(); });
      ul.appendChild(el("li", {}, [el("span", { text: f.name + " (" + (f.size / 1048576).toFixed(1) + " MB)" }), rm]));
    });
  }

  /* ---------------- analyze ---------------- */
  $("btn-analyze").addEventListener("click", function () {
    var btn = this;
    var fd = new FormData();
    fd.append("reel_url", $("reel-url").value.trim());
    fd.append("caption", $("caption").value.trim());
    state.files.forEach(function (f) { fd.append("files", f); });
    btn.disabled = true;
    say("analyze-msg", state.files.some(function (f) { return /video/.test(f.type); }) ? "Reading video frames… this can take up to a minute." : "Looking for places…", "info");
    fetch("/api/analyze", { method: "POST", body: fd })
      .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, j: j }; }); })
      .then(function (res) {
        if (!res.ok) { say("analyze-msg", res.j.error || "Something went wrong.", "err"); return; }
        showCandidates(res.j);
      })
      .catch(function () { say("analyze-msg", "Could not reach the server. Is it running?", "err"); })
      .then(function () { btn.disabled = false; });
  });

  function showCandidates(data) {
    state.candidates = data.candidates.map(function (c) {
      c.checked = !c.ambiguous && c.confidence >= 0.9;
      return c;
    });
    var warn = data.warnings && data.warnings.length ? data.warnings.join(" ") : "";
    if (data.candidates.length) say("analyze-msg", warn, warn ? "warn" : "");
    else say("analyze-msg", warn || "No places detected.", "warn");

    $("ocr-text").textContent = data.extracted_text || "(no text found)";
    var un = $("unresolved");
    if (data.unresolved && data.unresolved.length) {
      un.textContent = "Mentioned but not in the offline place list: " + data.unresolved.join(", ") + ".";
      un.classList.remove("hidden");
    } else {
      un.classList.add("hidden");
    }
    $("card-places").classList.remove("hidden");
    $("card-prefs").classList.remove("hidden");
    renderCandidates();
    loadCatalog();
  }

  function renderCandidates() {
    var ul = $("candidates");
    ul.textContent = "";
    if (!state.candidates.length) {
      ul.appendChild(el("li", {}, [el("span", { class: "meta", text: "Nothing detected yet. Add places manually below." })]));
    }
    state.candidates.forEach(function (c, i) {
      var cb = el("input", { type: "checkbox", id: "cand-" + i });
      cb.checked = !!c.checked;
      cb.addEventListener("change", function () { c.checked = cb.checked; });
      var title = el("span", { class: "nm", text: c.name });
      var meta = c.city + (c.mentions ? " · mentioned " + c.mentions + "×" : " · added by you");
      var label = el("label", { for: "cand-" + i, style: "margin:0;font-weight:400;cursor:pointer" }, [
        title,
        c.ambiguous ? el("span", { class: "badge warn", text: "same name in several cities" }) : null,
        c.match === "fuzzy" ? el("span", { class: "badge warn", text: "approximate match " + Math.round(c.confidence * 100) + "%" }) : null,
        el("div", { class: "meta", text: meta })
      ]);
      ul.appendChild(el("li", {}, [cb, label]));
    });
  }

  /* ---------------- catalog: manual add + interests ---------------- */
  function loadCatalog() {
    if (state.catalog) return;
    fetch("/api/places").then(function (r) { return r.json(); }).then(function (j) {
      state.catalog = j;
      var sel = $("add-select");
      sel.textContent = "";
      var groups = {};
      j.places.forEach(function (p) {
        if (!groups[p.city]) { groups[p.city] = el("optgroup", { label: p.city }); sel.appendChild(groups[p.city]); }
        groups[p.city].appendChild(el("option", { value: p.id, text: p.name }));
      });
      var chips = $("interests");
      chips.textContent = "";
      j.interests.forEach(function (name) {
        var b = el("button", { type: "button", class: "chip", "aria-pressed": "false", text: name });
        b.addEventListener("click", function () {
          var on = b.getAttribute("aria-pressed") !== "true";
          b.setAttribute("aria-pressed", on ? "true" : "false");
          if (on) state.selectedInterests.add(name); else state.selectedInterests.delete(name);
        });
        var origin = $("origin-place");
        j.places.forEach(function (p) {
          origin.appendChild(el("option", { value: p.id, text: p.name + " (" + p.city + ")" }));
        });
        chips.appendChild(b);
      });
    });
  }

  $("btn-add").addEventListener("click", function () {
    if (!state.catalog) return;
    var id = $("add-select").value;
    var existing = state.candidates.filter(function (c) { return c.id === id; })[0];
    if (existing) { existing.checked = true; }
    else {
      var p = state.catalog.places.filter(function (x) { return x.id === id; })[0];
      if (!p) return;
      state.candidates.push({ id: p.id, name: p.name, city: p.city, lat: p.lat, lon: p.lon, tags: p.tags, mentions: 0, confidence: 1, match: "manual", ambiguous: false, checked: true });
    }
    renderCandidates();
  });

  /* ---------------- plan ---------------- */
  $("btn-plan").addEventListener("click", function () {
    var btn = this;
    var chosen = state.candidates.filter(function (c) { return c.checked; });
    if (!chosen.length) { say("plan-msg", "Tick at least one place.", "err"); return; }
    var mentions = {};
    chosen.forEach(function (c) { mentions[c.id] = c.mentions || 1; });
    var body = {
      place_ids: chosen.map(function (c) { return c.id; }),
      mentions: mentions,
      budget: Number($("budget").value),
      days: Number($("days").value),
      interests: Array.from(state.selectedInterests)
      ,origin_place: $("origin-place").value || null
    };
    btn.disabled = true;
    say("plan-msg", "Planning…", "info");
    fetch("/api/plan", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) })
      .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, j: j }; }); })
      .then(function (res) {
        if (!res.ok) { say("plan-msg", res.j.error || "Something went wrong.", "err"); return; }
        say("plan-msg", "");
        renderItinerary(res.j);
        if (res.j.trip_id) history.replaceState(null, "", "?trip=" + encodeURIComponent(res.j.trip_id));
      })
      .catch(function () { say("plan-msg", "Could not reach the server.", "err"); })
      .then(function () { btn.disabled = false; });
  });

  /* ---------------- render itinerary ---------------- */
  function tile(k, v, cls) { return el("div", { class: "tile " + (cls || "") }, [el("div", { class: "v", text: v }), el("div", { class: "k", text: k })]); }

  function renderItinerary(it) {
    $("empty").classList.add("hidden");
    var out = $("out");
    out.textContent = "";
    out.classList.remove("hidden");
    var t = it.totals;

    out.appendChild(el("div", { class: "tiles" }, [
      tile("Estimated total", inr(t.total)),
      tile("Left from " + inr(it.budget), inr(t.remaining), t.remaining >= 0 ? "ok" : ""),
      tile("Travel distance", t.km + " km"),
      tile("City · days", it.city + " · " + it.days_used)
    ]));

    if (it.warnings && it.warnings.length) {
      var wb = el("div", { class: "box" }, [el("h3", { text: "Notes" }), el("ul", {}, it.warnings.map(function (w) { return el("li", { text: w }); }))]);
      out.appendChild(wb);
    }

    it.days.forEach(function (day, di) {
      var color = DAY_COLORS[di % DAY_COLORS.length];
      var box = el("div", { class: "day" }, [
        el("h3", {}, [el("span", { text: "Day " + day.day }), el("span", { class: "dm", text: day.km + " km · about " + inr(day.cost) + " · ends " + day.ends_at })])
      ]);
      day.stops.forEach(function (s) {
        if (s.travel_km > 0) {
          var via = s.via && s.via.length ? " via " + s.via.join(", ") : "";
          box.appendChild(el("div", { class: "travel", text: "↓ " + s.travel_km + " km · ~" + s.travel_min + " min · " + inr(s.travel_cost) + via }));
        }
        box.appendChild(el("div", { class: "stop" }, [
          el("div", { class: "pin", style: "background:" + color, text: String(s.order) }),
          el("div", {}, [
            el("div", { class: "nm", text: s.name }),
            el("div", { class: "meta", text: s.arrive + "–" + s.depart + " · " + (s.category === "food" ? "food" : s.tags.slice(0, 3).join(", ")) })
          ]),
          el("div", { class: "cost", text: s.cost ? inr(s.cost) : "Free" })
        ]));
      });
      out.appendChild(box);
    });

    var rows = [
      ["Entry & activities", t.entry_and_activities], ["Food (restaurants)", t.food],
      ["Local transport", t.transport], ["Daily snacks & water", t.daily_allowance]
    ];
    var table = el("table", { class: "cost" });
    rows.forEach(function (r) { table.appendChild(el("tr", {}, [el("td", { text: r[0] }), el("td", { text: inr(r[1]) })])); });
    table.appendChild(el("tr", { class: "total" }, [el("td", { text: "Total" }), el("td", { text: inr(t.total) })]));
    out.appendChild(el("div", { class: "box" }, [el("h3", { text: "Cost breakdown (estimate)" }), table]));

    if (it.dropped && it.dropped.length) {
      out.appendChild(el("div", { class: "box" }, [el("h3", { text: "Left out" }),
        el("ul", {}, it.dropped.map(function (d) { return el("li", { text: d.name + " — " + d.reason }); }))]));
    }
    var a = it.assumptions;
    out.appendChild(el("div", { class: "box" }, [el("h3", { text: "Assumptions" }), el("ul", {}, [
      el("li", { text: "Transport ≈ " + inr(a.transport_inr_per_km) + "/km (auto/cab), average speed " + a.average_speed_kmph + " km/h." }),
      el("li", { text: "Distances are road estimates (A* over a road graph, ×" + a.road_factor + " straight-line)." }),
      el("li", { text: "Day window " + a.day_window + ". " + a.note })
    ])]));

    drawMap(it);
    out.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  /* ---------------- reopen a saved trip: /?trip=ID ---------------- */
  var tripId = new URLSearchParams(location.search).get("trip");
  if (tripId) {
    fetch("/api/trips/" + encodeURIComponent(tripId)).then(function (r) { return r.ok ? r.json() : null; }).then(function (t) {
      if (!t) return;
      $("budget").value = t.request.budget;
      $("days").value = t.request.days;
      if (t.request.origin_place) $("origin-place").value = t.request.origin_place;
      renderItinerary(t.result);
    });
  }
})();
