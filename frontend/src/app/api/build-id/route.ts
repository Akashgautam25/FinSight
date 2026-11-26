// Returns the id of the build this server is running (see next.config.mjs).
export const dynamic = "force-dynamic";

export function GET() {
  return Response.json({ buildId: process.env.NEXT_PUBLIC_BUILD_ID ?? "dev" }, { headers: { "Cache-Control": "no-store" } });
}
