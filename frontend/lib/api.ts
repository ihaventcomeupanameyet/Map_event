export type EventRecord = {
  id: string;
  source: "ticketmaster" | "eventbrite" | "seatgeek";
  sourceEventId: string;
  name: string;
  startTime: string | null;
  endTime?: string | null;
  venueName: string;
  address?: string | null;
  lat: number;
  lng: number;
  organizer?: string | null;
  description?: string | null;
  category?: string | null;
  ticketUrl: string;
  imageUrl?: string | null;
};

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";


export async function fetchEvents(selectedDate: string): Promise<EventRecord[]> {
  const response = await fetch(
    `${BACKEND_URL}/events?date=${encodeURIComponent(selectedDate)}`,
    {
      cache: "no-store",
    },
  );

  if (!response.ok) {
    throw new Error(`Failed to load events for ${selectedDate}`);
  }

  return response.json();
}
