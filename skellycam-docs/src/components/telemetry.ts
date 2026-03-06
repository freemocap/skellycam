/**
 * Skellypings telemetry server used for anonymous docs feedback.
 *
 * Events are sent without an HMAC signature, so they land in the
 * server's "unverified" collection — this is expected and fine for
 * public-facing docs feedback.
 */
export const SKELLYPINGS_SERVER_URL =
  'https://skellypings-401698866387.northamerica-northeast1.run.app';

export const DOCS_APP_VERSION = 'skellycam-docs@1.0.0';
