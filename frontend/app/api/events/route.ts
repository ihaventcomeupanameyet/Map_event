import { NextRequest } from "next/server";


function getBackendBaseUrl(): string {
  const configured =
    process.env.BACKEND_INTERNAL_URL?.trim() || "http://backend:8000";
  return configured.endsWith("/") ? configured.slice(0, -1) : configured;
}


export async function GET(request: NextRequest): Promise<Response> {
  const date = request.nextUrl.searchParams.get("date")?.trim();
  if (!date) {
    return Response.json({ error: "Missing required query parameter: date" }, { status: 400 });
  }

  const upstream = await fetch(
    `${getBackendBaseUrl()}/events?date=${encodeURIComponent(date)}`,
    {
      cache: "no-store",
    },
  );

  return new Response(upstream.body, {
    status: upstream.status,
    headers: {
      "content-type": upstream.headers.get("content-type") ?? "application/json",
      "cache-control": "no-store",
    },
  });
}
