"use client";

import dynamic from "next/dynamic";
import { startTransition, useEffect, useMemo, useState } from "react";

import { fetchEvents, type EventRecord } from "@/lib/api";


const EventMap = dynamic(() => import("@/components/event-map"), {
  ssr: false,
  loading: () => <div className="h-screen w-screen bg-[#d7e4ea]" />,
});

const DEFAULT_FALLBACK_IMAGE = "/default-event.svg";


function getDefaultDate(): string {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "America/Vancouver",
  }).format(new Date());
}


function formatEventCount(count: number): string {
  if (count === 1) {
    return "1 event";
  }

  return `${count} events`;
}


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


export default function HomePage() {
  const [selectedDate, setSelectedDate] = useState<string>(getDefaultDate);
  const [events, setEvents] = useState<EventRecord[]>([]);
  const [selectedEventId, setSelectedEventId] = useState<string | null>(null);
  const [selectedEventSource, setSelectedEventSource] = useState<"drawer" | "map" | null>(null);
  const [isPanelOpen, setIsPanelOpen] = useState(true);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isActive = true;

    const loadEvents = async () => {
      setLoading(true);
      setError(null);
      setSelectedEventId(null);
      setSelectedEventSource(null);

      try {
        const nextEvents = await fetchEvents(selectedDate);
        if (isActive) {
          setEvents(nextEvents);
        }
      } catch (loadError) {
        if (isActive) {
          setEvents([]);
          setError(
            loadError instanceof Error
              ? loadError.message
              : "Something went wrong while fetching events.",
          );
        }
      } finally {
        if (isActive) {
          setLoading(false);
        }
      }
    };

    void loadEvents();

    return () => {
      isActive = false;
    };
  }, [selectedDate]);

  const selectedEvent = useMemo(
    () => events.find((event) => event.id === selectedEventId) ?? null,
    [events, selectedEventId],
  );

  return (
    <main className="relative h-screen w-screen overflow-hidden bg-[#d7e4ea] text-slate-900">
      <EventMap
        events={events}
        selectedEventId={selectedEventId}
        selectedEventSource={selectedEventSource}
        fallbackImageUrl={DEFAULT_FALLBACK_IMAGE}
        onSelectEvent={(eventId, source) => {
          setSelectedEventId(eventId);
          setSelectedEventSource(source);
        }}
      />

      <section className="pointer-events-none absolute right-4 top-4 z-[1000] flex w-[22rem] max-w-[calc(100vw-2rem)] flex-col gap-4 sm:right-6 sm:top-6">
        <div className="pointer-events-auto flex w-full flex-col gap-3 rounded-[1.5rem] border border-white/35 bg-white/82 p-4 shadow-2xl backdrop-blur-xl">
          <label className="flex flex-col gap-2">
            <span className="text-xs font-bold uppercase tracking-[0.22em] text-slate-500">
              Selected date
            </span>
            <input
              type="date"
              value={selectedDate}
              onChange={(event) => {
                const nextDate = event.target.value;
                startTransition(() => setSelectedDate(nextDate));
              }}
              className="rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm font-semibold text-slate-900 outline-none transition focus:border-cyan-500"
            />
          </label>

          <button
            type="button"
            onClick={() => setIsPanelOpen((value) => !value)}
            className="rounded-xl bg-slate-950 px-4 py-3 text-sm font-semibold text-white transition hover:bg-slate-800"
          >
            {isPanelOpen ? "Hide events" : "Show events"}
          </button>
        </div>

        <aside
          className={`pointer-events-none w-full transition-all duration-300 ${
            isPanelOpen
              ? "translate-y-0 opacity-100"
              : "-translate-y-4 opacity-0"
          }`}
        >
          <div className="pointer-events-auto max-h-[calc(100vh-16rem)] overflow-hidden rounded-[1.75rem] border border-white/35 bg-white/84 shadow-2xl backdrop-blur-xl">
          <div className="border-b border-slate-200/80 px-5 py-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-xs font-bold uppercase tracking-[0.22em] text-slate-500">
                  Event drawer
                </p>
                <h2 className="mt-1 text-xl font-black text-slate-950">
                  {loading ? "Loading..." : formatEventCount(events.length)}
                </h2>
              </div>
              <button
                type="button"
                onClick={() => setIsPanelOpen(false)}
                className="rounded-full border border-slate-200 px-3 py-1 text-xs font-bold uppercase tracking-[0.16em] text-slate-600 transition hover:border-slate-400 hover:text-slate-950"
              >
                Close
              </button>
            </div>
          </div>

          <div className="max-h-[calc(100vh-18rem)] overflow-y-auto px-4 py-4">
            {error ? (
              <p className="rounded-2xl bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</p>
            ) : null}

            {loading ? (
              <div className="space-y-3">
                {Array.from({ length: 4 }).map((_, index) => (
                  <div
                    key={index}
                    className="h-28 animate-pulse rounded-[1.25rem] bg-slate-200/70"
                  />
                ))}
              </div>
            ) : null}

            {!loading && !error && events.length === 0 ? (
              <p className="rounded-2xl bg-slate-100 px-4 py-3 text-sm text-slate-600">
                No cached events were found for this date yet.
              </p>
            ) : null}

            {!loading && !error ? (
              <div className="space-y-3">
                {events.map((event) => {
                  const isSelected = event.id === selectedEventId;

                  return (
                    <button
                      key={event.id}
                      type="button"
                      onClick={() => {
                        setSelectedEventId(event.id);
                        setSelectedEventSource("drawer");
                      }}
                      className={`flex w-full items-start gap-4 rounded-[1.4rem] border p-3 text-left transition ${
                        isSelected
                          ? "border-cyan-400 bg-cyan-50 shadow-lg shadow-cyan-100"
                          : "border-slate-200/80 bg-white hover:border-slate-300 hover:bg-slate-50"
                      }`}
                    >
                      <img
                        src={event.imageUrl || DEFAULT_FALLBACK_IMAGE}
                        alt={event.name}
                        onError={(imageEvent) => {
                          imageEvent.currentTarget.src = DEFAULT_FALLBACK_IMAGE;
                        }}
                        className="h-20 w-20 rounded-[1rem] object-cover"
                      />
                      <div className="min-w-0 flex-1">
                        <p className="text-[0.65rem] font-bold uppercase tracking-[0.2em] text-cyan-700">
                          {event.category ?? "Event"}
                        </p>
                        <h3 className="mt-1 text-sm font-bold leading-5 text-slate-950">
                          {event.name}
                        </h3>
                        <p className="mt-2 truncate text-sm text-slate-600">{event.venueName}</p>
                        <p className="mt-1 text-xs text-slate-500">{formatTime(event.startTime)}</p>
                      </div>
                    </button>
                  );
                })}
              </div>
            ) : null}
          </div>
          </div>
        </aside>
      </section>

      {selectedEvent && selectedEventSource === "drawer" ? (
        <section className="pointer-events-none absolute bottom-4 left-4 z-[1000] max-w-[calc(100vw-2rem)] sm:bottom-6 sm:left-6 sm:w-[24rem]">
          <div className="pointer-events-auto overflow-hidden rounded-[1.75rem] border border-white/35 bg-slate-100/92 text-slate-950 shadow-2xl backdrop-blur-xl">
            <img
              src={selectedEvent.imageUrl || DEFAULT_FALLBACK_IMAGE}
              alt={selectedEvent.name}
              onError={(imageEvent) => {
                imageEvent.currentTarget.src = DEFAULT_FALLBACK_IMAGE;
              }}
              className="h-40 w-full object-cover"
            />
            <div className="space-y-2 px-5 py-4">
              <p className="text-[0.65rem] font-bold uppercase tracking-[0.24em] text-cyan-700">
                {selectedEvent.category ?? "Event"}
              </p>
              <h2 className="text-xl font-black leading-tight">{selectedEvent.name}</h2>
              <p className="text-sm text-slate-700">{selectedEvent.venueName}</p>
              <p className="text-sm text-slate-600">{formatTime(selectedEvent.startTime)}</p>
              {selectedEvent.address ? (
                <p className="text-sm leading-6 text-slate-600">{selectedEvent.address}</p>
              ) : null}
              <a
                href={selectedEvent.ticketUrl}
                target="_blank"
                rel="noreferrer"
                className="inline-flex rounded-full bg-cyan-300 px-4 py-2 text-sm font-bold text-slate-950 transition hover:bg-cyan-200"
              >
                Open event page
              </a>
            </div>
          </div>
        </section>
      ) : null}
    </main>
  );
}
