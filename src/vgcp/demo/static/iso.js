/* Isometric city view of the network topology (dashboard module).

   Projection: a true isometric drawing. The ground axes x and y run at ±30° from the
   horizontal (120° apart from each other and from the vertical z axis); vertical lines
   stay vertical and every axis keeps its true length, so there is no foreshortening
   and no vanishing point. A world point (x, y, z), in tiles, is drawn at
       ( (x − y)·cos30°·S , (x + y)·sin30°·S − z·S ).
   Lighting: one source at the top-left for every asset, so each box shows three
   value steps: top faces lightest, left (+y) faces mid, right (+x) faces darkest.

   Data: everything measured comes from the run - link utilization (overhead signs,
   road tint), slice rates and background load (how many vehicles), link power,
   the installed path of each slice and the controller's decision (the traffic
   light at the city gate). Where along a road a vehicle sits is illustrative.
   An unknown value draws no vehicles and an "n/a" sign; it is never shown as zero.

   Usage: VGCPIso.render(svgElement, {topology, state, limit, decision, t}) -> legend HTML
*/
(function () {
  "use strict";
  // Scene settings chosen on the design canvas ("Isometric city · tweak here", 2026-10-26)
  const STYLE = {span: 16, rowGap: 4, ring: 1, decorDensity: 15, vehicleDensity: 0.75, light: 0.20};
  const S = 30, C30 = Math.cos(Math.PI / 6), S30 = 0.5;
  const P = (x, y, z) => [(x - y) * C30 * S, (x + y) * S30 * S - (z || 0) * S];
  const r1 = (v) => Math.round(v * 10) / 10;
  const pts = (a) => a.map(([x, y, z]) => P(x, y, z).map(r1).join(",")).join(" ");
  const isNum = (v) => typeof v === "number" && Number.isFinite(v);
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c]));

  // ---------------------------------------------------------------- colour and faces
  function rgb(hex) { const n = parseInt(hex.slice(1), 16); return [n >> 16, (n >> 8) & 255, n & 255]; }
  function shade(hex, k) { // k > 0 mixes toward white, k < 0 toward black
    const t = k > 0 ? 255 : 0, a = Math.abs(k);
    return "rgb(" + rgb(hex).map((c) => Math.round(c + (t - c) * a)).join(",") + ")";
  }
  const LIGHT = {top: STYLE.light, left: 0, right: -STYLE.light}; // one light, top-left
  const poly = (p, fill, extra) => `<polygon points="${pts(p)}" fill="${fill}"${extra ? " " + extra : ""}/>`;
  const flat = (x, y, dx, dy, fill, z, extra) => poly([[x, y, z || 0], [x + dx, y, z || 0], [x + dx, y + dy, z || 0], [x, y + dy, z || 0]], fill, extra);
  const line = (a, b, stroke, w, extra) => {
    const [x1, y1] = P(...a), [x2, y2] = P(...b);
    return `<line x1="${r1(x1)}" y1="${r1(y1)}" x2="${r1(x2)}" y2="${r1(y2)}" stroke="${stroke}" stroke-width="${w}" stroke-linecap="round"${extra ? " " + extra : ""}/>`;
  };

  // A box seen from the viewer's side: left (+y), right (+x) and top faces.
  function box(x, y, z, dx, dy, dz, color, faces) {
    const f = faces || {};
    return poly([[x, y + dy, z], [x + dx, y + dy, z], [x + dx, y + dy, z + dz], [x, y + dy, z + dz]], f.left || shade(color, LIGHT.left))
      + poly([[x + dx, y, z], [x + dx, y + dy, z], [x + dx, y + dy, z + dz], [x + dx, y, z + dz]], f.right || shade(color, LIGHT.right))
      + poly([[x, y, z + dz], [x + dx, y, z + dz], [x + dx, y + dy, z + dz], [x, y + dy, z + dz]], f.top || shade(color, LIGHT.top));
  }
  // A band on the visible long side of a box lying along x or y (windows, stripes).
  function band(x, y, dx, dy, along, z0, z1, inset, color) {
    if (along === "x") {
      const Y = y + dy;
      return poly([[x + inset, Y, z0], [x + dx - inset, Y, z0], [x + dx - inset, Y, z1], [x + inset, Y, z1]], shade(color, LIGHT.left));
    }
    const X = x + dx;
    return poly([[X, y + inset, z0], [X, y + dy - inset, z0], [X, y + dy - inset, z1], [X, y + inset, z1]], shade(color, LIGHT.right));
  }
  function monoWindows(x, y, dx, dy, h) {
    let s = "";
    for (let z = 0.2; z + 0.24 < h; z += 0.44) {
      for (let u = 0.12; u + 0.16 <= dx - 0.08; u += 0.32)
        s += poly([[x + u, y + dy, z], [x + u + 0.16, y + dy, z], [x + u + 0.16, y + dy, z + 0.22], [x + u, y + dy, z + 0.22]], MONO.glass);
      for (let u = 0.12; u + 0.16 <= dy - 0.08; u += 0.32)
        s += poly([[x + dx, y + u, z], [x + dx, y + u + 0.16, z], [x + dx, y + u + 0.16, z + 0.22], [x + dx, y + u, z + 0.22]], MONO.glass);
    }
    return s;
  }

  // ---------------------------------------------------------------- background theme
  // Monochrome and line-drawn (lavender on white), so that colour is left to what carries
  // meaning: vehicles, the gate signal, utilization signs and overloaded roads.
  const MONO = {top: "#FFFFFF", left: "#E8EAF8", right: "#CED2EF", line: "#A2A8DA", ink: "#4B529C",
                ground: "#F6F7FD", groundLeft: "#DCDFF4", groundRight: "#BEC3E8", walk: "#FBFBFE",
                road: "#D7DAF1", plaza: "#CACEEC", paint: "#FFFFFF", glass: "#D6D9F2", roof: "#DCDFF5", roofSide: "#C3C8EA"};
  const OUT = `stroke="${MONO.line}" stroke-width="0.7" stroke-linejoin="round"`;
  function mbox(x, y, z, dx, dy, dz, faces) {
    const f = faces || {};
    return poly([[x, y + dy, z], [x + dx, y + dy, z], [x + dx, y + dy, z + dz], [x, y + dy, z + dz]], f.left || MONO.left, OUT)
      + poly([[x + dx, y, z], [x + dx, y + dy, z], [x + dx, y + dy, z + dz], [x + dx, y, z + dz]], f.right || MONO.right, OUT)
      + poly([[x, y, z + dz], [x + dx, y, z + dz], [x + dx, y + dy, z + dz], [x, y + dy, z + dz]], f.top || MONO.top, OUT);
  }
  // Shapes that overlap (road segments, sidewalks, plazas) are outlined as one: draw them
  // stroked, then fill them again unstroked, which leaves only the union's outer edge.
  const outlined = (shapes) => shapes.map((r) => flat(...r.slice(0, 4), r[4], 0, OUT)).join("") + shapes.map((r) => flat(...r)).join("");

  // ---------------------------------------------------------------- road paint
  // Text lying flat in the ground plane: its x runs along world +x, its y along world
  // +y, both at true length (the isometric axes keep unit scale), like road markings.
  function groundText(x, y, text, size, dy) {
    const [tx, ty] = P(x, y, 0);
    return `<text transform="matrix(${C30.toFixed(4)},0.5,${(-C30).toFixed(4)},0.5,${r1(tx)},${r1(ty)})" y="${dy}" text-anchor="middle" dominant-baseline="central"`
      + ` style="fill:${MONO.ink};font-family:system-ui,sans-serif;font-size:${size}px;font-weight:800;letter-spacing:0.5px">${esc(text)}</text>`;
  }
  // A switch's name painted on its intersection, inside a box-junction outline.
  function paintNode(x, y, h, name, sub) {
    const m = h - 0.1;
    return poly([[x - m, y - m, 0], [x + m, y - m, 0], [x + m, y + m, 0], [x - m, y + m, 0]], "none",
      'style="fill:none;stroke:${MONO.ink};stroke-width:1;stroke-opacity:0.7"')
      + groundText(x, y, name.toUpperCase(), 12.5, sub ? -2.5 : 0) + (sub ? groundText(x, y, sub, 6.2, 7.5) : "");
  }

  // ---------------------------------------------------------------- assets
  const CABIN = "#C7DBEA";
  function vehicleBox(x, y, along, L, W) {
    const [dx, dy] = along === "x" ? [L, W] : [W, L];
    return [x - dx / 2, y - dy / 2, dx, dy];
  }
  const Asset = {
    car(x, y, along, color) {
      const [x0, y0, dx, dy] = vehicleBox(x, y, along, 0.6, 0.32);
      const [cx, cy, cdx, cdy] = vehicleBox(x, y, along, 0.32, 0.27);
      return box(x0, y0, 0.05, dx, dy, 0.14, color) + box(cx, cy, 0.19, cdx, cdy, 0.11, CABIN);
    },
    bus(x, y, along, color) {
      const [x0, y0, dx, dy] = vehicleBox(x, y, along, 1.05, 0.36);
      return box(x0, y0, 0.05, dx, dy, 0.36, color) + band(x0, y0, dx, dy, along, 0.22, 0.34, 0.08, "#2D3A47");
    },
    ambulance(x, y, along) {
      const [x0, y0, dx, dy] = vehicleBox(x, y, along, 0.66, 0.34);
      const [bx, by, bdx, bdy] = vehicleBox(x, y, along, 0.14, 0.22);
      return box(x0, y0, 0.05, dx, dy, 0.32, "#F3F4F6") + band(x0, y0, dx, dy, along, 0.15, 0.21, 0.04, "#D6452B")
        + box(bx, by, 0.37, bdx, bdy, 0.05, "#D6452B");
    },
    scooter(x, y, along, color) {
      const [x0, y0, dx, dy] = vehicleBox(x, y, along, 0.26, 0.12);
      const [rx, ry, rdx, rdy] = vehicleBox(x, y, along, 0.1, 0.1);
      return box(x0, y0, 0.04, dx, dy, 0.08, color) + box(rx, ry, 0.12, rdx, rdy, 0.14, "#24543A");
    },
    tree(x, y, size) {
      const k = size || 1, [cx, cy] = P(x, y, 0.62 * k), r = 0.3 * k * S;
      return mbox(x - 0.04, y - 0.04, 0, 0.08, 0.08, 0.4 * k)
        + `<circle cx="${r1(cx)}" cy="${r1(cy)}" r="${r1(r)}" fill="${MONO.left}" ${OUT}/>`
        + `<circle cx="${r1(cx - r * 0.28)}" cy="${r1(cy - r * 0.3)}" r="${r1(r * 0.5)}" fill="${MONO.top}"/>`;
    },
    house(x, y, dx, dy, h) {
      const ridge = 0.42, ym = y + dy / 2;
      return mbox(x, y, 0, dx, dy, h) + monoWindows(x, y, dx, dy, h)
        + poly([[x, y, h], [x + dx, y, h], [x + dx, ym, h + ridge], [x, ym, h + ridge]], MONO.roof, OUT)
        + poly([[x, ym, h + ridge], [x + dx, ym, h + ridge], [x + dx, y + dy, h], [x, y + dy, h]], MONO.roofSide, OUT)
        + poly([[x + dx, y, h], [x + dx, y + dy, h], [x + dx, ym, h + ridge]], MONO.right, OUT);
    },
    tower(x, y, dx, dy, h) {
      return mbox(x, y, 0, dx, dy, h) + monoWindows(x, y, dx, dy, h)
        + mbox(x + dx * 0.2, y + dy * 0.25, h, 0.18, 0.18, 0.1) + mbox(x + dx * 0.6, y + dy * 0.5, h, 0.18, 0.18, 0.1);
    },
    shop(x, y, dx, dy) {
      return mbox(x, y, 0, dx, dy, 0.42) + poly([[x + 0.1, y + dy, 0.06], [x + dx - 0.1, y + dy, 0.06], [x + dx - 0.1, y + dy, 0.3], [x + 0.1, y + dy, 0.3]], MONO.glass, OUT)
        + mbox(x - 0.03, y - 0.03, 0.42, dx + 0.06, dy + 0.06, 0.05) + mbox(x + dx * 0.3, y + dy * 0.3, 0.47, 0.22, 0.16, 0.08);
    },
    lamp(x, y) {
      return line([x, y, 0], [x, y, 0.95], MONO.line, 1.4) + mbox(x - 0.05, y - 0.05, 0.95, 0.1, 0.1, 0.05);
    },
    trafficLight(x, y, state) {
      const on = {green: "#33C76A", amber: "#F5B83D", red: "#E5483C"}, dim = "#4A4F57";
      const lamp = (z, colour) => {
        const [cx, cy] = P(x + 0.06, y, z), lit = state === colour;
        return `<circle cx="${r1(cx)}" cy="${r1(cy)}" r="2.6" fill="${lit ? on[colour] : dim}"${lit ? ` stroke="${on[colour]}" stroke-opacity=".45" stroke-width="3"` : ""}/>`;
      };
      return line([x, y, 0], [x, y, 0.8], MONO.ink, 2) + box(x - 0.06, y - 0.06, 0.8, 0.12, 0.12, 0.44, "#353A66")
        + lamp(1.15, "red") + lamp(1.02, "amber") + lamp(0.89, "green");
    },
    // Overhead sign across a road (as in the reference): two poles, a bar, a board.
    gantry(cx, cy, along, w, text, boardColor) {
      const off = w / 2 + 0.22, z = 1.05;
      let s = "";
      if (along === "x") {
        const a = [cx, cy - off], b = [cx, cy + off];
        s += line([...a, 0], [...a, z], MONO.line, 1.4) + line([...b, 0], [...b, z], MONO.line, 1.4) + line([...a, z], [...b, z], MONO.line, 1.4);
        s += poly([[cx, cy + 0.48, z - 0.34], [cx, cy - 0.48, z - 0.34], [cx, cy - 0.48, z + 0.02], [cx, cy + 0.48, z + 0.02]], boardColor, 'stroke="#FFFFFF" stroke-width="0.8"');
        const [tx, ty] = P(cx, cy + 0.42, z - 0.21);
        s += `<text transform="matrix(${C30.toFixed(4)},-0.5,0,1,${r1(tx)},${r1(ty)})" font-size="7.5" font-weight="700" style="fill:#FFFFFF">${esc(text)}</text>`;
      } else {
        const a = [cx - off, cy], b = [cx + off, cy];
        s += line([...a, 0], [...a, z], MONO.line, 1.4) + line([...b, 0], [...b, z], MONO.line, 1.4) + line([...a, z], [...b, z], MONO.line, 1.4);
        s += poly([[cx - 0.48, cy, z - 0.34], [cx + 0.48, cy, z - 0.34], [cx + 0.48, cy, z + 0.02], [cx - 0.48, cy, z + 0.02]], boardColor, 'stroke="#FFFFFF" stroke-width="0.8"');
        const [tx, ty] = P(cx - 0.42, cy, z - 0.21);
        s += `<text transform="matrix(${C30.toFixed(4)},0.5,0,1,${r1(tx)},${r1(ty)})" font-size="7.5" font-weight="700" style="fill:#FFFFFF">${esc(text)}</text>`;
      }
      return s;
    },
    barrier(x, y, along, w) {
      let s = "";
      for (let i = 0; i < 4; i++) {
        const u = -w / 2 + 0.08 + i * (w - 0.16) / 3;
        const [bx, by] = along === "x" ? [x, y + u] : [x + u, y];
        s += box(bx - 0.05, by - 0.05, 0, 0.1, 0.1, 0.22, i % 2 ? "#F3F4F6" : "#D6452B");
      }
      return s;
    },
  };

  // ---------------------------------------------------------------- city layout
  // Nodes on a tile grid from the configured paths: ingress and egress at the ends,
  // one row per path, each path's inner switches spread evenly along its row.
  function cityLayout(T) {
    const pids = Object.keys(T.paths).sort(), rows = pids.length, span = STYLE.span, gap = STYLE.rowGap;
    const node = {};
    node[T.ingress] = [0, (rows - 1) * gap / 2];
    node[T.egress] = [span, (rows - 1) * gap / 2];
    pids.forEach((pid, i) => {
      const ns = T.paths[pid].nodes;
      ns.forEach((n, j) => { if (!(n in node)) node[n] = [span * j / (ns.length - 1), i * gap]; });
    });
    const maxCap = Math.max(...Object.values(T.links).map((l) => l.capacity_mbps));
    const links = {};
    for (const [lid, l] of Object.entries(T.links)) {
      const a = node[l.a], b = node[l.b], mid = (rows - 1) * gap / 2;
      let pl;
      if (a[1] === b[1]) pl = [a, b];
      else if (a[1] === mid) pl = [a, [a[0], b[1]], b]; // leave the gate vertically, then along the row
      else pl = [a, [b[0], a[1]], b];                     // along the row, then into the hub
      links[lid] = {poly: pl, w: 0.4 + 0.6 * l.capacity_mbps / maxCap, a: l.a, b: l.b};
    }
    const half = {};
    for (const n of Object.keys(node)) {
      const ws = Object.values(links).filter((k) => k.a === n || k.b === n).map((k) => k.w);
      half[n] = Math.max(0.3, ...ws) / 2 + 0.15;
    }
    return {node, links, half, bounds: {x0: -STYLE.ring, y0: -STYLE.ring, x1: span + STYLE.ring, y1: (rows - 1) * gap + STYLE.ring}};
  }
  const segRect = (a, b, w) => {
    const x0 = Math.min(a[0], b[0]), x1 = Math.max(a[0], b[0]), y0 = Math.min(a[1], b[1]), y1 = Math.max(a[1], b[1]);
    return a[1] === b[1] ? [x0, y0 - w / 2, x1 - x0, w] : [x0 - w / 2, y0, w, y1 - y0];
  };
  const polyLen = (pl) => pl.slice(1).reduce((s, p, i) => s + Math.abs(p[0] - pl[i][0]) + Math.abs(p[1] - pl[i][1]), 0);
  function pointAt(pl, s) {
    for (let i = 0; i < pl.length - 1; i++) {
      const a = pl[i], b = pl[i + 1], L = Math.abs(b[0] - a[0]) + Math.abs(b[1] - a[1]);
      if (s <= L || i === pl.length - 2) {
        const t = L ? Math.max(0, Math.min(1, s / L)) : 0;
        return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[1] === b[1] ? "x" : "y"];
      }
      s -= L;
    }
    return [pl[0][0], pl[0][1], "x"];
  }
  const hash = (x, y) => (((x + 17) * 73856093) ^ ((y + 31) * 19349663)) >>> 0;

  // ---------------------------------------------------------------- the scene
  function render(svg, opts) {
    const T = opts.topology, st = opts.state || null, limit = opts.limit || 0.9;
    const util = (st && st.link_util) || {}, bg = (st && st.background_mbps) || {}, inst = st && st.installed;
    const thr = (st && st.throughput_mbps) || {}, power = (inst && inst.link_power) || {};
    const C = cityLayout(T), {node, links, half, bounds: B} = C;
    const ground = [], marks = [], objs = [], labels = [];
    const add = (depth, svgText) => objs.push([depth, svgText]);

    // diorama slab: grass on top, soil sides
    ground.push(mbox(B.x0, B.y0, -0.35, B.x1 - B.x0, B.y1 - B.y0, 0.35, {top: MONO.ground, left: MONO.groundLeft, right: MONO.groundRight}));
    // sidewalks, then asphalt, per link segment; squares at bends and plazas at nodes
    const segs = [];
    for (const [lid, k] of Object.entries(links))
      for (let i = 0; i < k.poly.length - 1; i++) segs.push([lid, k.poly[i], k.poly[i + 1], k.w]);
    const walks = [], asphalt = [];
    for (const [, a, b, w] of segs) walks.push([...segRect(a, b, w + 0.44), MONO.walk]);
    for (const n of Object.keys(node)) { const [x, y] = node[n], h = half[n] + 0.22; walks.push([x - h, y - h, 2 * h, 2 * h, MONO.walk]); }
    for (const k of Object.values(links)) for (const p of k.poly.slice(1, -1)) { const h = k.w / 2 + 0.22; walks.push([p[0] - h, p[1] - h, 2 * h, 2 * h, MONO.walk]); }
    for (const [, a, b, w] of segs) asphalt.push([...segRect(a, b, w), MONO.road]);
    for (const k of Object.values(links)) for (const p of k.poly.slice(1, -1)) asphalt.push([p[0] - k.w / 2, p[1] - k.w / 2, k.w, k.w, MONO.road]);
    ground.push(outlined(walks), outlined(asphalt));
    for (const [lid, a, b, w] of segs) {
      const [x, y, dx, dy] = segRect(a, b, w);
      const u = util[lid];
      if (power[lid] === false) ground.push(flat(x, y, dx, dy, "#9AA1AB", 0, 'fill-opacity="0.55"'));
      else if (isNum(u) && u > 1.0) ground.push(flat(x, y, dx, dy, "#E5483C", 0, 'fill-opacity="0.45"'));
      else if (isNum(u) && u > limit) ground.push(flat(x, y, dx, dy, "#F5A524", 0, 'fill-opacity="0.4"'));
    }
    for (const n of Object.keys(node)) { const [x, y] = node[n], h = half[n]; ground.push(flat(x - h, y - h, 2 * h, 2 * h, MONO.plaza, 0, OUT)); }

    // lane dashes and zebra crossings
    for (const [, a, b, w] of segs) {
      const horiz = a[1] === b[1], len = Math.abs(horiz ? b[0] - a[0] : b[1] - a[1]), dir = Math.sign(horiz ? b[0] - a[0] : b[1] - a[1]);
      const startPad = (node_at(a) ? half[node_at(a)] : w / 2) + 0.35, endPad = (node_at(b) ? half[node_at(b)] : w / 2) + 0.35;
      for (let s = startPad; s + 0.3 < len - endPad; s += 0.6) {
        const c = horiz ? [a[0] + dir * (s + 0.15), a[1]] : [a[0], a[1] + dir * (s + 0.15)];
        marks.push(horiz ? flat(c[0] - 0.15, c[1] - 0.025, 0.3, 0.05, MONO.paint) : flat(c[0] - 0.025, c[1] - 0.15, 0.05, 0.3, MONO.paint));
      }
      for (const [end, sgn] of [[a, dir], [b, -dir]]) {
        const n = node_at(end); if (!n) continue;
        const from = half[n] + 0.04;
        for (let v = -w / 2 + 0.06; v + 0.06 <= w / 2; v += 0.13)
          marks.push(horiz ? flat(end[0] + sgn * from + (sgn > 0 ? 0 : -0.26), end[1] + v, 0.26, 0.065, MONO.paint)
                           : flat(end[0] + v, end[1] + sgn * from + (sgn > 0 ? 0 : -0.26), 0.065, 0.26, MONO.paint));
      }
    }
    function node_at(p) { return Object.keys(node).find((n) => node[n][0] === p[0] && node[n][1] === p[1]); }

    // decor in the free tiles: never on a road or plaza
    const busy = (cx, cy) => segs.some(([, a, b, w]) => { const [x, y, dx, dy] = segRect(a, b, w + 1.2); return cx > x && cx < x + dx && cy > y && cy < y + dy; })
      || Object.keys(node).some((n) => Math.abs(cx - node[n][0]) < half[n] + 0.8 && Math.abs(cy - node[n][1]) < half[n] + 0.8);
    for (let gx = Math.ceil(B.x0); gx < B.x1 - 0.5; gx++) for (let gy = Math.ceil(B.y0); gy < B.y1 - 0.5; gy++) {
      const cx = gx + 0.5, cy = gy + 0.5;
      if (busy(cx, cy) || hash(gy, gx) % 100 >= STYLE.decorDensity) continue; // keep the city sparse
      const h = hash(gx, gy) % 100, x = gx + 0.2, y = gy + 0.2; // a 0.6-tile lot in the middle of the tile
      // tall objects hide what lies behind them on screen, so towers only stand in the
      // back ring (behind every road); elsewhere the city stays low
      const back = cx < 0 || cy < 0;
      if (h < 22) add(cx + cy, Asset.house(x, y, 0.6, 0.6, back ? 0.58 : 0.46));
      else if (h < 36 && back) add(cx + cy, Asset.tower(x, y, 0.6, 0.6, 1.3 + (h % 3) * 0.25));
      else if (h < 48) add(cx + cy, Asset.shop(x, y, 0.6, 0.55));
      else if (h < 90) add(cx + cy, Asset.tree(cx, cy, 0.85));
      else add(cx + cy, Asset.lamp(cx, cy));
    }

    // vehicles: count follows the rate; unknown rates draw none
    const route = (pid) => {
      const p = T.paths[pid]; if (!p) return null;
      const out = [];
      for (const lid of p.links) { const pl = links[lid].poly; for (const q of (out.length ? pl.slice(1) : pl)) out.push(q); }
      return out;
    };
    const place = (pl, n, lane, phase, draw) => {
      const L = polyLen(pl), lo = 0.7, hi = L - 0.7;
      // never stop on an intersection: its painted name stays readable
      const onPlaza = (x, y) => Object.keys(node).some((m) => Math.abs(x - node[m][0]) < half[m] + 0.4 && Math.abs(y - node[m][1]) < half[m] + 0.4);
      for (let i = 0; i < n; i++) {
        let s = lo + ((i + phase) / n % 1) * (hi - lo), [x, y, along] = pointAt(pl, s);
        for (let k = 0; k < 4 && onPlaza(x, y); k++) { s = lo + ((s - lo + 0.5) % (hi - lo)); [x, y, along] = pointAt(pl, s); }
        if (onPlaza(x, y)) continue;
        const [vx, vy] = along === "x" ? [x, y + lane] : [x + lane, y];
        add(vx + vy, draw(vx, vy, along, i));
      }
    };
    const phase = ((opts.t || 0) * 0.137) % 1;
    if (inst) {
      const counts = {
        urllc: (v) => Math.max(1, Math.min(3, Math.round(v / 1.5 * STYLE.vehicleDensity))),
        embb: (v) => Math.max(1, Math.min(10, Math.round(v / 14 * STYLE.vehicleDensity))),
        mmtc: (v) => Math.max(1, Math.min(8, Math.round(v / 0.5 * STYLE.vehicleDensity))),
      };
      for (const sl of Object.keys(counts)) {
        const pl = route(inst.path[sl]), v = thr[sl];
        if (!pl || !isNum(v) || v <= 0) continue;
        const k = links[T.paths[inst.path[sl]].links[0]].w;
        const lane = k / 4;
        if (sl === "urllc") place(pl, counts.urllc(v), lane, phase, (x, y, al) => Asset.ambulance(x, y, al));
        if (sl === "embb") place(pl, counts.embb(v), lane, (phase + 0.31) % 1, (x, y, al) => Asset.bus(x, y, al, "#1F6FD1"));
        if (sl === "mmtc") place(pl, counts.mmtc(v), lane, (phase + 0.57) % 1, (x, y, al) => Asset.scooter(x, y, al, "#2E8B57"));
      }
    }
    const civ = ["#9AA1AB", "#C9524A", "#E3B341", "#7C8592", "#B5BBC4", "#5E7FA8"];
    for (const [lid, k] of Object.entries(links)) {
      const v = bg[lid];
      if (power[lid] === false || !isNum(v) || v <= 0.5) continue;
      place(k.poly, Math.max(1, Math.min(12, Math.round(v / 12 * STYLE.vehicleDensity))), -k.w / 4, (phase + 0.73) % 1, (x, y, al, i) => Asset.car(x, y, al, civ[i % civ.length]));
    }

    // overhead signs: one per link, on its longest segment, showing utilization
    for (const [lid, k] of Object.entries(links)) {
      let best = null;
      for (let i = 0; i < k.poly.length - 1; i++) {
        const a = k.poly[i], b = k.poly[i + 1], L = Math.abs(b[0] - a[0]) + Math.abs(b[1] - a[1]);
        if (!best || L > best[2]) best = [a, b, L];
      }
      const [a, b] = best, horiz = a[1] === b[1];
      const c = horiz ? [a[0] + (b[0] - a[0]) * 0.62, a[1]] : [a[0], a[1] + (b[1] - a[1]) * 0.62];
      const u = util[lid], off = power[lid] === false;
      const text = off ? `${lid} closed` : isNum(u) ? `${lid} ${Math.round(u * 100)}%` : `${lid} n/a`;
      const colour = off ? "#7A808A" : !isNum(u) ? "#7A808A" : u > 1.0 ? "#C0362C" : u > limit ? "#C77700" : "#2F7D4A";
      add(c[0] + c[1] + 0.3, Asset.gantry(c[0], c[1], horiz ? "x" : "y", k.w, text, colour));
      if (off) { add(a[0] + a[1], Asset.barrier(...(horiz ? [a[0] + (b[0] > a[0] ? 1 : -1) * 0.8, a[1]] : [a[0], a[1] + (b[1] > a[1] ? 1 : -1) * 0.8]), horiz ? "y" : "x", k.w)); }
    }

    // the city gate's traffic light shows the controller's decision
    const light = {"CERTIFIED ACTION": "green", "CERTIFIED FALLBACK": "amber", "UNVERIFIED (baseline)": "amber",
                   "UNCERTIFIED FALLBACK": "red", "NOT APPLIED": "red"}[opts.decision] || null;
    { const [x, y] = node[T.ingress], h = half[T.ingress]; add(x + y - 2 * h, Asset.trafficLight(x - h - 0.12, y - h - 0.12, light)); }

    // switch names painted on their intersections (ground layer: vehicles pass over paint)
    for (const n of Object.keys(node)) {
      const [x, y] = node[n];
      marks.push(paintNode(x, y, half[n], n, n === T.ingress ? "GATE" : n === T.egress ? "HUB" : ""));
    }
    // path names (flat text, on top)
    for (const pid of Object.keys(T.paths)) { // beside the path's middle switch, off the road
      const ns = T.paths[pid].nodes, m = ns[Math.floor(ns.length / 2)], [x, y] = node[m], h = half[m];
      const [tx, ty] = P(x - h - 0.9, y - h - 0.25, 0);
      labels.push(`<text x="${r1(tx)}" y="${r1(ty)}" text-anchor="middle" font-size="11" font-weight="700" style="fill:#FFFFFF;stroke:${MONO.ink};stroke-width:3.5px;paint-order:stroke">Path ${esc(pid)}</text>`);
    }

    objs.sort((a, b) => a[0] - b[0]);
    const [xa] = P(B.x0, B.y1, 0), [xb] = P(B.x1, B.y0, 0), [, ya] = P(B.x0, B.y0, 1.6), [, yb] = P(B.x1, B.y1, -0.35);
    svg.setAttribute("viewBox", `${r1(xa - 12)} ${r1(ya - 8)} ${r1(xb - xa + 24)} ${r1(yb - ya + 20)}`);
    svg.innerHTML = ground.join("") + marks.join("") + objs.map((o) => o[1]).join("") + labels.join("");

    return legend(T, limit, light);
  }

  // ---------------------------------------------------------------- illustrated key
  // Each entry is drawn with the same assets as the scene, fitted into a small icon.
  function icon(inner) {
    const xs = [], ys = [];
    for (const m of inner.matchAll(/points="([^"]+)"/g))
      for (const pr of m[1].split(" ")) { const [x, y] = pr.split(",").map(Number); xs.push(x); ys.push(y); }
    for (const m of inner.matchAll(/x1="([-\d.]+)" y1="([-\d.]+)" x2="([-\d.]+)" y2="([-\d.]+)"/g)) { xs.push(+m[1], +m[3]); ys.push(+m[2], +m[4]); }
    for (const m of inner.matchAll(/cx="([-\d.]+)" cy="([-\d.]+)" r="([-\d.]+)"/g)) { xs.push(+m[1] - +m[3], +m[1] + +m[3]); ys.push(+m[2] - +m[3], +m[2] + +m[3]); }
    const pad = 3, x0 = Math.min(...xs) - pad, y0 = Math.min(...ys) - pad;
    const w = Math.max(...xs) + pad - x0, h = Math.max(...ys) + pad - y0;
    return `<svg viewBox="${r1(x0)} ${r1(y0)} ${r1(w)} ${r1(h)}" aria-hidden="true" preserveAspectRatio="xMidYMid meet">${inner}</svg>`;
  }
  const entry = (art, title, text) => `<div class="iso-item">${icon(art)}<div><b>${title}</b><span>${text}</span></div></div>`;
  function roads(T) {
    const caps = Object.values(T.links).map((l) => l.capacity_mbps), lo = Math.min(...caps), hi = Math.max(...caps);
    let s = "";
    for (const [y, cap] of [[0, lo], [1.6, hi]]) {
      const w = 0.4 + 0.6 * cap / hi;
      s += flat(0, y - w / 2 - 0.2, 2, w + 0.4, MONO.walk, 0, OUT) + flat(0, y - w / 2, 2, w, MONO.road, 0, OUT);
      for (let x = 0.2; x < 1.9; x += 0.6) s += flat(x, y - 0.025, 0.3, 0.05, MONO.paint);
    }
    return [s, lo, hi];
  }
  function plaza() {
    let s = flat(-0.7, -0.7, 1.4, 1.4, MONO.walk, 0, OUT) + flat(-0.5, -0.5, 1.0, 1.0, MONO.plaza, 0, OUT);
    for (let v = -0.42; v < 0.4; v += 0.13) s += flat(0.52, v, 0.24, 0.065, MONO.paint) + flat(v, 0.52, 0.065, 0.24, MONO.paint);
    return s + paintNode(0, 0, 0.5, "s1", "GATE");
  }
  function legend(T, limit, light) {
    const [roadArt, lo, hi] = roads(T);
    const signs = Asset.gantry(0, 0, "x", 0.3, "OK", "#2F7D4A") + Asset.gantry(0, 1.5, "x", 0.3, `>${Math.round(limit * 100)}%`, "#C77700")
      + Asset.gantry(0, 3.0, "x", 0.3, ">100%", "#C0362C");
    const now = light ? {green: "now green: certified action", amber: "now amber: fallback or unverified action", red: "now red: uncertified fallback or not applied"}[light]
      : "off until the first decision";
    return `<div class="iso-legend">`
      + entry(Asset.ambulance(0, 0, "x"), "Ambulance · URLLC", "low-latency slice (1 ms promise)")
      + entry(Asset.bus(0, 0, "x", "#1F6FD1"), "Bus · eMBB", "high-throughput slice")
      + entry(Asset.scooter(0, 0, "x", "#2E8B57"), "Scooter · mMTC", "many small devices")
      + entry(Asset.car(0, 0, "x", "#9AA1AB") + Asset.car(0.9, 0.45, "x", "#C9524A"), "Other cars · background", "traffic the controller does not manage")
      + entry(roadArt, "Road · link", `wider road = more capacity (${hi} vs ${lo} Mb/s)`)
      + entry(plaza(), "Intersection · switch", `name painted on the road; ${esc(T.ingress)} gate = ingress, ${esc(T.egress)} hub = egress`)
      + entry(signs, "Overhead sign · utilization", `green within the ${limit} limit · amber over it · red over capacity`)
      + entry(Asset.trafficLight(0, 0, light), "Gate light · decision", `${now}. Red also means not shown safe.`)
      + `</div>`;
  }

  window.VGCPIso = {render, project: P, layout: cityLayout};
})();
