"use strict";

const form = document.getElementById("search-form");
const searchButton = document.getElementById("searchButton");
const lookupStatus = document.getElementById("lookup-status");
const coordinateFields = ["ra_hours", "ra_minutes", "ra_seconds", "dec_degrees", "dec_minutes", "dec_seconds"];

function updateSearchButton() {
    const complete = coordinateFields.every(name => {
        const input = form.elements.namedItem(name);
        return input.value.trim() && input.validity.valid;
    });
    searchButton.disabled = !complete || !form.elements.namedItem("search_degrees").validity.valid;
    searchButton.textContent = "Buscar fuentes";
}

function setLookupStatus(message, error = false) {
    lookupStatus.textContent = message;
    lookupStatus.hidden = !message;
    lookupStatus.toggleAttribute("data-error", error);
}

form.querySelectorAll("[data-mode]").forEach(button => {
    button.addEventListener("click", () => {
        form.elements.namedItem("coordinate_source").value = button.dataset.mode;
        form.querySelectorAll("[data-mode]").forEach(mode => {
            mode.setAttribute("aria-pressed", String(mode === button));
        });
        form.querySelectorAll("[data-panel]").forEach(panel => {
            panel.hidden = panel.dataset.panel !== button.dataset.mode;
        });
        setLookupStatus("");
    });
});

form.querySelectorAll("[data-lookup]").forEach(button => {
    button.addEventListener("click", async () => {
        const input = button.closest("[data-panel]").querySelector("input");
        const identifier = input.value.trim();
        if (!identifier) {
            setLookupStatus("Introduce un identificador.", true);
            input.focus();
            return;
        }

        button.disabled = true;
        setLookupStatus("Consultando coordenadas…");
        try {
            const response = await fetch(button.dataset.lookup, {
                method: "POST",
                body: new URLSearchParams({ [input.name]: identifier }),
            });
            const result = await response.json();
            if (!response.ok || result.error) {
                setLookupStatus(result.error || "No se pudieron consultar las coordenadas.", true);
                return;
            }
            coordinateFields.forEach(name => {
                form.elements.namedItem(name).value = name === "dec_degrees"
                    ? (result.dec_degrees_text ?? result.dec_degrees)
                    : result[name];
            });
            setLookupStatus("");
            updateSearchButton();
        } catch {
            setLookupStatus("No se pudo conectar con el servicio de coordenadas.", true);
        } finally {
            button.disabled = false;
        }
    });
});

form.addEventListener("input", updateSearchButton);
form.addEventListener("submit", () => {
    searchButton.disabled = true;
    searchButton.textContent = "Buscando…";
});
window.addEventListener("pageshow", updateSearchButton);
updateSearchButton();

const rows = Array.from(document.querySelectorAll(".results-table tr[data-object]"));
const rowsById = new Map(rows.map(row => [row.dataset.object, row]));
const card = document.getElementById("source-card");
const cardTitle = document.getElementById("source-card-title");
const cardData = document.getElementById("source-card-data");
const spectrum = document.getElementById("source-spectrum");
const spectrumView = document.getElementById("spectrum-view");
const fullscreenButton = document.getElementById("spectrum-fullscreen");
const frame = document.getElementById("spectrum-frame");
const spectrumModes = spectrum.querySelectorAll("[data-spectrum]");
let selectedRow = null;
let sourceTrigger = null;
let aladin = null;

function showSpectrum(kind) {
    const path = selectedRow.dataset[kind];
    const url = new URL(path, window.location.origin);
    url.searchParams.set("embed", "1");
    if (frame.src !== url.href) frame.src = url.href;
    frame.title = kind === "sampled" ? "Espectro muestreado" : "Espectro continuo";
    spectrumModes.forEach(mode => {
        mode.setAttribute("aria-pressed", String(mode.dataset.spectrum === kind));
    });
}

function updateFullscreenButton() {
    const expanded = document.fullscreenElement === spectrumView || spectrum.matches(":modal");
    fullscreenButton.textContent = expanded ? "Salir de pantalla completa" : "Ver espectro a pantalla completa";
    fullscreenButton.focus({ preventScroll: true });
}

