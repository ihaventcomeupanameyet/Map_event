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

export async function fetchEvents(selectedDate: string): Promise<EventRecord[]> {
  const response = await fetch(
    `/api/events?date=${encodeURIComponent(selectedDate)}`,
    {
      cache: "no-store",
    },
  );

  if (!response.ok) {
    throw new Error(`Failed to load events for ${selectedDate}`);
  }

  return response.json();
}
