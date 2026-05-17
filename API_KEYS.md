# API Keys

This project currently supports these event providers:

- Ticketmaster
- Eventbrite
- SeatGeek

Meetup is not wired into the app because new API access now requires Meetup Pro.

## Ticketmaster

1. Create a Ticketmaster developer account.
2. Create an app in the Ticketmaster developer dashboard.
3. Copy the Discovery API key into:
   - `TICKETMASTER_API_KEY`

## Eventbrite

1. Create or log into an Eventbrite account.
2. Go to Account Settings.
3. Open `API Keys` under Developer Links.
4. Choose `Create API key`.
5. Fill in the requested application details.
6. After approval, copy the private token into:
   - `EVENTBRITE_API_KEY`

## SeatGeek

1. Create a SeatGeek developer account from the SeatGeek developer portal.
2. Create an application in the developer portal.
3. Copy the credentials into:
   - `SEATGEEK_CLIENT_ID`
   - `SEATGEEK_CLIENT_SECRET`

The app can usually query public data with `SEATGEEK_CLIENT_ID` alone, but keep `SEATGEEK_CLIENT_SECRET` available for compatibility.

## Local env files

Development:

- `.env`
- `.env.example`
- `.env.docker.example`

Production:

- `.env.production`
- `.env.production.example`
