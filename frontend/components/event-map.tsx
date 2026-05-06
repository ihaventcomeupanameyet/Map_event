"use client";

import { useEffect, useRef, useState } from "react";

import type { EventRecord } from "@/lib/api";


const VANCOUVER_CENTER: [number, number] = [49.2827, -123.1207];
const VANCOUVER_ZOOM = 12;
const SELECTED_EVENT_ZOOM = 15;


function formatTime(value: string | null | undefined): string {
  if (!value) {
    return "Time TBD";
  }

  return new Intl.DateTimeFormat("en-CA", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "America/Vancouver",
  }).format(new Date(value));
}


function escapeHtml(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}


function buildPopupHtml(event: EventRecord, fallbackImageUrl: string): string {
  const imageUrl = escapeHtml(event.imageUrl || fallbackImageUrl);
  const safeFallbackImageUrl = escapeHtml(fallbackImageUrl);
  const title = escapeHtml(event.name);
  const venueName = escapeHtml(event.venueName);
  const eventTime = escapeHtml(formatTime(event.startTime));
  const category = event.category ? escapeHtml(event.category) : "";
  const ticketUrl = escapeHtml(event.ticketUrl);

  return `
    <article class="event-popup">
      <img class="event-popup__image" src="${imageUrl}" alt="${title}" onerror="this.onerror=null;this.src='${safeFallbackImageUrl}';" />
      <div class="event-popup__body">
        <p class="event-popup__eyebrow">${category || "Event"}</p>
        <h3 class="event-popup__title">${title}</h3>
        <p class="event-popup__meta">${venueName}</p>
        <p class="event-popup__meta">${eventTime}</p>
        <a class="event-popup__link" href="${ticketUrl}" target="_blank" rel="noreferrer">View event</a>
      </div>
    </article>
  `;
}


type EventMapProps = {
  events: EventRecord[];
  selectedEventId: string | null;
  selectedEventSource: "drawer" | "map" | null;
  fallbackImageUrl: string;
  onSelectEvent: (eventId: string, source: "drawer" | "map") => void;
};


export default function EventMap({
  events,
  selectedEventId,
  selectedEventSource,
  fallbackImageUrl,
  onSelectEvent,
}: EventMapProps) {
  const mapContainerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<import("leaflet").Map | null>(null);
  const markersRef = useRef<Map<string, import("leaflet").Marker>>(new Map());
  const markerLayerRef = useRef<import("leaflet").LayerGroup | null>(null);
  const leafletRef = useRef<typeof import("leaflet") | null>(null);
  const previousSelectedEventIdRef = useRef<string | null>(null);
  const [mapReady, setMapReady] = useState(false);

  useEffect(() => {
    let isMounted = true;

    const initializeMap = async () => {
      if (!mapContainerRef.current || mapRef.current) {
        return;
      }

      const L = await import("leaflet");
      if (!isMounted || !mapContainerRef.current || mapRef.current) {
        return;
      }

      leafletRef.current = L;

      const map = L.map(mapContainerRef.current, {
        zoomControl: false,
      }).setView(VANCOUVER_CENTER, VANCOUVER_ZOOM);

      L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: "&copy; OpenStreetMap contributors",
      }).addTo(map);

      markerLayerRef.current = L.layerGroup().addTo(map);
      mapRef.current = map;
      setMapReady(true);

      window.setTimeout(() => {
        map.invalidateSize();
        map.setView(VANCOUVER_CENTER, VANCOUVER_ZOOM);
      }, 0);
    };

    void initializeMap();

    return () => {
      isMounted = false;
      markersRef.current.clear();
      mapRef.current?.remove();
      mapRef.current = null;
      markerLayerRef.current = null;
    };
  }, []);

  useEffect(() => {
    const L = leafletRef.current;
    const map = mapRef.current;
    const markerLayer = markerLayerRef.current;

    if (!L || !map || !markerLayer) {
      return;
    }

    markerLayer.clearLayers();
    markersRef.current.clear();

    const defaultIcon = L.divIcon({
      className: "",
      html: '<div class="map-pin"></div>',
      iconSize: [20, 20],
      iconAnchor: [10, 10],
      popupAnchor: [0, -14],
    });

    const activeIcon = L.divIcon({
      className: "",
      html: '<div class="map-pin map-pin--active"></div>',
      iconSize: [28, 28],
      iconAnchor: [14, 14],
      popupAnchor: [0, -18],
    });

    for (const event of events) {
      const marker = L.marker([event.lat, event.lng], {
        icon: event.id === selectedEventId ? activeIcon : defaultIcon,
      });

      marker.bindPopup(buildPopupHtml(event, fallbackImageUrl), {
        maxWidth: 320,
      });

      marker.on("click", () => {
        onSelectEvent(event.id, "map");
      });

      marker.addTo(markerLayer);
      markersRef.current.set(event.id, marker);
    }

    map.invalidateSize();

    if (events.length === 0) {
      previousSelectedEventIdRef.current = null;
      map.closePopup();
      map.setView(VANCOUVER_CENTER, VANCOUVER_ZOOM);
      return;
    }

    if (!selectedEventId) {
      previousSelectedEventIdRef.current = null;
      map.closePopup();
      map.setView(VANCOUVER_CENTER, VANCOUVER_ZOOM);
      return;
    }

    const selectedEvent = events.find((event) => event.id === selectedEventId);
    const selectedMarker = selectedEventId ? markersRef.current.get(selectedEventId) : null;

    if (!selectedEvent || !selectedMarker) {
      previousSelectedEventIdRef.current = null;
      map.setView(VANCOUVER_CENTER, VANCOUVER_ZOOM);
      return;
    }

    if (previousSelectedEventIdRef.current !== selectedEventId) {
      map.flyTo([selectedEvent.lat, selectedEvent.lng], SELECTED_EVENT_ZOOM, {
        duration: 0.6,
      });
      if (selectedEventSource === "map") {
        selectedMarker.openPopup();
      } else {
        selectedMarker.closePopup();
      }
      previousSelectedEventIdRef.current = selectedEventId;
      return;
    }

    if (selectedEventSource === "map") {
      selectedMarker.openPopup();
    } else {
      selectedMarker.closePopup();
    }
  }, [events, fallbackImageUrl, mapReady, onSelectEvent, selectedEventId, selectedEventSource]);

  return <div ref={mapContainerRef} className="h-screen w-screen" />;
}