function closeSpectrumModal() {
    spectrum.close();
    spectrum.show();
    updateFullscreenButton();
}

fullscreenButton.addEventListener("click", async () => {
    if (document.fullscreenElement === spectrumView) {
        await document.exitFullscreen();
        return;
    }
    if (spectrum.matches(":modal")) {
        closeSpectrumModal();
        return;
    }
    if (document.fullscreenEnabled) {
        try {
            await spectrumView.requestFullscreen();
            return;
        } catch {
            // Si el navegador rechaza la pantalla completa, amplía el espectro en la página.
        }
    }
    spectrum.close();
    spectrum.showModal();
    updateFullscreenButton();
});
spectrumView.addEventListener("fullscreenchange", updateFullscreenButton);
spectrum.addEventListener("cancel", event => {
    event.preventDefault();
    closeSpectrumModal();
});

function openSource(row, trigger, preferredSpectrum) {
    if (!row) return;
    if (selectedRow) {
        selectedRow.classList.remove("is-selected");
        selectedRow.querySelector("[data-open-source]").setAttribute("aria-expanded", "false");
    }
    selectedRow = row;
    sourceTrigger = trigger;
    row.classList.add("is-selected");
    row.querySelector("[data-open-source]").setAttribute("aria-expanded", "true");
    cardTitle.textContent = row.dataset.object || "Fuente Gaia DR3";
    cardData.replaceChildren(row.querySelector(".source-detail").content.cloneNode(true));

    const defaultSpectrum = row.dataset.sampled ? "sampled" : "continuous";
    spectrum.hidden = !row.dataset.sampled && !row.dataset.continuous;
    spectrumModes.forEach(mode => { mode.hidden = !row.dataset[mode.dataset.spectrum]; });
    if (spectrum.hidden) {
        frame.removeAttribute("src");
    } else {
        const availableKind = preferredSpectrum && row.dataset[preferredSpectrum] ? preferredSpectrum : defaultSpectrum;
        showSpectrum(availableKind);
    }
    card.hidden = false;
    card.querySelector(".source-card-body").scrollTop = 0;
    cardTitle.focus({ preventScroll: true });
}

function closeSource() {
    if (card.hidden) return;
    card.hidden = true;
    frame.removeAttribute("src");
    selectedRow.classList.remove("is-selected");
    selectedRow.querySelector("[data-open-source]").setAttribute("aria-expanded", "false");
    selectedRow = null;
    sourceTrigger?.focus({ preventScroll: true });
    sourceTrigger = null;
}

function numberValue(value) {
    return value === "" || value === undefined ? NaN : Number(value);
}

rows.forEach(row => {
    row.querySelectorAll("[data-open-source], [data-open-spectrum]").forEach(button => {
        button.addEventListener("click", () => {
            const ra = numberValue(row.dataset.ra);
            const dec = numberValue(row.dataset.dec);
            if (aladin && Number.isFinite(ra) && Number.isFinite(dec)) aladin.gotoRaDec(ra, dec);
            openSource(row, button, button.dataset.openSpectrum);
        });
    });
});
spectrumModes.forEach(mode => {
    mode.addEventListener("click", () => showSpectrum(mode.dataset.spectrum));
});
document.getElementById("close-source-card").addEventListener("click", closeSource);
function handleEscape(event) {
    if (event.key !== "Escape" || event.defaultPrevented) return;
    if (document.fullscreenElement === spectrumView) {
        event.preventDefault();
        void document.exitFullscreen();
    } else if (spectrum.matches(":modal")) {
        event.preventDefault();
        closeSpectrumModal();
    } else if (!document.fullscreenElement) {
        closeSource();
    }
}
document.addEventListener("keydown", handleEscape);
frame.addEventListener("load", () => {
    frame.contentDocument?.addEventListener("keydown", handleEscape);
});

