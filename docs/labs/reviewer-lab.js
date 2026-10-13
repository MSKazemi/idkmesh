"use strict";

/*
 * Optional, offline Reviewer Lab. This is an educational projection of the
 * ground-truthed fixture, NOT the full idkmesh gate-audit implementation.
 * It deliberately does not compute effective votes, statistical independence,
 * confidence intervals, or recommendation/merge authority.
 *
 * This file uses no network, no storage, no third-party scripts, and no eval.
 * Keep the approval predicate aligned with idkmesh/gate_audit.py:
 * accept_votes > quorum * total (strictly greater; ties reject).
 */
(function () {
  function analyze(fixture, selectedIds, quorum) {
    if (!Array.isArray(selectedIds) || selectedIds.length === 0 ||
        !Number.isFinite(quorum) || quorum <= 0 || quorum >= 1) {
      throw new Error("Select at least one reviewer and a valid threshold.");
    }
    const reviewers = fixture.verifiers.filter(function (v) {
      return selectedIds.includes(v.id);
    });
    if (reviewers.length !== selectedIds.length ||
        new Set(selectedIds).size !== selectedIds.length) {
      throw new Error("Unknown or repeated reviewer selection.");
    }
    const rows = fixture.candidates.map(function (candidate) {
      const approvalCount = reviewers.filter(function (reviewer) {
        return reviewer.verdicts[candidate.id] === "accept";
      }).length;
      const panelVerdict = approvalCount > quorum * reviewers.length
        ? "accept" : "reject";
      return {
        id: candidate.id,
        groundTruth: candidate.ground_truth,
        probe: candidate.probe === true,
        probeKind: candidate.probe_kind || "",
        approvalCount: approvalCount,
        total: reviewers.length,
        panelVerdict: panelVerdict,
        wrong: panelVerdict !== candidate.ground_truth,
        wrongReviewers: reviewers.filter(function (reviewer) {
          return reviewer.verdicts[candidate.id] !== candidate.ground_truth;
        }).map(function (reviewer) { return reviewer.id; })
      };
    });
    const normal = rows.filter(function (row) { return !row.probe; });
    const probes = rows.filter(function (row) { return row.probe; });
    const pairs = [];
    for (let a = 0; a < reviewers.length; a += 1) {
      for (let b = a + 1; b < reviewers.length; b += 1) {
        const first = reviewers[a].id;
        const second = reviewers[b].id;
        pairs.push({
          first: first,
          second: second,
          sharedIds: normal.filter(function (row) {
            return row.wrongReviewers.includes(first) &&
              row.wrongReviewers.includes(second);
          }).map(function (row) { return row.id; })
        });
      }
    }
    pairs.sort(function (a, b) {
      return b.sharedIds.length - a.sharedIds.length ||
        a.first.localeCompare(b.first) ||
        a.second.localeCompare(b.second);
    });
    return {
      rows: rows,
      pairs: pairs,
      activeIds: reviewers.map(function (reviewer) { return reviewer.id; }),
      requiredApprovals: Math.floor(quorum * reviewers.length) + 1,
      falseAccepts: normal.filter(function (row) {
        return row.wrong && row.panelVerdict === "accept";
      }).length,
      falseRejects: normal.filter(function (row) {
        return row.wrong && row.panelVerdict === "reject";
      }).length,
      probeBreaches: probes.filter(function (row) {
        return row.panelVerdict === "accept";
      }).length,
      normalCount: normal.length,
      probeCount: probes.length
    };
  }

  // Node's built-in test runner can check the *actual* browser calculation.
  if (typeof module !== "undefined" && module.exports) {
    module.exports = { analyze: analyze };
  }
  if (typeof document === "undefined") {
    return;
  }

  function el(tag, className, textValue) {
    const node = document.createElement(tag);
    if (className) { node.className = className; }
    if (textValue !== undefined) { node.textContent = textValue; }
    return node;
  }

  function readable(id) {
    return id.replace("reviewer-", "Reviewer ").replace(/(^|\s)\w/g, function (m) {
      return m.toUpperCase();
    });
  }

  function start() {
    const payload = document.getElementById("votes-fixture");
    const errorNode = document.getElementById("lab-error");
    if (!payload || !errorNode) { return; }
    let fixture;
    try {
      fixture = JSON.parse(payload.textContent);
    } catch (err) {
      errorNode.textContent = "The bundled example could not be read.";
      errorNode.hidden = false;
      return;
    }
    const checkboxes = Array.from(document.querySelectorAll('input[name="lab-reviewer"]'));
    const rule = document.getElementById("lab-quorum");
    const candidate = document.getElementById("lab-candidate");
    const live = document.getElementById("lab-live");
    const voteGrid = document.getElementById("lab-votes");
    const tableBody = document.getElementById("lab-rows");

    fixture.candidates.forEach(function (entry) {
      const option = document.createElement("option");
      option.value = entry.id;
      option.textContent = entry.id + (entry.probe ? " · known-bad probe" : " · ordinary example");
      candidate.appendChild(option);
    });
    candidate.value = "p01";

    function showCandidate(id) {
      candidate.value = id;
      render();
      candidate.focus();
    }

    function render() {
      const ids = checkboxes.filter(function (input) {
        return input.checked;
      }).map(function (input) { return input.value; });
      let analysis;
      try {
        analysis = analyze(fixture, ids, Number(rule.value));
      } catch (err) {
        errorNode.textContent = "Select at least one reviewer to continue.";
        errorNode.hidden = false;
        return;
      }
      errorNode.hidden = true;
      const focused = analysis.rows.find(function (row) {
        return row.id === candidate.value;
      }) || analysis.rows[0];
      const original = fixture.candidates.find(function (row) {
        return row.id === focused.id;
      });
      const threshold = Math.round(Number(rule.value) * 100);
      document.getElementById("lab-required").textContent =
        "At least " + analysis.requiredApprovals + " of " + ids.length +
        " approvals are required (strictly more than " + threshold + "%). Ties reject.";
      document.getElementById("lab-false-accepts").textContent =
        String(analysis.falseAccepts) + " / " + analysis.normalCount;
      document.getElementById("lab-false-rejects").textContent =
        String(analysis.falseRejects) + " / " + analysis.normalCount;
      document.getElementById("lab-breaches").textContent =
        String(analysis.probeBreaches) + " / " + analysis.probeCount;

      document.getElementById("lab-truth").textContent =
        focused.groundTruth === "accept" ? "Should APPROVE" : "Should REJECT";
      document.getElementById("lab-panel").textContent =
        focused.panelVerdict === "accept" ? "Panel APPROVES" : "Panel REJECTS";
      const status = document.getElementById("lab-status");
      status.textContent = focused.wrong ? "Mistake: panel disagrees with the known answer" :
        "Matches the known answer";
      status.className = "lab-status " + (focused.wrong ? "lab-status-wrong" : "lab-status-right");
      document.getElementById("lab-vote-count").textContent =
        focused.approvalCount + " of " + ids.length + " selected reviewers approved " +
        focused.id + ".";
      document.getElementById("lab-candidate-context").textContent =
        original.probe ?
        "This candidate is a deliberately known-bad " +
          original.probe_kind.replace(/-/g, " ") + " probe." :
        "This is an ordinary labelled candidate (not a seeded probe).";

      voteGrid.replaceChildren();
      fixture.verifiers.forEach(function (reviewer) {
        const value = reviewer.verdicts[focused.id];
        const active = ids.includes(reviewer.id);
        const isWrong = value !== focused.groundTruth;
        const card = el("div", "lab-vote-card" + (active ? "" : " lab-excluded"));
        card.appendChild(el("strong", "lab-reviewer", readable(reviewer.id)));
        card.appendChild(el("span", "lab-verdict " + (value === "accept" ?
          "lab-approve" : "lab-reject"), value === "accept" ? "APPROVE" : "REJECT"));
        card.appendChild(el("small", "lab-vote-note", active ?
          (isWrong ? "Wrong vote" : "Correct vote") :
          "Not counted in this panel"));
        voteGrid.appendChild(card);
      });

      const pairNode = document.getElementById("lab-pair-summary");
      const top = analysis.pairs[0];
      if (top) {
        pairNode.textContent = readable(top.first) + " and " + readable(top.second) +
          " made the same wrong decision on " + top.sharedIds.length +
          " of the " + analysis.normalCount + " ordinary candidates" +
          (top.sharedIds.length ? " (" + top.sharedIds.join(", ") + ")." : ".");
      } else {
        pairNode.textContent = "Choose two or more reviewers to compare overlapping mistakes.";
      }

      tableBody.replaceChildren();
      analysis.rows.forEach(function (row) {
        const tr = el("tr", (row.probe ? "lab-probe-row " : "") +
          (row.id === focused.id ? "lab-selected-row" : ""));
        const heading = el("th", "", row.id + (row.probe ? " · probe" : ""));
        heading.scope = "row";
        tr.appendChild(heading);
        tr.appendChild(el("td", "", row.groundTruth === "accept" ? "Approve" : "Reject"));
        tr.appendChild(el("td", "", row.approvalCount + " / " + row.total));
        tr.appendChild(el("td", "", row.panelVerdict === "accept" ? "Approve" : "Reject"));
        tr.appendChild(el("td", row.wrong ? "lab-cell-wrong" : "lab-cell-right",
          row.wrong ? "Wrong" : "Correct"));
        const last = el("td");
        const inspect = el("button", "lab-inspect", "Inspect");
        inspect.type = "button";
        inspect.setAttribute("aria-label", "Inspect candidate " + row.id);
        inspect.setAttribute("aria-pressed", row.id === focused.id ? "true" : "false");
        inspect.addEventListener("click", function () { showCandidate(row.id); });
        last.appendChild(inspect);
        tr.appendChild(last);
        tableBody.appendChild(tr);
      });
      live.textContent = "Candidate " + focused.id + ": " + focused.approvalCount +
        " of " + ids.length + " approve; panel " + focused.panelVerdict +
        "; known answer " + focused.groundTruth + "; " +
        (focused.wrong ? "incorrect" : "correct") + ". " +
        "Across ordinary candidates: " + analysis.falseAccepts +
        " false accepts and " + analysis.falseRejects +
        " false rejects; " + analysis.probeBreaches + " of " +
        analysis.probeCount + " known-bad probes breached.";
    }

    checkboxes.forEach(function (input) {
      input.addEventListener("change", function () {
        if (!checkboxes.some(function (box) { return box.checked; })) {
          input.checked = true;
          errorNode.textContent = "Keep at least one reviewer selected.";
          errorNode.hidden = false;
          return;
        }
        render();
      });
    });
    rule.addEventListener("change", render);
    candidate.addEventListener("change", render);
    document.getElementById("lab-reset").addEventListener("click", function () {
      checkboxes.forEach(function (input) { input.checked = true; });
      rule.value = "0.5";
      showCandidate("p01");
    });
    document.getElementById("lab-example-probe").addEventListener("click", function () {
      showCandidate("p01");
    });
    document.getElementById("lab-example-shared").addEventListener("click", function () {
      showCandidate("c10");
    });
    render();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
})();
