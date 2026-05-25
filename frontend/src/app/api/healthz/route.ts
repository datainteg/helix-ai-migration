import { NextResponse } from "next/server";

// Minimal liveness probe for container orchestrators. Does not reach out to
// the backend so it stays cheap and never flaps because of an upstream blip.
export async function GET() {
  return NextResponse.json({ status: "ok" });
}