const sortButtons = document.querySelectorAll(".results-table [data-sort]");
const byId = new Intl.Collator("es", { numeric: true });
sortButtons.forEach(button => {
    button.addEventListener("click", () => {
        const column = button.closest("th");
        const descending = column.getAttribute("aria-sort") === "ascending";
        sortButtons.forEach(sort => sort.closest("th").removeAttribute("aria-sort"));
        column.setAttribute("aria-sort", descending ? "descending" : "ascending");
        const key = button.dataset.sort === "id" ? "object" : button.dataset.sort;
        const sorted = [...rows].sort((first, second) => {
            const a = first.dataset[key];
            const b = second.dataset[key];
            if (key === "object") return (descending ? -1 : 1) * byId.compare(a, b);
            const firstValue = numberValue(a);
            const secondValue = numberValue(b);
            if (!Number.isFinite(firstValue)) return Number.isFinite(secondValue) ? 1 : 0;
            if (!Number.isFinite(secondValue)) return -1;
            return (descending ? -1 : 1) * (firstValue - secondValue);
        });
        button.closest("table").tBodies[0].append(...sorted);
    });
});

const map = document.getElementById("aladin-lite-div");
const mapPanel = document.getElementById("sky-panel");
const mapStatus = document.getElementById("map-status");

function initializeMap() {
    const Atlas = window.A;
    if (!Atlas) {
        mapStatus.textContent = "El mapa de Aladin no está disponible.";
        return;
    }
    try {
        const radius = Number(map.dataset.radius);
        const target = map.dataset.target;
        const options = { survey: "P/DSS2/color", showReticle: true };
        if (target) {
            options.target = target;
            options.fov = radius * 8;
        }
        aladin = Atlas.aladin("#aladin-lite-div", options);
        mapStatus.hidden = true;
        if (target) {
            const [ra, dec] = target.split(" ").map(Number);
            const region = Atlas.graphicOverlay({ color: "#b3e332", lineWidth: 2 });
            aladin.addOverlay(region);
            region.add(Atlas.circle(ra, dec, radius));
        }

        const colors = getComputedStyle(document.documentElement);
        const groups = [
            { color: colors.getPropertyValue("--red").trim(), name: "BP−RP < 0,52", sources: [] },
            { color: colors.getPropertyValue("--yellow").trim(), name: "0,52 ≤ BP−RP < 1,12", sources: [] },
            { color: colors.getPropertyValue("--blue").trim(), name: "BP−RP ≥ 1,12", sources: [] },
            { color: colors.getPropertyValue("--neutral").trim(), name: "Sin BP−RP", sources: [] },
        ];
        rows.forEach(row => {
            const ra = numberValue(row.dataset.ra);
            const dec = numberValue(row.dataset.dec);
            if (!Number.isFinite(ra) || !Number.isFinite(dec)) return;
            const color = numberValue(row.dataset.color);
            let group = 3;
            if (Number.isFinite(color)) group = color < 0.52 ? 0 : color < 1.12 ? 1 : 2;
            groups[group].sources.push(Atlas.source(ra, dec, { gaiaId: row.dataset.object }));
        });
        groups.filter(group => group.sources.length).forEach(group => {
            const catalog = Atlas.catalog({
                name: group.name,
                color: group.color,
                sourceSize: 10,
                shape: "circle",
                onClick: source => openSource(rowsById.get(source.data.gaiaId), map),
            });
            aladin.addCatalog(catalog);
            catalog.addSources(group.sources);
        });
    } catch {
        mapStatus.hidden = false;
        mapStatus.textContent = "No se pudo iniciar el mapa de Aladin.";
    }
}

mapPanel.addEventListener("toggle", () => {
    if (mapPanel.open) window.dispatchEvent(new Event("resize"));
});
initializeMap();

const cookieNotice = document.getElementById("cookie-notice");
try {
    cookieNotice.hidden = localStorage.getItem("cookieConsent") === "true";
    document.getElementById("accept-cookies").addEventListener("click", () => {
        localStorage.setItem("cookieConsent", "true");
        cookieNotice.hidden = true;
    });
} catch {
    cookieNotice.hidden = true;
}
