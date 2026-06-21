const form = document.getElementById("metar-form");
const input = document.getElementById("code-input");
const statusEl = document.getElementById("status");
const resultEl = document.getElementById("result");
const iconEl = document.getElementById("icon");
const stationNameEl = document.getElementById("station-name");
const summaryEl = document.getElementById("summary");
const detailsTableEl = document.getElementById("details-table");
const rawMetarEl = document.getElementById("raw-metar");

function showStatus(message, isError) {
  statusEl.textContent = message;
  statusEl.className = "status" + (isError ? " error" : "");
  statusEl.hidden = false;
}

function hideStatus() {
  statusEl.hidden = true;
}

function renderResult(data) {
  iconEl.textContent = data.icon || "";
  stationNameEl.textContent = data.station;
  summaryEl.textContent = data.summary;

  detailsTableEl.innerHTML = "";
  data.details.forEach(([label, value]) => {
    const row = document.createElement("tr");
    const th = document.createElement("th");
    th.textContent = label;
    const td = document.createElement("td");
    td.textContent = value;
    row.append(th, td);
    detailsTableEl.appendChild(row);
  });

  rawMetarEl.textContent = data.raw;
  resultEl.hidden = false;
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const code = input.value.trim();
  if (!code) {
    showStatus("Please enter an airport code.", true);
    return;
  }

  resultEl.hidden = true;
  showStatus("Fetching weather…", false);

  try {
    const response = await fetch(`/api/metar?code=${encodeURIComponent(code)}`);
    const data = await response.json();

    if (!response.ok) {
      showStatus(data.error || "Something went wrong.", true);
      return;
    }

    hideStatus();
    renderResult(data);
  } catch (err) {
    showStatus("Could not reach the server. Please try again.", true);
  }
});
